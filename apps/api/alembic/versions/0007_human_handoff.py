"""Explicit tenant-scoped human support handoff; preserve private AI chat."""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_conversations",
        sa.Column("support_state", sa.String(20), nullable=False, server_default="AI"),
    )
    op.add_column("chat_conversations", sa.Column("assigned_to", sa.Uuid(), nullable=True))
    op.create_check_constraint(
        "support_state", "chat_conversations", "support_state IN ('AI','WAITING','HUMAN')"
    )
    op.create_check_constraint(
        "support_assignment",
        "chat_conversations",
        "(support_state = 'HUMAN' AND assigned_to IS NOT NULL) OR "
        "(support_state IN ('AI','WAITING') AND assigned_to IS NULL)",
    )
    op.create_foreign_key(
        "fk_chat_assignee",
        "chat_conversations",
        "organization_memberships",
        ["organization_id", "assigned_to"],
        ["organization_id", "user_id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_chats_support", "chat_conversations", ["organization_id", "support_state", "created_at"]
    )
    op.create_table(
        "human_chat_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("sender_id", sa.Uuid(), nullable=False),
        sa.Column("sender_role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(100), nullable=False),
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
            ["organization_id", "conversation_id"],
            ["chat_conversations.organization_id", "chat_conversations.id"],
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["organization_id", "sender_id"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("conversation_id", "idempotency_key", name="uq_human_chat_key"),
        sa.CheckConstraint("sender_role IN ('REQUESTER','SUPPORT')", name="sender_role"),
        sa.CheckConstraint("length(content) BETWEEN 1 AND 4000", name="content_length"),
    )
    op.create_index(
        "ix_human_chat_history",
        "human_chat_messages",
        ["organization_id", "conversation_id", "created_at"],
    )
    op.execute("ALTER TABLE human_chat_messages ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE human_chat_messages FORCE ROW LEVEL SECURITY")
    scope = "organization_id = NULLIF(current_setting('app.organization_id',true),'')::uuid"
    op.execute(
        f"CREATE POLICY tenant_scope ON human_chat_messages USING ({scope}) WITH CHECK ({scope})"
    )
    op.execute(
        "CREATE TRIGGER touch_updated_at BEFORE UPDATE ON human_chat_messages "
        "FOR EACH ROW EXECUTE FUNCTION orqentra_update_timestamp()"
    )


def downgrade() -> None:
    op.drop_table("human_chat_messages")
    op.drop_index("ix_chats_support", "chat_conversations")
    op.drop_constraint("fk_chat_assignee", "chat_conversations", type_="foreignkey")
    op.drop_constraint(
        op.f("ck_chat_conversations_support_state"), "chat_conversations", type_="check"
    )
    op.drop_constraint(
        op.f("ck_chat_conversations_support_assignment"), "chat_conversations", type_="check"
    )
    op.drop_column("chat_conversations", "assigned_to")
    op.drop_column("chat_conversations", "support_state")
