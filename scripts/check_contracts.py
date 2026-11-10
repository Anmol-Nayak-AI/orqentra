"""Verify generated contracts without modifying source, even on generator failure."""

import subprocess
import sys
import tempfile
from pathlib import Path

root = Path(__file__).resolve().parents[1]
paths = [
    root / "packages/contracts/openapi.json",
    root / "packages/contracts/src/api.d.ts",
]
with tempfile.TemporaryDirectory(prefix="orqentra-contracts-") as directory:
    output = Path(directory)
    subprocess.run(
        [
            "uv",
            "run",
            "--locked",
            "--package",
            "orqentra-api",
            "python",
            "scripts/export_openapi.py",
            "--output",
            str(output / "openapi.json"),
        ],
        cwd=root,
        check=True,
    )
    subprocess.run(
        [
            "npm",
            "exec",
            "--",
            "openapi-typescript",
            str(output / "openapi.json"),
            "-o",
            str(output / "api.d.ts"),
        ],
        cwd=root,
        check=True,
    )
    generated = [output / "openapi.json", output / "api.d.ts"]
    changed = [
        str(path.relative_to(root))
        for path, candidate in zip(paths, generated, strict=True)
        if not path.exists() or path.read_bytes() != candidate.read_bytes()
    ]
if changed:
    sys.exit(
        "Contract drift: run make contracts, review and commit: " + ", ".join(changed)
    )
print("OpenAPI and TypeScript contracts match source; source files unchanged.")
