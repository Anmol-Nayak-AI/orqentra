"""Razorpay TEST webhook processing. A signature is not permission to choose any tenant/plan."""

import hashlib
import json
import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy import or_, select

from orqentra.billing.providers import BillingUnavailable, provider
from orqentra.billing.service import lock_organization
from orqentra.persistence.models import (
    BillingSnapshot,
    BillingWebhookEvent,
    OrganizationSubscription,
)
from orqentra.persistence.session import TrustedOrganizationContext, transaction
from orqentra.rag.service import require_restricted

router = APIRouter(prefix="/api/v1/billing/webhooks", tags=["billing provider callbacks"])
STATE = {
    "active": "ACTIVE",
    "created": "PENDING",
    "authenticated": "PENDING",
    "pending": "PAST_DUE",
    "halted": "PAST_DUE",
    "paused": "PAST_DUE",
    "cancelled": "CANCELLED",
    "completed": "EXPIRED",
    "expired": "EXPIRED",
}
RANK = {"ACTIVE": 3, "PENDING": 2, "PAST_DUE": 1, "CANCELLED": 0, "EXPIRED": 0, "UNAVAILABLE": 0}


@router.post("/razorpay", response_model=dict[str, str])
async def razorpay_webhook(request: Request) -> dict[str, str]:
    settings = request.app.state.settings
    if settings.billing_provider != "razorpay" or request.app.state.database_engine is None:
        raise HTTPException(503)
    raw = await request.body()
    try:
        valid = provider(settings).verify(raw, request.headers.get("x-razorpay-signature", ""))
    except BillingUnavailable:
        raise HTTPException(503) from None
    if not valid:
        raise HTTPException(401)
    event_id = request.headers.get("x-razorpay-event-id", "")
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", event_id):
        raise HTTPException(400)
    try:
        data = json.loads(raw)
        entity = data["payload"]["subscription"]["entity"]
        if not isinstance(entity, dict) or not isinstance(entity.get("notes"), dict):
            raise ValueError
        if data.get("event") not in {"subscription." + state for state in STATE} | {
            "subscription.activated",
            "subscription.charged",
            "subscription.resumed",
        }:
            raise ValueError
        if not isinstance(entity.get("status"), str):
            raise ValueError
        organization_id = UUID(str(entity["notes"]["orqentra_organization_id"]))
        external_id = entity["id"]
        if not isinstance(external_id, str) or not re.fullmatch(
            r"sub_[A-Za-z0-9]{1,90}", external_id
        ):
            raise ValueError
        if not isinstance(data["created_at"], int) or isinstance(data["created_at"], bool):
            raise ValueError
        created_at = datetime.fromtimestamp(data["created_at"], UTC)
        if (
            not datetime.now(UTC) - timedelta(days=2)
            <= created_at
            <= datetime.now(UTC) + timedelta(minutes=5)
        ):
            raise ValueError
    except (ValueError, TypeError, KeyError, OverflowError):
        raise HTTPException(400) from None
    body_hash = hashlib.sha256(raw).hexdigest()
    context = TrustedOrganizationContext(
        organization_id, UUID(int=0), UUID(request.state.correlation_id)
    )
    with transaction(request.app.state.database_engine, context) as session:
        require_restricted(session)
        lock_organization(session, organization_id)
        subscription = session.scalar(
            select(OrganizationSubscription)
            .where(
                OrganizationSubscription.organization_id == organization_id,
                OrganizationSubscription.provider == "razorpay",
                OrganizationSubscription.mode == "test",
                OrganizationSubscription.external_id == external_id,
            )
            .with_for_update()
        )
        if subscription is None:
            raise HTTPException(404)
        expected_plan = settings.razorpay_plan_ids.get(subscription.plan_key)
        if not expected_plan or entity.get("plan_id") != expected_plan:
            raise HTTPException(409)
        old = session.scalar(
            select(BillingWebhookEvent).where(
                BillingWebhookEvent.organization_id == organization_id,
                BillingWebhookEvent.provider == "razorpay",
                or_(
                    BillingWebhookEvent.event_id == event_id,
                    BillingWebhookEvent.body_hash == body_hash,
                ),
            )
        )
        if old:
            if old.event_id == event_id and old.body_hash != body_hash:
                raise HTTPException(409)
            return {"status": "duplicate"}
        status = STATE.get(str(entity["status"]), "UNAVAILABLE")
        end = None
        if status == "ACTIVE":
            try:
                if not isinstance(entity["current_end"], int) or isinstance(
                    entity["current_end"], bool
                ):
                    raise ValueError
                end = datetime.fromtimestamp(entity["current_end"], UTC)
                if end <= datetime.now(UTC):
                    status = "EXPIRED"
            except (KeyError, ValueError, TypeError, OverflowError):
                raise HTTPException(400) from None
        older = (
            subscription.provider_event_at is not None
            and created_at < subscription.provider_event_at
        )
        equal_upgrade = (
            subscription.provider_event_at == created_at
            and RANK[status] >= RANK[subscription.status]
        )
        terminal = subscription.status in {"CANCELLED", "EXPIRED"}
        result = "IGNORED" if older or equal_upgrade or terminal else "APPLIED"
        if result == "APPLIED":
            subscription.status = status
            subscription.period_end = end
            subscription.provider_event_at = created_at
            session.add(
                BillingSnapshot(
                    organization_id=organization_id,
                    external_id=external_id,
                    plan_key=subscription.plan_key,
                    status=status,
                    period_end=end,
                    source="signed_webhook",
                )
            )
        session.add(
            BillingWebhookEvent(
                organization_id=organization_id,
                subscription_id=subscription.id,
                provider="razorpay",
                event_id=event_id,
                body_hash=body_hash,
                result=result,
                provider_created_at=created_at,
            )
        )
    return {"status": result.lower()}
