import copy
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC
from uuid import UUID, uuid4

import pytest
from alembic.config import Config
from psycopg import sql
from sqlalchemy import Engine, create_engine, func, inspect, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.orm import Session

from alembic import command
from orqentra.persistence.errors import (
    DuplicateRecord,
    ForbiddenOperation,
    IntegrityViolation,
    RecordNotFound,
    StaleRevision,
)
from orqentra.persistence.models import (
    AgentDefinition,
    AgentToolPermission,
    AgentVersion,
    AuditEvent,
    Organization,
    OrganizationMembership,
    User,
    Workspace,
)
from orqentra.persistence.repositories import AgentRepository
from orqentra.persistence.session import TrustedOrganizationContext, transaction


def seed(owner: Engine, *, role: str = "OWNER") -> tuple[UUID, UUID, UUID]:
    with Session(owner) as s, s.begin():
        organization = Organization(name="Test organization", slug="org-" + uuid4().hex)
        user = User(email="synthetic@example.invalid", display_name="Test user")
        s.add_all([organization, user])
        s.flush()
        s.add(OrganizationMembership(organization_id=organization.id, user_id=user.id, role=role))
        workspace = Workspace(organization_id=organization.id, name="Workspace", slug="default")
        s.add(workspace)
        s.flush()
        return organization.id, user.id, workspace.id


def ctx(seed_data: tuple[UUID, UUID, UUID]) -> TrustedOrganizationContext:
    return TrustedOrganizationContext(seed_data[0], seed_data[1], uuid4())


def create_agent(owner: Engine, runtime: Engine) -> tuple[TrustedOrganizationContext, UUID]:
    data = seed(owner)
    context = ctx(data)
    with transaction(runtime, context) as session:
        agent = AgentRepository(session, context).create(
            workspace_id=data[2],
            name="Onboarding",
            slug="Onboarding Specialist",
            configuration={"instructions": "Synthetic fixture", "limits": {"steps": 5}},
        )
        return context, agent.id


def test_connectivity(db: tuple[Engine, Engine]) -> None:
    with db[1].connect() as c:
        assert c.scalar(text("SELECT 1")) == 1
        assert not c.scalar(
            text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user")
        )


def test_organization_creation_and_slug(db: tuple[Engine, Engine]) -> None:
    data = seed(db[0])
    with transaction(db[1], ctx(data)) as s:
        assert s.get(Organization, data[0]).status == "ACTIVE"
    with Session(db[0]) as s, s.begin(), pytest.raises(IntegrityError):
        s.add(Organization(name="bad", slug="Not Normalized"))
        s.flush()


def test_membership_uniqueness(db: tuple[Engine, Engine]) -> None:
    data = seed(db[0])
    with pytest.raises(DuplicateRecord), transaction(db[1], ctx(data)) as session:
        session.add(OrganizationMembership(organization_id=data[0], user_id=data[1], role="ADMIN"))
        session.flush()


def test_workspace_uniqueness_and_scope(db: tuple[Engine, Engine]) -> None:
    a, b = seed(db[0]), seed(db[0])
    with pytest.raises(DuplicateRecord), transaction(db[1], ctx(a)) as s:
        s.add(Workspace(organization_id=a[0], name="Duplicate", slug="default"))
        s.flush()
    with transaction(db[1], ctx(b)) as s:
        assert len(s.scalars(select(Workspace)).all()) == 1


def test_cross_tenant_workspace_fk_even_for_owner(db: tuple[Engine, Engine]) -> None:
    a, b = seed(db[0]), seed(db[0])
    with Session(db[0]) as s, s.begin(), pytest.raises(IntegrityError):
        s.add(
            AgentDefinition(
                organization_id=a[0], workspace_id=b[2], name="bad", slug="bad", created_by=a[1]
            )
        )
        s.flush()


