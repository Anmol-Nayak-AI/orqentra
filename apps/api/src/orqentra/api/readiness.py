"""Dependency readiness without publishing credentials or database diagnostics."""

from fastapi import APIRouter, Request, Response
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from orqentra.api.schemas import ReadinessResponse
from orqentra.persistence.models import Base

router = APIRouter()


def database_ready(request: Request) -> bool:
    engine = request.app.state.database_engine
    if engine is None:
        return False
    try:
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL statement_timeout = '1000ms'"))
            safe = connection.scalar(
                text(
                    "SELECT NOT rolsuper AND NOT rolbypassrls "
                    "FROM pg_roles WHERE rolname=current_user"
                )
            )
            if not safe:
                return False
            scoped = connection.scalar(
                text(
                    "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE n.nspname='public' AND c.relname=ANY(:tables) "
                    "AND c.relrowsecurity AND c.relforcerowsecurity "
                    "AND c.relowner<>(SELECT oid FROM pg_roles WHERE rolname=current_user)"
                ),
                {"tables": list(Base.metadata.tables)},
            )
            functions = connection.scalar(
                text(
                    "SELECT count(*) FROM pg_proc WHERE pronamespace='public'::regnamespace "
                    "AND proname=ANY(:functions) AND prosecdef "
                    "AND has_function_privilege(current_user,oid,'EXECUTE')"
                ),
                {
                    "functions": [
                        "orqentra_identity_id",
                        "orqentra_provision_identity",
                        "orqentra_my_organizations",
                        "orqentra_membership_for_org",
                        "orqentra_create_organization",
                        "orqentra_accept_invitation",
                    ]
                },
            )
            return bool(scoped == len(Base.metadata.tables) and functions == 6)
    except SQLAlchemyError:
        return False


@router.get(
    "/ready",
    response_model=ReadinessResponse,
    responses={503: {"model": ReadinessResponse}},
    tags=["system"],
)
def ready(request: Request, response: Response) -> ReadinessResponse:
    """Local configuration and restricted-database readiness; no external Clerk request."""
    if not request.app.state.settings.auth_configured or not database_ready(request):
        response.status_code = 503
        return ReadinessResponse(status="not_ready")
    return ReadinessResponse(status="ready")
