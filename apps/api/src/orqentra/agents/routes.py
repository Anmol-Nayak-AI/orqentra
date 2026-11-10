from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy import select

from orqentra.agents.schemas import (
    AgentCreate,
    AgentResponse,
    AgentRevision,
    AgentUpdate,
    AgentVersionResponse,
    TeammateConfiguration,
)
from orqentra.auth.dependencies import AuthorizedOrganization, OrganizationPermission
from orqentra.persistence.errors import StaleRevision
from orqentra.persistence.models import AgentDefinition, AgentVersion
from orqentra.persistence.repositories import AgentRepository

router = APIRouter(prefix="/api/v1/organizations/{organization_id}/agents", tags=["teammates"])
Read = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("agent.read"))]
Create = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("agent.create"))]
Edit = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("agent.update"))]
Publish = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("agent.publish"))]
Archive = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("agent.archive"))]


def repository(access: AuthorizedOrganization) -> AgentRepository:
    return AgentRepository(access.authenticated.session, access.context)


@router.get("", response_model=list[AgentResponse])
def list_agents(
    access: Read, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)
) -> list[AgentDefinition]:
    return repository(access).list(limit=limit, offset=offset)


@router.post("", response_model=AgentResponse, status_code=201)
def create_agent(body: AgentCreate, access: Create) -> AgentDefinition:
    return repository(access).create(
        workspace_id=body.workspace_id,
        name=body.name.strip(),
        slug=body.slug,
        configuration=body.configuration.model_dump(),
    )


@router.get("/{agent_id}", response_model=AgentResponse)
def get_agent(agent_id: UUID, access: Read) -> AgentDefinition:
    return repository(access).get(agent_id)


@router.patch("/{agent_id}", response_model=AgentResponse)
def update_agent(agent_id: UUID, body: AgentUpdate, access: Edit) -> AgentDefinition:
    return repository(access).update_draft(
        agent_id,
        expected_revision=body.expected_revision,
        configuration=body.configuration.model_dump(),
    )


@router.post("/{agent_id}/publish", response_model=AgentVersionResponse, status_code=201)
def publish_agent(agent_id: UUID, body: AgentRevision, access: Publish) -> AgentVersion:
    repo = repository(access)
    agent = repo.get(agent_id, lock=True)
    # Validate legacy drafts as well as newly submitted configurations before immutable publication.
    try:
        TeammateConfiguration.model_validate(agent.draft_configuration)
    except ValidationError:
        raise HTTPException(422, "Draft configuration requires updating.") from None
    return repo.publish(agent_id, expected_revision=body.expected_revision)


@router.post("/{agent_id}/archive", response_model=AgentResponse)
def archive_agent(agent_id: UUID, body: AgentRevision, access: Archive) -> AgentDefinition:
    repo = repository(access)
    agent = repo.get(agent_id, lock=True)
    if agent.revision != body.expected_revision or agent.lifecycle_status == "ARCHIVED":
        raise StaleRevision("Draft is stale or already archived.")
    agent.lifecycle_status = "ARCHIVED"
    agent.archived_at = datetime.now(UTC)
    agent.revision += 1
    repo._audit("agent.archived", agent.id, revision=agent.revision)
    return agent


@router.get("/{agent_id}/versions", response_model=list[AgentVersionResponse])
def versions(
    agent_id: UUID, access: Read, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)
) -> list[AgentVersion]:
    repository(access).get(agent_id)
    return list(
        access.authenticated.session.scalars(
            select(AgentVersion)
            .where(
                AgentVersion.organization_id == access.context.organization_id,
                AgentVersion.agent_definition_id == agent_id,
            )
            .order_by(AgentVersion.version_number.desc())
            .limit(limit)
            .offset(offset)
        )
    )