@pytest.mark.parametrize("table", ["agent_versions", "agent_tool_permissions"])
def test_cross_tenant_child_fk(db: tuple[Engine, Engine], table: str) -> None:
    context, agent_id = create_agent(*db)
    b = seed(db[0])
    with Session(db[0]) as s, s.begin(), pytest.raises(IntegrityError):
        if table == "agent_versions":
            s.add(
                AgentVersion(
                    organization_id=b[0],
                    agent_definition_id=agent_id,
                    published_by=b[1],
                    version_number=1,
                    configuration_snapshot={},
                )
            )
        else:
            s.add(
                AgentToolPermission(
                    organization_id=b[0],
                    agent_definition_id=agent_id,
                    tool_identifier="knowledge.search",
                )
            )
        s.flush()


def test_foreign_member_creator_fk(db: tuple[Engine, Engine]) -> None:
    a, b = seed(db[0]), seed(db[0])
    with Session(db[0]) as s, s.begin(), pytest.raises(IntegrityError):
        s.add(
            AgentDefinition(
                organization_id=a[0], workspace_id=a[2], name="bad", slug="bad", created_by=b[1]
            )
        )
        s.flush()


def test_publication_snapshots_and_numbering(db: tuple[Engine, Engine]) -> None:
    context, aid = create_agent(*db)
    with transaction(db[1], context) as s:
        repo = AgentRepository(s, context)
        first = repo.publish(aid, expected_revision=1)
        frozen = copy.deepcopy(first.configuration_snapshot)
    with transaction(db[1], context) as s:
        repo = AgentRepository(s, context)
        updated = repo.update_draft(aid, expected_revision=2, configuration={"changed": True})
        second = repo.publish(aid, expected_revision=updated.revision)
        assert second.version_number == 2
    with transaction(db[1], context) as s:
        assert s.get(AgentVersion, first.id).configuration_snapshot == frozen
        with pytest.raises(StaleRevision):
            AgentRepository(s, context).publish(aid, expected_revision=1)


@pytest.mark.parametrize("table", ["agent_versions", "audit_events"])
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE", "TRUNCATE"])
def test_database_append_only_even_owner(
    db: tuple[Engine, Engine], table: str, operation: str
) -> None:
    context, aid = create_agent(*db)
    with transaction(db[1], context) as s:
        AgentRepository(s, context).publish(aid, expected_revision=1)
    field = "version_number=version_number" if table == "agent_versions" else "action=action"
    query = (
        f"{operation} {table} CASCADE"
        if operation == "TRUNCATE"
        else (f"UPDATE {table} SET {field}" if operation == "UPDATE" else f"DELETE FROM {table}")
    )
    with db[0].begin() as c, pytest.raises(DBAPIError) as error:
        c.execute(text(query))
    assert error.value.orig.sqlstate == "55000"


def test_runtime_cannot_modify_immutable_tables(db: tuple[Engine, Engine]) -> None:
    context, aid = create_agent(*db)
    with transaction(db[1], context) as s:
        AgentRepository(s, context).publish(aid, expected_revision=1)
    with pytest.raises(ForbiddenOperation), transaction(db[1], context) as s:
        s.execute(text("UPDATE agent_versions SET version_number=99"))


def test_tool_permission_unique_and_configuration(db: tuple[Engine, Engine]) -> None:
    context, aid = create_agent(*db)
    with transaction(db[1], context) as s:
        s.add(
            AgentToolPermission(
                organization_id=context.organization_id,
                agent_definition_id=aid,
                tool_identifier="knowledge.search",
                permission_scope={"collections": ["synthetic"]},
            )
        )
    with pytest.raises(DuplicateRecord), transaction(db[1], context) as s:
        s.add(
            AgentToolPermission(
                organization_id=context.organization_id,
                agent_definition_id=aid,
                tool_identifier="knowledge.search",
            )
        )
        s.flush()
    with transaction(db[1], context) as s:
        version = AgentRepository(s, context).publish(aid, expected_revision=1)
        assert version.configuration_snapshot["tool_permissions"][0]["permission_scope"] == {
            "collections": ["synthetic"]
        }


def test_jsonb_and_utc(db: tuple[Engine, Engine]) -> None:
    context, aid = create_agent(*db)
    with transaction(db[1], context) as s:
        agent = AgentRepository(s, context).get(aid)
        assert agent.draft_configuration["limits"]["steps"] == 5
        assert agent.created_at.utcoffset() == UTC.utcoffset(None)
        assert agent.updated_at.tzinfo is not None
    with pytest.raises(IntegrityViolation), transaction(db[1], context) as s:
        s.execute(
            text(
                "UPDATE agent_definitions SET draft_configuration='[]'::jsonb, "
                "revision=revision+1 WHERE id=:id"
            ),
            {"id": aid},
        )


