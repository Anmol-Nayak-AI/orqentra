"""Single-use, expiring member/viewer invitation capabilities."""

import sqlalchemy as sa

from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("organization_id", sa.Uuid(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), server_default="PENDING", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
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
        sa.UniqueConstraint("token_hash", name="uq_invitations_hash"),
        sa.ForeignKeyConstraint(
            ["organization_id", "created_by"],
            ["organization_memberships.organization_id", "organization_memberships.user_id"],
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint("role IN ('MEMBER','VIEWER')", name="role"),
        sa.CheckConstraint("status IN ('PENDING','ACCEPTED','REVOKED')", name="status"),
    )
    op.create_index(
        "ix_invitations_org_status", "organization_invitations", ["organization_id", "status"]
    )
    op.execute("ALTER TABLE organization_invitations ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE organization_invitations FORCE ROW LEVEL SECURITY")
    scope = "organization_id = NULLIF(current_setting('app.organization_id',true),'')::uuid"
    op.execute(
        f"CREATE POLICY tenant_scope ON organization_invitations USING ({scope}) "
        f"WITH CHECK ({scope})"
    )
    op.execute("""
    CREATE FUNCTION public.orqentra_accept_invitation(hashed text, correlation uuid)
    RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,public AS $$
    DECLARE actor uuid:=public.orqentra_identity_id(); invitation public.organization_invitations;
    BEGIN
      IF actor IS NULL OR hashed !~ '^[a-f0-9]{64}$' OR correlation IS NULL THEN
        RAISE EXCEPTION 'invalid invitation' USING ERRCODE='42501';
      END IF;
      SELECT * INTO invitation FROM public.organization_invitations
        WHERE token_hash=hashed AND status='PENDING' AND expires_at>now() FOR UPDATE;
      IF NOT FOUND THEN RAISE EXCEPTION 'invalid invitation' USING ERRCODE='42501'; END IF;
      PERFORM 1 FROM public.organizations WHERE id=invitation.organization_id AND
        status='ACTIVE' FOR UPDATE;
      IF NOT FOUND OR NOT EXISTS(SELECT 1 FROM public.organization_memberships
        WHERE organization_id=invitation.organization_id AND user_id=invitation.created_by
        AND status='ACTIVE' AND role IN ('OWNER','ADMIN')) THEN
        RAISE EXCEPTION 'inviter unavailable' USING ERRCODE='42501';
      END IF;
      IF EXISTS(SELECT 1 FROM public.organization_memberships WHERE
        organization_id=invitation.organization_id AND user_id=actor) THEN
        RAISE EXCEPTION 'membership already exists' USING ERRCODE='23505';
      END IF;
      INSERT INTO public.organization_memberships(id,organization_id,user_id,role,status)
        VALUES(gen_random_uuid(),invitation.organization_id,actor,invitation.role,'ACTIVE');
      UPDATE public.organization_invitations SET status='ACCEPTED',updated_at=now()
        WHERE id=invitation.id;
      INSERT INTO
        public.audit_events(id,organization_id,actor_user_id,action,resource_type,resource_id,correlation_id,metadata)
       
        VALUES(gen_random_uuid(),invitation.organization_id,actor,'invitation.accepted','membership',invitation.id,correlation,'{}');
      RETURN invitation.organization_id;
    END $$;
    REVOKE ALL ON FUNCTION public.orqentra_accept_invitation(text,uuid) FROM PUBLIC;
    """)


def downgrade() -> None:
    op.execute("DROP FUNCTION public.orqentra_accept_invitation(text,uuid)")
    op.drop_table("organization_invitations")
