"""Narrow identity bootstrap, membership discovery and owner invariant.

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

FUNCTIONS = (
    "orqentra_identity_id()",
    "orqentra_provision_identity()",
    "orqentra_my_organizations()",
    "orqentra_membership_for_org(uuid)",
    "orqentra_create_organization(text,text,uuid)",
)


def upgrade() -> None:
    op.drop_constraint(op.f("ck_audit_events_metadata_keys"), "audit_events", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_events_metadata_keys"),
        "audit_events",
        "metadata - ARRAY['revision','version_number','reason_code','old_role','new_role']::text[] "
        "= '{}'::jsonb",
    )
    for key in ("old_role", "new_role"):
        op.create_check_constraint(
            op.f(f"ck_audit_events_{key}"),
            "audit_events",
            f"NOT(metadata ? '{key}') OR metadata->'{key}' = 'null'::jsonb OR "
            f"metadata->>'{key}' IN ('OWNER','ADMIN','MEMBER','VIEWER')",
        )
    # Fixed search_path, no dynamic SQL, no caller-supplied user/role/organization ownership.
    # The server sets this subject only after verifying a Clerk session JWT.
    op.execute("""
    CREATE FUNCTION public.orqentra_identity_id() RETURNS uuid
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
      SELECT id FROM public.users
      WHERE external_auth_id = NULLIF(current_setting('app.external_auth_id', true), '')
        AND status = 'ACTIVE'
    $$;
    CREATE FUNCTION public.orqentra_provision_identity() RETURNS uuid
    LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    DECLARE subject text := NULLIF(current_setting('app.external_auth_id', true), '');
            result uuid;
    BEGIN
      IF subject IS NULL OR subject !~ '^user_[a-zA-Z0-9_]{1,200}$' THEN
        RAISE EXCEPTION 'verified subject required' USING ERRCODE='42501';
      END IF;
      SELECT id INTO result FROM public.users WHERE external_auth_id=subject AND status='ACTIVE';
      IF result IS NOT NULL THEN RETURN result; END IF;
      INSERT INTO public.users(id, external_auth_id, email, display_name, status)
      VALUES(gen_random_uuid(),subject,'','Member','ACTIVE')
      ON CONFLICT(external_auth_id) DO NOTHING;
      SELECT id INTO result FROM public.users WHERE external_auth_id=subject AND status='ACTIVE';
      IF result IS NULL THEN
        RAISE EXCEPTION 'identity inactive' USING ERRCODE='42501';
      END IF;
      RETURN result;
    END $$;
    CREATE FUNCTION public.orqentra_my_organizations()
    RETURNS TABLE(id uuid, name varchar, slug varchar, status varchar, role varchar,
                  membership_id uuid)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
      SELECT o.id,o.name,o.slug,o.status,m.role,m.id
      FROM public.organization_memberships m JOIN public.organizations o ON o.id=m.organization_id
      WHERE m.user_id=public.orqentra_identity_id() AND m.status='ACTIVE' AND o.status='ACTIVE'
      ORDER BY o.created_at,o.id LIMIT 1000
    $$;
    CREATE FUNCTION public.orqentra_membership_for_org(target uuid)
    RETURNS TABLE(role varchar, membership_id uuid)
    LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public AS $$
      SELECT m.role,m.id FROM public.organization_memberships m
      JOIN public.organizations o ON o.id=m.organization_id
      WHERE m.organization_id=target AND m.user_id=public.orqentra_identity_id()
        AND m.status='ACTIVE' AND o.status='ACTIVE'
    $$;
    CREATE FUNCTION public.orqentra_create_organization(org_name text,org_slug text,
      correlation uuid)
    RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path = pg_catalog, public AS $$
    DECLARE actor uuid := public.orqentra_identity_id(); result uuid := gen_random_uuid();
    BEGIN
      IF actor IS NULL THEN
        RAISE EXCEPTION 'active identity required' USING ERRCODE='42501';
      END IF;
      IF length(trim(org_name)) NOT BETWEEN 1 AND 200 OR length(org_slug) NOT BETWEEN 1 AND 100
         OR org_slug !~ '^[a-z0-9]+(-[a-z0-9]+)*$' OR correlation IS NULL THEN
        RAISE EXCEPTION 'invalid organization' USING ERRCODE='23514';
      END IF;
      PERFORM set_config('app.organization_id',result::text,true);
      INSERT INTO public.organizations(id,name,slug,status)
        VALUES(result,trim(org_name),org_slug,'ACTIVE');
      INSERT INTO public.organization_memberships(id,organization_id,user_id,role,status)
        VALUES(gen_random_uuid(),result,actor,'OWNER','ACTIVE');
      INSERT INTO public.workspaces(id,organization_id,name,slug,status)
        VALUES(gen_random_uuid(),result,'Default workspace','default','ACTIVE');
      INSERT INTO public.audit_events(id,organization_id,actor_user_id,action,resource_type,
                                      resource_id,correlation_id,metadata)
        VALUES(gen_random_uuid(),result,actor,'organization.created','organization',result,
               correlation,'{"reason_code":"created"}'::jsonb);
      RETURN result;
    END $$;
    CREATE FUNCTION public.orqentra_guard_last_owner() RETURNS trigger
    LANGUAGE plpgsql SET search_path = pg_catalog, public AS $$
    BEGIN
      IF OLD.role='OWNER' AND OLD.status='ACTIVE'
         AND (NEW.role<>'OWNER' OR NEW.status<>'ACTIVE') THEN
        PERFORM 1 FROM public.organizations WHERE id=OLD.organization_id FOR UPDATE;
        IF (SELECT count(*) FROM public.organization_memberships
            WHERE organization_id=OLD.organization_id AND role='OWNER' AND status='ACTIVE') <= 1
        THEN RAISE EXCEPTION 'final owner is protected' USING ERRCODE='23514'; END IF;
      END IF;
      RETURN NEW;
    END $$;
    CREATE TRIGGER guard_last_owner BEFORE UPDATE ON public.organization_memberships
      FOR EACH ROW EXECUTE FUNCTION public.orqentra_guard_last_owner();
    CREATE POLICY users_self_identity ON public.users FOR SELECT USING
      (external_auth_id = NULLIF(current_setting('app.external_auth_id',true),'')
       AND status='ACTIVE');
    """)
    for function in FUNCTIONS:
        op.execute(f"REVOKE ALL ON FUNCTION public.{function} FROM PUBLIC")
    op.execute("REVOKE ALL ON FUNCTION public.orqentra_guard_last_owner() FROM PUBLIC")
    # Provisioning scripts grant execution to explicitly named restricted roles after upgrade.


def downgrade() -> None:
    # A downgrade with newer audit metadata intentionally fails rather than deleting history.
    for key in ("old_role", "new_role"):
        op.drop_constraint(op.f(f"ck_audit_events_{key}"), "audit_events", type_="check")
    op.drop_constraint(op.f("ck_audit_events_metadata_keys"), "audit_events", type_="check")
    op.create_check_constraint(
        op.f("ck_audit_events_metadata_keys"),
        "audit_events",
        "metadata - ARRAY['revision','version_number','reason_code']::text[] = '{}'::jsonb",
    )
    op.execute("DROP POLICY users_self_identity ON public.users")
    op.execute("DROP TRIGGER guard_last_owner ON public.organization_memberships")
    op.execute("DROP FUNCTION public.orqentra_guard_last_owner()")
    for function in reversed(FUNCTIONS):
        op.execute(f"DROP FUNCTION public.{function}")