def test_rollback_includes_audit(db: tuple[Engine, Engine]) -> None:
    data = seed(db[0])
    context = ctx(data)
    aid = None
    with pytest.raises(ValueError), transaction(db[1], context) as s:
        agent = AgentRepository(s, context).create(
            workspace_id=data[2], name="rollback", slug="rollback", configuration={}
        )
        aid = agent.id
        raise ValueError("Simulated application failure")
    with transaction(db[1], context) as s:
        assert s.get(AgentDefinition, aid) is None
        assert s.scalar(select(func.count()).select_from(AuditEvent)) == 0


def test_concurrent_update_conflict(db: tuple[Engine, Engine]) -> None:
    context, aid = create_agent(*db)

    def writer(n: int) -> str:
        try:
            with transaction(db[1], context) as s:
                AgentRepository(s, context).update_draft(
                    aid, expected_revision=1, configuration={"writer": n}
                )
            return "saved"
        except StaleRevision:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(writer, [1, 2])) == ["saved", "stale"]


def test_concurrent_publish_conflict(db: tuple[Engine, Engine]) -> None:
    context, aid = create_agent(*db)

    def publish(_: int) -> str:
        try:
            with transaction(db[1], context) as s:
                AgentRepository(s, context).publish(aid, expected_revision=1)
            return "published"
        except StaleRevision:
            return "stale"

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(publish, [1, 2])) == ["published", "stale"]
    with transaction(db[1], context) as s:
        assert s.scalar(select(func.count()).select_from(AgentVersion)) == 1


def test_repository_and_rls_scope(db: tuple[Engine, Engine]) -> None:
    a, aid = create_agent(*db)
    b, bid = create_agent(*db)
    with transaction(db[1], a) as s:
        assert [v.id for v in AgentRepository(s, a).list()] == [aid]
        assert [v.id for v in s.scalars(select(AgentDefinition))] == [aid]
        with pytest.raises(RecordNotFound):
            AgentRepository(s, a).get(bid)
        assert (
            s.execute(
                update(AgentDefinition).where(AgentDefinition.id == bid).values(revision=2)
            ).rowcount
            == 0
        )
    with transaction(db[1], b) as s:
        assert s.get(AgentDefinition, bid) is not None
    with db[1].connect() as c:
        assert c.scalar(text("SELECT count(*) FROM agent_definitions")) == 0
        assert c.scalar(text("SELECT count(*) FROM users")) == 0


def test_rls_rejects_forged_insert(db: tuple[Engine, Engine]) -> None:
    a, b = seed(db[0]), seed(db[0])
    with pytest.raises(ForbiddenOperation), transaction(db[1], ctx(a)) as s:
        s.add(Workspace(organization_id=b[0], name="bad", slug="forged"))
        s.flush()


def test_viewer_cannot_write(db: tuple[Engine, Engine]) -> None:
    data = seed(db[0], role="VIEWER")
    with transaction(db[1], ctx(data)) as s, pytest.raises(ForbiddenOperation):
        AgentRepository(s, ctx(data)).create(
            workspace_id=data[2], name="bad", slug="bad", configuration={}
        )


def test_published_number_unique(db: tuple[Engine, Engine]) -> None:
    context, aid = create_agent(*db)
    with transaction(db[1], context) as s:
        AgentRepository(s, context).publish(aid, expected_revision=1)
    with pytest.raises(DuplicateRecord), transaction(db[1], context) as s:
        s.add(
            AgentVersion(
                organization_id=context.organization_id,
                agent_definition_id=aid,
                version_number=1,
                published_by=context.actor_user_id,
                configuration_snapshot={},
            )
        )
        s.flush()


def test_nonexistent_user_fk(db: tuple[Engine, Engine]) -> None:
    data = seed(db[0])
    with pytest.raises(IntegrityViolation), transaction(db[1], ctx(data)) as s:
        s.add(OrganizationMembership(organization_id=data[0], user_id=uuid4(), role="MEMBER"))
        s.flush()


