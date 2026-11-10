"""Offline syntax/policy checks only; never invokes a cloud provider."""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
for environment in ("staging", "production"):
    path = ROOT / "infrastructure" / "render" / f"{environment}.yaml"
    document = yaml.safe_load(path.read_text())
    services = document["services"]
    assert len(services) == 3
    by_name = {service["name"]: service for service in services}
    prefix = f"orqentra-{environment}"
    assert by_name[f"{prefix}-api"]["type"] == "pserv"
    assert by_name[f"{prefix}-worker"]["type"] == "worker"
    assert by_name[f"{prefix}-web"]["type"] == "web"
    for service in services:
        assert service["runtime"] == "docker"
        assert service["autoDeployTrigger"] == "off"
        assert (ROOT / service["dockerfilePath"]).is_file()
        assert not service.get("preDeployCommand"), (
            "Migrations must be a separate reviewed job"
        )
    keys = {
        row.get("key") for group in document["envVarGroups"] for row in group["envVars"]
    }
    assert "ORQENTRA_MIGRATION_DATABASE_URL" not in keys
    assert "RAZORPAY_KEY_SECRET" not in keys and "E2B_API_KEY" not in keys
    assert not document.get("databases"), "Database creation requires separate approval"
    print(
        f"{environment}: syntax and local policy valid; cloud validation/deployment NOT performed"
    )

maintenance = yaml.safe_load(
    (ROOT / ".github/workflows/database-maintenance.yml").read_text()
)
# YAML 1.1 parses the GitHub 'on' key as True; accept either parser representation.
triggers = maintenance.get("on", maintenance.get(True))
assert set(triggers) == {"workflow_dispatch"}
assert maintenance["permissions"] == {"contents": "read"}
assert maintenance["concurrency"]["cancel-in-progress"] is False
assert maintenance["jobs"]["database"]["environment"].endswith("-database-maintenance")
steps = maintenance["jobs"]["database"]["steps"]
commands = [step["run"] for step in steps if "run" in step]
assert "hosted_database.py validate" in commands[-2]
assert "hosted_database.py" in commands[-1]
assert all("render deploy" not in command for command in commands)
print("Hosted maintenance: manual-only workflow policy valid; job NOT triggered")
