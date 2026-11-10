"""Provisioning helpers; migration credentials only, never called by HTTP handlers."""

import re

from sqlalchemy import Connection

from orqentra.persistence.models import Base


def grant_runtime(connection: Connection, role: str) -> None:
    if not re.fullmatch(r"orqentra_(?:runtime|test_[a-f0-9]+)", role):
        raise ValueError("Unexpected runtime role name.")
    quoted = f'"{role}"'
    connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA public TO {quoted}")
    for table in Base.metadata.sorted_tables:
        privileges = "SELECT, INSERT, UPDATE"
        if table.name in {
            "agent_versions",
            "audit_events",
            "action_receipts",
            "usage_events",
            "billing_webhook_events",
            "billing_snapshots",
            "invoice_snapshots",
            "workflow_checkpoints",
        }:
            privileges = "SELECT, INSERT"
        if table.name == "users":
            privileges = "SELECT"
        connection.exec_driver_sql(f'REVOKE ALL ON TABLE "{table.name}" FROM {quoted}')
        connection.exec_driver_sql(f'GRANT {privileges} ON TABLE "{table.name}" TO {quoted}')
    connection.exec_driver_sql(f"REVOKE CREATE ON SCHEMA public FROM {quoted}")

    # Only known security-definer functions, never EXECUTE on arbitrary future functions.
    from sqlalchemy import text

    functions = (
        "orqentra_identity_id()",
        "orqentra_provision_identity()",
        "orqentra_my_organizations()",
        "orqentra_membership_for_org(uuid)",
        "orqentra_create_organization(text,text,uuid)",
        "orqentra_accept_invitation(text,uuid)",
    )
    if connection.scalar(
        text("SELECT to_regprocedure('public.orqentra_identity_id()') IS NOT NULL")
    ):
        for function in functions:
            connection.exec_driver_sql(f"GRANT EXECUTE ON FUNCTION public.{function} TO {quoted}")


def provision_identity_owner(connection: Connection, role: str) -> None:
    """Non-login, narrowly granted owner for the six reviewed definer functions."""
    from sqlalchemy import text

    if not re.fullmatch(r"orqentra_identity_owner|orqentra_definer_[a-f0-9]+", role):
        raise ValueError("Unexpected identity-owner role name.")
    if not connection.scalar(
        text("SELECT to_regprocedure('public.orqentra_identity_id()') IS NOT NULL")
    ):
        return
    existing = connection.execute(
        text(
            "SELECT rolcanlogin,rolsuper,rolcreatedb,rolcreaterole,rolbypassrls "
            "FROM pg_roles WHERE rolname=:role"
        ),
        {"role": role},
    ).first()
    if existing is None:
        connection.exec_driver_sql(
            f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE BYPASSRLS'
        )
    elif any(existing[:4]) or not existing[4]:
        raise ValueError("Existing identity owner has unsafe role attributes.")
    connection.exec_driver_sql(f'GRANT USAGE, CREATE ON SCHEMA public TO "{role}"')
    for table in (
        "users",
        "organizations",
        "organization_memberships",
        "workspaces",
        "audit_events",
    ):
        connection.exec_driver_sql(f'REVOKE ALL ON public.{table} FROM "{role}"')
        connection.exec_driver_sql(f'GRANT SELECT, INSERT ON public.{table} TO "{role}"')
    connection.exec_driver_sql(
        f'GRANT SELECT, UPDATE ON public.organization_invitations TO "{role}"'
    )
    connection.exec_driver_sql(f'GRANT UPDATE(id) ON public.organizations TO "{role}"')
    for function in (
        "orqentra_identity_id()",
        "orqentra_provision_identity()",
        "orqentra_my_organizations()",
        "orqentra_membership_for_org(uuid)",
        "orqentra_create_organization(text,text,uuid)",
        "orqentra_accept_invitation(text,uuid)",
    ):
        connection.exec_driver_sql(f'ALTER FUNCTION public.{function} OWNER TO "{role}"')
    connection.exec_driver_sql(f'REVOKE CREATE ON SCHEMA public FROM "{role}"')
