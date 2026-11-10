"""Create a local restricted role without exposing passwords in CLI output."""

import os
import secrets

from database_support import ROOT, local_admin_url
from dotenv import dotenv_values
from orqentra.persistence.roles import grant_runtime, provision_identity_owner
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

path = ROOT / ".env.runtime"
values = dotenv_values(path) if path.exists() else {}
password = values.get("ORQENTRA_RUNTIME_PASSWORD") or secrets.token_hex(24)
engine = create_engine(local_admin_url(), hide_parameters=True)
try:
    with engine.begin() as connection:
        row = connection.execute(
            text(
                "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication "
                "FROM pg_roles WHERE rolname='orqentra_runtime'"
            )
        ).first()
        inherited = connection.scalar(
            text(
                "SELECT EXISTS (SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid=m.member "
                "WHERE r.rolname='orqentra_runtime')"
            )
        )
        if inherited:
            raise RuntimeError(
                "Runtime role has inherited roles; refusing to adopt it."
            )
        if row is not None and any(row):
            raise RuntimeError(
                "Existing runtime role is privileged; refusing to adopt it."
            )
        if row is None:
            connection.exec_driver_sql(
                sql.SQL(
                    "CREATE ROLE orqentra_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE "
                    "NOBYPASSRLS PASSWORD {}"
                )
                .format(sql.Literal(password))
                .as_string()
            )
        elif not path.exists():
            raise RuntimeError(
                "Existing runtime role has no local credentials; refusing rotation."
            )
        provision_identity_owner(connection, "orqentra_identity_owner")
        grant_runtime(connection, "orqentra_runtime")
    if not path.exists():
        container_url = local_admin_url().set(
            username="orqentra_runtime", password=password, host="postgres", port=5432
        )
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as handle:
            handle.write("# LOCAL runtime credentials; never commit.\n")
            handle.write("ORQENTRA_RUNTIME_PASSWORD=" + password + "\n")
            handle.write(
                "ORQENTRA_DATABASE_URL="
                + container_url.render_as_string(hide_password=False)
                + "\n"
            )
    print("Restricted runtime role provisioned; existing credentials preserved.")
except (SQLAlchemyError, OSError, RuntimeError):
    raise RuntimeError(
        "Runtime provisioning failed; inspect role privileges/credential state."
    ) from None
finally:
    engine.dispose()
