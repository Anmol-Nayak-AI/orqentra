"""Forward-only local migration runner, with preflight and private backup."""

import argparse
import json
import os
import subprocess
from datetime import UTC, datetime

from alembic import command
from alembic.config import Config
from database_support import ROOT, local_admin_url
from orqentra.persistence.models import Base
from sqlalchemy import create_engine, inspect, text

parser = argparse.ArgumentParser()
parser.add_argument("action", choices=["upgrade", "current", "check"])
parser.add_argument("--local", action="store_true", required=True)
args = parser.parse_args()
engine = create_engine(local_admin_url(), hide_parameters=True)
config = Config(str(ROOT / "apps/api/alembic.ini"))
try:
    with engine.connect() as connection:
        tables = inspect(connection).get_table_names()
        collisions = set(tables) & set(Base.metadata.tables)
        if "alembic_version" not in tables and collisions:
            raise RuntimeError(
                "Unversioned domain tables exist; review before any migration."
            )
        if args.action == "upgrade":
            # Snapshot all existing public tables before forward-only mutation.
            counts = {
                t: connection.execute(
                    text(
                        "SELECT count(*) FROM "
                        + connection.dialect.identifier_preparer.quote(t)
                    )
                ).scalar_one()
                for t in tables
                if t != "alembic_version"
            }
            backup_dir = ROOT / ".local/backups"
            backup_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
            target = backup_dir / (
                datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ") + ".dump"
            )
            fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as handle:
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
                        'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc',
                    ],
                    cwd=ROOT,
                    stdout=handle,
                    check=True,
                )
            print("Private pre-migration backup:", target.relative_to(ROOT))
            # End inspection transaction; Alembic controls the migration transaction.
            connection.commit()
            config.attributes["connection"] = connection
            command.upgrade(config, "head")
            connection.commit()
            for table, count in counts.items():
                assert (
                    connection.execute(
                        text(
                            "SELECT count(*) FROM "
                            + connection.dialect.identifier_preparer.quote(table)
                        )
                    ).scalar_one()
                    == count
                )
            print("Preexisting table row counts preserved:", json.dumps(counts))
        else:
            config.attributes["connection"] = connection
            if args.action == "current":
                command.current(config, check_heads=True)
            else:
                command.check(config)
finally:
    engine.dispose()
