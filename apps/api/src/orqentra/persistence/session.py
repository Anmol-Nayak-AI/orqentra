from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from orqentra.persistence.errors import translate_database_error


@dataclass(frozen=True)
class TrustedOrganizationContext:
    """Internal service context, to be constructed after authentication in 2C.

    Not an API schema and not proof of membership. No HTTP path accepts this object.
    """

    organization_id: UUID
    actor_user_id: UUID
    correlation_id: UUID


def database_engine(url: str) -> Engine:
    parsed = make_url(url)
    if parsed.drivername != "postgresql+psycopg":
        raise ValueError("A PostgreSQL Psycopg 3 URL is required.")
    return create_engine(
        parsed,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        hide_parameters=True,
        pool_timeout=5,
        connect_args={
            "connect_timeout": 5,
            "options": "-c timezone=UTC -c statement_timeout=15000 -c lock_timeout=5000",
        },
    )


@contextmanager
def transaction(engine: Engine, context: TrustedOrganizationContext) -> Iterator[Session]:
    """Single explicit commit boundary; context disappears on commit/rollback."""
    try:
        with Session(engine, expire_on_commit=False) as session, session.begin():
            session.execute(
                text("SELECT set_config('app.organization_id', :id, true)"),
                {"id": str(context.organization_id)},
            )
            yield session
    except DBAPIError as exc:
        # Rollback already occurred; do not retain sensitive driver error as a cause.
        raise translate_database_error(exc) from None
