import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import select, text

from orqentra.auth.dependencies import (
    AuthenticatedSession,
    AuthorizedOrganization,
    OrganizationPermission,
    identity_session,
)
from orqentra.execution.routes import audit
from orqentra.organizations.schemas import Contract
from orqentra.persistence.models import OrganizationInvitation

router = APIRouter(prefix="/api/v1", tags=["invitations"])
Manage = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("membership.invite"))]
Identity = Annotated[AuthenticatedSession, Depends(identity_session, scope="function")]


class InvitationCreate(Contract):
    role: Literal["MEMBER", "VIEWER"] = "MEMBER"


class InvitationResponse(Contract):
    id: UUID
    role: str
    status: str
    expires_at: datetime


class InvitationCreated(InvitationResponse):
    token: str


class InvitationAccept(Contract):
    token: str = Field(pattern=r"^[A-Za-z0-9_-]{43}$")


@router.post(
    "/organizations/{organization_id}/invitations",
    response_model=InvitationCreated,
    status_code=201,
)
def invite(body: InvitationCreate, access: Manage) -> dict[str, object]:
    token = secrets.token_urlsafe(32)
    invitation = OrganizationInvitation(
        organization_id=access.context.organization_id,
        created_by=access.authenticated.user_id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        role=body.role,
        expires_at=datetime.now(UTC) + timedelta(days=2),
    )
    access.authenticated.session.add(invitation)
    access.authenticated.session.flush()
    audit(access, "invitation.created", invitation.id)
    return {
        "id": invitation.id,
        "role": invitation.role,
        "status": invitation.status,
        "expires_at": invitation.expires_at,
        "token": token,
    }


@router.get("/organizations/{organization_id}/invitations", response_model=list[InvitationResponse])
def list_invitations(access: Manage) -> list[OrganizationInvitation]:
    return list(
        access.authenticated.session.scalars(
            select(OrganizationInvitation)
            .where(OrganizationInvitation.organization_id == access.context.organization_id)
            .order_by(OrganizationInvitation.created_at.desc())
            .limit(50)
        )
    )


@router.delete(
    "/organizations/{organization_id}/invitations/{invitation_id}",
    response_model=InvitationResponse,
)
def revoke_invitation(invitation_id: UUID, access: Manage) -> OrganizationInvitation:
    invitation = access.authenticated.session.scalar(
        select(OrganizationInvitation)
        .where(
            OrganizationInvitation.id == invitation_id,
            OrganizationInvitation.organization_id == access.context.organization_id,
        )
        .with_for_update()
    )
    if invitation is None:
        raise HTTPException(404)
    if invitation.status != "PENDING":
        raise HTTPException(409)
    invitation.status = "REVOKED"
    audit(access, "invitation.revoked", invitation.id)
    return invitation


@router.post("/invitations/accept", response_model=dict[str, UUID])
def accept_invitation(
    body: InvitationAccept, identity: Identity, request: Request
) -> dict[str, UUID]:
    result = identity.session.scalar(
        text("SELECT public.orqentra_accept_invitation(:hashed,:correlation)"),
        {
            "hashed": hashlib.sha256(body.token.encode()).hexdigest(),
            "correlation": UUID(request.state.correlation_id),
        },
    )
    assert isinstance(result, UUID)
    return {"organization_id": result}
