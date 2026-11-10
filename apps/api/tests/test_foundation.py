import json
import logging
from uuid import UUID, uuid4

import pytest
from auth_helpers import ISSUER, PUBLIC
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError

from orqentra.core.config import Settings
from orqentra.core.logging import JsonFormatter
from orqentra.main import create_app


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
async def test_liveness_contract_and_correlation() -> None:
    supplied = str(uuid4())
    async with AsyncClient(
        transport=ASGITransport(app=create_app(Settings(environment="test"))),
        base_url="http://test",
    ) as client:
        response = await client.get("/api/v1/health", headers={"X-Request-ID": supplied})
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "orqentra-api", "checkpoint": "2A"}
    assert response.headers["x-request-id"] == supplied
    assert response.headers["cache-control"] == "no-store"


@pytest.mark.anyio
async def test_untrusted_request_id_and_error_contract() -> None:
    async with AsyncClient(
        transport=ASGITransport(app=create_app(Settings(environment="test"))),
        base_url="http://test",
    ) as client:
        response = await client.get(
            "/missing?token=do-not-echo", headers={"X-Request-ID": "do-not-echo"}
        )
    assert response.status_code == 404
    body = response.json()
    assert UUID(body["correlation_id"])
    assert body["correlation_id"] == response.headers["x-request-id"]
    assert body["retryable"] is False
    assert "do-not-echo" not in response.text


@pytest.mark.anyio
async def test_unexpected_error_does_not_expose_details() -> None:
    app = create_app(Settings(environment="test"))

    @app.get("/test-crash")
    def crash() -> None:
        raise RuntimeError("secret-canary")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.get("/test-crash")
    assert response.status_code == 500
    assert response.json()["code"] == "internal_error"
    assert response.json()["correlation_id"] == response.headers["x-request-id"]
    assert "secret-canary" not in response.text


@pytest.mark.anyio
async def test_production_disables_interactive_spec_routes() -> None:
    async with AsyncClient(
        transport=ASGITransport(
            app=create_app(
                Settings(
                    environment="production",
                    allowed_hosts="test",
                    clerk_issuer=ISSUER,
                    clerk_jwt_key=PUBLIC,
                    clerk_allowed_origins="https://orqentra.example.invalid",
                    database_url="postgresql+psycopg://runtime:test@db.example.invalid/test?sslmode=verify-full",
                )
            )
        ),
        base_url="http://test",
    ) as client:
        assert (await client.get("/api/docs")).status_code == 404
        assert (await client.get("/api/openapi.json")).status_code == 404
        assert (await client.get("/api/v1/health")).status_code == 200


def test_rejects_unknown_deployment_environment() -> None:
    with pytest.raises(ValidationError):
        Settings(environment="bypass")  # type: ignore[arg-type]


def test_log_allowlist_excludes_sensitive_extra_fields() -> None:
    record = logging.LogRecord("orqentra", logging.INFO, "", 0, "request.completed", (), None)
    record.token = "secret-canary"
    record.correlation_id = str(uuid4())
    rendered = JsonFormatter().format(record)
    assert "secret-canary" not in rendered
    assert json.loads(rendered)["correlation_id"] == record.correlation_id
