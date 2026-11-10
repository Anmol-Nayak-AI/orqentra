"""tenant foundation tables

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Reviewed additive schema; no preexisting table is altered.
    op.create_table(
        "organizations",
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name=op.f("ck_organizations_slug_normalized")
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','SUSPENDED','ARCHIVED')", name=op.f("ck_organizations_status")
        ),
        sa.CheckConstraint("length(trim(name)) > 0", name=op.f("ck_organizations_name_nonempty")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organizations")),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )
    op.create_table(
        "users",
        sa.Column("external_auth_id", sa.String(length=255), nullable=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint("status IN ('ACTIVE','DISABLED')", name=op.f("ck_users_status")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("external_auth_id", name="uq_users_external_auth_id"),
    )
    op.create_table(
        "organization_memberships",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "role IN ('OWNER','ADMIN','MEMBER','VIEWER')",
            name=op.f("ck_organization_memberships_role"),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','INVITED','REVOKED')",
            name=op.f("ck_organization_memberships_status"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_organization_memberships_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_organization_memberships_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_organization_memberships")),
        sa.UniqueConstraint("organization_id", "user_id", name="uq_memberships_org_user"),
    )
    op.create_index("ix_memberships_user", "organization_memberships", ["user_id"], unique=False)
    op.create_table(
        "workspaces",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name=op.f("ck_workspaces_slug_normalized")
        ),
        sa.CheckConstraint("status IN ('ACTIVE','ARCHIVED')", name=op.f("ck_workspaces_status")),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_workspaces_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_workspaces")),
        sa.UniqueConstraint("organization_id", "id", name="uq_workspaces_org_id"),
        sa.UniqueConstraint("organization_id", "slug", name="uq_workspaces_org_slug"),
    )
    op.create_table(
        "agent_definitions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("lifecycle_status", sa.String(length=20), server_default="DRAFT", nullable=False),
        sa.Column(
            "draft_configuration",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(lifecycle_status = 'ARCHIVED') = (archived_at IS NOT NULL)",
            name=op.f("ck_agent_definitions_archive_consistent"),
        ),
        sa.CheckConstraint(
            "jsonb_typeof(draft_configuration) = 'object'",
            name=op.f("ck_agent_definitions_draft_object"),
        ),
        sa.CheckConstraint(
            "lifecycle_status IN ('DRAFT','PUBLISHED','ARCHIVED')",
            name=op.f("ck_agent_definitions_lifecycle"),
        ),
        sa.CheckConstraint(
            "slug ~ '^[a-z0-9]+(-[a-z0-9]+)*$'", name=op.f("ck_agent_definitions_slug_normalized")
        ),
        sa.CheckConstraint("revision > 0", name=op.f("ck_agent_definitions_revision_positive")),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            name="fk_agents_creator_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            name="fk_agents_workspace_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_agent_definitions_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_definitions")),
        sa.UniqueConstraint("organization_id", "id", name="uq_agents_org_id"),
        sa.UniqueConstraint(
            "organization_id", "workspace_id", "slug", name="uq_agents_workspace_slug"
        ),
    )
    op.create_index(
        "ix_agents_creator", "agent_definitions", ["organization_id", "created_by"], unique=False
    )
    op.create_index(
        "ix_agents_org_lifecycle_created",
        "agent_definitions",
        ["organization_id", "lifecycle_status", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_agents_workspace",
        "agent_definitions",
        ["organization_id", "workspace_id"],
        unique=False,
    )
    op.create_table(
        "audit_events",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("resource_type", sa.String(length=80), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.Column("correlation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "metadata", postgresql.JSONB(astext_type=sa.Text()), server_default="{}", nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(metadata) = 'object'", name=op.f("ck_audit_events_metadata_object")
        ),
        sa.CheckConstraint(
            "metadata - ARRAY['revision','version_number','reason_code']::text[] = '{}'::jsonb",
            name=op.f("ck_audit_events_metadata_keys"),
        ),
        sa.CheckConstraint(
            "NOT(metadata ? 'revision') OR jsonb_typeof(metadata->'revision') = 'number'",
            name=op.f("ck_audit_events_metadata_revision"),
        ),
        sa.CheckConstraint(
            "NOT(metadata ? 'version_number') OR "
            "jsonb_typeof(metadata->'version_number') = 'number'",
            name=op.f("ck_audit_events_metadata_version"),
        ),
        sa.CheckConstraint(
            "NOT(metadata ? 'reason_code') OR metadata->>'reason_code' IN "
            "('created','changed','published','archived','membership_changed')",
            name=op.f("ck_audit_events_metadata_reason"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "actor_user_id"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            name="fk_audit_actor_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_audit_events_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_audit_events")),
    )
    op.create_index(
        "ix_audit_actor", "audit_events", ["organization_id", "actor_user_id"], unique=False
    )
    op.create_index(
        "ix_audit_org_created",
        "audit_events",
        ["organization_id", "created_at", "id"],
        unique=False,
    )
    op.create_index(
        "ix_audit_resource",
        "audit_events",
        ["organization_id", "resource_type", "resource_id"],
        unique=False,
    )
    op.create_table(
        "agent_tool_permissions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("agent_definition_id", sa.Uuid(), nullable=False),
        sa.Column("tool_identifier", sa.String(length=100), nullable=False),
        sa.Column(
            "permission_scope",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("status", sa.String(length=20), server_default="ACTIVE", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(permission_scope) = 'object'",
            name=op.f("ck_agent_tool_permissions_scope_object"),
        ),
        sa.CheckConstraint(
            "status IN ('ACTIVE','REVOKED')", name=op.f("ck_agent_tool_permissions_status")
        ),
        sa.CheckConstraint(
            "tool_identifier ~ '^[a-z][a-z0-9_.-]{0,99}$'",
            name=op.f("ck_agent_tool_permissions_identifier"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "agent_definition_id"],
            ["agent_definitions.organization_id", "agent_definitions.id"],
            name="fk_tools_agent_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_agent_tool_permissions_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_tool_permissions")),
        sa.UniqueConstraint(
            "organization_id",
            "agent_definition_id",
            "tool_identifier",
            name="uq_tools_agent_identifier",
        ),
    )
    op.create_table(
        "agent_versions",
        sa.Column("organization_id", sa.Uuid(), nullable=False),
        sa.Column("agent_definition_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column(
            "configuration_snapshot", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("configuration_schema_version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("published_by", sa.Uuid(), nullable=False),
        sa.Column(
            "published_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "jsonb_typeof(configuration_snapshot) = 'object'",
            name=op.f("ck_agent_versions_snapshot_object"),
        ),
        sa.CheckConstraint(
            "configuration_schema_version > 0", name=op.f("ck_agent_versions_schema_positive")
        ),
        sa.CheckConstraint("version_number > 0", name=op.f("ck_agent_versions_number_positive")),
        sa.ForeignKeyConstraint(
            ["organization_id", "agent_definition_id"],
            ["agent_definitions.organization_id", "agent_definitions.id"],
            name="fk_versions_agent_scope",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "published_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            name="fk_versions_publisher_membership",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id"],
            ["organizations.id"],
            name=op.f("fk_agent_versions_organization_id_organizations"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_agent_versions")),
        sa.UniqueConstraint(
            "agent_definition_id", "version_number", name="uq_versions_agent_number"
        ),
    )
    op.create_index(
        "ix_versions_org_agent",
        "agent_versions",
        ["organization_id", "agent_definition_id"],
        unique=False,
    )
    op.create_index(
        "ix_versions_publisher", "agent_versions", ["organization_id", "published_by"], unique=False
    )


def downgrade() -> None:
    # Destructive reversal: disposable migration-test databases only.
    op.drop_index("ix_versions_publisher", table_name="agent_versions")
    op.drop_index("ix_versions_org_agent", table_name="agent_versions")
    op.drop_table("agent_versions")
    op.drop_table("agent_tool_permissions")
    op.drop_index("ix_audit_resource", table_name="audit_events")
    op.drop_index("ix_audit_org_created", table_name="audit_events")
    op.drop_index("ix_audit_actor", table_name="audit_events")
    op.drop_table("audit_events")
    op.drop_index("ix_agents_workspace", table_name="agent_definitions")
    op.drop_index("ix_agents_org_lifecycle_created", table_name="agent_definitions")
    op.drop_index("ix_agents_creator", table_name="agent_definitions")
    op.drop_table("agent_definitions")
    op.drop_table("workspaces")
    op.drop_index("ix_memberships_user", table_name="organization_memberships")
    op.drop_table("organization_memberships")
    op.drop_table("users")
    op.drop_table("organizations")
