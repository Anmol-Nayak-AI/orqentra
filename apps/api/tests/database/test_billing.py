from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_identity_authorization import call
from test_rag_chat import chat_fixture

from orqentra.billing.service import day
from orqentra.persistence.models import OrganizationSubscription, UsageBucket, UsageEvent


def test_atomic_quota_and_idempotency_are_tenant_scoped(db: tuple[Engine, Engine]) -> None:
    owner, base, doc, chat = chat_fixture(db)
    _, other_base, _, _ = chat_fixture(db)
    tenant = UUID(base.split("/")[4])
    second = call(db, owner, base + "/chats", "POST", {"workspace_id": doc["workspace_id"]})[1][
        "id"
    ]
    start, end = day()
    with Session(db[0]) as session, session.begin():
        session.add(
            UsageBucket(
                organization_id=tenant,
                metric="chat_turns",
                period_start=start,
                period_end=end,
                used=19,
            )
        )

    def send(chat_id):
        body = {"question": "A synthetic quota test question", "idempotency_key": uuid4().hex}
        code, result = call(db, owner, base + f"/chats/{chat_id}/messages", "POST", body)
        return chat_id, body, code, result

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(send, [chat, second]))
    assert sorted(row[2] for row in results) == [202, 429]
    chat_id, body, _, message = next(row for row in results if row[2] == 202)
    assert call(db, owner, base + f"/chats/{chat_id}/messages", "POST", body)[1] == message
    status, billing = call(db, owner, base + "/billing")
    assert status == 200 and billing["quotas"]["chat_turns"] == {
        "used": 20,
        "limit": 20,
        "remaining": 0,
    }
    assert billing["provider"] == "disabled" and billing["subscription_status"] == "UNAVAILABLE"
    assert billing["recorded_usage"]["chat_turns"] == 1
    assert call(db, owner, other_base + "/billing")[0] == 403
    with Session(db[0]) as session:
        event = session.scalar(
            select(UsageEvent.id).where(
                UsageEvent.organization_id == tenant, UsageEvent.metric == "chat_turns"
            )
        )
        with pytest.raises(DBAPIError):
            session.execute(text("UPDATE usage_events SET amount=999 WHERE id=:id"), {"id": event})


def test_expired_or_cancelled_subscriptions_do_not_grant_entitlements(
    db: tuple[Engine, Engine],
) -> None:
    owner, base, _, chat = chat_fixture(db)
    tenant = UUID(base.split("/")[4])
    with Session(db[0]) as session, session.begin():
        subscription = OrganizationSubscription(
            organization_id=tenant,
            provider="razorpay",
            mode="test",
            plan_key="pilot",
            status="ACTIVE",
            external_id="sub_synthetic_" + uuid4().hex,
            period_end=datetime.now(UTC) - timedelta(days=1),
        )
        session.add(subscription)
    code, status = call(db, owner, base + "/billing")
    assert code == 200 and status["entitlements_available"] is False
    assert (
        call(
            db,
            owner,
            base + f"/chats/{chat}/messages",
            "POST",
            {"question": "Should be denied", "idempotency_key": uuid4().hex},
        )[0]
        == 402
    )
    with Session(db[0]) as session, session.begin():
        sub = session.scalar(
            select(OrganizationSubscription).where(
                OrganizationSubscription.organization_id == tenant
            )
        )
        sub.status = "CANCELLED"
        sub.period_end = datetime.now(UTC) + timedelta(days=1)
    assert call(db, owner, base + "/billing")[1]["entitlements_available"] is False
