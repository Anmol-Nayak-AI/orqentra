"""Code-specific approvals and worker availability; no execution in migrations."""

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # LangGraph may commit pending writes before their checkpoint. Retain the
    # tenant/run FK, without imposing an ordering the checkpointer does not promise.
    op.drop_constraint(
        "fk_workflow_writes_organization_id_workflow_checkpoints",
        "workflow_writes",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "fk_workflow_writes_run_scope",
        "workflow_writes",
        "task_runs",
        ["organization_id", "run_id"],
        ["organization_id", "id"],
    )
    op.create_table(
        "worker_runtime",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("last_seen", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sandbox_available", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("organization_id", name="uq_worker_runtime_org"),
    )
    op.create_table(
        "code_executions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("code_hash", sa.String(64), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.Column("approval_expires_at", sa.DateTime(timezone=True)),
        sa.Column("claim_token", sa.Uuid()),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.Column("error_code", sa.String(80)),
        sa.Column("external_sandbox_id", sa.String(200)),
        sa.Column("output", sa.Text(), nullable=False, server_default=""),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "run_id"], ["task_runs.organization_id", "task_runs.id"]
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            name="fk_code_creator",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "reviewed_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            name="fk_code_reviewer",
        ),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_code_execution_request"),
        sa.CheckConstraint(
            "status IN ('AWAITING_REVIEW','APPROVED','REJECTED','QUEUED','RUNNING',"
            "'COMPLETED','FAILED','UNKNOWN','CANCELLED')",
            name="status",
        ),
        sa.CheckConstraint(
            "reviewed_by IS NULL OR reviewed_by <> created_by", name="independent_review"
        ),
        sa.CheckConstraint("octet_length(code) BETWEEN 1 AND 16384", name="code_size"),
        sa.CheckConstraint("octet_length(output) <= 8192", name="output_size"),
    )
    op.create_index("ix_code_queue", "code_executions", ["organization_id", "status", "created_at"])
    op.execute(
        "CREATE TRIGGER touch_updated_at BEFORE UPDATE ON code_executions "
        "FOR EACH ROW EXECUTE FUNCTION orqentra_update_timestamp()"
    )
    for table in ("worker_runtime", "code_executions"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        scope = "organization_id = NULLIF(current_setting('app.organization_id',true),'')::uuid"
        op.execute(f"CREATE POLICY tenant_scope ON {table} USING ({scope}) WITH CHECK ({scope})")


def downgrade() -> None:
    # Reversibility is supported for empty disposable fixtures, never data-discarding rollback.
    bind = op.get_bind()
    if any(
        bind.scalar(sa.text(f"SELECT count(*) FROM {table}"))
        for table in ("code_executions", "worker_runtime")
    ):
        raise RuntimeError("Use forward recovery: code reviews or worker records exist.")
    staged = bind.scalar(
        sa.text(
            "SELECT count(*) FROM workflow_writes w WHERE NOT EXISTS ("
            "SELECT 1 FROM workflow_checkpoints c WHERE c.organization_id=w.organization_id "
            "AND c.run_id=w.run_id AND c.namespace=w.namespace AND c.checkpoint_id=w.checkpoint_id)"
        )
    )
    if staged:
        raise RuntimeError("Use forward recovery: staged writes must be preserved.")
    op.drop_table("code_executions")
    op.drop_table("worker_runtime")
    op.drop_constraint("fk_workflow_writes_run_scope", "workflow_writes", type_="foreignkey")
    op.create_foreign_key(
        "fk_workflow_writes_organization_id_workflow_checkpoints",
        "workflow_writes",
        "workflow_checkpoints",
        ["organization_id", "run_id", "namespace", "checkpoint_id"],
        ["organization_id", "run_id", "namespace", "checkpoint_id"],
    )