def test_mutation_emits_sanitized_audit(db: tuple[Engine, Engine]) -> None:
    context, aid = create_agent(*db)
    with transaction(db[1], context) as s:
        AgentRepository(s, context).update_draft(
            aid, expected_revision=1, configuration={"instructions": "sensitive-canary"}
        )
    with transaction(db[1], context) as s:
        events = s.scalars(select(AuditEvent)).all()
        assert len(events) == 2
        assert {e.action for e in events} == {"agent.created", "agent.updated"}
        assert all("sensitive-canary" not in str(e.safe_metadata) for e in events)
        assert all(e.correlation_id == context.correlation_id for e in events)


def test_fresh_migration_reversibility_and_data_preservation(
    databases: tuple[Engine, Engine, Config],
) -> None:
    # Completely separate generated database; never downgrade the development DB or suite DB.
    url = os.environ["ORQENTRA_TEST_ADMIN_URL"]
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    name = "orqentra_test_" + uuid4().hex
    with admin.connect() as c:
        c.exec_driver_sql(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)).as_string())
    engine = create_engine(make_url(url).set(database=name))
    config = Config(databases[2].config_file_name)
    try:
        with engine.begin() as c:
            config.attributes["connection"] = c
            command.upgrade(config, "0001")
            organization_id = uuid4()
            c.execute(
                text("INSERT INTO organizations(id,name,slug) VALUES(:id,'preserve','preserve')"),
                {"id": organization_id},
            )
        with engine.begin() as c:
            config.attributes["connection"] = c
            command.upgrade(config, "0002")
        retained = seed(engine)
        with transaction(engine, ctx(retained)) as session:
            agent = AgentRepository(session, ctx(retained)).create(
                workspace_id=retained[2],
                name="Preserved",
                slug="preserved",
                configuration={"instructions": "migration sentinel"},
            )
            version = AgentRepository(session, ctx(retained)).publish(agent.id, expected_revision=1)
            version_id = version.id
            snapshot_before = version.configuration_snapshot
        with engine.begin() as c:
            audit_before = c.execute(
                text("SELECT id, metadata FROM audit_events ORDER BY id")
            ).all()
            config.attributes["connection"] = c
            command.upgrade(config, "head")
            assert (
                c.scalar(text("SELECT id FROM organizations WHERE id=:id"), {"id": organization_id})
                == organization_id
            )
            assert (
                c.scalar(
                    text("SELECT configuration_snapshot FROM agent_versions WHERE id=:id"),
                    {"id": version_id},
                )
                == snapshot_before
            )
            assert (
                c.execute(text("SELECT id, metadata FROM audit_events ORDER BY id")).all()
                == audit_before
            )
            command.check(config)
        with engine.begin() as c:
            config.attributes["connection"] = c
            command.downgrade(config, "base")
            assert set(inspect(c).get_table_names()) <= {"alembic_version"}
            command.upgrade(config, "head")
            assert c.scalar(text("SELECT version_num FROM alembic_version")) == "0011"
    finally:
        engine.dispose()
        with admin.connect() as c:
            c.exec_driver_sql(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)).as_string()
            )
        admin.dispose()


def test_orm_version_immutability(db: tuple[Engine, Engine]) -> None:
    context, aid = create_agent(*db)
    with transaction(db[1], context) as session:
        version = AgentRepository(session, context).publish(aid, expected_revision=1)
        version_id = version.id
    with pytest.raises(ForbiddenOperation), transaction(db[1], context) as session:
        stored = session.get(AgentVersion, version_id)
        assert stored is not None
        stored.configuration_snapshot = {"changed": True}
        session.flush()


def test_user_external_identity_unique_email_not_identity(db: tuple[Engine, Engine]) -> None:
    external = "synthetic-" + uuid4().hex
    with Session(db[0]) as session, session.begin():
        session.add_all(
            [
                User(email="same@example.invalid", display_name="one", external_auth_id=external),
                User(email="same@example.invalid", display_name="two"),
                User(email="same@example.invalid", display_name="three"),
            ]
        )
    with Session(db[0]) as session, session.begin(), pytest.raises(IntegrityError):
        session.add(
            User(email="other@example.invalid", display_name="duplicate", external_auth_id=external)
        )
        session.flush()


