"""Tenant RLS and append-only/immutability controls.

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "organizations",
    "organization_memberships",
    "workspaces",
    "agent_definitions",
    "agent_versions",
    "agent_tool_permissions",
    "audit_events",
)


def upgrade() -> None:
    op.execute("""
      CREATE FUNCTION orqentra_reject_mutation() RETURNS trigger
      LANGUAGE plpgsql AS $$ BEGIN
        RAISE EXCEPTION 'append-only record' USING ERRCODE = '55000';
      END $$
    """)
    for table in ("agent_versions", "audit_events"):
        op.execute(
            f"CREATE TRIGGER immutable_rows BEFORE UPDATE OR DELETE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION orqentra_reject_mutation()"
        )
        op.execute(
            f"CREATE TRIGGER immutable_truncate BEFORE TRUNCATE ON {table} "
            "FOR EACH STATEMENT EXECUTE FUNCTION orqentra_reject_mutation()"
        )
    op.execute("""
      CREATE FUNCTION orqentra_update_timestamp() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN NEW.updated_at = clock_timestamp(); RETURN NEW; END $$
    """)
    for table in (
        "organizations",
        "users",
        "organization_memberships",
        "workspaces",
        "agent_definitions",
    ):
        op.execute(
            f"CREATE TRIGGER touch_updated_at BEFORE UPDATE ON {table} "
            "FOR EACH ROW EXECUTE FUNCTION orqentra_update_timestamp()"
        )
    op.execute("""
      CREATE FUNCTION orqentra_guard_agent() RETURNS trigger LANGUAGE plpgsql AS $$
      BEGIN
        IF NEW.organization_id <> OLD.organization_id OR NEW.workspace_id <> OLD.workspace_id
           OR NEW.created_by <> OLD.created_by OR NEW.id <> OLD.id THEN
          RAISE EXCEPTION 'agent ownership is immutable' USING ERRCODE = '23514';
        END IF;
        IF OLD.lifecycle_status = 'ARCHIVED' THEN
          RAISE EXCEPTION 'archived agent is immutable' USING ERRCODE = '55000';
        END IF;
        IF NEW.revision <> OLD.revision + 1 THEN
          RAISE EXCEPTION 'agent revision must advance once' USING ERRCODE = '23514';
        END IF;
        RETURN NEW;
      END $$
    """)
    op.execute(
        "CREATE TRIGGER guard_agent BEFORE UPDATE ON agent_definitions "
        "FOR EACH ROW EXECUTE FUNCTION orqentra_guard_agent()"
    )
    # No role names hardcoded: applies to any non-bypass runtime role with table grants.
    expression = "NULLIF(current_setting('app.organization_id', true), '')::uuid"
    for table in TENANT_TABLES:
        column = "id" if table == "organizations" else "organization_id"
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"CREATE POLICY tenant_scope ON {table} USING ({column} = {expression}) "
            f"WITH CHECK ({column} = {expression})"
        )
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")
    op.execute(f"""CREATE POLICY users_visible_members ON users FOR SELECT USING (
        EXISTS (SELECT 1 FROM organization_memberships m WHERE m.user_id = users.id
                AND m.organization_id = {expression} AND m.status = 'ACTIVE'))""")


def downgrade() -> None:
    # Used only in disposable migration tests. Never downgrade a populated user's database.
    op.execute("DROP POLICY users_visible_members ON users")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users NO FORCE ROW LEVEL SECURITY")
    for table in reversed(TENANT_TABLES):
        op.execute(f"DROP POLICY tenant_scope ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    op.execute("DROP TRIGGER guard_agent ON agent_definitions")
    op.execute("DROP FUNCTION orqentra_guard_agent()")
    for table in (
        "organizations",
        "users",
        "organization_memberships",
        "workspaces",
        "agent_definitions",
    ):
        op.execute(f"DROP TRIGGER touch_updated_at ON {table}")
    op.execute("DROP FUNCTION orqentra_update_timestamp()")
    for table in ("agent_versions", "audit_events"):
        op.execute(f"DROP TRIGGER immutable_rows ON {table}")
        op.execute(f"DROP TRIGGER immutable_truncate ON {table}")
    op.execute("DROP FUNCTION orqentra_reject_mutation()")
