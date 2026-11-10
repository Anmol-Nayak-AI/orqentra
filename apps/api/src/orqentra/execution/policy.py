from sqlalchemy import select, text
from sqlalchemy.orm import Session

from orqentra.persistence.models import (
    AgentDefinition,
    AgentVersion,
    KnowledgeDocument,
    Organization,
    OrganizationMembership,
    TaskRun,
    Workspace,
)


def eligible(session: Session, run: TaskRun) -> bool:
    # Serializes policy checks against organization membership changes until commit.
    session.execute(
        text("SELECT id FROM organizations WHERE id=:id FOR UPDATE"), {"id": run.organization_id}
    )
    return bool(
        session.scalar(
            select(Organization.id).where(
                Organization.id == run.organization_id, Organization.status == "ACTIVE"
            )
        )
        and session.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.organization_id == run.organization_id,
                OrganizationMembership.user_id == run.created_by,
                OrganizationMembership.status == "ACTIVE",
                OrganizationMembership.role.in_(["OWNER", "ADMIN", "MEMBER"]),
            )
        )
        and session.scalar(
            select(Workspace.id).where(
                Workspace.id == run.workspace_id, Workspace.status == "ACTIVE"
            )
        )
        and session.scalar(
            select(AgentDefinition.id)
            .join(AgentVersion, AgentVersion.agent_definition_id == AgentDefinition.id)
            .where(
                AgentVersion.id == run.agent_version_id,
                AgentDefinition.lifecycle_status != "ARCHIVED",
            )
        )
    )


def approved_sources_active(session: Session, run: TaskRun) -> bool:
    from uuid import UUID

    if not run.source_ids:
        return False
    ids = {UUID(value) for value in run.source_ids}
    active = set(
        session.scalars(
            select(KnowledgeDocument.id)
            .where(
                KnowledgeDocument.id.in_(ids),
                KnowledgeDocument.workspace_id == run.workspace_id,
                KnowledgeDocument.status == "ACTIVE",
            )
            .with_for_update()
        )
    )
    return active == ids
