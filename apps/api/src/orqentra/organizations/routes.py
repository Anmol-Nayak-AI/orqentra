from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy import select, text

from orqentra.auth.dependencies import (
    AuthenticatedSession,
    AuthorizedOrganization,
    OrganizationPermission,
    identity_session,
)
from orqentra.organizations.schemas import (
    MembershipResponse,
    MembershipUpdate,
    MeResponse,
    OrganizationCreate,
    OrganizationResponse,
    WorkspaceResponse,
)
from orqentra.organizations.service import change_membership
from orqentra.persistence.models import Organization, OrganizationMembership, User, Workspace

router = APIRouter(prefix="/api/v1", tags=["identity and organizations"])
Identity = Annotated[AuthenticatedSession, Depends(identity_session, scope="function")]
ReadOrganization = Annotated[
    AuthorizedOrganization, Depends(OrganizationPermission("organization.read"))
]
ReadMembership = Annotated[
    AuthorizedOrganization, Depends(OrganizationPermission("membership.read"))
]
WriteMembership = Annotated[
    AuthorizedOrganization, Depends(OrganizationPermission("membership.update"))
]
RemoveMembership = Annotated[
    AuthorizedOrganization, Depends(OrganizationPermission("membership.remove"))
]
ReadWorkspace = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("workspace.read"))]


@router.get("/me", response_model=MeResponse)
def me(identity: Identity) -> User:
    user = identity.session.get(User, identity.user_id)
    assert user is not None
    return user


@router.get("/organizations", response_model=list[OrganizationResponse])
def organizations(identity: Identity) -> list[dict[str, object]]:
    return [
        {k: v for k, v in r.items() if k != "membership_id"}
        for r in identity.session.execute(
            text("SELECT * FROM public.orqentra_my_organizations()")
        ).mappings()
    ]


@router.post("/organizations", response_model=OrganizationResponse, status_code=201)
def create_organization(
    body: OrganizationCreate, identity: Identity, request: Request
) -> dict[str, object]:
    org_id = identity.session.scalar(
        text("SELECT public.orqentra_create_organization(:name,:slug,:correlation)"),
        {"name": body.name, "slug": body.slug, "correlation": UUID(request.state.correlation_id)},
    )
    row = identity.session.get(Organization, org_id)
    assert row is not None
    return {"id": row.id, "name": row.name, "slug": row.slug, "status": row.status, "role": "OWNER"}


@router.get("/organizations/{organization_id}", response_model=OrganizationResponse)
def organization(organization_id: UUID, access: ReadOrganization) -> dict[str, object]:
    row = access.authenticated.session.get(Organization, organization_id)
    assert row is not None
    return {
        "id": row.id,
        "name": row.name,
        "slug": row.slug,
        "status": row.status,
        "role": access.role,
    }


@router.get("/organizations/{organization_id}/memberships/me", response_model=MembershipResponse)
def current_membership(organization_id: UUID, access: ReadMembership) -> OrganizationMembership:
    row = access.authenticated.session.get(OrganizationMembership, access.membership_id)
    assert row is not None
    return row


@router.get("/organizations/{organization_id}/memberships", response_model=list[MembershipResponse])
def memberships(
    organization_id: UUID,
    access: ReadMembership,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[OrganizationMembership]:
    return list(
        access.authenticated.session.scalars(
            select(OrganizationMembership)
            .where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.status == "ACTIVE",
            )
            .order_by(OrganizationMembership.created_at, OrganizationMembership.id)
            .limit(limit)
            .offset(offset)
        )
    )


@router.patch(
    "/organizations/{organization_id}/memberships/{membership_id}",
    response_model=MembershipResponse,
)
def update_membership(
    organization_id: UUID, membership_id: UUID, body: MembershipUpdate, access: WriteMembership
) -> OrganizationMembership:
    return change_membership(access, membership_id, body.role)


@router.delete("/organizations/{organization_id}/memberships/{membership_id}", status_code=204)
def remove_membership(
    organization_id: UUID, membership_id: UUID, access: RemoveMembership
) -> Response:
    change_membership(access, membership_id, None)
    return Response(status_code=204)


@router.get("/organizations/{organization_id}/workspaces", response_model=list[WorkspaceResponse])
def workspaces(
    organization_id: UUID,
    access: ReadWorkspace,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[Workspace]:
    return list(
        access.authenticated.session.scalars(
            select(Workspace)
            .where(
                Workspace.organization_id == organization_id,
                Workspace.status == "ACTIVE",
            )
            .order_by(Workspace.created_at, Workspace.id)
            .limit(limit)
            .offset(offset)
        )
    )
