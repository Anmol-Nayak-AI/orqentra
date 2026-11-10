from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ok"] = "ok"
    service: Literal["orqentra-api"] = "orqentra-api"
    checkpoint: Literal["2A"] = "2A"


class ErrorResponse(BaseModel):
    code: str
    message: str
    correlation_id: str
    retryable: bool = False


class ReadinessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["ready", "not_ready"]
