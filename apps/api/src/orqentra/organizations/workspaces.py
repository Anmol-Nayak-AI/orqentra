"""Bounded organization workspace creation and conflict-checked naming."""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import Field
from sqlalchemy import func, select, text

from orqentra.auth.dependencies import AuthorizedOrganization, OrganizationPermission
from orqentra.execution.routes import audit
from orqentra.organizations.schemas import Contract, WorkspaceResponse
from orqentra.persistence.models import OrganizationMembership, Workspace

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/workspaces", tags=["workspace administration"]
)
Manage = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("workspace.create"))]


class WorkspaceCreate(Contract):
    name: str = Field(min_length=1, max_length=200, pattern=r"\S")
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")


class WorkspaceRename(Contract):
    name: str = Field(min_length=1, max_length=200, pattern=r"\S")
    expected_updated_at: datetime


def lock_access(access: AuthorizedOrganization) -> None:
    session = access.authenticated.session
    session.execute(
        text("SELECT id FROM organizations WHERE id=:id FOR UPDATE"),
        {"id": access.context.organization_id},
    )
    member = session.scalar(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.user_id == access.authenticated.user_id,
            OrganizationMembership.status == "ACTIVE",
        )
        .execution_options(populate_existing=True)
    )
    if not member or member.role not in {"OWNER", "ADMIN"}:
        raise HTTPException(403)


@router.post("", response_model=WorkspaceResponse, status_code=201)
def create_workspace(body: WorkspaceCreate, access: Manage) -> Workspace:
    lock_access(access)
    session = access.authenticated.session
    old = session.scalar(select(Workspace).where(Workspace.slug == body.slug))
    if old:
        if old.name != body.name.strip() or old.status != "ACTIVE":
            raise HTTPException(409)
        return old
    if (session.scalar(select(func.count()).select_from(Workspace)) or 0) >= 20:
        raise HTTPException(409)
    item = Workspace(
        organization_id=access.context.organization_id, name=body.name.strip(), slug=body.slug
    )
    session.add(item)
    session.flush()
    audit(access, "workspace.created", item.id)
    return item


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
def rename_workspace(workspace_id: UUID, body: WorkspaceRename, access: Manage) -> Workspace:
    lock_access(access)
    item = access.authenticated.session.scalar(
        select(Workspace).where(Workspace.id == workspace_id).with_for_update()
    )
    if item is None:
        raise HTTPException(404)
    if item.updated_at != body.expected_updated_at or item.status != "ACTIVE":
        raise HTTPException(409)
    item.name = body.name.strip()
    access.authenticated.session.flush()
    audit(access, "workspace.renamed", item.id)
    return item
