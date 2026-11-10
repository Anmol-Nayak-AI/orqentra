from enum import StrEnum


class Role(StrEnum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"
    VIEWER = "VIEWER"


READ = {"organization.read", "membership.read", "workspace.read", "agent.read"}
ADMIN = READ | {
    "organization.update",
    "membership.invite",
    "membership.update",
    "membership.remove",
    "workspace.create",
    "workspace.update",
    "workspace.delete",
    "agent.create",
    "agent.update",
    "agent.publish",
    "agent.archive",
    "audit.read",
}
PERMISSIONS: dict[Role, set[str]] = {
    Role.OWNER: ADMIN | {"organization.delete"},
    Role.ADMIN: ADMIN,
    Role.MEMBER: READ | {"agent.create", "agent.update"},
    Role.VIEWER: READ,
}


def permits(role: Role, permission: str) -> bool:
    return permission in PERMISSIONS[role]
