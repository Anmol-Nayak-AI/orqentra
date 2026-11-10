"""Synthetic merchant transports: no real checkout, invoice or customer payment evidence."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from auth_helpers import ISSUER, ORIGIN, PUBLIC, token
from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_identity_authorization import add_existing_member, org

from orqentra.billing.providers import BillingUnavailable
from orqentra.core.config import Settings
from orqentra.main import create_app
from orqentra.persistence.models import BillingOperation, InvoiceSnapshot, OrganizationSubscription


def call(db, subject, path, method="GET", body=None, actions=True):
    app = create_app(
        Settings(
            database_url=db[1].url.render_as_string(hide_password=False),
            clerk_issuer=ISSUER,
            clerk_jwt_key=PUBLIC,
            clerk_allowed_origins=ORIGIN,
            billing_provider="razorpay",
            billing_test_actions_enabled=actions,
            RAZORPAY_KEY_ID="rzp_test_synthetic",
            RAZORPAY_KEY_SECRET="synthetic",
            RAZORPAY_WEBHOOK_SECRET="synthetic",
            razorpay_plan_ids={"pilot": "plan_synthetic"},
        )
    )

    async def run():
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
                result = await client.request(
                    method,
                    path,
                    json=body,
                    headers={"Authorization": "Bearer " + token(subject)} if subject else {},
                )
                return result.status_code, result.json()
        finally:
            app.state.database_engine.dispose()

    return asyncio.run(run())


class Merchant:
    def __init__(self):
        self.created = []
        self.cancelled = []
        self.remote = {}
        self.state = "created"
        self.timeout = False
        self.amount = 50000

    def fetch_plan(self, key):
        return {
            "id": key,
            "item": {"amount": self.amount, "currency": "INR"},
            "interval": 1,
            "period": "monthly",
        }

    def create_subscription(self, key, notes):
        reference = "sub_" + uuid4().hex
        self.created.append(reference)
        self.remote = {
            "id": reference,
            "plan_id": key,
            "status": self.state,
            "notes": notes,
            "short_url": "https://rzp.io/rzp/synthetic",
        }
        if self.timeout:
            raise BillingUnavailable("synthetic_transport_timeout")
        return dict(self.remote)

    def fetch_subscription(self, reference):
        return {
            **self.remote,
            "id": reference,
            "status": self.state,
            "current_end": int((datetime.now(UTC) + timedelta(days=30)).timestamp()),
        }

    def cancel_subscription(self, reference):
        self.cancelled.append(reference)
        return self.fetch_subscription(reference)

    def invoices(self, reference, offset):
        return {
            "items": [
                {
                    "id": "inv_synthetic",
                    "subscription_id": reference,
                    "status": "paid",
                    "currency": "INR",
                    "amount": 50000,
                    "amount_paid": 50000,
                    "amount_due": 0,
                    "short_url": "https://rzp.io/i/synthetic",
                    "customer_details": {"email": "must-not-be-stored@example.invalid"},
                }
            ]
        }


def test_test_checkout_reconcile_cancel_invoices_and_tenant_guards(db, monkeypatch):
    owner = "user_" + uuid4().hex
    tenant = org(db, owner)
    base = f"/api/v1/organizations/{tenant['id']}/billing"
    merchant = Merchant()
    monkeypatch.setattr("orqentra.billing.lifecycle.provider", lambda settings: merchant)
    payload = {
        "plan_key": "pilot",
        "idempotency_key": uuid4().hex,
        "quote_hash": call(db, owner, base + "/catalog")[1]["plans"][0]["quote_hash"],
    }
    assert call(db, owner, base + "/checkout", "POST", payload, actions=False)[0] == 503
    assert not merchant.created

    def submit(_):
        return call(db, owner, base + "/checkout", "POST", payload)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(submit, range(2)))
    assert all(code == 200 for code, _ in results)
    assert len(merchant.created) == 1
    code, operation = call(db, owner, base + "/checkout", "POST", payload)
    assert code == 200 and operation["status"] == "READY" and operation["mode"] == "test"
    status = call(db, owner, base)[1]
    assert status["subscription_status"] == "PENDING" and status["entitlements_available"] is False
    merchant.state = "active"
    assert call(db, owner, base + "/reconcile", "POST")[1]["status"] == "ACTIVE"
    assert call(db, owner, base)[1]["entitlements_available"] is True
    cancelled = call(db, owner, base + "/cancel", "POST", {"idempotency_key": uuid4().hex})
    assert cancelled[1]["status"] == "READY"
    assert call(db, owner, base + "/cancel", "POST", {"idempotency_key": uuid4().hex})[0] == 200
    assert len(merchant.cancelled) == 1
    # Scheduled cancellation does not invent an ended/paid state.
    assert call(db, owner, base)[1]["subscription_status"] == "ACTIVE"
    assert (
        call(db, owner, base + "/invoices/sync", "POST")[1]["invoices"][0]["amount_minor"] == 50000
    )
    assert call(db, owner, base + "/invoices/sync", "POST")[0] == 200
    docs = call(db, owner, base + "/invoices")[1]["invoices"]
    assert len(docs) == 1 and "customer_details" not in docs[0]
    with Session(db[0]) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(InvoiceSnapshot)
                .where(InvoiceSnapshot.organization_id == UUID(tenant["id"]))
            )
            == 1
        )
    member = "user_" + uuid4().hex
    add_existing_member(db, tenant["id"], member, "MEMBER")
    assert call(db, member, base + "/invoices")[0] == 403
    stranger = "user_" + uuid4().hex
    org(db, stranger)
    assert call(db, stranger, base + "/operations")[0] == 403
    merchant.state = "cancelled"
    assert call(db, owner, base + "/reconcile", "POST")[1]["status"] == "CANCELLED"
    assert call(db, owner, base)[1]["entitlements_available"] is False


def test_uncertain_creation_is_not_reissued_and_can_be_bound_afterward(db, monkeypatch):
    owner = "user_" + uuid4().hex
    tenant = org(db, owner)
    base = f"/api/v1/organizations/{tenant['id']}/billing"
    merchant = Merchant()
    merchant.timeout = True
    monkeypatch.setattr("orqentra.billing.lifecycle.provider", lambda settings: merchant)
    payload = {
        "plan_key": "pilot",
        "idempotency_key": uuid4().hex,
        "quote_hash": call(db, owner, base + "/catalog")[1]["plans"][0]["quote_hash"],
    }
    code, operation = call(db, owner, base + "/checkout", "POST", payload)
    assert code == 200 and operation["status"] == "UNKNOWN"
    assert call(db, owner, base + "/checkout", "POST", payload)[1]["status"] == "UNKNOWN"
    assert (
        call(db, owner, base + "/checkout", "POST", dict(payload, idempotency_key=uuid4().hex))[0]
        == 409
    )
    assert len(merchant.created) == 1
    with Session(db[0]) as session, session.begin():
        record = session.get(BillingOperation, UUID(operation["id"]))
        record.created_at = datetime.now(UTC) - timedelta(minutes=1)
    original_notes = dict(merchant.remote["notes"])
    merchant.remote["notes"]["orqentra_checkout_request"] = str(uuid4())
    assert (
        call(
            db,
            owner,
            base + f"/operations/{operation['id']}/resolve",
            "POST",
            {"external_id": merchant.created[0]},
        )[0]
        == 409
    )
    merchant.remote["notes"] = original_notes
    resolved = call(
        db,
        owner,
        base + f"/operations/{operation['id']}/resolve",
        "POST",
        {"external_id": merchant.created[0]},
    )
    assert resolved[0] == 200 and resolved[1]["status"] == "READY"
    assert call(db, owner, base)[1]["subscription_status"] == "PENDING"


def test_reconciliation_cannot_grant_entitlement_from_another_tenant_or_plan(db, monkeypatch):
    owner = "user_" + uuid4().hex
    tenant = org(db, owner)
    base = f"/api/v1/organizations/{tenant['id']}/billing"
    merchant = Merchant()
    monkeypatch.setattr("orqentra.billing.lifecycle.provider", lambda settings: merchant)
    assert (
        call(
            db,
            owner,
            base + "/checkout",
            "POST",
            {
                "plan_key": "pilot",
                "idempotency_key": uuid4().hex,
                "quote_hash": call(db, owner, base + "/catalog")[1]["plans"][0]["quote_hash"],
            },
        )[0]
        == 200
    )
    merchant.state = "active"
    merchant.remote["notes"] = {"orqentra_organization_id": str(uuid4())}
    assert call(db, owner, base + "/reconcile", "POST")[0] == 503
    assert call(db, owner, base)[1]["entitlements_available"] is False
    with Session(db[0]) as session:
        assert (
            session.scalar(
                select(OrganizationSubscription.status).where(
                    OrganizationSubscription.organization_id == UUID(tenant["id"])
                )
            )
            == "PENDING"
        )


def test_checkout_rejects_changed_quote_and_reconciliation_fences_newer_state(db, monkeypatch):
    owner = "user_" + uuid4().hex
    tenant = org(db, owner)
    base = f"/api/v1/organizations/{tenant['id']}/billing"
    merchant = Merchant()
    monkeypatch.setattr("orqentra.billing.lifecycle.provider", lambda settings: merchant)
    quote = call(db, owner, base + "/catalog")[1]["plans"][0]["quote_hash"]
    merchant.amount = 60000
    assert (
        call(
            db,
            owner,
            base + "/checkout",
            "POST",
            {"plan_key": "pilot", "idempotency_key": uuid4().hex, "quote_hash": quote},
        )[0]
        == 409
    )
    assert not merchant.created
    quote = call(db, owner, base + "/catalog")[1]["plans"][0]["quote_hash"]
    assert (
        call(
            db,
            owner,
            base + "/checkout",
            "POST",
            {"plan_key": "pilot", "idempotency_key": uuid4().hex, "quote_hash": quote},
        )[0]
        == 200
    )
    original = merchant.fetch_subscription

    def newer_state(reference):
        remote = original(reference)
        with Session(db[0]) as session, session.begin():
            row = session.scalar(
                select(OrganizationSubscription).where(
                    OrganizationSubscription.organization_id == UUID(tenant["id"])
                )
            )
            row.status = "CANCELLED"
        return remote

    merchant.state = "active"
    merchant.fetch_subscription = newer_state
    assert call(db, owner, base + "/reconcile", "POST")[0] == 409
    assert call(db, owner, base)[1]["subscription_status"] == "CANCELLED"


def test_uncertain_cancellation_is_not_replayed_and_resolves_only_after_provider_end(
    db, monkeypatch
):
    owner = "user_" + uuid4().hex
    tenant = org(db, owner)
    base = f"/api/v1/organizations/{tenant['id']}/billing"
    merchant = Merchant()
    monkeypatch.setattr("orqentra.billing.lifecycle.provider", lambda settings: merchant)
    quote = call(db, owner, base + "/catalog")[1]["plans"][0]["quote_hash"]
    assert (
        call(
            db,
            owner,
            base + "/checkout",
            "POST",
            {"plan_key": "pilot", "quote_hash": quote, "idempotency_key": uuid4().hex},
        )[0]
        == 200
    )
    merchant.state = "active"
    assert call(db, owner, base + "/reconcile", "POST")[0] == 200

    def uncertain(reference):
        merchant.cancelled.append(reference)
        raise BillingUnavailable("synthetic_timeout_after_accept")

    merchant.cancel_subscription = uncertain
    code, operation = call(db, owner, base + "/cancel", "POST", {"idempotency_key": uuid4().hex})
    assert code == 200 and operation["status"] == "UNKNOWN"
    assert (
        call(db, owner, base + "/cancel", "POST", {"idempotency_key": uuid4().hex})[1]["status"]
        == "UNKNOWN"
    )
    assert len(merchant.cancelled) == 1
    with Session(db[0]) as session, session.begin():
        session.get(BillingOperation, UUID(operation["id"])).created_at = datetime.now(
            UTC
        ) - timedelta(minutes=1)
    path = base + f"/operations/{operation['id']}/resolve"
    assert call(db, owner, path, "POST", {"external_id": merchant.created[0]})[0] == 409
    merchant.state = "cancelled"
    assert (
        call(db, owner, path, "POST", {"external_id": merchant.created[0]})[1]["status"] == "READY"
    )
    assert call(db, owner, base)[1]["entitlements_available"] is False
