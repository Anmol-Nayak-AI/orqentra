import asyncio
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

import pytest
from auth_helpers import ISSUER, ORIGIN, PUBLIC, token
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from orqentra.core.config import Settings
from orqentra.main import create_app
from orqentra.persistence.models import AuditEvent, OrganizationMembership, User


async def request(
    db: tuple[Engine, Engine],
    subject: str | None,
    path: str,
    method: str = "GET",
    body: dict[str, object] | None = None,
    raw: str | None = None,
    extra_headers: dict[str, str] | None = None,
) -> tuple[int, object]:
    config = Settings(
        database_url=db[1].url.render_as_string(hide_password=False),
        clerk_issuer=ISSUER,
        clerk_jwt_key=PUBLIC,
        clerk_allowed_origins=ORIGIN,
    )
    app = create_app(config)
    headers = {"Authorization": "Bearer " + (raw or token(subject))} if subject else {}
    headers.update(extra_headers or {})
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            r = await client.request(method, path, headers=headers, json=body)
            return r.status_code, r.json() if r.content else None
    finally:
        app.state.database_engine.dispose()


def call(
    db: tuple[Engine, Engine],
    subject: str | None,
    path: str,
    method: str = "GET",
    body: dict[str, object] | None = None,
    raw: str | None = None,
) -> tuple[int, object]:
    return asyncio.run(request(db, subject, path, method, body, raw))


def org(db: tuple[Engine, Engine], subject: str) -> dict[str, object]:
    status, data = call(
        db,
        subject,
        "/api/v1/organizations",
        "POST",
        {"name": "Synthetic tenant", "slug": "tenant-" + uuid4().hex},
    )
    assert status == 201, data
    assert isinstance(data, dict)
    return data


def add_existing_member(
    db: tuple[Engine, Engine], org_id: object, subject: str, role: str, status: str = "ACTIVE"
) -> UUID:
    # Approved test fixture, not an application membership-creation endpoint.
    response, data = call(db, subject, "/api/v1/me")
    assert response == 200
    assert isinstance(data, dict)
    with Session(db[0]) as session, session.begin():
        m = OrganizationMembership(
            organization_id=UUID(str(org_id)), user_id=UUID(data["id"]), role=role, status=status
        )
        session.add(m)
        session.flush()
        return m.id


def test_missing_token_and_untrusted_headers(db: tuple[Engine, Engine]) -> None:
    status, _ = asyncio.run(
        request(
            db,
            None,
            "/api/v1/me",
            extra_headers={
                "X-User-Id": "user_forged",
                "X-Organization-Id": str(uuid4()),
                "X-Role": "OWNER",
            },
        )
    )
    assert status == 401


def test_jit_repeated_and_concurrent(db: tuple[Engine, Engine]) -> None:
    subject = "user_" + uuid4().hex

    def login(_: int) -> object:
        status, data = call(db, subject, "/api/v1/me")
        assert status == 200, data
        return data

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(login, range(4)))
    assert all(r == results[0] for r in results)
    with Session(db[0]) as session:
        assert (
            session.scalar(
                select(func.count()).select_from(User).where(User.external_auth_id == subject)
            )
            == 1
        )


def test_no_email_linking(db: tuple[Engine, Engine]) -> None:
    with Session(db[0]) as s, s.begin():
        legacy = User(email="match@example.invalid", display_name="Legacy")
        s.add(legacy)
        s.flush()
        legacy_id = legacy.id
    status, data = call(
        db,
        "user_" + uuid4().hex,
        "/api/v1/me",
        raw=token("user_" + uuid4().hex, email="match@example.invalid"),
    )
    assert status == 200 and isinstance(data, dict)
    assert data["id"] != str(legacy_id)
    with Session(db[0]) as s:
        assert s.get(User, legacy_id).external_auth_id is None


