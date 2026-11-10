"""Offline production configuration check. Never prints credential values or approves release."""

import argparse
import json
from pathlib import Path

from dotenv import dotenv_values
from orqentra.core.config import Settings
from pydantic import ValidationError

parser = argparse.ArgumentParser()
parser.add_argument("--env-file", action="append", required=True)
parser.add_argument("--frontend-env-file", required=True)
args = parser.parse_args()
raw = {}
for filename in args.env_file:
    if not Path(filename).is_file():
        raise SystemExit("A requested backend configuration file is missing.")
    raw.update(dotenv_values(filename))
if not Path(args.frontend_env_file).is_file():
    raise SystemExit("The requested frontend configuration file is missing.")
values = {}
for name, field in Settings.model_fields.items():
    alias = (
        field.validation_alias
        if isinstance(field.validation_alias, str)
        else "ORQENTRA_" + name.upper()
    )
    values[name] = raw.get(alias, field.default)
backend_ok = False
try:
    config = Settings(**values)
    backend_ok = config.environment == "production"
except ValidationError:
    pass
frontend_key = (
    dotenv_values(args.frontend_env_file).get("VITE_CLERK_PUBLISHABLE_KEY") or ""
)
report = {
    "check": "offline_production_configuration",
    "backend_configuration_valid": backend_ok,
    "frontend_uses_live_publishable_key": frontend_key.startswith("pk_live_"),
    "runtime_database_privileges_verified": False,
    "live_authentication_verified": False,
    "release_approved": False,
    "note": "Offline configuration only. Live authentication, runtime privileges, TLS deployment, backups, integrations and release evidence still require verification.",
}
print(json.dumps(report, indent=2))
if not backend_ok or not report["frontend_uses_live_publishable_key"]:
    raise SystemExit(1)
