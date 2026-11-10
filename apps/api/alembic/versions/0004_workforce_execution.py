"""Tenant-scoped knowledge, durable tasks and immutable simulated receipts."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def timestamps() -> list[sa.Column]:
    return [
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
    ]


def upgrade() -> None:
    op.create_unique_constraint("uq_versions_org_id", "agent_versions", ["organization_id", "id"])
    op.create_table(
        "knowledge_documents",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(20), server_default="ACTIVE", nullable=False),
        *timestamps(),
        sa.UniqueConstraint("organization_id", "id", name="uq_documents_org_id"),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("status IN ('ACTIVE','REVOKED')", name="status"),
        sa.CheckConstraint("length(content) BETWEEN 1 AND 24000", name="content_length"),
    )
    op.create_index(
        "ix_documents_scope", "knowledge_documents", ["organization_id", "workspace_id", "status"]
    )
    op.create_table(
        "task_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("agent_version_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("request_text", sa.Text(), nullable=False),
        sa.Column("status", sa.String(30), server_default="QUEUED", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("claim_token", sa.Uuid(), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("output", JSONB, server_default="{}", nullable=False),
        sa.Column("source_ids", JSONB, server_default="[]", nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("usage", JSONB, server_default="{}", nullable=False),
        sa.Column("artifact_hash", sa.String(64), nullable=True),
        sa.Column("review_expires_at", sa.DateTime(timezone=True), nullable=True),
        *timestamps(),
        sa.UniqueConstraint("organization_id", "id", name="uq_runs_org_id"),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_runs_idempotency"),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "agent_version_id"],
            ["agent_versions.organization_id", "agent_versions.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            "status IN "
            "('QUEUED','RUNNING','NEEDS_CLARIFICATION','AWAITING_REVIEW','APPROVED','"
            "REJECTED','CANCELLED','FAILED')",
            name="status",
        ),
        sa.CheckConstraint("attempts BETWEEN 0 AND 3", name="attempts"),
        sa.CheckConstraint("revision > 0", name="revision_positive"),
    )
    op.create_index("ix_runs_queue", "task_runs", ["organization_id", "status", "created_at"])
    op.create_table(
        "action_receipts",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=False),
        sa.Column("artifact_hash", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(20), server_default="SIMULATED", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.UniqueConstraint("run_id", name="uq_receipts_run"),
        sa.ForeignKeyConstraint(
            ["organization_id", "run_id"],
            ["task_runs.organization_id", "task_runs.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "reviewed_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("mode = 'SIMULATED'", name="simulation_only"),
    )
    op.create_index("ix_receipts_org", "action_receipts", ["organization_id", "created_at"])
    for table in ("knowledge_documents", "task_runs", "action_receipts"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        scope = "organization_id = NULLIF(current_setting('app.organization_id',true),'')::uuid"
        op.execute(f"CREATE POLICY tenant_scope ON {table} USING ({scope}) WITH CHECK ({scope})")
    for table in ("knowledge_documents", "task_runs"):
        op.execute(
            f"CREATE TRIGGER touch_updated_at BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION orqentra_update_timestamp()"
        )
    for operation in ("UPDATE OR DELETE", "TRUNCATE"):
        name = "immutable_rows" if operation != "TRUNCATE" else "immutable_truncate"
        level = "ROW" if operation != "TRUNCATE" else "STATEMENT"
        op.execute(
            f"CREATE TRIGGER {name} BEFORE {operation} ON action_receipts "
            f"FOR EACH {level} EXECUTE FUNCTION orqentra_reject_mutation()"
        )


def downgrade() -> None:
    # Never used on the development database; explicit operator-only rollback.
    op.drop_table("action_receipts")
    op.drop_table("task_runs")
    op.drop_table("knowledge_documents")
    op.drop_constraint("uq_versions_org_id", "agent_versions", type_="unique")
