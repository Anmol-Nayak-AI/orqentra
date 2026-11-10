"""Bound request bodies before routing, including clients using chunked transfer."""

import logging
from uuid import UUID, uuid4

from fastapi import Request
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from orqentra.core.errors import error_response

logger = logging.getLogger("orqentra")


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request = Request(scope)
        lengths = request.headers.getlist("content-length")
        status = 0
        if lengths:
            if len(lengths) != 1 or not lengths[0].isascii() or not lengths[0].isdigit():
                status = 400
            elif len(lengths[0]) > 10 or int(lengths[0]) > self.max_bytes:
                status = 413
        chunks: list[bytes] = []
        total = 0
        while not status:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunk = message.get("body", b"")
            total += len(chunk)
            if total > self.max_bytes:
                status = 413
                break
            chunks.append(chunk)
            if not message.get("more_body", False):
                break
        if status:
            supplied = request.headers.get("x-request-id", "")
            try:
                correlation = str(UUID(supplied)) if len(supplied) <= 36 else str(uuid4())
            except ValueError:
                correlation = str(uuid4())
            request.state.correlation_id = correlation
            response = error_response(
                request,
                status,
                "request_too_large" if status == 413 else "invalid_request",
                "Request exceeds the permitted size."
                if status == 413
                else "Invalid request framing.",
            )
            response.headers.update(
                {
                    "X-Request-ID": correlation,
                    "Cache-Control": "no-store",
                    "X-Content-Type-Options": "nosniff",
                }
            )
            logger.info(
                "request.rejected", extra={"correlation_id": correlation, "status_code": status}
            )
            await response(scope, receive, send)
            return
        body = b"".join(chunks)
        delivered = False

        async def bounded_receive() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": body, "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
