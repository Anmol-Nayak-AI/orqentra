"""One remote attempt per approved job; uncertain execution is never retried automatically."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import Engine, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from orqentra.billing.service import policy
from orqentra.core.config import Settings
from orqentra.execution.policy import approved_sources_active, eligible
from orqentra.execution.routes import digest
from orqentra.persistence.models import (
    AuditEvent,
    CodeExecution,
    Organization,
    OrganizationMembership,
    TaskRun,
    WorkerRuntime,
)
from orqentra.persistence.session import TrustedOrganizationContext, transaction
from orqentra.rag.service import require_restricted
from orqentra.sandbox.provider import ApprovedCode, SandboxUnavailable, provider
from orqentra.sandbox.routes import code_hash


def heartbeat(engine: Engine, organization_id: UUID, settings: Settings) -> None:
    context = TrustedOrganizationContext(organization_id, UUID(int=0), uuid4())
    with transaction(engine, context) as session:
        require_restricted(session)
        statement = insert(WorkerRuntime).values(
            id=uuid4(),
            organization_id=organization_id,
            last_seen=datetime.now(UTC),
            sandbox_available=bool(
                settings.sandbox_provider == "e2b"
                and settings.sandbox_execution_approved
                and settings.e2b_api_key
                and settings.e2b_template_id
            ),
        )
        session.execute(
            statement.on_conflict_do_update(
                index_elements=[WorkerRuntime.organization_id],
                set_={
                    "last_seen": statement.excluded.last_seen,
                    "sandbox_available": statement.excluded.sandbox_available,
                },
            )
        )


def authorized(session: Session, item: CodeExecution) -> bool:
    parent = session.scalar(select(TaskRun).where(TaskRun.id == item.run_id).with_for_update())
    if (
        not parent
        or parent.status != "APPROVED"
        or parent.artifact_hash != digest(parent.output)
        or not eligible(session, parent)
        or not approved_sources_active(session, parent)
        or code_hash(item.code) != item.code_hash
        or item.reviewed_by is None
        or item.reviewed_by == item.created_by
        or not item.approval_expires_at
        or item.approval_expires_at <= datetime.now(UTC)
    ):
        return False
    creator = session.scalar(
        select(OrganizationMembership.id).where(
            OrganizationMembership.user_id == item.created_by,
            OrganizationMembership.status == "ACTIVE",
            OrganizationMembership.role.in_(["OWNER", "ADMIN", "MEMBER"]),
        )
    )
    reviewer = session.scalar(
        select(OrganizationMembership.id).where(
            OrganizationMembership.user_id == item.reviewed_by,
            OrganizationMembership.status == "ACTIVE",
            OrganizationMembership.role.in_(["OWNER", "ADMIN"]),
        )
    )
    return bool(creator and reviewer)


def event(session: Session, item: CodeExecution, name: str) -> None:
    session.add(
        AuditEvent(
            organization_id=item.organization_id,
            actor_user_id=item.created_by,
            action="sandbox." + name,
            resource_type="code_execution",
            resource_id=item.id,
            correlation_id=uuid4(),
            safe_metadata={"revision": item.revision},
        )
    )


def code_tick(engine: Engine, organization_id: UUID, settings: Settings) -> bool:
    context = TrustedOrganizationContext(organization_id, UUID(int=0), uuid4())
    token = uuid4()
    with transaction(engine, context) as session:
        require_restricted(session)
        # A dead worker may have created/executed a remote sandbox. Never reissue that attempt.
        expired = session.scalar(
            select(CodeExecution)
            .where(CodeExecution.status == "RUNNING", CodeExecution.lease_until < datetime.now(UTC))
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if expired:
            expired.status = "UNKNOWN"
            expired.error_code = "worker_lost_execution_uncertain"
            expired.claim_token = None
            expired.revision += 1
            event(session, expired, "unknown")
            return True
        if not (
            settings.sandbox_provider == "e2b"
            and settings.sandbox_execution_approved
            and settings.e2b_api_key
            and settings.e2b_template_id
        ):
            return False
        # Serialize admission per tenant across worker replicas, not only within this process.
        # RUNNING includes uncertain in-flight attempts until their two-minute lease expires;
        # the remote sandbox lifetime is bounded to sixty seconds and is never auto-reissued.
        session.execute(select(Organization.id).with_for_update()).scalar_one()
        running = session.scalar(
            select(func.count()).select_from(CodeExecution).where(CodeExecution.status == "RUNNING")
        )
        if (running or 0) >= settings.sandbox_max_concurrent_per_organization:
            return False
        item = session.scalar(
            select(CodeExecution)
            .where(CodeExecution.status == "QUEUED")
            .order_by(CodeExecution.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if item is None:
            return False
        if policy(session, organization_id, settings.environment) is None or not authorized(
            session, item
        ):
            item.status = "CANCELLED"
            item.error_code = "code_approval_or_access_revoked"
            item.revision += 1
            event(session, item, "cancelled")
            return True
        item.status = "RUNNING"
        item.claim_token = token
        item.lease_until = datetime.now(UTC) + timedelta(minutes=2)
        item.revision += 1
        item_id, run_id, code, approval_hash, expiry = (
            item.id,
            item.run_id,
            item.code,
            item.code_hash,
            item.approval_expires_at,
        )
        assert expiry is not None
        event(session, item, "started")

    def audit(metadata: dict[str, str]) -> None:
        with transaction(engine, context) as session:
            require_restricted(session)
            row = session.scalar(
                select(CodeExecution).where(CodeExecution.id == item_id).with_for_update()
            )
            if not row or row.status != "RUNNING" or row.claim_token != token:
                raise SandboxUnavailable("sandbox_claim_lost")
            if metadata["outcome"] == "requested" and (
                policy(session, organization_id, settings.environment) is None
                or not authorized(session, row)
            ):
                raise SandboxUnavailable("sandbox_approval_revoked")
            if metadata.get("sandbox_id"):
                row.external_sandbox_id = metadata["sandbox_id"]
            event(session, row, metadata["outcome"])

    output, failure = "", None
    try:
        output = provider(settings, audit).execute(
            code, ApprovedCode(organization_id, run_id, item_id, approval_hash, expiry)
        )
    except Exception:
        failure = "sandbox_execution_uncertain"
    with transaction(engine, context) as session:
        require_restricted(session)
        item = session.scalar(
            select(CodeExecution).where(CodeExecution.id == item_id).with_for_update()
        )
        if not item or item.status != "RUNNING" or item.claim_token != token:
            return True
        if policy(session, organization_id, settings.environment) is None or not authorized(
            session, item
        ):
            item.status, item.error_code = "UNKNOWN", "access_changed_during_execution"
        elif failure:
            item.status, item.error_code = "UNKNOWN", failure
        else:
            item.status, item.output = "COMPLETED", output
        item.revision += 1
        item.claim_token, item.lease_until = None, None
        event(session, item, item.status.lower())
    return True
