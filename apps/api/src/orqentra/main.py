import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from time import perf_counter
from uuid import UUID, uuid4

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from opentelemetry.trace import SpanKind, StatusCode
from starlette.exceptions import HTTPException
from starlette.middleware.trustedhost import TrustedHostMiddleware

from orqentra.agents.routes import router as agent_router
from orqentra.api.health import router
from orqentra.api.readiness import router as readiness_router
from orqentra.api.schemas import ErrorResponse
from orqentra.billing.lifecycle import router as billing_lifecycle_router
from orqentra.billing.routes import router as billing_router
from orqentra.billing.webhooks import router as billing_webhook_router
from orqentra.core.config import Settings
from orqentra.core.errors import error_response
from orqentra.core.logging import configure_logging
from orqentra.core.request_limits import RequestBodyLimitMiddleware
from orqentra.core.telemetry import propagator, provider
from orqentra.execution.routes import router as execution_router
from orqentra.organizations.administration import router as administration_router
from orqentra.organizations.invitations import router as invitation_router
from orqentra.organizations.routes import router as organization_router
from orqentra.organizations.workspaces import router as workspace_router
from orqentra.persistence.errors import (
    DuplicateRecord,
    ForbiddenOperation,
    IntegrityViolation,
    PersistenceError,
    RecordNotFound,
    StaleRevision,
)
from orqentra.persistence.session import database_engine
from orqentra.rag.routes import router as rag_router
from orqentra.sandbox.routes import router as sandbox_router

logger = logging.getLogger("orqentra")


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    configure_logging()
    telemetry = provider(config)
    tracer = telemetry.get_tracer("orqentra.http")

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            telemetry.shutdown()
            engine = app.state.database_engine
            if engine is not None:
                engine.dispose()

    application = FastAPI(
        title="Orqentra API",
        lifespan=lifespan,
        version="0.1.0",
        description="Clerk-verified identity and organization APIs; health remains public.",
        docs_url=None if config.environment in {"staging", "production"} else "/api/docs",
        redoc_url=None,
        openapi_url=None
        if config.environment in {"staging", "production"}
        else "/api/openapi.json",
        responses={
            413: {"model": ErrorResponse},
            404: {"model": ErrorResponse},
            422: {"model": ErrorResponse},
            500: {"model": ErrorResponse},
        },
    )

    if config.environment in {"staging", "production"}:
        application.add_middleware(TrustedHostMiddleware, allowed_hosts=config.trusted_hosts)

    @application.middleware("http")
    async def request_context(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = perf_counter()
        parent = request.headers.get("traceparent", "")
        # No baggage, tracestate, arbitrary headers or query values are propagated.
        context = propagator.extract({"traceparent": parent if len(parent) == 55 else ""})
        with tracer.start_as_current_span(
            "http.request",
            context=context,
            kind=SpanKind.SERVER,
            record_exception=False,
            set_status_on_exception=False,
        ) as span:
            span_context = span.get_span_context()
            trace_id = format(span_context.trace_id, "032x")
            span_id = format(span_context.span_id, "016x")
            request.state.trace_id = trace_id
            supplied = request.headers.get("x-request-id", "")
            try:
                correlation_id = str(UUID(supplied)) if len(supplied) <= 36 else str(uuid4())
            except ValueError:
                correlation_id = str(uuid4())
            request.state.correlation_id = correlation_id
            try:
                response = await call_next(request)
            except Exception as exc:
                logger.error(
                    "request.failed",
                    extra={"correlation_id": correlation_id, "error_type": type(exc).__name__},
                )
                response = error_response(
                    request, 500, "internal_error", "An unexpected error occurred.", retryable=True
                )
            response.headers["X-Request-ID"] = correlation_id
            response.headers["traceparent"] = (
                f"00-{trace_id}-{span_id}-{int(span_context.trace_flags):02x}"
            )
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Cache-Control"] = "no-store"
            route = request.scope.get("route")
            logger.info(
                "request.completed",
                extra={
                    "correlation_id": correlation_id,
                    "status_code": response.status_code,
                    "method": request.method,
                    "route": getattr(route, "name", "unmatched"),
                    "trace_id": trace_id,
                    "span_id": span_id,
                    "duration_ms": round((perf_counter() - started) * 1000, 3),
                },
            )
            # Only fixed route metadata; never exception strings or dynamic request paths.
            span.set_attribute(
                "http.request.method",
                request.method
                if request.method in {"GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"}
                else "OTHER",
            )
            span.set_attribute("http.route", getattr(route, "path", "unmatched"))
            span.set_attribute("http.response.status_code", response.status_code)
            if response.status_code >= 500:
                span.set_status(StatusCode.ERROR)
            return response

    @application.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        # Avoid reflecting arbitrary exception detail (which could contain sensitive input).
        response = error_response(
            request, exc.status_code, "http_error", "Request could not be completed."
        )
        if exc.headers:
            response.headers.update(exc.headers)
        return response

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return error_response(request, 422, "validation_error", "Request validation failed.")

    @application.exception_handler(PersistenceError)
    async def persistence_error(request: Request, exc: PersistenceError) -> JSONResponse:
        status = 500
        if isinstance(exc, (DuplicateRecord, StaleRevision)):
            status = 409
        elif isinstance(exc, IntegrityViolation):
            status = 422
        elif isinstance(exc, ForbiddenOperation):
            status = 403
        elif isinstance(exc, RecordNotFound):
            status = 404
        return error_response(
            request, status, "persistence_error", "Request could not be completed."
        )

    application.add_middleware(RequestBodyLimitMiddleware, max_bytes=config.max_request_bytes)

    application.state.telemetry = telemetry
    application.state.settings = config
    application.state.database_engine = (
        database_engine(config.database_url.get_secret_value()) if config.database_url else None
    )
    application.include_router(rag_router)
    application.include_router(sandbox_router)
    application.include_router(workspace_router)
    application.include_router(invitation_router)
    application.include_router(execution_router)
    application.include_router(agent_router)
    application.include_router(organization_router)
    application.include_router(administration_router)
    application.include_router(billing_router)
    application.include_router(billing_lifecycle_router)
    application.include_router(billing_webhook_router)
    application.include_router(router, prefix="/api/v1")
    application.include_router(readiness_router, prefix="/api/v1")
    return application


app = create_app()
