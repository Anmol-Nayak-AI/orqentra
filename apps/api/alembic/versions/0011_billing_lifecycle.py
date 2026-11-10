"""Durable provider operations, reconciliation history and invoice snapshots."""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def identity():
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
    ]


def created():
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "billing_operations",
        *identity(),
        created(),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("plan_key", sa.String(30), nullable=False),
        sa.Column("external_id", sa.String(100)),
        sa.Column("hosted_url", sa.String(2048)),
        sa.Column("request_snapshot", JSONB(), nullable=False),
        sa.Column("error_code", sa.String(80)),
        sa.UniqueConstraint("organization_id", "idempotency_key", name="uq_billing_operation_key"),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
        ),
        sa.CheckConstraint("kind IN ('CHECKOUT','CANCEL')", name="kind"),
        sa.CheckConstraint("status IN ('CREATING','READY','UNKNOWN','FAILED')", name="status"),
        sa.CheckConstraint("mode = 'test'", name="mode"),
    )
    op.create_table(
        "billing_snapshots",
        *identity(),
        created(),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("plan_key", sa.String(30), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True)),
        sa.Column("source", sa.String(30), nullable=False),
    )
    op.create_table(
        "invoice_snapshots",
        *identity(),
        created(),
        sa.Column("external_id", sa.String(100), nullable=False),
        sa.Column("subscription_external_id", sa.String(100), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("document", JSONB(), nullable=False),
        sa.UniqueConstraint(
            "organization_id", "external_id", "content_hash", name="uq_invoice_snapshot"
        ),
    )
    op.create_index(
        "ix_billing_operations_history", "billing_operations", ["organization_id", "created_at"]
    )
    op.create_index(
        "ix_billing_snapshot_history", "billing_snapshots", ["organization_id", "created_at"]
    )
    op.create_index(
        "ix_invoice_snapshot_history", "invoice_snapshots", ["organization_id", "created_at"]
    )
    for table in ("billing_operations", "billing_snapshots", "invoice_snapshots"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        scope = "organization_id = NULLIF(current_setting('app.organization_id',true),'')::uuid"
        op.execute(f"CREATE POLICY tenant_scope ON {table} USING ({scope}) WITH CHECK ({scope})")
        if table == "billing_operations":
            op.execute(
                f"CREATE TRIGGER touch_updated_at BEFORE UPDATE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION orqentra_update_timestamp()"
            )
        else:
            op.execute(
                f"CREATE TRIGGER immutable_rows BEFORE UPDATE OR DELETE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION orqentra_reject_mutation()"
            )
            op.execute(
                f"CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON {table} "
                "FOR EACH STATEMENT EXECUTE FUNCTION orqentra_reject_mutation()"
            )


def downgrade() -> None:
    bind = op.get_bind()
    for table in ("invoice_snapshots", "billing_snapshots", "billing_operations"):
        if bind.scalar(sa.text(f"SELECT count(*) FROM {table}")):
            raise RuntimeError("Use forward recovery: financial history must be retained.")
    for table in ("invoice_snapshots", "billing_snapshots", "billing_operations"):
        op.drop_table(table)