def test_org_bootstrap_owner_and_audit(db: tuple[Engine, Engine]) -> None:
    owner = "user_" + uuid4().hex
    created = org(db, owner)
    status, m = call(db, owner, f"/api/v1/organizations/{created['id']}/memberships/me")
    assert status == 200 and isinstance(m, dict) and m["role"] == "OWNER"
    status, w = call(db, owner, f"/api/v1/organizations/{created['id']}/workspaces")
    assert status == 200 and isinstance(w, list) and len(w) == 1
    status, items = call(db, owner, "/api/v1/organizations")
    assert status == 200 and isinstance(items, list) and len(items) == 1
    with Session(db[0]) as s:
        events = s.scalars(
            select(AuditEvent).where(AuditEvent.organization_id == UUID(created["id"]))
        ).all()
        assert [e.action for e in events] == ["organization.created"]


@pytest.mark.parametrize("role", ["MEMBER", "VIEWER"])
def test_read_only_membership_policy(db: tuple[Engine, Engine], role: str) -> None:
    owner = "user_" + uuid4().hex
    created = org(db, owner)
    actor = "user_" + uuid4().hex
    mid = add_existing_member(db, created["id"], actor, role)
    base = f"/api/v1/organizations/{created['id']}"
    assert call(db, actor, base)[0] == 200
    assert call(db, actor, f"{base}/memberships/{mid}", "PATCH", {"role": "OWNER"})[0] == 403
    assert call(db, actor, f"{base}/memberships/{mid}", "DELETE")[0] == 403


def test_admin_escalation_and_owner_protection(db: tuple[Engine, Engine]) -> None:
    owner = "user_" + uuid4().hex
    created = org(db, owner)
    admin = "user_" + uuid4().hex
    admin_id = add_existing_member(db, created["id"], admin, "ADMIN")
    base = f"/api/v1/organizations/{created['id']}"
    _, membership = call(db, owner, base + "/memberships/me")
    assert isinstance(membership, dict)
    assert call(db, admin, f"{base}/memberships/{admin_id}", "PATCH", {"role": "OWNER"})[0] == 403
    assert call(db, admin, f"{base}/memberships/{membership['id']}", "DELETE")[0] == 403
    assert call(db, owner, f"{base}/memberships/{membership['id']}", "DELETE")[0] == 409
    assert (
        call(db, owner, f"{base}/memberships/{membership['id']}", "PATCH", {"role": "ADMIN"})[0]
        == 409
    )


def test_role_change_removal_audits_and_inactive(db: tuple[Engine, Engine]) -> None:
    owner = "user_" + uuid4().hex
    created = org(db, owner)
    actor = "user_" + uuid4().hex
    mid = add_existing_member(db, created["id"], actor, "MEMBER")
    base = f"/api/v1/organizations/{created['id']}"
    assert call(db, owner, f"{base}/memberships/{mid}", "PATCH", {"role": "ADMIN"})[0] == 200
    assert call(db, owner, f"{base}/memberships/{mid}", "DELETE")[0] == 204
    assert call(db, actor, base)[0] == 403
    with Session(db[0]) as s:
        events = s.scalars(
            select(AuditEvent).where(AuditEvent.resource_id == mid).order_by(AuditEvent.created_at)
        ).all()
        assert [e.action for e in events] == ["membership.role_changed", "membership.removed"]
        assert events[0].safe_metadata["old_role"] == "MEMBER"
        assert events[0].safe_metadata["new_role"] == "ADMIN"
        assert s.get(OrganizationMembership, mid).status == "REVOKED"


def test_cross_tenant_read_mutation_workspace(db: tuple[Engine, Engine]) -> None:
    owner = "user_" + uuid4().hex
    foreign = "user_" + uuid4().hex
    org(db, owner)
    second = org(db, foreign)
    _, m = call(db, foreign, f"/api/v1/organizations/{second['id']}/memberships/me")
    assert isinstance(m, dict)
    base = f"/api/v1/organizations/{second['id']}"
    for path in [base, base + "/memberships", base + "/workspaces", base + "/memberships/me"]:
        assert call(db, owner, path)[0] == 403
    assert call(db, owner, f"{base}/memberships/{m['id']}", "PATCH", {"role": "VIEWER"})[0] == 403
    assert call(db, owner, f"{base}/memberships/{m['id']}", "DELETE")[0] == 403
    with Session(db[0]) as s:
        assert s.get(OrganizationMembership, UUID(m["id"])).role == "OWNER"


