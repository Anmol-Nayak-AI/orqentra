import os
import subprocess
from pathlib import Path

import pytest


@pytest.mark.parametrize(
    "upstream",
    [
        "https://api.example.invalid:8000",
        "api:8000;echo injected",
        "api:0",
        "api:65536",
        "api",
        "api:8000/path",
    ],
)
def test_web_entrypoint_rejects_invalid_upstreams_before_startup(upstream: str) -> None:
    root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        ["sh", str(root / "infrastructure/start-web.sh")],
        env={**os.environ, "ORQENTRA_API_UPSTREAM": upstream},
        capture_output=True,
        text=True,
        timeout=3,
    )
    assert result.returncode != 0 and "injected" not in result.stdout