def test_runtime_has_no_schema_ddl_or_user_inserts(db: tuple[Engine, Engine]) -> None:
    with db[1].begin() as connection, pytest.raises(DBAPIError):
        connection.execute(text("CREATE TABLE forbidden_runtime_ddl(id integer)"))
    data = seed(db[0])
    with pytest.raises(ForbiddenOperation), transaction(db[1], ctx(data)) as session:
        session.add(User(email="not-allowed@example.invalid", display_name="forbidden"))
        session.flush()


def test_timestamp_update_and_archive_rules(db: tuple[Engine, Engine]) -> None:
    context, aid = create_agent(*db)
    with transaction(db[1], context) as session:
        before = AgentRepository(session, context).get(aid).updated_at
    with transaction(db[1], context) as session:
        current = AgentRepository(session, context).update_draft(
            aid, expected_revision=1, configuration={}
        )
        session.refresh(current)
        assert current.updated_at >= before
    with pytest.raises(IntegrityViolation), transaction(db[1], context) as session:
        session.execute(
            text(
                "UPDATE agent_definitions SET lifecycle_status='ARCHIVED', "
                "revision=revision+1 WHERE id=:id"
            ),
            {"id": aid},
        )


def test_audit_failure_rolls_back_domain_write(db: tuple[Engine, Engine]) -> None:
    data = seed(db[0])
    context = ctx(data)
    aid = uuid4()
    with pytest.raises(IntegrityViolation), transaction(db[1], context) as session:
        session.add(
            AgentDefinition(
                id=aid,
                organization_id=data[0],
                workspace_id=data[2],
                name="Atomic",
                slug="atomic",
                created_by=data[1],
            )
        )
        session.flush()
        session.add(
            AuditEvent(
                organization_id=data[0],
                actor_user_id=uuid4(),
                action="agent.created",
                resource_type="agent",
                resource_id=aid,
                correlation_id=uuid4(),
            )
        )
        session.flush()
    with transaction(db[1], context) as session:
        assert session.get(AgentDefinition, aid) is None


@pytest.mark.parametrize("metadata", [{"instructions": "sensitive-canary"}, {"revision": "secret"}])
def test_audit_metadata_allowlist(db: tuple[Engine, Engine], metadata: dict[str, str]) -> None:
    data = seed(db[0])
    with pytest.raises(IntegrityViolation), transaction(db[1], ctx(data)) as session:
        session.add(
            AuditEvent(
                organization_id=data[0],
                actor_user_id=data[1],
                action="test.event",
                resource_type="test",
                resource_id=uuid4(),
                correlation_id=uuid4(),
                safe_metadata=metadata,
            )
        )
        session.flush()


def test_all_tables_are_rls_scoped(db: tuple[Engine, Engine]) -> None:
    context, aid = create_agent(*db)
    other_context, other_id = create_agent(*db)
    for current, agent_id in [(context, aid), (other_context, other_id)]:
        with transaction(db[1], current) as session:
            session.add(
                AgentToolPermission(
                    organization_id=current.organization_id,
                    agent_definition_id=agent_id,
                    tool_identifier="knowledge.search",
                )
            )
            session.flush()
            AgentRepository(session, current).publish(agent_id, expected_revision=1)
    tables = [
        "organizations",
        "organization_memberships",
        "workspaces",
        "agent_definitions",
        "agent_versions",
        "agent_tool_permissions",
        "audit_events",
    ]
    with transaction(db[1], context) as session:
        for table in tables:
            column = "id" if table == "organizations" else "organization_id"
            assert set(session.scalars(text(f"SELECT DISTINCT {column} FROM {table}"))) == {
                context.organization_id
            }
        assert set(session.scalars(text("SELECT id FROM users"))) == {context.actor_user_id}
    with db[1].connect() as connection:
        for table in [*tables, "users"]:
            assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0
    with db[0].connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT count(*) FROM pg_class WHERE relname = ANY(:tables) "
                    "AND relrowsecurity AND relforcerowsecurity"
                ),
                {"tables": [*tables, "users"]},
            )
            == 8
        )