def test_disabled_identity_denied(db: tuple[Engine, Engine]) -> None:
    subject = "user_" + uuid4().hex
    assert call(db, subject, "/api/v1/me")[0] == 200
    with Session(db[0]) as s, s.begin():
        user = s.scalar(select(User).where(User.external_auth_id == subject))
        user.status = "DISABLED"
    assert call(db, subject, "/api/v1/me")[0] == 403


def test_pool_context_cleared(db: tuple[Engine, Engine]) -> None:
    a, b = "user_" + uuid4().hex, "user_" + uuid4().hex
    first, second = org(db, a), org(db, b)
    for _ in range(3):
        assert call(db, a, f"/api/v1/organizations/{first['id']}")[0] == 200
        assert call(db, b, f"/api/v1/organizations/{first['id']}")[0] == 403
        assert call(db, b, f"/api/v1/organizations/{second['id']}")[0] == 200
    with db[1].connect() as c:
        assert (
            c.scalar(text("SELECT NULLIF(current_setting('app.organization_id',true),'')")) is None
        )
        assert (
            c.scalar(text("SELECT NULLIF(current_setting('app.external_auth_id',true),'')")) is None
        )
        assert c.scalar(text("SELECT count(*) FROM organizations")) == 0


def test_no_arbitrary_membership_creation(db: tuple[Engine, Engine]) -> None:
    actor = "user_" + uuid4().hex
    created = org(db, actor)
    assert (
        call(
            db,
            actor,
            f"/api/v1/organizations/{created['id']}/memberships",
            "POST",
            {"user_id": str(uuid4()), "role": "OWNER"},
        )[0]
        == 405
    )


def test_concurrent_last_owner_protection(db: tuple[Engine, Engine]) -> None:
    a, b = "user_" + uuid4().hex, "user_" + uuid4().hex
    created = org(db, a)
    second_id = add_existing_member(db, created["id"], b, "OWNER")
    _, own = call(db, a, f"/api/v1/organizations/{created['id']}/memberships/me")
    assert isinstance(own, dict)

    def demote(item: tuple[str, object]) -> int:
        subject, target = item
        return call(
            db,
            subject,
            f"/api/v1/organizations/{created['id']}/memberships/{target}",
            "PATCH",
            {"role": "ADMIN"},
        )[0]

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(demote, [(a, own["id"]), (b, second_id)])) == [200, 409]
    with Session(db[0]) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(OrganizationMembership)
                .where(
                    OrganizationMembership.organization_id == UUID(created["id"]),
                    OrganizationMembership.role == "OWNER",
                    OrganizationMembership.status == "ACTIVE",
                )
            )
            == 1
        )


def test_same_connection_reused_across_verified_tenants(db: tuple[Engine, Engine]) -> None:
    from sqlalchemy import event

    a, b = "user_" + uuid4().hex, "user_" + uuid4().hex
    first, second = org(db, a), org(db, b)
    app = create_app(
        Settings(
            database_url=db[1].url.render_as_string(hide_password=False),
            clerk_issuer=ISSUER,
            clerk_jwt_key=PUBLIC,
            clerk_allowed_origins=ORIGIN,
        )
    )
    engine = app.state.database_engine
    seen: set[int] = set()
    event.listen(engine, "checkout", lambda connection, record, proxy: seen.add(id(connection)))

    async def journey() -> None:
        async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
            for subject, item in [(a, first), (b, second), (a, first), (b, second)]:
                r = await client.get(
                    f"/api/v1/organizations/{item['id']}",
                    headers={"Authorization": "Bearer " + token(subject)},
                )
                assert r.status_code == 200
                assert r.json()["id"] == item["id"]

    try:
        asyncio.run(journey())
        with engine.connect() as connection:
            assert (
                connection.scalar(
                    text("SELECT NULLIF(current_setting('app.organization_id',true),'')")
                )
                is None
            )
            assert (
                connection.scalar(
                    text("SELECT NULLIF(current_setting('app.external_auth_id',true),'')")
                )
                is None
            )
        assert len(seen) == 1
    finally:
        engine.dispose()


