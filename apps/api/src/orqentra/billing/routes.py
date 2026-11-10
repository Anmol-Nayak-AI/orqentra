from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import func, select

from orqentra.auth.dependencies import AuthorizedOrganization, OrganizationPermission
from orqentra.billing.providers import BillingUnavailable, provider
from orqentra.billing.service import PLAN_LIMITS, day, legacy_count, lock_organization, policy
from orqentra.execution.routes import audit
from orqentra.organizations.schemas import Contract
from orqentra.persistence.models import (
    BillingSnapshot,
    OrganizationMembership,
    OrganizationSubscription,
    UsageBucket,
    UsageEvent,
)

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/billing", tags=["billing entitlements"]
)
Manage = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("organization.update"))]


class BillingStatus(Contract):
    provider: str
    mode: str
    subscription_status: str
    plan_key: str | None
    entitlements_available: bool
    quotas: dict[str, dict[str, int]]
    recorded_usage: dict[str, int]
    notice: str
    actions_enabled: bool
    external_id: str | None
    period_end: datetime | None


@router.get("", response_model=BillingStatus)
def status(access: Manage, request: Request) -> dict[str, object]:
    session = access.authenticated.session
    organization_id = access.context.organization_id
    subscription = session.scalar(
        select(OrganizationSubscription).where(
            OrganizationSubscription.organization_id == organization_id
        )
    )
    limits = policy(session, organization_id, request.app.state.settings.environment)
    start, end = day()
    quotas = {}
    for metric in ("chat_turns", "task_runs", "sandbox_runs"):
        bucket = session.scalar(
            select(UsageBucket).where(
                UsageBucket.organization_id == organization_id,
                UsageBucket.metric == metric,
                UsageBucket.period_start == start,
            )
        )
        used = bucket.used if bucket else legacy_count(session, organization_id, metric, start, end)
        limit = (limits or {}).get(metric, 0)
        quotas[metric] = {"used": used, "limit": limit, "remaining": max(0, limit - used)}
    usage = session.execute(
        select(UsageEvent.metric, func.sum(UsageEvent.amount))
        .where(
            UsageEvent.organization_id == organization_id,
            UsageEvent.created_at >= start,
            UsageEvent.created_at < end,
        )
        .group_by(UsageEvent.metric)
    ).all()
    return {
        "actions_enabled": request.app.state.settings.billing_test_actions_enabled,
        "external_id": subscription.external_id if subscription else None,
        "period_end": subscription.period_end if subscription else None,
        "provider": subscription.provider
        if subscription
        else request.app.state.settings.billing_provider,
        "mode": subscription.mode
        if subscription
        else "test"
        if request.app.state.settings.billing_provider == "razorpay"
        else "disabled",
        "subscription_status": subscription.status if subscription else "UNAVAILABLE",
        "plan_key": subscription.plan_key if subscription else "development" if limits else None,
        "entitlements_available": limits is not None,
        "quotas": quotas,
        "recorded_usage": {metric: int(amount) for metric, amount in usage},
        "notice": (
            "Draft internal policies; hosted checkout is test-only and disabled by default. "
            "No live payments. "
            "Quotas count accepted intakes per UTC day; recorded usage excludes pre-ledger "
            "history and calls without reported usage. This is not an invoice. "
            "Existing worker reservation budgets still apply."
        ),
    }


class TestSubscriptionLink(Contract):
    external_id: str = Field(pattern=r"^sub_[A-Za-z0-9]{1,90}$")
    plan_key: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,29}$")


@router.post("/test-subscription", response_model=BillingStatus)
def link_test_subscription(
    body: TestSubscriptionLink, access: Manage, request: Request
) -> dict[str, object]:
    settings = request.app.state.settings
    if settings.billing_provider != "razorpay":
        raise HTTPException(503)
    expected_plan = settings.razorpay_plan_ids.get(body.plan_key)
    if body.plan_key not in PLAN_LIMITS or not expected_plan:
        raise HTTPException(422)
    try:
        remote = provider(settings).fetch_subscription(body.external_id)
    except BillingUnavailable:
        raise HTTPException(503) from None
    notes = remote.get("notes")
    if not isinstance(notes, dict):
        raise HTTPException(502)
    if remote.get("plan_id") != expected_plan or notes.get("orqentra_organization_id") != str(
        access.context.organization_id
    ):
        raise HTTPException(403)
    session = access.authenticated.session
    lock_organization(session, access.context.organization_id)
    member = session.scalar(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.organization_id == access.context.organization_id,
            OrganizationMembership.user_id == access.authenticated.user_id,
            OrganizationMembership.status == "ACTIVE",
        )
        .execution_options(populate_existing=True)
    )
    if member is None or member.role not in {"OWNER", "ADMIN"}:
        raise HTTPException(403)
    subscription = session.scalar(
        select(OrganizationSubscription)
        .where(OrganizationSubscription.organization_id == access.context.organization_id)
        .with_for_update()
    )
    if subscription:
        if subscription.external_id != body.external_id or subscription.plan_key != body.plan_key:
            raise HTTPException(409)
    else:
        subscription = OrganizationSubscription(
            organization_id=access.context.organization_id,
            provider="razorpay",
            mode="test",
            external_id=body.external_id,
            plan_key=body.plan_key,
            status="PENDING",
        )
        session.add(subscription)
        session.flush()
        session.add(
            BillingSnapshot(
                organization_id=subscription.organization_id,
                external_id=body.external_id,
                plan_key=body.plan_key,
                status="PENDING",
                source="existing_test_link",
            )
        )
        audit(access, "billing.test_subscription_linked", subscription.id)
    return status(access, request)
