"""Restore a selected private dump into a generated disposable database, never the app DB."""

import argparse
import json
import subprocess
from uuid import uuid4

from database_support import ROOT, local_admin_url
from psycopg import sql
from sqlalchemy import create_engine, inspect, text

parser = argparse.ArgumentParser()
parser.add_argument("backup")
args = parser.parse_args()
backup = (ROOT / args.backup).resolve()
if (
    not backup.is_relative_to((ROOT / ".local/backups").resolve())
    or backup.suffix != ".dump"
):
    raise SystemExit("Select a dump inside the private local backup directory.")
target = "orqentra_restore_" + uuid4().hex
admin = create_engine(
    local_admin_url("postgres"), isolation_level="AUTOCOMMIT", hide_parameters=True
)
try:
    with admin.connect() as connection:
        connection.exec_driver_sql(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(target)).as_string()
        )
    with backup.open("rb") as handle:
        subprocess.run(
            [
                "docker",
                "compose",
                "--env-file",
                ".env",
                "-f",
                "infrastructure/compose.yaml",
                "exec",
                "-T",
                "postgres",
                "sh",
                "-c",
                'pg_restore -U "$POSTGRES_USER" --no-owner --no-privileges -d "$1"',
                "sh",
                target,
            ],
            stdin=handle,
            check=True,
            cwd=ROOT,
            capture_output=True,
        )
    restored = create_engine(local_admin_url(target), hide_parameters=True)
    try:
        with restored.connect() as connection:
            names = inspect(connection).get_table_names()
            counts = {
                name: connection.scalar(
                    text("SELECT count(*) FROM " + sql.Identifier(name).as_string())
                )
                for name in names
                if name != "alembic_version"
            }
            version = connection.scalar(text("SELECT version_num FROM alembic_version"))
            rls = connection.scalar(
                text(
                    "SELECT count(*) FROM pg_class WHERE relnamespace='public'::regnamespace AND relrowsecurity AND relforcerowsecurity"
                )
            )
            assert (
                counts.get("users") is not None
                and counts.get("organizations") is not None
            )
            assert rls == len(counts)
            print(
                json.dumps(
                    {
                        "restore_verified": True,
                        "schema_version": version,
                        "row_counts": counts,
                        "forced_rls_tables": rls,
                    }
                )
            )
    finally:
        restored.dispose()
finally:
    assert target.startswith("orqentra_restore_") and len(target) == 49
    with admin.connect() as connection:
        connection.exec_driver_sql(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)")
            .format(sql.Identifier(target))
            .as_string()
        )
    admin.dispose()
