"""Local CLI support only: explicitly requested Compose credentials, never API defaults."""

from pathlib import Path

from dotenv import dotenv_values
from sqlalchemy import URL

ROOT = Path(__file__).resolve().parents[1]


def local_admin_url(database: str | None = None) -> URL:
    values = dotenv_values(ROOT / ".env")
    required = ("POSTGRES_USER", "POSTGRES_DB", "POSTGRES_PASSWORD")
    if not all(values.get(k) for k in required):
        raise RuntimeError("Local .env is incomplete; run make setup first.")
    return URL.create(
        "postgresql+psycopg",
        username=values["POSTGRES_USER"],
        password=values["POSTGRES_PASSWORD"],
        host="127.0.0.1",
        port=int(values.get("POSTGRES_PORT") or "5432"),
        database=database or values["POSTGRES_DB"],
    )
