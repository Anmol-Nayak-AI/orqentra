"""Run via `uv run --package orqentra-api python scripts/export_openapi.py`."""

import argparse
import json
import os
import tempfile
from pathlib import Path

from orqentra.core.config import Settings
from orqentra.main import create_app

root = Path(__file__).resolve().parents[1]
parser = argparse.ArgumentParser()
parser.add_argument(
    "--output", type=Path, default=root / "packages/contracts/openapi.json"
)
target = parser.parse_args().output.resolve()
spec = create_app(Settings(environment="test")).openapi()
# A full disk must not truncate an existing generated contract.
with tempfile.NamedTemporaryFile(mode="w", dir=target.parent, delete=False) as handle:
    temporary = Path(handle.name)
    try:
        handle.write(json.dumps(spec, indent=2, sort_keys=True) + "\n")
        handle.flush()
        os.fsync(handle.fileno())
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
try:
    os.replace(temporary, target)
finally:
    temporary.unlink(missing_ok=True)
print(f"Exported OpenAPI to {target.name}")
