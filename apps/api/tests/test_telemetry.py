import httpx
import pytest
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from pydantic import ValidationError

import orqentra.main as main
from orqentra.core.config import Settings
from orqentra.core.telemetry import CollectorSession, provider


@pytest.mark.anyio
async def test_exported_spans_exclude_payloads_headers_query_and_exception_text(monkeypatch):
    exporter = InMemorySpanExporter()
    tracer = TracerProvider(resource=Resource({"service.name": "test"}), shutdown_on_exit=False)
    tracer.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(main, "provider", lambda _: tracer)
    app = main.create_app(Settings(environment="test"))

    @app.post("/private/{identifier}")
    async def failure(identifier: str):
        raise RuntimeError("private exception token NEVER_EXPORT")

    incoming = "00-" + "a" * 32 + "-" + "b" * 16 + "-01"
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.post(
                "/private/NEVER_EXPORT?password=NEVER_EXPORT",
                content="prompt NEVER_EXPORT",
                headers={
                    "authorization": "Bearer NEVER_EXPORT",
                    "baggage": "secret=NEVER_EXPORT",
                    "traceparent": incoming,
                },
            )
        assert response.status_code == 500
        spans = exporter.get_finished_spans()
        assert len(spans) == 1
        span = spans[0]
        assert span.parent.span_id == int("b" * 16, 16)
        assert span.context.trace_id == int("a" * 32, 16)
        assert span.status.is_ok is False
        assert not span.events
        assert dict(span.attributes) == {
            "http.request.method": "POST",
            "http.route": "/private/{identifier}",
            "http.response.status_code": 500,
        }
        assert "NEVER_EXPORT" not in str(span.to_json())
    finally:
        tracer.shutdown()


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://collector/v1/traces",
        "https://user:secret@collector/v1/traces",
        "https://collector/v1/traces?token=secret",
        "https://collector/wrong",
    ],
)
def test_collector_rejects_insecure_or_secret_bearing_endpoint(endpoint):
    with pytest.raises(ValidationError):
        Settings(tracing_endpoint=endpoint)


def test_default_tracing_opens_no_exporter_or_network(monkeypatch):
    import orqentra.core.telemetry as module

    monkeypatch.setattr(module, "OTLPSpanExporter", lambda **_: pytest.fail("Must remain disabled"))
    result = provider(Settings())
    try:
        with result.get_tracer("test").start_as_current_span("disabled") as span:
            assert not span.is_recording()
    finally:
        result.shutdown()
    session = CollectorSession()
    assert session.trust_env is False
    session.close()
