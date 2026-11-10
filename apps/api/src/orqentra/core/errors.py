from fastapi import Request
from fastapi.responses import JSONResponse

from orqentra.api.schemas import ErrorResponse


def error_response(
    request: Request, status: int, code: str, message: str, *, retryable: bool = False
) -> JSONResponse:
    payload = ErrorResponse(
        code=code,
        message=message,
        correlation_id=request.state.correlation_id,
        retryable=retryable,
    )
    return JSONResponse(status_code=status, content=payload.model_dump())
