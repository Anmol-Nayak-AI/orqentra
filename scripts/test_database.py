"""Mandatory real-Postgres suite; fixture alone creates/drops random test databases."""

import os
import subprocess
import sys

from database_support import ROOT, local_admin_url

environment = dict(os.environ)
environment["ORQENTRA_TEST_ADMIN_URL"] = local_admin_url("postgres").render_as_string(
    hide_password=False
)
raise SystemExit(
    subprocess.call(
        [
            sys.executable,
            "-m",
            "pytest",
            "-c",
            "apps/api/pyproject.toml",
            "apps/api/tests/database",
            "-ra",
            *sys.argv[1:],
        ],
        cwd=ROOT,
        env=environment,
    )
)
