from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector  # type: ignore[import-untyped]
from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

NAMING = {
    "ix": "ix_%(table_name)s_%(column_0_name)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING)


class Identity:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)


class Timestamps:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Organization(Identity, Timestamps, Base):
    __tablename__ = "organizations"
    __table_args__ = (
        UniqueConstraint("slug", name="uq_organizations_slug"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="slug_normalized"),
        CheckConstraint("status IN ('ACTIVE','SUSPENDED','ARCHIVED')", name="status"),
        CheckConstraint("length(trim(name)) > 0", name="name_nonempty"),
    )
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")


class User(Identity, Timestamps, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("external_auth_id", name="uq_users_external_auth_id"),
        CheckConstraint("status IN ('ACTIVE','DISABLED')", name="status"),
    )
    external_auth_id: Mapped[str | None] = mapped_column(String(255))
    email: Mapped[str] = mapped_column(String(320))
    display_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")


class OrganizationMembership(Identity, Timestamps, Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_memberships_org_user"),
        CheckConstraint("role IN ('OWNER','ADMIN','MEMBER','VIEWER')", name="role"),
        CheckConstraint("status IN ('ACTIVE','INVITED','REVOKED')", name="status"),
        Index("ix_memberships_user", "user_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    role: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")
    organization: Mapped[Organization] = relationship(viewonly=True)
    user: Mapped[User] = relationship(viewonly=True)


class Workspace(Identity, Timestamps, Base):
    __tablename__ = "workspaces"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_workspaces_org_id"),
        UniqueConstraint("organization_id", "slug", name="uq_workspaces_org_slug"),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="slug_normalized"),
        CheckConstraint("status IN ('ACTIVE','ARCHIVED')", name="status"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")
    organization: Mapped[Organization] = relationship(viewonly=True)


class AgentDefinition(Identity, Timestamps, Base):
    __tablename__ = "agent_definitions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_agents_org_id"),
        UniqueConstraint(
            "organization_id", "workspace_id", "slug", name="uq_agents_workspace_slug"
        ),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            ondelete="RESTRICT",
            name="fk_agents_workspace_scope",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_agents_creator_membership",
        ),
        CheckConstraint("slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name="slug_normalized"),
        CheckConstraint("lifecycle_status IN ('DRAFT','PUBLISHED','ARCHIVED')", name="lifecycle"),
        CheckConstraint("revision > 0", name="revision_positive"),
        CheckConstraint("jsonb_typeof(draft_configuration) = 'object'", name="draft_object"),
        CheckConstraint(
            "(lifecycle_status = 'ARCHIVED') = (archived_at IS NOT NULL)", name="archive_consistent"
        ),
        Index(
            "ix_agents_org_lifecycle_created",
            "organization_id",
            "lifecycle_status",
            "created_at",
            "id",
        ),
        Index("ix_agents_workspace", "organization_id", "workspace_id"),
        Index("ix_agents_creator", "organization_id", "created_by"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    workspace_id: Mapped[UUID]
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text, default="", server_default="")
    lifecycle_status: Mapped[str] = mapped_column(
        String(20), default="DRAFT", server_default="DRAFT"
    )
    draft_configuration: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_by: Mapped[UUID]
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    organization: Mapped[Organization] = relationship(viewonly=True)
    workspace: Mapped[Workspace] = relationship(viewonly=True)
    versions: Mapped[list["AgentVersion"]] = relationship(
        viewonly=True, order_by="AgentVersion.version_number"
    )
    tool_permissions: Mapped[list["AgentToolPermission"]] = relationship(viewonly=True)


class AgentVersion(Identity, Base):
    __tablename__ = "agent_versions"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_versions_org_id"),
        ForeignKeyConstraint(
            ["organization_id", "agent_definition_id"],
            ["agent_definitions.organization_id", "agent_definitions.id"],
            ondelete="RESTRICT",
            name="fk_versions_agent_scope",
        ),
        ForeignKeyConstraint(
            ["organization_id", "published_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_versions_publisher_membership",
        ),
        UniqueConstraint("agent_definition_id", "version_number", name="uq_versions_agent_number"),
        CheckConstraint("version_number > 0", name="number_positive"),
        CheckConstraint("configuration_schema_version > 0", name="schema_positive"),
        CheckConstraint("jsonb_typeof(configuration_snapshot) = 'object'", name="snapshot_object"),
        Index("ix_versions_org_agent", "organization_id", "agent_definition_id"),
        Index("ix_versions_publisher", "organization_id", "published_by"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    agent_definition_id: Mapped[UUID]
    version_number: Mapped[int]
    configuration_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
    configuration_schema_version: Mapped[int] = mapped_column(
        Integer, default=1, server_default="1"
    )
    published_by: Mapped[UUID]
    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    agent_definition: Mapped[AgentDefinition] = relationship(viewonly=True)


class AgentToolPermission(Identity, Base):
    __tablename__ = "agent_tool_permissions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "agent_definition_id"],
            ["agent_definitions.organization_id", "agent_definitions.id"],
            ondelete="RESTRICT",
            name="fk_tools_agent_scope",
        ),
        UniqueConstraint(
            "organization_id",
            "agent_definition_id",
            "tool_identifier",
            name="uq_tools_agent_identifier",
        ),
        CheckConstraint("tool_identifier ~ '^[a-z][a-z0-9_.-]{0,99}$'", name="identifier"),
        CheckConstraint("status IN ('ACTIVE','REVOKED')", name="status"),
        CheckConstraint("jsonb_typeof(permission_scope) = 'object'", name="scope_object"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    agent_definition_id: Mapped[UUID]
    tool_identifier: Mapped[str] = mapped_column(String(100))
    permission_scope: Mapped[dict[str, Any]] = mapped_column(
        JSONB, default=dict, server_default="{}"
    )
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    agent_definition: Mapped[AgentDefinition] = relationship(viewonly=True)


class AuditEvent(Identity, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_audit_actor_membership",
        ),
        CheckConstraint("jsonb_typeof(metadata) = 'object'", name="metadata_object"),
        CheckConstraint(
            "metadata - ARRAY['revision','version_number','reason_code',"
            "'old_role','new_role']::text[] "
            "= '{}'::jsonb",
            name="metadata_keys",
        ),
        CheckConstraint(
            "NOT(metadata ? 'old_role') OR metadata->'old_role' = 'null'::jsonb OR "
            "metadata->>'old_role' IN ('OWNER','ADMIN','MEMBER','VIEWER')",
            name="old_role",
        ),
        CheckConstraint(
            "NOT(metadata ? 'new_role') OR metadata->'new_role' = 'null'::jsonb OR "
            "metadata->>'new_role' IN ('OWNER','ADMIN','MEMBER','VIEWER')",
            name="new_role",
        ),
        CheckConstraint(
            "NOT(metadata ? 'revision') OR jsonb_typeof(metadata->'revision') = 'number'",
            name="metadata_revision",
        ),
        CheckConstraint(
            "NOT(metadata ? 'version_number') OR "
            "jsonb_typeof(metadata->'version_number') = 'number'",
            name="metadata_version",
        ),
        CheckConstraint(
            "NOT(metadata ? 'reason_code') OR metadata->>'reason_code' IN "
            "('created','changed','published','archived','membership_changed')",
            name="metadata_reason",
        ),
        Index("ix_audit_org_created", "organization_id", "created_at", "id"),
        Index("ix_audit_actor", "organization_id", "actor_user_id"),
        Index("ix_audit_resource", "organization_id", "resource_type", "resource_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(
        ForeignKey("organizations.id", ondelete="RESTRICT")
    )
    actor_user_id: Mapped[UUID]
    action: Mapped[str] = mapped_column(String(100))
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[UUID]
    correlation_id: Mapped[UUID]
    safe_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ORM guard complements the database trigger (bulk/raw SQL is still DB-protected).
from sqlalchemy import event  # noqa: E402

from orqentra.persistence.errors import ForbiddenOperation  # noqa: E402


def _reject_immutable_change(*_: Any) -> None:
    raise ForbiddenOperation("Published versions and audit records are append-only.")


for _model in (AgentVersion, AuditEvent):
    event.listen(_model, "before_update", _reject_immutable_change)
    event.listen(_model, "before_delete", _reject_immutable_change)


class KnowledgeDocument(Identity, Timestamps, Base):
    __tablename__ = "knowledge_documents"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_documents_org_id"),
        UniqueConstraint("organization_id", "workspace_id", "id", name="uq_documents_workspace_id"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("status IN ('ACTIVE','REVOKED')", name="status"),
        CheckConstraint("length(content) BETWEEN 1 AND 24000", name="content_length"),
        CheckConstraint(
            "index_status IN ('PENDING','INDEXING','READY','FAILED')", name="index_status"
        ),
        CheckConstraint("index_attempts BETWEEN 0 AND 3", name="index_attempts"),
        Index("ix_documents_scope", "organization_id", "workspace_id", "status"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    workspace_id: Mapped[UUID]
    title: Mapped[str] = mapped_column(String(200))
    content: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64))
    index_status: Mapped[str] = mapped_column(
        String(20), default="PENDING", server_default="PENDING"
    )
    index_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    index_token: Mapped[UUID | None]
    index_lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    index_error: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", server_default="ACTIVE")


class TaskRun(Identity, Timestamps, Base):
    __tablename__ = "task_runs"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_runs_org_id"),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_runs_idempotency"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "agent_version_id"],
            ["agent_versions.organization_id", "agent_versions.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint(
            "status IN "
            "('QUEUED','RUNNING','NEEDS_CLARIFICATION','AWAITING_REVIEW','APPROVED','"
            "REJECTED','CANCELLED','FAILED')",
            name="status",
        ),
        CheckConstraint("attempts BETWEEN 0 AND 3", name="attempts"),
        CheckConstraint("revision > 0", name="revision_positive"),
        Index("ix_runs_queue", "organization_id", "status", "created_at"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    workspace_id: Mapped[UUID]
    agent_version_id: Mapped[UUID]
    created_by: Mapped[UUID]
    idempotency_key: Mapped[str] = mapped_column(String(100))
    payload_hash: Mapped[str] = mapped_column(String(64))
    request_text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", server_default="QUEUED")
    revision: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    claim_token: Mapped[UUID | None]
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    output: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    source_ids: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    error_code: Mapped[str | None] = mapped_column(String(80))
    usage: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")
    artifact_hash: Mapped[str | None] = mapped_column(String(64))
    review_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ActionReceipt(Identity, Base):
    __tablename__ = "action_receipts"
    __table_args__ = (
        UniqueConstraint("run_id", name="uq_receipts_run"),
        ForeignKeyConstraint(
            ["organization_id", "run_id"],
            ["task_runs.organization_id", "task_runs.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reviewed_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("mode = 'SIMULATED'", name="simulation_only"),
        Index("ix_receipts_org", "organization_id", "created_at"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    run_id: Mapped[UUID]
    reviewed_by: Mapped[UUID]
    artifact_hash: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(20), default="SIMULATED", server_default="SIMULATED")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


for _receipt_model in (ActionReceipt,):
    event.listen(_receipt_model, "before_update", _reject_immutable_change)
    event.listen(_receipt_model, "before_delete", _reject_immutable_change)


class OrganizationInvitation(Identity, Timestamps, Base):
    __tablename__ = "organization_invitations"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_invitations_hash"),
        ForeignKeyConstraint(
            ["organization_id", "created_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("role IN ('MEMBER','VIEWER')", name="role"),
        CheckConstraint("status IN ('PENDING','ACCEPTED','REVOKED')", name="status"),
        Index("ix_invitations_org_status", "organization_id", "status"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    created_by: Mapped[UUID]
    token_hash: Mapped[str] = mapped_column(String(64))
    role: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="PENDING", server_default="PENDING")
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class KnowledgeChunk(Identity, Base):
    __tablename__ = "knowledge_chunks"
    __table_args__ = (
        UniqueConstraint("document_id", "ordinal", name="uq_chunks_document_ordinal"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id", "document_id"],
            [
                "knowledge_documents.organization_id",
                "knowledge_documents.workspace_id",
                "knowledge_documents.id",
            ],
            ondelete="RESTRICT",
        ),
        CheckConstraint("ordinal >= 0", name="ordinal"),
        CheckConstraint("length(content) BETWEEN 1 AND 1600", name="content_length"),
        Index("ix_chunks_scope", "organization_id", "workspace_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    workspace_id: Mapped[UUID]
    document_id: Mapped[UUID]
    ordinal: Mapped[int]
    content: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(Vector(1536))
    embedding_model: Mapped[str] = mapped_column(String(80), default="text-embedding-3-small")


class DemoMember(Identity, Timestamps, Base):
    __tablename__ = "demo_members"
    __table_args__ = (
        UniqueConstraint("organization_id", "email", name="uq_demo_members_email"),
        CheckConstraint("email LIKE '%@example.invalid'", name="fictional_email"),
        CheckConstraint("demo_role IN ('ADMIN','MEMBER','VIEWER')", name="demo_role"),
        Index("ix_demo_members_org", "organization_id"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    display_name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(200))
    job_title: Mapped[str] = mapped_column(String(120))
    demo_role: Mapped[str] = mapped_column(String(20))


class ChatConversation(Identity, Timestamps, Base):
    __tablename__ = "chat_conversations"
    __table_args__ = (
        UniqueConstraint("organization_id", "id", name="uq_chats_org_id"),
        ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            ondelete="RESTRICT",
        ),
        CheckConstraint("support_state IN ('AI','WAITING','HUMAN')", name="support_state"),
        CheckConstraint(
            "(support_state = 'HUMAN' AND assigned_to IS NOT NULL) OR "
            "(support_state IN ('AI','WAITING') AND assigned_to IS NULL)",
            name="support_assignment",
        ),
        ForeignKeyConstraint(
            ["organization_id", "assigned_to"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            ondelete="RESTRICT",
            name="fk_chat_assignee",
        ),
        Index("ix_chats_support", "organization_id", "support_state", "created_at"),
        Index("ix_chats_owner", "organization_id", "created_by", "created_at"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    workspace_id: Mapped[UUID]
    created_by: Mapped[UUID]
    title: Mapped[str] = mapped_column(String(100), default="New knowledge chat")
    support_state: Mapped[str] = mapped_column(String(20), default="AI", server_default="AI")
    assigned_to: Mapped[UUID | None]


class ChatExchange(Identity, Timestamps, Base):
    __tablename__ = "chat_exchanges"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "conversation_id"],
            ["chat_conversations.organization_id", "chat_conversations.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("conversation_id", "idempotency_key", name="uq_chat_exchange_key"),
        CheckConstraint("status IN ('QUEUED','RUNNING','COMPLETED','FAILED')", name="status"),
        CheckConstraint("attempts BETWEEN 0 AND 3", name="attempts"),
        Index("ix_chat_queue", "organization_id", "status", "created_at"),
        Index("ix_chat_history", "organization_id", "conversation_id", "created_at"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    conversation_id: Mapped[UUID]
    idempotency_key: Mapped[str] = mapped_column(String(100))
    question: Mapped[str] = mapped_column(Text)
    answer: Mapped[str] = mapped_column(Text, default="", server_default="")
    citations: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, default=list, server_default="[]"
    )
    status: Mapped[str] = mapped_column(String(20), default="QUEUED", server_default="QUEUED")
    claim_token: Mapped[UUID | None]
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    error_code: Mapped[str | None] = mapped_column(String(80))
    usage: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, server_default="{}")


class HumanChatMessage(Identity, Timestamps, Base):
    __tablename__ = "human_chat_messages"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "conversation_id"],
            ["chat_conversations.organization_id", "chat_conversations.id"],
            ondelete="RESTRICT",
        ),
        ForeignKeyConstraint(
            ["organization_id", "sender_id"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("conversation_id", "idempotency_key", name="uq_human_chat_key"),
        CheckConstraint("sender_role IN ('REQUESTER','SUPPORT')", name="sender_role"),
        CheckConstraint("length(content) BETWEEN 1 AND 4000", name="content_length"),
        Index("ix_human_chat_history", "organization_id", "conversation_id", "created_at"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    conversation_id: Mapped[UUID]
    sender_id: Mapped[UUID]
    sender_role: Mapped[str] = mapped_column(String(20))
    content: Mapped[str] = mapped_column(Text)
    idempotency_key: Mapped[str] = mapped_column(String(100))


class OrganizationSubscription(Identity, Timestamps, Base):
    __tablename__ = "organization_subscriptions"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_subscription_org"),
        UniqueConstraint("organization_id", "id", name="uq_subscription_org_id"),
        UniqueConstraint("provider", "external_id", name="uq_subscription_external"),
        CheckConstraint("provider IN ('disabled','razorpay','stripe')", name="provider"),
        CheckConstraint("mode IN ('disabled','test')", name="mode"),
        CheckConstraint(
            "status IN ('UNAVAILABLE','PENDING','ACTIVE','PAST_DUE','CANCELLED','EXPIRED')",
            name="status",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    provider: Mapped[str] = mapped_column(String(20), default="disabled", server_default="disabled")
    mode: Mapped[str] = mapped_column(String(20), default="disabled", server_default="disabled")
    plan_key: Mapped[str] = mapped_column(
        String(30), default="development", server_default="development"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="UNAVAILABLE", server_default="UNAVAILABLE"
    )
    external_id: Mapped[str | None] = mapped_column(String(100))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    provider_event_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class UsageBucket(Identity, Timestamps, Base):
    __tablename__ = "usage_buckets"
    __table_args__ = (
        UniqueConstraint("organization_id", "metric", "period_start", name="uq_usage_bucket"),
        CheckConstraint("used >= 0", name="used"),
        CheckConstraint("period_end > period_start", name="period"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    metric: Mapped[str] = mapped_column(String(40))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[int] = mapped_column(BigInteger, default=0, server_default="0")


class UsageEvent(Identity, Base):
    __tablename__ = "usage_events"
    __table_args__ = (
        UniqueConstraint("organization_id", "metric", "idempotency_key", name="uq_usage_event"),
        CheckConstraint("amount > 0", name="amount"),
        Index("ix_usage_events_period", "organization_id", "metric", "created_at"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    metric: Mapped[str] = mapped_column(String(40))
    amount: Mapped[int] = mapped_column(BigInteger)
    idempotency_key: Mapped[str] = mapped_column(String(200))
    resource_id: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class BillingWebhookEvent(Identity, Base):
    __tablename__ = "billing_webhook_events"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "subscription_id"],
            ["organization_subscriptions.organization_id", "organization_subscriptions.id"],
            ondelete="RESTRICT",
        ),
        UniqueConstraint("provider", "event_id", name="uq_billing_provider_event"),
        UniqueConstraint("organization_id", "provider", "body_hash", name="uq_billing_body"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    subscription_id: Mapped[UUID]
    provider: Mapped[str] = mapped_column(String(20))
    event_id: Mapped[str] = mapped_column(String(100))
    body_hash: Mapped[str] = mapped_column(String(64))
    result: Mapped[str] = mapped_column(String(20))
    provider_created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


for _billing_immutable in (UsageEvent, BillingWebhookEvent):
    event.listen(_billing_immutable, "before_update", _reject_immutable_change)
    event.listen(_billing_immutable, "before_delete", _reject_immutable_change)


class WorkflowCheckpoint(Identity, Base):
    __tablename__ = "workflow_checkpoints"
    __table_args__ = (
        CheckConstraint("octet_length(payload::text) <= 3000000", name="payload_size"),
        ForeignKeyConstraint(
            ["organization_id", "run_id"], ["task_runs.organization_id", "task_runs.id"]
        ),
        UniqueConstraint(
            "organization_id", "run_id", "namespace", "checkpoint_id", name="uq_workflow_checkpoint"
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    run_id: Mapped[UUID] = mapped_column()
    namespace: Mapped[str] = mapped_column(String(100))
    checkpoint_id: Mapped[str] = mapped_column(String(100))
    parent_id: Mapped[str | None] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class WorkflowWrite(Identity, Base):
    __tablename__ = "workflow_writes"
    __table_args__ = (
        CheckConstraint("octet_length(payload::text) <= 3000000", name="payload_size"),
        ForeignKeyConstraint(
            ["organization_id", "run_id"],
            ["task_runs.organization_id", "task_runs.id"],
            name="fk_workflow_writes_run_scope",
        ),
        UniqueConstraint(
            "organization_id",
            "run_id",
            "namespace",
            "checkpoint_id",
            "task_id",
            "write_index",
            name="uq_workflow_write",
        ),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    run_id: Mapped[UUID] = mapped_column()
    namespace: Mapped[str] = mapped_column(String(100))
    checkpoint_id: Mapped[str] = mapped_column(String(100))
    task_id: Mapped[str] = mapped_column(String(100))
    task_path: Mapped[str] = mapped_column(String(300))
    write_index: Mapped[int] = mapped_column(Integer)
    channel: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB)


event.listen(WorkflowCheckpoint, "before_update", _reject_immutable_change)
event.listen(WorkflowCheckpoint, "before_delete", _reject_immutable_change)


class WorkerRuntime(Identity, Base):
    __tablename__ = "worker_runtime"
    __table_args__ = (UniqueConstraint("organization_id", name="uq_worker_runtime_org"),)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sandbox_available: Mapped[bool] = mapped_column(default=False)


class CodeExecution(Identity, Timestamps, Base):
    __tablename__ = "code_executions"
    __table_args__ = (
        ForeignKeyConstraint(
            ["organization_id", "run_id"], ["task_runs.organization_id", "task_runs.id"]
        ),
        ForeignKeyConstraint(
            ["organization_id", "created_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            name="fk_code_creator",
        ),
        ForeignKeyConstraint(
            ["organization_id", "reviewed_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            name="fk_code_reviewer",
        ),
        UniqueConstraint("organization_id", "idempotency_key", name="uq_code_execution_request"),
        CheckConstraint(
            "status IN ('AWAITING_REVIEW','APPROVED','REJECTED','QUEUED','RUNNING',"
            "'COMPLETED','FAILED','UNKNOWN','CANCELLED')",
            name="status",
        ),
        CheckConstraint(
            "reviewed_by IS NULL OR reviewed_by <> created_by", name="independent_review"
        ),
        CheckConstraint("octet_length(code) BETWEEN 1 AND 16384", name="code_size"),
        CheckConstraint("octet_length(output) <= 8192", name="output_size"),
        Index("ix_code_queue", "organization_id", "status", "created_at"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    run_id: Mapped[UUID]
    created_by: Mapped[UUID]
    reviewed_by: Mapped[UUID | None]
    idempotency_key: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(200))
    code: Mapped[str] = mapped_column(Text)
    code_hash: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(30), default="AWAITING_REVIEW")
    revision: Mapped[int] = mapped_column(default=1)
    approval_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    claim_token: Mapped[UUID | None]
    lease_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(80))
    external_sandbox_id: Mapped[str | None] = mapped_column(String(200))
    output: Mapped[str] = mapped_column(Text, default="", server_default="")


class BillingOperation(Identity, Timestamps, Base):
    __tablename__ = "billing_operations"
    __table_args__ = (
        UniqueConstraint("organization_id", "idempotency_key", name="uq_billing_operation_key"),
        CheckConstraint("kind IN ('CHECKOUT','CANCEL')", name="kind"),
        CheckConstraint("status IN ('CREATING','READY','UNKNOWN','FAILED')", name="status"),
        CheckConstraint("mode = 'test'", name="mode"),
        ForeignKeyConstraint(
            ["organization_id", "created_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
        ),
        Index("ix_billing_operations_history", "organization_id", "created_at"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    created_by: Mapped[UUID]
    idempotency_key: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="CREATING")
    provider: Mapped[str] = mapped_column(String(20), default="razorpay")
    mode: Mapped[str] = mapped_column(String(10), default="test")
    plan_key: Mapped[str] = mapped_column(String(30))
    external_id: Mapped[str | None] = mapped_column(String(100))
    hosted_url: Mapped[str | None] = mapped_column(String(2048))
    request_snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error_code: Mapped[str | None] = mapped_column(String(80))


class BillingSnapshot(Identity, Base):
    __tablename__ = "billing_snapshots"
    __table_args__ = (Index("ix_billing_snapshot_history", "organization_id", "created_at"),)
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    external_id: Mapped[str] = mapped_column(String(100))
    plan_key: Mapped[str] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(20))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    source: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class InvoiceSnapshot(Identity, Base):
    __tablename__ = "invoice_snapshots"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "external_id", "content_hash", name="uq_invoice_snapshot"
        ),
        Index("ix_invoice_snapshot_history", "organization_id", "created_at"),
    )
    organization_id: Mapped[UUID] = mapped_column(ForeignKey("organizations.id"))
    external_id: Mapped[str] = mapped_column(String(100))
    subscription_external_id: Mapped[str] = mapped_column(String(100))
    content_hash: Mapped[str] = mapped_column(String(64))
    document: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


for _financial in (BillingSnapshot, InvoiceSnapshot):
    event.listen(_financial, "before_update", _reject_immutable_change)
    event.listen(_financial, "before_delete", _reject_immutable_change)
