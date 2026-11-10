"""Render static preview only. Never provisions paid compute, databases or AI resources."""

import argparse
import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import yaml
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
STATE = ROOT / ".local/render-free-preview.json"
REPO = "https://github.com/Anmol-Nayak-AI/orqentra"


class PreviewError(RuntimeError):
    pass


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["inspect", "deploy", "status"])
    parser.add_argument("--owner")
    args = parser.parse_args()
    key = os.environ.get("RENDER_API_KEY") or dotenv_values(ROOT / ".env.render").get(
        "RENDER_API_KEY"
    )
    if not key:
        raise PreviewError("Configure RENDER_API_KEY in ignored .env.render.")
    opener = urllib.request.build_opener(NoRedirect())

    def api(method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        request = urllib.request.Request(
            "https://api.render.com/v1/" + path,
            method=method,
            data=json.dumps(body).encode() if body is not None else None,
            headers={
                "Authorization": "Bearer " + key,
                "Content-Type": "application/json",
            },
        )
        try:
            with opener.open(request, timeout=30) as response:
                raw = response.read()
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as error:
            raise PreviewError(
                f"Render request failed with HTTP {error.code}; details redacted."
            ) from None

    if args.action == "inspect":
        owners = [row["owner"] for row in api("GET", "owners?limit=100")]
        print(
            json.dumps(
                {
                    "workspaces": [
                        {"id": row["id"], "name": row["name"]} for row in owners
                    ]
                }
            )
        )
        return
    if args.action == "status":
        state = json.loads(STATE.read_text())
        if not state.get("service_id"):
            raise PreviewError(
                "Uncertain creation: inspect workspace services before retrying."
            )
        service = api("GET", "services/" + state["service_id"])
        if service["type"] != "static_site":
            raise PreviewError("Refusing a non-static service.")
        deploys = api("GET", "services/" + state["service_id"] + "/deploys?limit=5")
        print(
            json.dumps(
                {
                    "service_id": service["id"],
                    "url": service["serviceDetails"]["url"],
                    "type": service["type"],
                    "deploys": [
                        {
                            "id": row["deploy"]["id"],
                            "status": row["deploy"]["status"],
                            "commit": row["deploy"].get("commit", {}).get("id"),
                        }
                        for row in deploys
                    ],
                }
            )
        )
        return
    if not args.owner:
        raise PreviewError("An explicit authorized workspace ID is required.")
    config = yaml.safe_load(
        (ROOT / "infrastructure/render/free-preview.yaml").read_text()
    )
    services = config["services"]
    if len(services) != 1 or config.get("databases") or config.get("envVarGroups"):
        raise PreviewError("Free preview must contain one static site only.")
    row = services[0]
    if (
        row["runtime"] != "static"
        or row.get("plan")
        or row["autoDeployTrigger"] != "off"
        or row["previews"]["generation"] not in {"off", False}
        or any(
            item["key"] not in {"NODE_VERSION", "SKIP_INSTALL_DEPS"}
            for item in row["envVars"]
        )
    ):
        raise PreviewError(
            "Refusing paid/automatic builds or provider environment variables."
        )
    if args.owner not in {
        owner["owner"]["id"] for owner in api("GET", "owners?limit=100")
    }:
        raise PreviewError("Authorized workspace not found.")
    existing = [
        item["service"]
        for item in api("GET", "services?limit=100")
        if item["service"]["name"] == row["name"]
        and item["service"]["ownerId"] == args.owner
    ]
    if existing:
        raise PreviewError(
            "A matching service exists; inspect it instead of creating or updating blindly."
        )
    if STATE.exists():
        raise PreviewError(
            "A creation attempt is recorded; resolve it before any repeat POST."
        )
    STATE.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "type": "static_site",
        "name": row["name"],
        "ownerId": args.owner,
        "repo": REPO,
        "branch": row["branch"],
        "autoDeployTrigger": "off",
        "envVars": [
            {"key": item["key"], "value": str(item["value"])} for item in row["envVars"]
        ],
        "serviceDetails": {
            "buildCommand": row["buildCommand"],
            "publishPath": row["staticPublishPath"],
            "previews": {"generation": "off"},
            "headers": row["headers"],
            "routes": row["routes"],
        },
    }
    STATE.write_text(
        json.dumps({"status": "CREATING", "name": row["name"], "owner_id": args.owner})
    )
    response = api(
        "POST", "services", payload
    )  # One POST only; no uncertain automatic retry.
    service = response["service"]
    if service["type"] != "static_site":
        raise PreviewError("Unexpected provider resource type; inspect manually.")
    state = {
        "status": "CREATED",
        "service_id": service["id"],
        "deploy_id": response.get("deployId"),
        "url": service["serviceDetails"]["url"],
    }
    STATE.write_text(json.dumps(state))
    print(json.dumps(state))


if __name__ == "__main__":
    try:
        main()
    except PreviewError as error:
        print(str(error))
        raise SystemExit(1) from None
    except Exception:  # noqa: BLE001 -- CLI must not print credentials or provider response bodies.
        print(
            "Free preview operation failed; inspect private state and provider status. No automatic retry."
        )
        raise SystemExit(1) from None
