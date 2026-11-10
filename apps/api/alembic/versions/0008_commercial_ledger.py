"""Tenant subscription state, atomic quota buckets and immutable usage/webhook receipts."""

import sqlalchemy as sa

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def identity() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
    ]


def created() -> sa.Column:
    return sa.Column(
        "created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def updated() -> sa.Column:
    return sa.Column(
        "updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False
    )


def upgrade() -> None:
    op.create_table(
        "organization_subscriptions",
        *identity(),
        created(),
        updated(),
        sa.Column("provider", sa.String(20), server_default="disabled", nullable=False),
        sa.Column("mode", sa.String(20), server_default="disabled", nullable=False),
        sa.Column("plan_key", sa.String(30), server_default="development", nullable=False),
        sa.Column("status", sa.String(20), server_default="UNAVAILABLE", nullable=False),
        sa.Column("external_id", sa.String(100), nullable=True),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("provider_event_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organization_id", name="uq_subscription_org"),
        sa.UniqueConstraint("organization_id", "id", name="uq_subscription_org_id"),
        sa.UniqueConstraint("provider", "external_id", name="uq_subscription_external"),
        sa.CheckConstraint("provider IN ('disabled','razorpay','stripe')", name="provider"),
        sa.CheckConstraint("mode IN ('disabled','test')", name="mode"),
        sa.CheckConstraint(
            "status IN ('UNAVAILABLE','PENDING','ACTIVE','PAST_DUE','CANCELLED','EXPIRED')",
            name="status",
        ),
    )
    op.create_table(
        "usage_buckets",
        *identity(),
        created(),
        updated(),
        sa.Column("metric", sa.String(40), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.BigInteger(), server_default="0", nullable=False),
        sa.UniqueConstraint("organization_id", "metric", "period_start", name="uq_usage_bucket"),
        sa.CheckConstraint("used >= 0", name="used"),
        sa.CheckConstraint("period_end > period_start", name="period"),
    )
    op.create_table(
        "usage_events",
        *identity(),
        created(),
        sa.Column("metric", sa.String(40), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("idempotency_key", sa.String(200), nullable=False),
        sa.Column("resource_id", sa.Uuid(), nullable=False),
        sa.UniqueConstraint("organization_id", "metric", "idempotency_key", name="uq_usage_event"),
        sa.CheckConstraint("amount > 0", name="amount"),
    )
    op.create_index(
        "ix_usage_events_period", "usage_events", ["organization_id", "metric", "created_at"]
    )
    op.create_table(
        "billing_webhook_events",
        *identity(),
        created(),
        sa.Column("subscription_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("event_id", sa.String(100), nullable=False),
        sa.Column("body_hash", sa.String(64), nullable=False),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("provider_created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "subscription_id"],
            ["organization_subscriptions.organization_id", "organization_subscriptions.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("provider", "event_id", name="uq_billing_provider_event"),
        sa.UniqueConstraint("organization_id", "provider", "body_hash", name="uq_billing_body"),
    )
    scope = "organization_id = NULLIF(current_setting('app.organization_id',true),'')::uuid"
    for table in (
        "organization_subscriptions",
        "usage_buckets",
        "usage_events",
        "billing_webhook_events",
    ):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_scope ON {table} USING ({scope}) WITH CHECK ({scope})")
        if table in ("organization_subscriptions", "usage_buckets"):
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
    for table in (
        "billing_webhook_events",
        "usage_events",
        "usage_buckets",
        "organization_subscriptions",
    ):
        op.drop_table(table)
