import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "hosted_database", Path(__file__).resolve().parents[3] / "scripts/hosted_database.py"
)
job = importlib.util.module_from_spec(spec)
spec.loader.exec_module(job)


@pytest.mark.parametrize(
    "url",
    [
        "postgresql+psycopg://owner:secret@db.example/org?sslmode=require",
        "postgresql+psycopg://owner:secret@wrong.example/org?sslmode=verify-full",
        "postgresql+psycopg://owner:secret@db.example/wrong?sslmode=verify-full",
        "postgresql+psycopg://owner:secret@db.example/org?sslmode=verify-full&options=unsafe",
    ],
)
def test_hosted_target_is_exact_and_tls_verified(url):
    with pytest.raises(ValueError):
        job.validate_target(url, "db.example", "org")


def test_validate_is_offline_and_hides_credentials(monkeypatch, capsys):
    monkeypatch.setenv(
        "ORQENTRA_MIGRATION_DATABASE_URL",
        "postgresql+psycopg://owner:NEVER_PRINT@db.example/org?sslmode=verify-full",
    )
    monkeypatch.setenv(
        "ORQENTRA_DATABASE_URL",
        "postgresql+psycopg://orqentra_runtime:NEVER_PRINT@db.example/org?sslmode=verify-full",
    )
    monkeypatch.setattr(
        "sys.argv",
        [
            "hosted_database.py",
            "validate",
            "--environment",
            "staging",
            "--host",
            "db.example",
            "--database",
            "org",
        ],
    )
    monkeypatch.setattr(job, "create_engine", lambda *a, **kw: pytest.fail("No connection allowed"))
    assert job.main() == 0
    assert "NEVER_PRINT" not in capsys.readouterr().out
