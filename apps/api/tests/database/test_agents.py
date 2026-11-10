from uuid import uuid4

import pytest
from sqlalchemy import Engine
from test_identity_authorization import add_existing_member, call, org


def setup_agent(db: tuple[Engine, Engine]) -> tuple[str, str, dict[str, object]]:
    subject = "user_" + uuid4().hex
    tenant = org(db, subject)
    base = f"/api/v1/organizations/{tenant['id']}"
    code, workspaces = call(db, subject, base + "/workspaces")
    assert code == 200 and isinstance(workspaces, list)
    body = {
        "name": "Onboarding specialist",
        "slug": "onboarding",
        "workspace_id": workspaces[0]["id"],
        "configuration": {
            "instructions": "Use approved sources and request clarification when missing."
        },
    }
    return subject, base + "/agents", body


def test_agent_lifecycle_and_revision_conflict(db: tuple[Engine, Engine]) -> None:
    subject, base, body = setup_agent(db)
    code, agent = call(db, subject, base, "POST", body)
    assert code == 201 and isinstance(agent, dict)
    path = f"{base}/{agent['id']}"
    config = {"instructions": "Prepare a grounded onboarding checklist with supporting evidence."}
    assert (
        call(db, subject, path, "PATCH", {"expected_revision": 9, "configuration": config})[0]
        == 409
    )
    assert (
        call(db, subject, path, "PATCH", {"expected_revision": 1, "configuration": config})[0]
        == 200
    )
    code, version = call(db, subject, path + "/publish", "POST", {"expected_revision": 2})
    assert code == 201 and isinstance(version, dict)
    assert (
        version["configuration_snapshot"]["configuration"]["instructions"] == config["instructions"]
    )
    assert call(db, subject, path + "/publish", "POST", {"expected_revision": 2})[0] == 409
    assert call(db, subject, path + "/archive", "POST", {"expected_revision": 3})[0] == 200
    assert (
        call(db, subject, path, "PATCH", {"expected_revision": 4, "configuration": config})[0]
        == 409
    )
    code, history = call(db, subject, path + "/versions")
    assert code == 200 and history == [version]


@pytest.mark.parametrize(
    "role,create,publish", [("ADMIN", 201, 201), ("MEMBER", 201, 403), ("VIEWER", 403, 403)]
)
def test_agent_http_permissions(
    db: tuple[Engine, Engine], role: str, create: int, publish: int
) -> None:
    subject, base, body = setup_agent(db)
    other = "user_" + uuid4().hex
    add_existing_member(db, base.split("/")[4], other, role)
    assert call(db, other, base, "POST", body)[0] == create
    body["slug"] = "owner-draft"
    code, agent = call(db, subject, base, "POST", body)
    assert code == 201 and isinstance(agent, dict)
    assert (
        call(db, other, f"{base}/{agent['id']}/publish", "POST", {"expected_revision": 1})[0]
        == publish
    )


def test_agent_cross_tenant_and_invalid_configuration(db: tuple[Engine, Engine]) -> None:
    subject, base, body = setup_agent(db)
    stranger, other_base, other_body = setup_agent(db)
    bad = dict(
        body,
        configuration={
            "instructions": "Valid instruction but unsafe tool configuration.",
            "tools": ["shell.exec"],
        },
    )
    assert call(db, subject, base, "POST", bad)[0] == 422
    bad = dict(body, workspace_id=other_body["workspace_id"])
    assert call(db, subject, base, "POST", bad)[0] == 404
    code, agent = call(db, subject, base, "POST", body)
    assert code == 201 and isinstance(agent, dict)
    assert call(db, stranger, f"{base}/{agent['id']}")[0] == 403
    assert call(db, stranger, f"{other_base}/{agent['id']}")[0] == 404
    assert call(db, None, base)[0] == 401
