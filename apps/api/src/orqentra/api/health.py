from fastapi import APIRouter

from orqentra.api.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse, tags=["system"])
def health() -> HealthResponse:
    """Process liveness only; does not claim database or identity readiness."""
    return HealthResponse()
