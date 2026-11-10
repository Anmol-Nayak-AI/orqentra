import copy
import json
import re
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from orqentra.persistence.errors import ForbiddenOperation, RecordNotFound, StaleRevision
from orqentra.persistence.models import (
    AgentDefinition,
    AgentToolPermission,
    AgentVersion,
    AuditEvent,
    OrganizationMembership,
    Workspace,
)
from orqentra.persistence.session import TrustedOrganizationContext


def normalized_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    if not slug or len(slug) > 100:
        raise ValueError("Slug must contain 1–100 normalized characters.")
    return slug


def validated_configuration(value: dict[str, Any]) -> dict[str, Any]:
    # Persistence contract only; model/tool/output-schema allowlists are Phase 2D.
    encoded = json.dumps(value, allow_nan=False)
    if len(encoded.encode()) > 65536:
        raise ValueError("Configuration exceeds 64 KiB.")
    return copy.deepcopy(value)


class AgentRepository:
    def __init__(self, session: Session, context: TrustedOrganizationContext) -> None:
        self.session = session
        self.context = context

    def _writer(self) -> None:
        actor = self.session.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.organization_id == self.context.organization_id,
                OrganizationMembership.user_id == self.context.actor_user_id,
                OrganizationMembership.status == "ACTIVE",
                OrganizationMembership.role.in_(["OWNER", "ADMIN", "MEMBER"]),
            )
        )
        if actor is None:
            raise ForbiddenOperation("Active write membership required.")

    def get(self, agent_id: UUID, *, lock: bool = False) -> AgentDefinition:
        statement = select(AgentDefinition).where(
            AgentDefinition.id == agent_id,
            AgentDefinition.organization_id == self.context.organization_id,
        )
        if lock:
            statement = statement.with_for_update().execution_options(populate_existing=True)
        agent = self.session.scalar(statement)
        if agent is None:
            raise RecordNotFound("Agent not found in this organization.")
        return agent

    def list(self, *, limit: int = 50, offset: int = 0) -> list[AgentDefinition]:
        if not 1 <= limit <= 100 or offset < 0:
            raise ValueError("Invalid pagination bounds.")
        return list(
            self.session.scalars(
                select(AgentDefinition)
                .where(
                    AgentDefinition.organization_id == self.context.organization_id,
                )
                .order_by(AgentDefinition.created_at, AgentDefinition.id)
                .limit(limit)
                .offset(offset)
            )
        )

    def create(
        self, *, workspace_id: UUID, name: str, slug: str, configuration: dict[str, Any]
    ) -> AgentDefinition:
        self._writer()
        workspace = self.session.scalar(
            select(Workspace).where(
                Workspace.id == workspace_id,
                Workspace.organization_id == self.context.organization_id,
                Workspace.status == "ACTIVE",
            )
        )
        if workspace is None:
            raise RecordNotFound("Workspace not found in this organization.")
        agent = AgentDefinition(
            organization_id=self.context.organization_id,
            workspace_id=workspace_id,
            name=name,
            slug=normalized_slug(slug),
            draft_configuration=validated_configuration(configuration),
            created_by=self.context.actor_user_id,
        )
        self.session.add(agent)
        self.session.flush()
        self._audit("agent.created", agent.id, revision=agent.revision)
        return agent

    def update_draft(
        self, agent_id: UUID, *, expected_revision: int, configuration: dict[str, Any]
    ) -> AgentDefinition:
        self._writer()
        result = self.session.execute(
            update(AgentDefinition)
            .where(
                AgentDefinition.organization_id == self.context.organization_id,
                AgentDefinition.id == agent_id,
                AgentDefinition.revision == expected_revision,
                AgentDefinition.lifecycle_status != "ARCHIVED",
            )
            .values(
                draft_configuration=validated_configuration(configuration),
                revision=AgentDefinition.revision + 1,
                lifecycle_status="DRAFT",
            )
            .returning(AgentDefinition)
            .execution_options(populate_existing=True)
        ).scalar_one_or_none()
        if result is None:
            self.get(agent_id)
            raise StaleRevision("Agent draft revision is stale or archived.")
        self._audit("agent.updated", agent_id, revision=result.revision)
        return result

    def publish(self, agent_id: UUID, *, expected_revision: int) -> AgentVersion:
        self._writer()
        agent = self.get(agent_id, lock=True)
        if agent.revision != expected_revision or agent.lifecycle_status == "ARCHIVED":
            raise StaleRevision("Agent draft revision is stale or archived.")
        latest = (
            self.session.scalar(
                select(func.max(AgentVersion.version_number)).where(
                    AgentVersion.organization_id == self.context.organization_id,
                    AgentVersion.agent_definition_id == agent_id,
                )
            )
            or 0
        )
        tools = self.session.scalars(
            select(AgentToolPermission)
            .where(
                AgentToolPermission.organization_id == self.context.organization_id,
                AgentToolPermission.agent_definition_id == agent_id,
                AgentToolPermission.status == "ACTIVE",
            )
            .order_by(AgentToolPermission.tool_identifier)
        )
        snapshot = {
            "configuration": copy.deepcopy(agent.draft_configuration),
            "tool_permissions": [
                {
                    "tool_identifier": t.tool_identifier,
                    "permission_scope": copy.deepcopy(t.permission_scope),
                }
                for t in tools
            ],
        }
        version = AgentVersion(
            organization_id=self.context.organization_id,
            agent_definition_id=agent_id,
            version_number=latest + 1,
            configuration_snapshot=snapshot,
            published_by=self.context.actor_user_id,
        )
        self.session.add(version)
        agent.revision += 1
        agent.lifecycle_status = "PUBLISHED"
        self.session.flush()
        self._audit(
            "agent.published",
            version.id,
            revision=agent.revision,
            version_number=version.version_number,
        )
        return version

    def _audit(
        self, action: str, resource_id: UUID, *, revision: int, version_number: int | None = None
    ) -> None:
        metadata: dict[str, Any] = {"revision": revision}
        if version_number is not None:
            metadata["version_number"] = version_number
        self.session.add(
            AuditEvent(
                organization_id=self.context.organization_id,
                actor_user_id=self.context.actor_user_id,
                action=action,
                resource_type="agent",
                resource_id=resource_id,
                correlation_id=self.context.correlation_id,
                safe_metadata=metadata,
            )
        )
        self.session.flush()
