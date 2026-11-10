"""Opt-in manual spans. No HTTP/SQL/LLM automatic instrumentation or payload capture."""

from opentelemetry.exporter.otlp.proto.http import Compression
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
from requests import Session
from requests.adapters import HTTPAdapter

from orqentra.core.config import Settings


class CollectorSession(Session):
    def __init__(self) -> None:
        super().__init__()
        self.trust_env = False  # No netrc credentials, environment proxies or ambient auth.
        self.mount("https://", HTTPAdapter(max_retries=0))

    def send(self, request, **kwargs):  # type: ignore[no-untyped-def]
        kwargs["allow_redirects"] = False
        return super().send(request, **kwargs)


def provider(settings: Settings) -> TracerProvider:
    # Explicit resource and sampler: do not import OTEL_RESOURCE_ATTRIBUTES or parent baggage.
    result = TracerProvider(
        resource=Resource(
            {"service.name": "orqentra-api", "deployment.environment": settings.environment}
        ),
        sampler=TraceIdRatioBased(0.1 if settings.tracing_endpoint else 0),
        shutdown_on_exit=False,
    )
    if settings.tracing_endpoint:
        result.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(
                    endpoint=settings.tracing_endpoint,
                    headers={"x-orqentra-telemetry": "1"},
                    timeout=3,
                    compression=Compression.NoCompression,
                    session=CollectorSession(),
                ),
                max_queue_size=256,
                max_export_batch_size=64,
                schedule_delay_millis=2000,
                export_timeout_millis=3000,
            )
        )
    return result


propagator = TraceContextTextMapPropagator()
