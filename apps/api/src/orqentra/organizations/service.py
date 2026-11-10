from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select

from orqentra.auth.dependencies import AuthorizedOrganization
from orqentra.auth.permissions import Role, permits
from orqentra.persistence.models import AuditEvent, Organization, OrganizationMembership


def change_membership(
    authorized: AuthorizedOrganization, target_id: UUID, new_role: Role | None
) -> OrganizationMembership:
    session = authorized.authenticated.session
    context = authorized.context
    # All role/removal writes take this same lock before membership reads or updates.
    organization = session.scalar(
        select(Organization)
        .where(Organization.id == context.organization_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if organization is None or organization.status != "ACTIVE":
        raise HTTPException(403, "Organization access denied.")
    actor = session.scalar(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.organization_id == context.organization_id,
            OrganizationMembership.user_id == context.actor_user_id,
            OrganizationMembership.status == "ACTIVE",
        )
        .execution_options(populate_existing=True)
    )
    permission = "membership.remove" if new_role is None else "membership.update"
    if actor is None or not permits(Role(actor.role), permission):
        raise HTTPException(403, "Permission denied.")
    target = session.scalar(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.id == target_id,
            OrganizationMembership.organization_id == context.organization_id,
            OrganizationMembership.status == "ACTIVE",
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if target is None:
        raise HTTPException(404, "Membership not found.")
    if actor.role != "OWNER" and (
        target.role in {"OWNER", "ADMIN"} or new_role in {Role.OWNER, Role.ADMIN}
    ):
        raise HTTPException(403, "Owners control administrative roles.")
    if target.role == "OWNER" and new_role != Role.OWNER:
        count = session.scalar(
            select(func.count())
            .select_from(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == context.organization_id,
                OrganizationMembership.status == "ACTIVE",
                OrganizationMembership.role == "OWNER",
            )
        )
        if count is None or count <= 1:
            raise HTTPException(409, "The final active owner is protected.")
    old_role = target.role
    if new_role is None:
        target.status = "REVOKED"
    else:
        target.role = new_role.value
    session.add(
        AuditEvent(
            organization_id=context.organization_id,
            actor_user_id=context.actor_user_id,
            action="membership.removed" if new_role is None else "membership.role_changed",
            resource_type="membership",
            resource_id=target.id,
            correlation_id=context.correlation_id,
            safe_metadata={
                "reason_code": "membership_changed",
                "old_role": old_role,
                "new_role": new_role.value if new_role else None,
            },
        )
    )
    session.flush()
    return target
