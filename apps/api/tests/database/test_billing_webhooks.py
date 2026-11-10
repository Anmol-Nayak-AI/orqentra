"""Synthetic signed callbacks only: these are not real Razorpay payment evidence."""

import asyncio
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session
from test_rag_chat import chat_fixture

from orqentra.core.config import Settings
from orqentra.main import create_app
from orqentra.persistence.models import BillingWebhookEvent, OrganizationSubscription

SECRET = "synthetic-webhook-secret"


def callback(db, body, event_id, *, signature=None, enabled=True):
    config = Settings(
        database_url=db[1].url.render_as_string(hide_password=False),
        billing_provider="razorpay" if enabled else "disabled",
        RAZORPAY_KEY_ID="rzp_test_synthetic",
        RAZORPAY_KEY_SECRET="synthetic-key-secret",
        RAZORPAY_WEBHOOK_SECRET=SECRET,
        razorpay_plan_ids={"pilot": "plan_synthetic"},
    )
    app = create_app(config)
    raw = json.dumps(body).encode()

    async def run():
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
                response = await c.post(
                    "/api/v1/billing/webhooks/razorpay",
                    content=raw,
                    headers={
                        "x-razorpay-event-id": event_id,
                        "x-razorpay-signature": signature
                        if signature is not None
                        else hmac.new(SECRET.encode(), raw, hashlib.sha256).hexdigest(),
                    },
                )
                return response.status_code, response.json()
        finally:
            app.state.database_engine.dispose()

    return asyncio.run(run())


def fixture(db):
    _, base, _, _ = chat_fixture(db)
    tenant = UUID(base.split("/")[4])
    external = "sub_" + uuid4().hex
    with Session(db[0]) as s, s.begin():
        s.add(
            OrganizationSubscription(
                organization_id=tenant,
                provider="razorpay",
                mode="test",
                plan_key="pilot",
                status="PENDING",
                external_id=external,
            )
        )
    now = int(datetime.now(UTC).timestamp())
    body = {
        "event": "subscription.activated",
        "created_at": now,
        "payload": {
            "subscription": {
                "entity": {
                    "id": external,
                    "status": "active",
                    "plan_id": "plan_synthetic",
                    "current_end": now + 86400,
                    "notes": {"orqentra_organization_id": str(tenant)},
                }
            }
        },
    }
    return tenant, body


def test_signed_callback_replay_order_and_terminal_state(db: tuple[Engine, Engine]):
    tenant, body = fixture(db)
    event_id = "evt_" + uuid4().hex
    assert callback(db, body, event_id, enabled=False)[0] == 503
    assert callback(db, body, event_id, signature="0" * 64)[0] == 401
    assert callback(db, body, event_id) == (200, {"status": "applied"})
    assert callback(db, body, event_id) == (200, {"status": "duplicate"})
    assert callback(db, body, "evt_" + uuid4().hex) == (200, {"status": "duplicate"})
    entity = body["payload"]["subscription"]["entity"]
    entity["status"] = "cancelled"
    body["event"] = "subscription.cancelled"
    assert callback(db, body, event_id)[0] == 409
    body["created_at"] -= 10
    assert callback(db, body, "evt_" + uuid4().hex)[1] == {"status": "ignored"}
    body["created_at"] += 10
    assert callback(db, body, "evt_" + uuid4().hex)[1] == {"status": "applied"}
    entity["status"] = "active"
    body["event"] = "subscription.activated"
    body["created_at"] += 1
    assert callback(db, body, "evt_" + uuid4().hex)[1] == {"status": "ignored"}
    with Session(db[0]) as s:
        sub = s.scalar(
            select(OrganizationSubscription).where(
                OrganizationSubscription.organization_id == tenant
            )
        )
        assert sub.status == "CANCELLED"
        assert (
            s.scalar(
                select(func.count())
                .select_from(BillingWebhookEvent)
                .where(BillingWebhookEvent.organization_id == tenant)
            )
            == 4
        )


def test_callback_binding_and_malformed_payloads(db: tuple[Engine, Engine]):
    _, body = fixture(db)
    entity = body["payload"]["subscription"]["entity"]
    entity["notes"]["orqentra_organization_id"] = str(uuid4())
    assert callback(db, body, "evt_" + uuid4().hex)[0] == 403
    tenant, body = fixture(db)
    entity = body["payload"]["subscription"]["entity"]
    entity["plan_id"] = "plan_wrong"
    assert callback(db, body, "evt_" + uuid4().hex)[0] == 409
    entity["plan_id"] = "plan_synthetic"
    entity["status"] = {}
    assert callback(db, body, "evt_" + uuid4().hex)[0] == 400
    entity["status"] = "active"
    body["created_at"] = int((datetime.now(UTC) - timedelta(days=3)).timestamp())
    assert callback(db, body, "evt_" + uuid4().hex)[0] == 400


def test_existing_test_subscription_link_requires_admin_and_starts_pending(db, monkeypatch):
    from auth_helpers import ISSUER, ORIGIN, PUBLIC, token

    from orqentra.billing.providers import RazorpayTestProvider

    owner, base, _, _ = chat_fixture(db)
    tenant = UUID(base.split("/")[4])
    external = "sub_" + uuid4().hex
    monkeypatch.setattr(
        RazorpayTestProvider,
        "fetch_subscription",
        lambda self, reference: {
            "id": reference,
            "plan_id": "plan_synthetic",
            "status": "active",
            "notes": {"orqentra_organization_id": str(tenant)},
        },
    )
    config = Settings(
        database_url=db[1].url.render_as_string(hide_password=False),
        clerk_issuer=ISSUER,
        clerk_jwt_key=PUBLIC,
        clerk_allowed_origins=ORIGIN,
        billing_provider="razorpay",
        RAZORPAY_KEY_ID="rzp_test_synthetic",
        RAZORPAY_KEY_SECRET="synthetic",
        RAZORPAY_WEBHOOK_SECRET=SECRET,
        razorpay_plan_ids={"pilot": "plan_synthetic"},
    )
    app = create_app(config)

    async def run():
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
                path = base + "/billing/test-subscription"
                body = {"external_id": external, "plan_key": "pilot"}
                assert (await client.post(path, json=body)).status_code == 401
                denied = await client.post(
                    path,
                    json=body,
                    headers={"authorization": "Bearer " + token("user_" + uuid4().hex)},
                )
                assert denied.status_code == 403
                response = await client.post(
                    path, json=body, headers={"authorization": "Bearer " + token(owner)}
                )
                assert response.status_code == 200
                data = response.json()
                assert data["subscription_status"] == "PENDING"
                assert data["entitlements_available"] is False
        finally:
            app.state.database_engine.dispose()

    asyncio.run(run())
