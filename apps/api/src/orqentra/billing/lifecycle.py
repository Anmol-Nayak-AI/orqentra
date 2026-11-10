"""TEST-only hosted authorization and authoritative provider reconciliation."""

import re
from datetime import UTC, datetime, timedelta
from typing import Any, cast
from urllib.parse import urlsplit
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import Field
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from orqentra.billing.providers import BillingRejected, BillingUnavailable, provider
from orqentra.billing.routes import Manage
from orqentra.billing.service import PLAN_LIMITS, lock_organization
from orqentra.billing.webhooks import STATE
from orqentra.execution.routes import digest
from orqentra.organizations.schemas import Contract
from orqentra.persistence.models import (
    AuditEvent,
    BillingOperation,
    BillingSnapshot,
    InvoiceSnapshot,
    Organization,
    OrganizationMembership,
    OrganizationSubscription,
)
from orqentra.persistence.session import TrustedOrganizationContext, transaction
from orqentra.rag.service import require_restricted

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/billing", tags=["test billing lifecycle"]
)


class CheckoutRequest(Contract):
    quote_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    plan_key: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,29}$")
    idempotency_key: str = Field(min_length=16, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")


class CancelRequest(Contract):
    idempotency_key: str = Field(min_length=16, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")


class ResolveRequest(Contract):
    external_id: str = Field(pattern=r"^sub_[A-Za-z0-9]{1,90}$")


class OperationResponse(Contract):
    id: UUID
    kind: str
    status: str
    mode: str
    plan_key: str
    external_id: str | None
    hosted_url: str | None
    error_code: str | None
    created_at: datetime


def manager(session: Session, org: UUID, actor: UUID) -> bool:
    lock_organization(session, org)
    return bool(
        session.scalar(select(Organization.id).where(Organization.status == "ACTIVE"))
        and session.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.user_id == actor,
                OrganizationMembership.status == "ACTIVE",
                OrganizationMembership.role.in_(["OWNER", "ADMIN"]),
            )
        )
    )


def audit(session: Session, org: UUID, actor: UUID, action: str, resource: UUID) -> None:
    session.add(
        AuditEvent(
            organization_id=org,
            actor_user_id=actor,
            action="billing." + action,
            resource_type="billing",
            resource_id=resource,
            correlation_id=uuid4(),
            safe_metadata={},
        )
    )


def snapshot(session: Session, item: OrganizationSubscription, source: str) -> None:
    if item.external_id:
        session.add(
            BillingSnapshot(
                organization_id=item.organization_id,
                external_id=item.external_id,
                plan_key=item.plan_key,
                status=item.status,
                period_end=item.period_end,
                source=source,
            )
        )


