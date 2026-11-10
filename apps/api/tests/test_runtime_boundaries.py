from collections.abc import AsyncIterator
from uuid import UUID

import pytest
from auth_helpers import ISSUER, PUBLIC
from fastapi import Request
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from orqentra.core.config import Settings
from orqentra.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_body_boundary_handles_exact_limit_and_chunked_overflow() -> None:
    app = create_app(Settings(environment="test", max_request_bytes=1024))

    @app.post("/body-size")
    async def size(request: Request) -> dict[str, int]:
        return {"size": len(await request.body())}

    async def chunks() -> AsyncIterator[bytes]:
        yield b"a" * 512
        yield b"b" * 513

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        exact = await client.post("/body-size", content=b"a" * 1024)
        assert exact.status_code == 200
        assert exact.json() == {"size": 1024}
        oversized = await client.post("/body-size", content=chunks())
        assert oversized.status_code == 413
        assert oversized.json()["code"] == "request_too_large"
        assert UUID(oversized.headers["x-request-id"])
        assert oversized.headers["cache-control"] == "no-store"


@pytest.mark.anyio
async def test_oversize_header_rejected_without_consuming_body() -> None:
    consumed = False

    async def body() -> AsyncIterator[bytes]:
        nonlocal consumed
        consumed = True
        yield b"canary-never-read"

    async with AsyncClient(
        transport=ASGITransport(
            app=create_app(Settings(environment="test", max_request_bytes=1024))
        ),
        base_url="http://test",
    ) as client:
        result = await client.post(
            "/api/v1/organizations", content=body(), headers={"Content-Length": "2048"}
        )
    assert result.status_code == 413
    assert not consumed
    assert "canary-never-read" not in result.text


@pytest.mark.anyio
async def test_small_declared_size_cannot_bypass_actual_body_limit() -> None:
    async with AsyncClient(
        transport=ASGITransport(
            app=create_app(Settings(environment="test", max_request_bytes=1024))
        ),
        base_url="http://test",
    ) as client:
        result = await client.post(
            "/api/v1/organizations", content=b"x" * 1025, headers={"Content-Length": "1"}
        )
    assert result.status_code == 413


@pytest.mark.anyio
async def test_missing_auth_and_database_are_not_ready_but_liveness_survives() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app(Settings(environment="test"))),
        base_url="http://test",
    ) as client:
        result = await client.get("/api/v1/ready")
        assert result.status_code == 503
        assert result.json() == {"status": "not_ready"}
        assert (await client.get("/api/v1/health")).status_code == 200


def production(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": "production",
        "allowed_hosts": "api.example.invalid",
        "clerk_issuer": ISSUER,
        "clerk_jwt_key": PUBLIC,
        "clerk_allowed_origins": "https://app.example.invalid",
        "database_url": "postgresql+psycopg://runtime:test@db.example.invalid/test?sslmode=verify-full",
    }
    values.update(overrides)
    return Settings(**values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"database_url": None},
        {"clerk_allowed_origins": "http://localhost:8080"},
        {"migration_database_url": "postgresql+psycopg://owner:test@localhost/test"},
    ],
)
def test_production_rejects_unsafe_configuration(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        production(**overrides)


def test_production_requires_authentication_configuration() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="production")


@pytest.mark.parametrize(
    "overrides",
    [
        {"allowed_hosts": "*"},
        {"allowed_hosts": ""},
        {"clerk_issuer": "https://development.clerk.accounts.dev"},
        {"clerk_allowed_origins": "https://localhost"},
        {"clerk_allowed_origins": "https://127.0.0.1"},
        {"clerk_max_token_lifetime": 3600},
        {
            "database_url": "postgresql+psycopg://runtime:synthetic@db.example.invalid/app?sslmode=require"
        },
    ],
)
def test_production_release_boundaries(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        production(**overrides)


@pytest.mark.anyio
async def test_production_rejects_untrusted_host_header() -> None:
    app = create_app(production())
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="https://api.example.invalid"
        ) as client:
            assert (await client.get("/api/v1/health")).status_code == 200
            assert (
                await client.get("/api/v1/health", headers={"Host": "attacker.example.invalid"})
            ).status_code == 400
    finally:
        app.state.database_engine.dispose()


def test_staging_allows_separate_development_identity_but_requires_hosted_security() -> None:
    assert (
        production(
            environment="staging", clerk_issuer="https://stage.clerk.accounts.dev"
        ).environment
        == "staging"
    )
    with pytest.raises(ValidationError):
        production(environment="staging", allowed_hosts="*")


@pytest.mark.anyio
async def test_trace_correlation_is_bounded_and_uses_a_new_server_span() -> None:
    app = create_app(Settings(environment="test"))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        incoming = "00-" + "a" * 32 + "-" + "b" * 16 + "-01"
        response = await client.get("/api/v1/health", headers={"traceparent": incoming})
        parts = response.headers["traceparent"].split("-")
        assert parts[1] == "a" * 32 and parts[2] != "b" * 16
        malformed = await client.get(
            "/api/v1/health", headers={"traceparent": "invalid-unbounded-value"}
        )
        assert len(malformed.headers["traceparent"]) == 55
