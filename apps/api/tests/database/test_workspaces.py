from uuid import uuid4

from test_identity_authorization import add_existing_member, call, org


def test_workspace_create_rename_idempotency_and_permissions(db):
    owner = "user_" + uuid4().hex
    tenant = org(db, owner)
    base = f"/api/v1/organizations/{tenant['id']}/workspaces"
    request = {"name": "Customer success", "slug": "customer-success"}
    code, workspace = call(db, owner, base, "POST", request)
    assert code == 201
    assert call(db, owner, base, "POST", request)[1]["id"] == workspace["id"]
    assert call(db, owner, base, "POST", dict(request, name="Different"))[0] == 409
    code, renamed = call(
        db,
        owner,
        base + "/" + workspace["id"],
        "PATCH",
        {"name": "Enterprise success", "expected_updated_at": workspace["updated_at"]},
    )
    assert code == 200 and renamed["name"] == "Enterprise success"
    assert (
        call(
            db,
            owner,
            base + "/" + workspace["id"],
            "PATCH",
            {"name": "Stale name", "expected_updated_at": workspace["updated_at"]},
        )[0]
        == 409
    )
    member = "user_" + uuid4().hex
    add_existing_member(db, tenant["id"], member, "MEMBER")
    assert call(db, member, base, "POST", {"name": "Denied", "slug": "denied"})[0] == 403
    stranger = "user_" + uuid4().hex
    another = org(db, stranger)
    assert (
        call(
            db,
            stranger,
            f"/api/v1/organizations/{another['id']}/workspaces/{workspace['id']}",
            "PATCH",
            {"name": "Wrong tenant", "expected_updated_at": renamed["updated_at"]},
        )[0]
        == 404
    )
