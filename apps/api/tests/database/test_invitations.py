from uuid import uuid4

from sqlalchemy import Engine
from test_identity_authorization import add_existing_member, call, org


def test_invitation_single_use_and_role(db: tuple[Engine, Engine]) -> None:
    owner = "user_" + uuid4().hex
    tenant = org(db, owner)
    base = f"/api/v1/organizations/{tenant['id']}"
    code, invitation = call(db, owner, base + "/invitations", "POST", {"role": "MEMBER"})
    assert code == 201 and isinstance(invitation, dict)
    guest = "user_" + uuid4().hex
    assert (
        call(db, guest, "/api/v1/invitations/accept", "POST", {"token": invitation["token"]})[0]
        == 200
    )
    code, membership = call(db, guest, base + "/memberships/me")
    assert code == 200 and isinstance(membership, dict) and membership["role"] == "MEMBER"
    assert (
        call(db, guest, "/api/v1/invitations/accept", "POST", {"token": invitation["token"]})[0]
        == 403
    )
    assert call(db, guest, base + "/invitations", "POST", {"role": "MEMBER"})[0] == 403
    code, listing = call(db, owner, base + "/invitations")
    assert (
        code == 200
        and isinstance(listing, list)
        and "token" not in listing[0]
        and "token_hash" not in listing[0]
    )


def test_invite_revocation_and_no_admin_escalation(db: tuple[Engine, Engine]) -> None:
    owner = "user_" + uuid4().hex
    tenant = org(db, owner)
    base = f"/api/v1/organizations/{tenant['id']}"
    assert call(db, owner, base + "/invitations", "POST", {"role": "OWNER"})[0] == 422
    code, invitation = call(db, owner, base + "/invitations", "POST", {"role": "VIEWER"})
    assert code == 201 and isinstance(invitation, dict)
    assert call(db, owner, base + "/invitations/" + str(invitation["id"]), "DELETE")[0] == 200
    assert (
        call(
            db,
            "user_" + uuid4().hex,
            "/api/v1/invitations/accept",
            "POST",
            {"token": invitation["token"]},
        )[0]
        == 403
    )
    viewer = "user_" + uuid4().hex
    add_existing_member(db, tenant["id"], viewer, "VIEWER")
    assert call(db, viewer, base + "/invitations")[0] == 403