def test_client_claims_do_not_grant_organization_access(db: tuple[Engine, Engine]) -> None:
    a, b = "user_" + uuid4().hex, "user_" + uuid4().hex
    org(db, a)
    target = org(db, b)
    forged_claims = token(a, o={"id": target["id"], "rol": "owner"}, role="OWNER")
    assert call(db, a, f"/api/v1/organizations/{target['id']}", raw=forged_claims)[0] == 403


def test_duplicate_org_atomic_and_no_unauthorized_audit(db: tuple[Engine, Engine]) -> None:
    actor = "user_" + uuid4().hex
    created = org(db, actor)
    assert (
        call(
            db,
            actor,
            "/api/v1/organizations",
            "POST",
            {"name": "Duplicate", "slug": created["slug"]},
        )[0]
        == 409
    )
    with Session(db[0]) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(AuditEvent)
                .where(AuditEvent.organization_id == UUID(created["id"]))
            )
            == 1
        )


def test_definer_functions_are_narrow_and_public_execution_revoked(
    db: tuple[Engine, Engine],
) -> None:
    with db[0].connect() as c:
        rows = c.execute(
            text(
                "SELECT proname,prosecdef,proconfig, r.rolsuper,r.rolcanlogin,r.rolbypassrls, "
                "EXISTS(SELECT 1 FROM aclexplode(coalesce(proacl,acldefault('f',proowner))) "
                "WHERE grantee=0 AND privilege_type='EXECUTE') AS public_exec "
                "FROM pg_proc JOIN pg_roles r ON r.oid=proowner "
                "WHERE proname IN ('orqentra_identity_id',"
                "'orqentra_provision_identity','orqentra_membership_for_org',"
                "'orqentra_my_organizations','orqentra_create_organization','orqentra_accept_invitation')"
            )
        ).all()
        assert len(rows) == 6
        assert all(
            r.prosecdef
            and not r.public_exec
            and not r.rolsuper
            and not r.rolcanlogin
            and r.rolbypassrls
            and "search_path=pg_catalog, public" in r.proconfig
            for r in rows
        )


@pytest.mark.parametrize(
    "raw", ["not.a.jwt", token(iss="https://foreign.invalid"), token(azp="https://foreign.invalid")]
)
def test_http_rejects_invalid_tokens(db: tuple[Engine, Engine], raw: str) -> None:
    assert call(db, "user_fixture", "/api/v1/me", raw=raw)[0] == 401


def test_expired_session_recovers_without_duplicate_user(db: tuple[Engine, Engine]) -> None:
    from time import time

    subject = "user_" + uuid4().hex
    status, first = call(db, subject, "/api/v1/me")
    assert status == 200
    now = int(time())
    expired = token(subject, iat=now - 120, nbf=now - 120, exp=now - 60)
    assert call(db, subject, "/api/v1/me", raw=expired)[0] == 401
    status, recovered = call(db, subject, "/api/v1/me")
    assert status == 200
    assert recovered == first
    with Session(db[0]) as session:
        assert (
            session.scalar(
                select(func.count()).select_from(User).where(User.external_auth_id == subject)
            )
            == 1
        )


@pytest.mark.parametrize("connection_index,expected", [(1, 200), (0, 503)])
def test_readiness_requires_restricted_runtime_role(
    db: tuple[Engine, Engine], connection_index: int, expected: int
) -> None:
    async def probe() -> None:
        app = create_app(
            Settings(
                environment="test",
                database_url=db[connection_index].url.render_as_string(hide_password=False),
                clerk_issuer=ISSUER,
                clerk_jwt_key=PUBLIC,
                clerk_allowed_origins=ORIGIN,
            )
        )
        try:
            async with AsyncClient(transport=ASGITransport(app=app), base_url=ORIGIN) as client:
                response = await client.get("/api/v1/ready")
                assert response.status_code == expected
                assert response.json() == {"status": "ready" if expected == 200 else "not_ready"}
        finally:
            app.state.database_engine.dispose()

    asyncio.run(probe())
