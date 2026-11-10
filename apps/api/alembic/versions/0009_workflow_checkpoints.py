"""Tenant-scoped LangGraph checkpoints; existing task and approval records are preserved."""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "workflow_checkpoints",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("namespace", sa.String(100), nullable=False),
        sa.Column("checkpoint_id", sa.String(100), nullable=False),
        sa.Column("parent_id", sa.String(100)),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("octet_length(payload::text) <= 3000000", name="payload_size"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "run_id"], ["task_runs.organization_id", "task_runs.id"]
        ),
        sa.UniqueConstraint(
            "organization_id", "run_id", "namespace", "checkpoint_id", name="uq_workflow_checkpoint"
        ),
    )
    op.create_table(
        "workflow_writes",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("namespace", sa.String(100), nullable=False),
        sa.Column("checkpoint_id", sa.String(100), nullable=False),
        sa.Column("task_id", sa.String(100), nullable=False),
        sa.Column("task_path", sa.String(300), nullable=False),
        sa.Column("write_index", sa.Integer(), nullable=False),
        sa.Column("channel", sa.String(100), nullable=False),
        sa.Column("payload", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.CheckConstraint("octet_length(payload::text) <= 3000000", name="payload_size"),
        sa.ForeignKeyConstraint(
            ["organization_id", "run_id", "namespace", "checkpoint_id"],
            [
                "workflow_checkpoints.organization_id",
                "workflow_checkpoints.run_id",
                "workflow_checkpoints.namespace",
                "workflow_checkpoints.checkpoint_id",
            ],
        ),
        sa.UniqueConstraint(
            "organization_id",
            "run_id",
            "namespace",
            "checkpoint_id",
            "task_id",
            "write_index",
            name="uq_workflow_write",
        ),
    )
    for table in ("workflow_checkpoints", "workflow_writes"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        scope = "organization_id = NULLIF(current_setting('app.organization_id',true),'')::uuid"
        op.execute(f"CREATE POLICY tenant_scope ON {table} USING ({scope}) WITH CHECK ({scope})")
    op.execute(
        "CREATE TRIGGER immutable_rows BEFORE UPDATE OR DELETE ON workflow_checkpoints "
        "FOR EACH ROW EXECUTE FUNCTION orqentra_reject_mutation()"
    )
    op.execute(
        "CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON workflow_checkpoints "
        "FOR EACH STATEMENT EXECUTE FUNCTION orqentra_reject_mutation()"
    )


def downgrade() -> None:
    op.drop_table("workflow_writes")
    op.drop_table("workflow_checkpoints")