def hosted_url(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        parsed = urlsplit(value)
        allowed = (
            parsed.scheme == "https"
            and parsed.hostname in {"rzp.io", "razorpay.com", "checkout.razorpay.com"}
            and parsed.port in {None, 443}
            and not parsed.username
            and not parsed.password
            and not parsed.fragment
        )
    except ValueError:
        return None
    return value if allowed else None


def binding(
    remote: dict[str, Any],
    org: UUID,
    plan_id: str,
    external_id: str | None = None,
    operation: UUID | None = None,
) -> str:
    notes, reference = remote.get("notes"), remote.get("id")
    if (
        not isinstance(notes, dict)
        or notes.get("orqentra_organization_id") != str(org)
        or not isinstance(reference, str)
        or not re.fullmatch(r"sub_[A-Za-z0-9]{1,90}", reference)
        or remote.get("plan_id") != plan_id
        or external_id is not None
        and reference != external_id
        or operation is not None
        and notes.get("orqentra_checkout_request") != str(operation)
    ):
        raise BillingUnavailable("billing_provider_binding_mismatch")
    return reference


def remote_state(remote: dict[str, Any]) -> tuple[str, datetime | None]:
    name = remote.get("status")
    if not isinstance(name, str) or name not in STATE:
        raise BillingUnavailable("billing_provider_state_unknown")
    state, end = STATE[name], None
    if state == "ACTIVE":
        value = remote.get("current_end")
        if not isinstance(value, int) or isinstance(value, bool):
            raise BillingUnavailable("billing_period_unknown")
        try:
            end = datetime.fromtimestamp(value, UTC)
        except (ValueError, OverflowError):
            raise BillingUnavailable("billing_period_unknown") from None
        if end <= datetime.now(UTC):
            state = "EXPIRED"
    return state, end


def enabled(request: Request, mutations: bool = False) -> Any:
    settings = request.app.state.settings
    if (
        settings.billing_provider != "razorpay"
        or settings.environment == "production"
        or (mutations and not settings.billing_test_actions_enabled)
    ):
        raise HTTPException(503)
    return settings


class PlanView(Contract):
    quote_hash: str
    key: str
    amount_minor: int
    currency: str
    interval: int
    period: str
    quotas: dict[str, int]


class CatalogView(Contract):
    mode: str
    checkout_enabled: bool
    total_cycles: int
    plans: list[PlanView]
    notice: str


def quoted_plan(settings: Any, key: str) -> dict[str, Any]:
    reference = settings.razorpay_plan_ids.get(key)
    if key not in PLAN_LIMITS or not reference:
        raise BillingUnavailable("plan_not_configured")
    remote = provider(settings).fetch_plan(reference)
    item = remote.get("item")
    if remote.get("id") != reference or not isinstance(item, dict):
        raise BillingUnavailable("invalid_plan_reference")
    amount, currency, interval, period = (
        item.get("amount"),
        item.get("currency"),
        remote.get("interval"),
        remote.get("period"),
    )
    if (
        not isinstance(amount, int)
        or isinstance(amount, bool)
        or not 0 <= amount <= 10**12
        or not isinstance(currency, str)
        or not re.fullmatch(r"[A-Z]{3}", currency)
        or not isinstance(interval, int)
        or isinstance(interval, bool)
        or not 1 <= interval <= 120
        or not isinstance(period, str)
        or period not in {"daily", "weekly", "monthly", "yearly"}
    ):
        raise BillingUnavailable("invalid_plan_terms")
    quoted = {
        "key": key,
        "amount_minor": amount,
        "currency": currency,
        "interval": interval,
        "period": period,
        "quotas": PLAN_LIMITS[key],
    }
    quoted["quote_hash"] = digest(
        {
            **quoted,
            "provider_plan_id": reference,
            "total_cycles": settings.billing_test_total_cycles,
        }
    )
    return quoted


@router.get("/catalog", response_model=CatalogView)
def catalog(access: Manage, request: Request) -> dict[str, Any]:
    settings = request.app.state.settings
    plans = []
    if settings.billing_provider == "razorpay":
        for key in sorted(settings.razorpay_plan_ids):
            try:
                plans.append(quoted_plan(settings, key))
            except BillingUnavailable:
                continue
    return {
        "mode": "test" if settings.billing_provider == "razorpay" else "disabled",
        "checkout_enabled": settings.billing_provider == "razorpay"
        and settings.billing_test_actions_enabled,
        "total_cycles": settings.billing_test_total_cycles,
        "plans": plans,
        "notice": (
            "Test authorization only. Prices come from configured provider plans; "
            "no live customer payments."
        ),
    }


@router.get("/operations", response_model=list[OperationResponse])
def operations(access: Manage) -> list[BillingOperation]:
    return list(
        access.authenticated.session.scalars(
            select(BillingOperation).order_by(BillingOperation.created_at.desc()).limit(50)
        )
    )


@router.post("/checkout", response_model=OperationResponse)
def checkout(body: CheckoutRequest, access: Manage, request: Request) -> BillingOperation:
    operation: BillingOperation | None
    settings = enabled(request, True)
    plan_id = settings.razorpay_plan_ids.get(body.plan_key)
    if body.plan_key not in PLAN_LIMITS or not plan_id:
        raise HTTPException(422)
    try:
        quote = quoted_plan(settings, body.plan_key)
    except BillingUnavailable:
        raise HTTPException(503) from None
    if quote["quote_hash"] != body.quote_hash:
        raise HTTPException(409)
    org, actor = access.context.organization_id, access.authenticated.user_id
    context = TrustedOrganizationContext(org, actor, access.context.correlation_id)
    engine = request.app.state.database_engine
    with transaction(engine, context) as session:
        require_restricted(session)
        if not manager(session, org, actor):
            raise HTTPException(403)
        old = session.scalar(
            select(BillingOperation).where(BillingOperation.idempotency_key == body.idempotency_key)
        )
        if old:
            if (
                old.kind != "CHECKOUT"
                or old.plan_key != body.plan_key
                or old.request_snapshot.get("quote_hash") != body.quote_hash
            ):
                raise HTTPException(409)
            return old
        subscription = session.scalar(select(OrganizationSubscription))
        if subscription and subscription.status not in {"CANCELLED", "EXPIRED", "UNAVAILABLE"}:
            raise HTTPException(409)
        pending = session.scalar(
            select(BillingOperation.id).where(
                BillingOperation.kind == "CHECKOUT",
                BillingOperation.status.in_(["CREATING", "UNKNOWN"]),
            )
        )
        count = (
            session.scalar(
                select(func.count())
                .select_from(BillingOperation)
                .where(BillingOperation.created_at > datetime.now(UTC) - timedelta(days=1))
            )
            or 0
        )
        if pending or count >= 20:
            raise HTTPException(409 if pending else 429)
        operation = BillingOperation(
            organization_id=org,
            created_by=actor,
            idempotency_key=body.idempotency_key,
            kind="CHECKOUT",
            request_snapshot={
                **quote,
                "provider_plan_id": plan_id,
                "total_cycles": settings.billing_test_total_cycles,
            },
            plan_key=body.plan_key,
        )
        session.add(operation)
        session.flush()
        operation_id = operation.id
        audit(session, org, actor, "checkout_requested", operation_id)
    # The durable one-shot claim commits BEFORE the provider request. No retries on uncertain POST.
    remote, failure = None, None
    bound_id = None
    try:
        remote = provider(settings).create_subscription(
            plan_id,
            {"orqentra_organization_id": str(org), "orqentra_checkout_request": str(operation_id)},
        )
        bound_id = binding(remote, org, plan_id, operation=operation_id)
        if hosted_url(remote.get("short_url")) is None:
            raise BillingUnavailable("checkout_url_unverified")
    except BillingRejected:
        failure = "provider_rejected"
    except Exception:
        failure = "provider_request_uncertain"
    with transaction(engine, context) as session:
        require_restricted(session)
        allowed = manager(session, org, actor)
        operation = session.get(BillingOperation, operation_id)
        assert operation is not None
        current = session.scalar(select(OrganizationSubscription))
        if (
            not failure
            and current
            and current.external_id != bound_id
            and current.status not in {"CANCELLED", "EXPIRED", "UNAVAILABLE"}
        ):
            failure = "subscription_changed_during_request"
        if not allowed or failure:
            operation.external_id = bound_id
            operation.status = "FAILED" if failure == "provider_rejected" else "UNKNOWN"
            operation.error_code = failure or "access_changed_during_request"
        else:
            assert remote is not None
            operation.status, operation.external_id, operation.hosted_url = (
                "READY",
                remote["id"],
                hosted_url(remote["short_url"]),
            )
            current = session.scalar(select(OrganizationSubscription))
            if current:
                snapshot(session, current, "before_replacement")
            else:
                current = OrganizationSubscription(organization_id=org)
                session.add(current)
            current.provider, current.mode, current.plan_key = "razorpay", "test", body.plan_key
            current.external_id, current.status = remote["id"], "PENDING"
            current.period_end, current.provider_event_at = None, None
            session.flush()
            snapshot(session, current, "checkout_prepared")
        audit(session, org, actor, "checkout_" + operation.status.lower(), operation_id)
    if not allowed:
        raise HTTPException(403)
    return operation


@router.post("/reconcile", response_model=dict[str, str])
def reconcile(access: Manage, request: Request) -> dict[str, str]:
    settings = enabled(request)
    org, actor = access.context.organization_id, access.authenticated.user_id
    context = TrustedOrganizationContext(org, actor, access.context.correlation_id)
    with transaction(request.app.state.database_engine, context) as session:
        require_restricted(session)
        if not manager(session, org, actor):
            raise HTTPException(403)
        item = session.scalar(select(OrganizationSubscription))
        if not item or item.provider != "razorpay" or item.mode != "test" or not item.external_id:
            raise HTTPException(404)
        external, plan_key, version = item.external_id, item.plan_key, item.updated_at
    try:
        remote = provider(settings).fetch_subscription(external)
        binding(remote, org, settings.razorpay_plan_ids.get(plan_key, ""), external)
        state, end = remote_state(remote)
    except BillingUnavailable:
        raise HTTPException(503) from None
    with transaction(request.app.state.database_engine, context) as session:
        require_restricted(session)
        if not manager(session, org, actor):
            raise HTTPException(403)
        item = session.scalar(select(OrganizationSubscription).with_for_update())
        if not item or item.external_id != external or item.updated_at != version:
            raise HTTPException(409)
        item.status, item.period_end, item.provider_event_at = state, end, datetime.now(UTC)
        snapshot(session, item, "provider_reconcile")
        audit(session, org, actor, "subscription_reconciled", item.id)
    return {"status": state, "source": "verified_provider_fetch"}


@router.post("/operations/{operation_id}/resolve", response_model=OperationResponse)
def resolve(
    operation_id: UUID, body: ResolveRequest, access: Manage, request: Request
) -> BillingOperation:
    settings = enabled(request)
    org, actor = access.context.organization_id, access.authenticated.user_id
    context = TrustedOrganizationContext(org, actor, access.context.correlation_id)
    with transaction(request.app.state.database_engine, context) as session:
        require_restricted(session)
        if not manager(session, org, actor):
            raise HTTPException(403)
        operation = session.get(BillingOperation, operation_id)
        if not operation:
            raise HTTPException(404)
        if operation.status == "READY":
            if operation.external_id != body.external_id:
                raise HTTPException(409)
            return operation
        if operation.status not in {"UNKNOWN", "CREATING"} or operation.created_at > datetime.now(
            UTC
        ) - timedelta(seconds=30):
            raise HTTPException(409)
        key, kind, original_external = operation.plan_key, operation.kind, operation.external_id
    try:
        remote = provider(settings).fetch_subscription(body.external_id)
        binding(
            remote,
            org,
            settings.razorpay_plan_ids.get(key, ""),
            body.external_id,
            operation_id if kind == "CHECKOUT" else None,
        )
    except BillingUnavailable:
        raise HTTPException(409) from None
    if kind == "CANCEL":
        state, end = remote_state(remote)
        if original_external != body.external_id or state not in {"CANCELLED", "EXPIRED"}:
            raise HTTPException(409)
    with transaction(request.app.state.database_engine, context) as session:
        require_restricted(session)
        if not manager(session, org, actor):
            raise HTTPException(403)
        operation = session.get(BillingOperation, operation_id)
        assert operation is not None
        current = session.scalar(select(OrganizationSubscription))
        if kind == "CANCEL":
            if current and current.external_id == body.external_id:
                current.status, current.period_end, current.provider_event_at = (
                    state,
                    end,
                    datetime.now(UTC),
                )
                snapshot(session, current, "cancellation_resolved")
            operation.status, operation.error_code = "READY", None
            audit(session, org, actor, "cancellation_resolved", operation.id)
            return operation
        if (
            current
            and current.external_id != body.external_id
            and current.status not in {"EXPIRED", "CANCELLED", "UNAVAILABLE"}
        ):
            raise HTTPException(409)
        if not current:
            current = OrganizationSubscription(organization_id=org)
            session.add(current)
        else:
            snapshot(session, current, "before_resolution")
        if current.external_id != body.external_id:
            current.provider, current.mode, current.plan_key = "razorpay", "test", key
            current.external_id, current.status, current.period_end, current.provider_event_at = (
                body.external_id,
                "PENDING",
                None,
                None,
            )
        operation.status, operation.external_id, operation.hosted_url, operation.error_code = (
            "READY",
            body.external_id,
            hosted_url(remote.get("short_url")),
            None,
        )
        session.flush()
        snapshot(session, current, "checkout_resolved")
        audit(session, org, actor, "checkout_resolved", operation.id)
    return operation


@router.post("/cancel", response_model=OperationResponse)
def cancel(body: CancelRequest, access: Manage, request: Request) -> BillingOperation:
    operation: BillingOperation | None
    settings = enabled(request, True)
    org, actor = access.context.organization_id, access.authenticated.user_id
    context = TrustedOrganizationContext(org, actor, access.context.correlation_id)
    with transaction(request.app.state.database_engine, context) as session:
        require_restricted(session)
        if not manager(session, org, actor):
            raise HTTPException(403)
        old = session.scalar(
            select(BillingOperation).where(BillingOperation.idempotency_key == body.idempotency_key)
        )
        if old:
            if old.kind != "CANCEL":
                raise HTTPException(409)
            return old
        item = session.scalar(select(OrganizationSubscription))
        if not item or not item.external_id or item.provider != "razorpay" or item.mode != "test":
            raise HTTPException(404)
        old = session.scalar(
            select(BillingOperation)
            .where(
                BillingOperation.kind == "CANCEL", BillingOperation.external_id == item.external_id
            )
            .order_by(BillingOperation.created_at.desc())
            .limit(1)
        )
        if old and old.status != "FAILED":
            return old
        if item.status not in {"ACTIVE", "PENDING", "PAST_DUE"}:
            raise HTTPException(409)
        external, key = item.external_id, item.plan_key
        operation = BillingOperation(
            organization_id=org,
            created_by=actor,
            idempotency_key=body.idempotency_key,
            kind="CANCEL",
            plan_key=key,
            external_id=external,
        )
        session.add(operation)
        session.flush()
        operation_id = operation.id
        audit(session, org, actor, "cancellation_requested", operation_id)
    failure = None
    try:
        remote = provider(settings).cancel_subscription(external)
        binding(remote, org, settings.razorpay_plan_ids.get(key, ""), external)
    except BillingRejected:
        failure = "provider_rejected"
    except Exception:
        failure = "provider_request_uncertain"
    with transaction(request.app.state.database_engine, context) as session:
        require_restricted(session)
        allowed = manager(session, org, actor)
        operation = session.get(BillingOperation, operation_id)
        assert operation is not None
        operation.status = (
            "READY"
            if not failure and allowed
            else "FAILED"
            if failure == "provider_rejected"
            else "UNKNOWN"
        )
        operation.error_code = failure or (None if allowed else "access_changed_during_request")
        audit(session, org, actor, "cancellation_" + operation.status.lower(), operation_id)
    if not allowed:
        raise HTTPException(403)
    return operation


class InvoiceView(Contract):
    external_id: str
    subscription_external_id: str
    status: str
    currency: str | None
    amount_minor: int | None
    paid_minor: int | None
    due_minor: int | None
    hosted_url: str | None


class InvoiceCollection(Contract):
    mode: str = "test"
    invoices: list[InvoiceView]
    next_offset: int | None = None
    notice: str = (
        "Provider TEST invoice snapshots only; not real customer charges "
        "or a tax invoice issued by Orqentra."
    )


def invoice_document(row: dict[str, Any], subscription: str) -> dict[str, Any]:
    if (
        not isinstance(row.get("id"), str)
        or not re.fullmatch(r"inv_[A-Za-z0-9]{1,90}", row["id"])
        or row.get("subscription_id") != subscription
    ):
        raise BillingUnavailable("invoice_binding_mismatch")
    currency = row.get("currency")
    draft = row.get("status") in {"draft", "cancelled", "deleted"}
    if not (draft and currency is None) and (
        not isinstance(currency, str) or not re.fullmatch(r"[A-Z]{3}", currency)
    ):
        raise BillingUnavailable("invoice_currency_unknown")
    if row.get("status") not in {
        "draft",
        "issued",
        "paid",
        "partially_paid",
        "cancelled",
        "expired",
        "deleted",
    }:
        raise BillingUnavailable("invoice_state_unknown")
    amounts = [row.get(name) for name in ("amount", "amount_paid", "amount_due")]
    if any(
        value is not None
        and (not isinstance(value, int) or isinstance(value, bool) or not 0 <= value <= 10**12)
        for value in amounts
    ):
        raise BillingUnavailable("invoice_amount_unknown")
    if not draft and any(value is None for value in amounts):
        raise BillingUnavailable("invoice_amount_unknown")
    if all(value is not None for value in amounts):
        numbers = cast(list[int], amounts)
        if numbers[1] + numbers[2] != numbers[0]:
            raise BillingUnavailable("invoice_amount_inconsistent")
    return {
        "external_id": row["id"],
        "subscription_external_id": subscription,
        "status": row["status"],
        "currency": currency,
        "amount_minor": amounts[0],
        "paid_minor": amounts[1],
        "due_minor": amounts[2],
        "hosted_url": hosted_url(row.get("short_url")),
    }


@router.get("/invoices", response_model=InvoiceCollection)
def invoices(access: Manage) -> dict[str, Any]:
    rows = access.authenticated.session.scalars(
        select(InvoiceSnapshot)
        .ext(distinct_on(InvoiceSnapshot.external_id))
        .order_by(
            InvoiceSnapshot.external_id,
            InvoiceSnapshot.created_at.desc(),
            InvoiceSnapshot.id.desc(),
        )
        .limit(100)
    )
    return {"invoices": [item.document for item in rows]}


@router.post("/invoices/sync", response_model=InvoiceCollection)
def sync_invoices(
    access: Manage, request: Request, offset: int = Query(0, ge=0, le=1000)
) -> dict[str, Any]:
    settings = enabled(request)
    org, actor = access.context.organization_id, access.authenticated.user_id
    context = TrustedOrganizationContext(org, actor, access.context.correlation_id)
    with transaction(request.app.state.database_engine, context) as session:
        require_restricted(session)
        if not manager(session, org, actor):
            raise HTTPException(403)
        item = session.scalar(select(OrganizationSubscription))
        if not item or item.provider != "razorpay" or item.mode != "test" or not item.external_id:
            raise HTTPException(404)
        external, key = item.external_id, item.plan_key
    try:
        remote = provider(settings).fetch_subscription(external)
        binding(remote, org, settings.razorpay_plan_ids.get(key, ""), external)
        page = provider(settings).invoices(external, offset)
        rows = page.get("items")
        if (
            not isinstance(rows, list)
            or len(rows) > 50
            or any(not isinstance(row, dict) for row in rows)
        ):
            raise BillingUnavailable("invoice_collection_invalid")
        documents = [invoice_document(row, external) for row in rows]
        if len({d["external_id"] for d in documents}) != len(documents):
            raise BillingUnavailable("invoice_collection_ambiguous")
    except (BillingUnavailable, TypeError):
        raise HTTPException(503) from None
    with transaction(request.app.state.database_engine, context) as session:
        require_restricted(session)
        if not manager(session, org, actor):
            raise HTTPException(403)
        current = session.scalar(select(OrganizationSubscription))
        if not current or current.external_id != external:
            raise HTTPException(409)
        for document in documents:
            hashed = digest(document)
            exists = session.scalar(
                select(InvoiceSnapshot.id).where(
                    InvoiceSnapshot.external_id == document["external_id"],
                    InvoiceSnapshot.content_hash == hashed,
                )
            )
            if not exists:
                session.add(
                    InvoiceSnapshot(
                        organization_id=org,
                        external_id=document["external_id"],
                        subscription_external_id=external,
                        content_hash=hashed,
                        document=document,
                    )
                )
        audit(session, org, actor, "invoices_synced", current.id)
    return {
        "invoices": documents,
        "next_offset": offset + 50 if len(documents) == 50 and offset < 1000 else None,
    }


class SubscriptionHistory(Contract):
    external_id: str
    plan_key: str
    status: str
    period_end: datetime | None
    source: str
    created_at: datetime


@router.get("/history", response_model=list[SubscriptionHistory])
def history(access: Manage) -> list[BillingSnapshot]:
    return list(
        access.authenticated.session.scalars(
            select(BillingSnapshot).order_by(BillingSnapshot.created_at.desc()).limit(100)
        )
    )
