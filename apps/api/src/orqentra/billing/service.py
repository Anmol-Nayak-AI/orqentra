"""Server-owned entitlement policies and transactionally coupled quota reservations."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from orqentra.persistence.models import (
    ChatExchange,
    OrganizationSubscription,
    TaskRun,
    UsageBucket,
    UsageEvent,
)

# Draft internal policies, not published prices or purchasable plans.
PLAN_LIMITS = {
    "development": {"chat_turns": 20, "task_runs": 10, "sandbox_runs": 2},
    "pilot": {"chat_turns": 100, "task_runs": 25, "sandbox_runs": 10},
}


def policy(session: Session, organization_id: UUID, environment: str) -> dict[str, int] | None:
    subscription = session.scalar(
        select(OrganizationSubscription).where(
            OrganizationSubscription.organization_id == organization_id
        )
    )
    if subscription is None or (
        subscription.provider == "disabled" and subscription.status == "UNAVAILABLE"
    ):
        return PLAN_LIMITS["development"] if environment in {"development", "test"} else None
    # No live payments or production paid entitlements are authorized in this phase.
    if (
        environment == "production"
        or subscription.mode != "test"
        or subscription.provider not in {"razorpay", "stripe"}
    ):
        return None
    if (
        subscription.status != "ACTIVE"
        or subscription.period_end is None
        or subscription.period_end <= datetime.now(UTC)
    ):
        return None
    return PLAN_LIMITS.get(subscription.plan_key)


def day() -> tuple[datetime, datetime]:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return start, start + timedelta(days=1)


def legacy_count(
    session: Session, organization_id: UUID, metric: str, start: datetime, end: datetime
) -> int:
    if metric == "sandbox_runs":
        # This metric has always used the ledger; draft proposals are not executions.
        return 0
    model = ChatExchange if metric == "chat_turns" else TaskRun
    return int(
        session.scalar(
            select(func.count())
            .select_from(model)
            .where(
                model.organization_id == organization_id,
                model.created_at >= start,
                model.created_at < end,
            )
        )
        or 0
    )


def lock_organization(session: Session, organization_id: UUID) -> None:
    if (
        session.scalar(
            text("SELECT id FROM organizations WHERE id=:id FOR UPDATE"), {"id": organization_id}
        )
        is None
    ):
        raise HTTPException(403)


def record_usage(
    session: Session, organization_id: UUID, metric: str, key: str, resource_id: UUID, amount: int
) -> None:
    if amount <= 0:
        return
    lock_organization(session, organization_id)
    old = session.scalar(
        select(UsageEvent).where(
            UsageEvent.organization_id == organization_id,
            UsageEvent.metric == metric,
            UsageEvent.idempotency_key == key,
        )
    )
    if old:
        if old.amount != amount or old.resource_id != resource_id:
            raise RuntimeError("Conflicting usage event identity.")
        return
    session.add(
        UsageEvent(
            organization_id=organization_id,
            metric=metric,
            amount=amount,
            idempotency_key=key,
            resource_id=resource_id,
        )
    )
    session.flush()


def reserve_intake(
    session: Session,
    organization_id: UUID,
    environment: str,
    metric: str,
    key: str,
    resource_id: UUID,
) -> None:
    lock_organization(session, organization_id)
    limits = policy(session, organization_id, environment)
    if limits is None or metric not in limits:
        raise HTTPException(402)
    existing = session.scalar(
        select(UsageEvent.id).where(
            UsageEvent.organization_id == organization_id,
            UsageEvent.metric == metric,
            UsageEvent.idempotency_key == key,
        )
    )
    if existing:
        return
    start, end = day()
    bucket = session.scalar(
        select(UsageBucket)
        .where(
            UsageBucket.organization_id == organization_id,
            UsageBucket.metric == metric,
            UsageBucket.period_start == start,
        )
        .with_for_update()
    )
    if bucket is None:
        bucket = UsageBucket(
            organization_id=organization_id,
            metric=metric,
            period_start=start,
            period_end=end,
            used=legacy_count(session, organization_id, metric, start, end),
        )
        session.add(bucket)
    if bucket.used >= limits[metric]:
        raise HTTPException(
            429,
            headers={"Retry-After": str(max(1, int((end - datetime.now(UTC)).total_seconds())))},
        )
    bucket.used += 1
    record_usage(session, organization_id, metric, key, resource_id, 1)


def record_generation(
    session: Session,
    organization_id: UUID,
    resource_id: UUID,
    claim_id: UUID,
    usage: dict[str, object],
) -> None:
    for metric in ("input_tokens", "output_tokens"):
        amount = usage.get(metric)
        if isinstance(amount, int) and not isinstance(amount, bool) and 0 < amount < 2**63:
            record_usage(
                session,
                organization_id,
                metric,
                f"generation:{resource_id}:{claim_id}",
                resource_id,
                amount,
            )
