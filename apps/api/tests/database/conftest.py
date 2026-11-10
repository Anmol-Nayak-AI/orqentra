import os
from collections.abc import Iterator
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from psycopg import sql
from sqlalchemy import Engine, create_engine, text

from alembic import command
from orqentra.persistence.roles import grant_runtime, provision_identity_owner
from orqentra.persistence.session import database_engine


@pytest.fixture(scope="session")
def databases() -> Iterator[tuple[Engine, Engine, Config]]:
    url = os.environ.get("ORQENTRA_TEST_ADMIN_URL")
    if not url:
        pytest.skip("Use make test-db: integration tests require an isolated test database.")
    admin = create_engine(url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    token = uuid4().hex
    database = "orqentra_test_" + token
    role = "orqentra_test_" + token
    identity_owner = "orqentra_definer_" + token
    password = uuid4().hex
    with admin.connect() as c:
        # Generated identifiers, never user-selected database destruction targets.
        c.exec_driver_sql(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)).as_string()
        )
        c.exec_driver_sql(
            sql.SQL(
                "CREATE ROLE {} LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS PASSWORD {}"
            )
            .format(sql.Identifier(role), sql.Literal(password))
            .as_string()
        )
    from sqlalchemy.engine import make_url

    db_url = make_url(url).set(database=database)
    owner = database_engine(db_url.render_as_string(hide_password=False))
    runtime = database_engine(
        db_url.set(username=role, password=password).render_as_string(hide_password=False)
    )
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    try:
        with owner.begin() as c:
            config.attributes["connection"] = c
            command.upgrade(config, "head")
            provision_identity_owner(c, identity_owner)
            grant_runtime(c, role)
        yield owner, runtime, config
    finally:
        owner.dispose()
        runtime.dispose()
        # Refuse arbitrary names, and operate only on this fixture's generated database.
        assert database == "orqentra_test_" + token
        with admin.connect() as c:
            c.exec_driver_sql(
                sql.SQL("DROP DATABASE {} WITH (FORCE)")
                .format(sql.Identifier(database))
                .as_string()
            )
            c.exec_driver_sql(sql.SQL("DROP ROLE {}").format(sql.Identifier(role)).as_string())
            if c.scalar(
                text("SELECT 1 FROM pg_roles WHERE rolname=:role"),
                {"role": identity_owner},
            ):
                c.exec_driver_sql(
                    sql.SQL("DROP ROLE {}").format(sql.Identifier(identity_owner)).as_string()
                )
        admin.dispose()


@pytest.fixture
def db(databases: tuple[Engine, Engine, Config]) -> tuple[Engine, Engine]:
    return databases[0], databases[1]


@pytest.fixture(autouse=True)
def synthetic_embeddings(monkeypatch: pytest.MonkeyPatch) -> None:
    # Explicit test adapter only; never registered in application configuration or HTTP routes.
    if os.environ.get("ORQENTRA_LIVE_MODEL_TEST") == "1":
        return

    def vectors(key: str, texts: list[str]) -> list[list[float]]:
        return [[1.0] + [0.0] * 1535 for _ in texts]

    monkeypatch.setattr("orqentra.rag.service.embed", vectors)
