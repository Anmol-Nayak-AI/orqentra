"""Explicit, forward-only hosted database job. Never loaded by the API or worker."""

import argparse
import os
import re
from pathlib import Path

from alembic import command
from alembic.config import Config
from orqentra.persistence.models import Base
from orqentra.persistence.roles import grant_runtime, provision_identity_owner
from sqlalchemy import URL, Connection, create_engine, inspect, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[1]


def validate_target(value: str, hostname: str, database: str) -> URL:
    url = make_url(value)
    if (
        url.drivername != "postgresql+psycopg"
        or not hostname
        or not re.fullmatch(r"[a-zA-Z0-9.-]+", hostname)
        or hostname in {"localhost", "postgres", "127.0.0.1", "::1"}
        or url.host != hostname
        or url.database != database
        or not database
        or not url.username
        or not url.password
        or url.query.get("sslmode") != "verify-full"
        or set(url.query) - {"sslmode", "sslrootcert"}
    ):
        raise ValueError(
            "Hosted target must match the explicit host/database and verified TLS."
        )
    return url


def verify_runtime_role(connection: Connection, role: str) -> None:
    unsafe = connection.execute(
        text(
            "SELECT rolsuper OR rolbypassrls OR rolcreatedb OR rolcreaterole OR rolreplication "
            "OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member = r.oid) "
            "FROM pg_roles r WHERE rolname = :role"
        ),
        {"role": role},
    ).scalar_one()
    if unsafe:
        raise RuntimeError("Runtime role has unsafe privileges or inherited roles.")


def verify_runtime(connection: Connection) -> None:
    # Kept separate from migration credentials: the API only gets this restricted login.
    role = connection.scalar(text("SELECT current_user"))
    assert isinstance(role, str)
    verify_runtime_role(connection, role)
    if connection.scalar(
        text("SELECT has_schema_privilege(current_user, 'public', 'CREATE')")
    ):
        raise RuntimeError("Runtime role must not create objects in public schema.")
    for table in Base.metadata.tables:
        row = connection.execute(
            text(
                "SELECT c.relrowsecurity, c.relforcerowsecurity, "
                "pg_get_userbyid(c.relowner) = current_user, "
                "has_table_privilege(current_user, c.oid, 'SELECT'), "
                "has_table_privilege(current_user, c.oid, 'DELETE,TRUNCATE') "
                "FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace "
                "WHERE n.nspname='public' AND c.relname=:table"
            ),
            {"table": table},
        ).one()
        if not row[0] or not row[1] or row[2] or not row[3] or row[4]:
            raise RuntimeError(
                "Runtime grants, table ownership or forced RLS are unsafe."
            )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["validate", "check", "upgrade"])
    parser.add_argument(
        "--environment", choices=["staging", "production"], required=True
    )
    parser.add_argument("--host", required=True)
    parser.add_argument("--database", required=True)
    parser.add_argument("--backup-reference")
    args = parser.parse_args()
    owner = validate_target(
        os.environ.get("ORQENTRA_MIGRATION_DATABASE_URL", ""), args.host, args.database
    )
    runtime = validate_target(
        os.environ.get("ORQENTRA_DATABASE_URL", ""), args.host, args.database
    )
    if owner.username == runtime.username or runtime.username != "orqentra_runtime":
        raise ValueError(
            "Separate migration owner and orqentra_runtime credentials are required."
        )
    if args.action == "validate":
        print(
            "Hosted job configuration validated offline; no connection or migration performed."
        )
        return 0
    if args.action == "upgrade" and (
        not args.backup_reference
        or not re.fullmatch(r"[A-Za-z0-9._:/-]{3,240}", args.backup_reference)
    ):
        raise ValueError(
            "A provider backup reference is required before forward migration."
        )
    # A reference is an operator assertion, never proof of restore success.
    engine = create_engine(
        owner, hide_parameters=True, connect_args={"connect_timeout": 10}
    )
    try:
        with engine.connect() as connection:
            connection.exec_driver_sql("SET statement_timeout = '120s'")
            connection.exec_driver_sql("SET lock_timeout = '10s'")
            connection.commit()
            locked = connection.scalar(
                text("SELECT pg_try_advisory_lock(172913, 2201)")
            )
            if not locked:
                raise RuntimeError("Another database maintenance job holds the lock.")
            connection.commit()
            config = Config(str(ROOT / "apps/api/alembic.ini"))
            config.attributes["connection"] = connection
            # Reject an absent/privileged/inherited login before any migration or grant mutation.
            verify_runtime_role(connection, "orqentra_runtime")
            connection.commit()
            if args.action == "upgrade":
                tables = inspect(connection).get_table_names()
                if "alembic_version" not in tables and set(tables) & set(
                    Base.metadata.tables
                ):
                    raise RuntimeError(
                        "Refusing to adopt unversioned application tables."
                    )
                connection.commit()
                command.upgrade(config, "head")
                connection.commit()
                # The hosting operator creates the login beforehand; never rotate its password.
                with connection.begin():
                    exists = connection.scalar(
                        text(
                            "SELECT EXISTS(SELECT 1 FROM pg_roles WHERE rolname='orqentra_runtime')"
                        )
                    )
                    if not exists:
                        raise RuntimeError(
                            "Create the restricted runtime login before provisioning."
                        )
                    provision_identity_owner(connection, "orqentra_identity_owner")
                    grant_runtime(connection, "orqentra_runtime")
            command.current(config, check_heads=True)
            command.check(config)
    finally:
        engine.dispose()
    runtime_engine = create_engine(
        runtime, hide_parameters=True, connect_args={"connect_timeout": 10}
    )
    try:
        with runtime_engine.connect() as connection:
            verify_runtime(connection)
    finally:
        runtime_engine.dispose()
    print("Hosted schema head, drift, runtime grants and forced RLS verified.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:  # noqa: BLE001 -- CLI boundary must redact every driver/config failure.
        # Driver errors can embed DSNs, passwords, SQL and parameters: do not print them.
        print(
            "Hosted database job failed; check target, backup, schema and restricted role privately."
        )
        raise SystemExit(1) from None
