"""Vector chunks, private chat histories and non-authenticating demo roster."""

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def base_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
    ]


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
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.add_column(
        "knowledge_documents",
        sa.Column("index_status", sa.String(20), server_default="PENDING", nullable=False),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("index_attempts", sa.Integer(), server_default="0", nullable=False),
    )
    op.add_column("knowledge_documents", sa.Column("index_token", sa.Uuid(), nullable=True))
    op.add_column(
        "knowledge_documents",
        sa.Column("index_lease_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column("knowledge_documents", sa.Column("index_error", sa.String(80), nullable=True))
    op.create_check_constraint(
        "index_status",
        "knowledge_documents",
        "index_status IN ('PENDING','INDEXING','READY','FAILED')",
    )
    op.create_check_constraint(
        "index_attempts", "knowledge_documents", "index_attempts BETWEEN 0 AND 3"
    )
    op.create_unique_constraint(
        "uq_documents_workspace_id",
        "knowledge_documents",
        ["organization_id", "workspace_id", "id"],
    )
    op.create_table(
        "knowledge_chunks",
        *base_columns(),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("document_id", sa.Uuid(), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(1536), nullable=False),
        sa.Column("embedding_model", sa.String(80), nullable=False),
        sa.UniqueConstraint("document_id", "ordinal", name="uq_chunks_document_ordinal"),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id", "document_id"],
            [
                "knowledge_documents.organization_id",
                "knowledge_documents.workspace_id",
                "knowledge_documents.id",
            ],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("ordinal >= 0", name="ordinal"),
        sa.CheckConstraint("length(content) BETWEEN 1 AND 1600", name="content_length"),
    )
    op.create_index("ix_chunks_scope", "knowledge_chunks", ["organization_id", "workspace_id"])
    op.create_table(
        "demo_members",
        *base_columns(),
        *timestamps(),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("email", sa.String(200), nullable=False),
        sa.Column("job_title", sa.String(120), nullable=False),
        sa.Column("demo_role", sa.String(20), nullable=False),
        sa.UniqueConstraint("organization_id", "email", name="uq_demo_members_email"),
        sa.CheckConstraint("email LIKE '%@example.invalid'", name="fictional_email"),
        sa.CheckConstraint("demo_role IN ('ADMIN','MEMBER','VIEWER')", name="demo_role"),
    )
    op.create_index("ix_demo_members_org", "demo_members", ["organization_id"])
    op.create_table(
        "chat_conversations",
        *base_columns(),
        *timestamps(),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(100), nullable=False),
        sa.UniqueConstraint("organization_id", "id", name="uq_chats_org_id"),
        sa.ForeignKeyConstraint(
            ["organization_id", "workspace_id"],
            ["workspaces.organization_id", "workspaces.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            ondelete="RESTRICT",
        ),
    )
    op.create_index(
        "ix_chats_owner", "chat_conversations", ["organization_id", "created_by", "created_at"]
    )
    op.create_table(
        "chat_exchanges",
        *base_columns(),
        *timestamps(),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("answer", sa.Text(), server_default="", nullable=False),
        sa.Column("citations", JSONB, server_default="[]", nullable=False),
        sa.Column("status", sa.String(20), server_default="QUEUED", nullable=False),
        sa.Column("claim_token", sa.Uuid(), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_code", sa.String(80), nullable=True),
        sa.Column("usage", JSONB, server_default="{}", nullable=False),
        sa.ForeignKeyConstraint(
            ["organization_id", "conversation_id"],
            ["chat_conversations.organization_id", "chat_conversations.id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("conversation_id", "idempotency_key", name="uq_chat_exchange_key"),
        sa.CheckConstraint("status IN ('QUEUED','RUNNING','COMPLETED','FAILED')", name="status"),
        sa.CheckConstraint("attempts BETWEEN 0 AND 3", name="attempts"),
    )
    op.create_index("ix_chat_queue", "chat_exchanges", ["organization_id", "status", "created_at"])
    op.create_index(
        "ix_chat_history", "chat_exchanges", ["organization_id", "conversation_id", "created_at"]
    )
    for table in ("knowledge_chunks", "demo_members", "chat_conversations", "chat_exchanges"):
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        scope = "organization_id = NULLIF(current_setting('app.organization_id',true),'')::uuid"
        op.execute(f"CREATE POLICY tenant_scope ON {table} USING ({scope}) WITH CHECK ({scope})")
        if table != "knowledge_chunks":
            op.execute(
                f"CREATE TRIGGER touch_updated_at BEFORE UPDATE ON {table} "
                "FOR EACH ROW EXECUTE FUNCTION orqentra_update_timestamp()"
            )


def downgrade() -> None:
    for table in ("chat_exchanges", "chat_conversations", "demo_members", "knowledge_chunks"):
        op.drop_table(table)
    op.drop_constraint("uq_documents_workspace_id", "knowledge_documents", type_="unique")
    for name in ("index_status", "index_attempts"):
        op.drop_constraint(
            op.f("ck_knowledge_documents_" + name), "knowledge_documents", type_="check"
        )
    for name in (
        "index_status",
        "index_attempts",
        "index_token",
        "index_lease_until",
        "index_error",
    ):
        op.drop_column("knowledge_documents", name)
    # Extension retained: never remove another application's vector dependency.
