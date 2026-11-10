import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, text

from orqentra.agents.schemas import TeammateConfiguration
from orqentra.auth.dependencies import AuthorizedOrganization, OrganizationPermission
from orqentra.billing.service import reserve_intake
from orqentra.execution.policy import eligible
from orqentra.execution.schemas import (
    Clarification,
    DocumentCreate,
    DocumentResponse,
    ExecutionCapabilities,
    ReceiptResponse,
    ReviewDecision,
    RunCreate,
    RunResponse,
)
from orqentra.persistence.models import (
    ActionReceipt,
    AgentDefinition,
    AgentVersion,
    AuditEvent,
    KnowledgeDocument,
    TaskRun,
    WorkerRuntime,
    Workspace,
)

router = APIRouter(prefix="/api/v1/organizations/{organization_id}", tags=["knowledge and tasks"])
Read = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("agent.read"))]
Write = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("agent.create"))]
Manage = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("agent.publish"))]
Audit = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("audit.read"))]


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), default=str).encode()
    ).hexdigest()


def audit(access: AuthorizedOrganization, action: str, resource: UUID, revision: int = 1) -> None:
    access.authenticated.session.add(
        AuditEvent(
            organization_id=access.context.organization_id,
            actor_user_id=access.authenticated.user_id,
            action=action,
            resource_type="workforce",
            resource_id=resource,
            correlation_id=access.context.correlation_id,
            safe_metadata={"revision": revision},
        )
    )


def get_run(access: AuthorizedOrganization, run_id: UUID, lock: bool = False) -> TaskRun:
    query = select(TaskRun).where(
        TaskRun.id == run_id, TaskRun.organization_id == access.context.organization_id
    )
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    run = access.authenticated.session.scalar(query)
    if run is None:
        raise HTTPException(404)
    return run


@router.get("/knowledge", response_model=list[DocumentResponse])
def documents(
    access: Read, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)
) -> list[KnowledgeDocument]:
    return list(
        access.authenticated.session.scalars(
            select(KnowledgeDocument)
            .where(KnowledgeDocument.organization_id == access.context.organization_id)
            .order_by(KnowledgeDocument.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )


@router.post("/knowledge", response_model=DocumentResponse, status_code=201)
def create_document(body: DocumentCreate, access: Manage) -> KnowledgeDocument:
    session = access.authenticated.session
    if (
        session.scalar(
            select(Workspace.id).where(
                Workspace.id == body.workspace_id,
                Workspace.organization_id == access.context.organization_id,
                Workspace.status == "ACTIVE",
            )
        )
        is None
    ):
        raise HTTPException(404)
    # Serialize bounded ingestion for this workspace to enforce a hard document cap.
    session.execute(
        text("SELECT id FROM workspaces WHERE id=:id FOR UPDATE"), {"id": body.workspace_id}
    )
    count = session.scalar(
        text("SELECT count(*) FROM knowledge_documents WHERE workspace_id=:id AND status='ACTIVE'"),
        {"id": body.workspace_id},
    )
    if count is not None and count >= 20:
        raise HTTPException(409)
    doc = KnowledgeDocument(
        organization_id=access.context.organization_id,
        workspace_id=body.workspace_id,
        title=body.title,
        content=body.content,
        content_hash=digest(body.content),
    )
    session.add(doc)
    session.flush()
    audit(access, "knowledge.created", doc.id)
    return doc


@router.delete("/knowledge/{document_id}", response_model=DocumentResponse)
def revoke_document(document_id: UUID, access: Manage) -> KnowledgeDocument:
    doc = access.authenticated.session.scalar(
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.organization_id == access.context.organization_id,
        )
        .with_for_update()
    )
    if doc is None:
        raise HTTPException(404)
    doc.status = "REVOKED"
    audit(access, "knowledge.revoked", doc.id)
    return doc


@router.get("/runs", response_model=list[RunResponse])
def runs(
    access: Read, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)
) -> list[TaskRun]:
    return list(
        access.authenticated.session.scalars(
            select(TaskRun)
            .where(TaskRun.organization_id == access.context.organization_id)
            .order_by(TaskRun.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
    )


@router.post("/runs", response_model=RunResponse, status_code=202)
def create_run(body: RunCreate, access: Write, request: Request) -> TaskRun:
    session = access.authenticated.session
    # Serialize same-tenant intake, including simultaneous idempotency keys.
    session.execute(
        text("SELECT id FROM organizations WHERE id=:id FOR UPDATE"),
        {"id": access.context.organization_id},
    )
    fingerprint = digest({"version": body.agent_version_id, "request": body.request_text})
    old = session.scalar(
        select(TaskRun).where(
            TaskRun.organization_id == access.context.organization_id,
            TaskRun.idempotency_key == body.idempotency_key,
        )
    )
    if old:
        if old.payload_hash != fingerprint:
            raise HTTPException(409)
        return old
    pair = session.execute(
        select(AgentVersion, AgentDefinition)
        .join(AgentDefinition, AgentVersion.agent_definition_id == AgentDefinition.id)
        .where(
            AgentVersion.id == body.agent_version_id,
            AgentVersion.organization_id == access.context.organization_id,
            AgentDefinition.lifecycle_status != "ARCHIVED",
        )
    ).first()
    if pair is None:
        raise HTTPException(404)
    version, agent = pair
    TeammateConfiguration.model_validate(version.configuration_snapshot["configuration"])
    run = TaskRun(
        organization_id=access.context.organization_id,
        workspace_id=agent.workspace_id,
        agent_version_id=version.id,
        created_by=access.authenticated.user_id,
        idempotency_key=body.idempotency_key,
        payload_hash=fingerprint,
        request_text=body.request_text,
    )
    from uuid import uuid4

    run.id = uuid4()
    reserve_intake(
        session,
        access.context.organization_id,
        request.app.state.settings.environment,
        "task_runs",
        f"task:{body.idempotency_key}",
        run.id,
    )
    session.add(run)
    session.flush()
    audit(access, "run.queued", run.id)
    return run


@router.get("/runs/{run_id}", response_model=RunResponse)
def run_detail(run_id: UUID, access: Read) -> TaskRun:
    return get_run(access, run_id)


@router.post("/runs/{run_id}/cancel", response_model=RunResponse)
def cancel_run(run_id: UUID, access: Write) -> TaskRun:
    run = get_run(access, run_id, True)
    if run.status in {"APPROVED", "REJECTED", "FAILED", "CANCELLED"}:
        raise HTTPException(409)
    run.status = "CANCELLED"
    run.claim_token = None
    run.revision += 1
    audit(access, "run.cancelled", run.id, run.revision)
    return run


@router.post("/runs/{run_id}/review", response_model=RunResponse)
def review_run(run_id: UUID, body: ReviewDecision, access: Manage) -> TaskRun:
    run = get_run(access, run_id, True)
    if (
        run.status != "AWAITING_REVIEW"
        or run.revision != body.expected_revision
        or run.artifact_hash != body.artifact_hash
        or run.review_expires_at is None
        or run.review_expires_at < datetime.now(UTC)
    ):
        raise HTTPException(409)
    if not eligible(access.authenticated.session, run) or digest(run.output) != run.artifact_hash:
        raise HTTPException(409)
    # Locks prevent a concurrent source revocation racing the review transaction.
    sources = list(
        access.authenticated.session.scalars(
            select(KnowledgeDocument)
            .where(
                KnowledgeDocument.id.in_([UUID(i) for i in run.source_ids]),
                KnowledgeDocument.organization_id == access.context.organization_id,
                KnowledgeDocument.workspace_id == run.workspace_id,
                KnowledgeDocument.status == "ACTIVE",
            )
            .with_for_update()
        )
    )
    if len(sources) != len(run.source_ids) or not sources:
        raise HTTPException(409)
    run.status = "APPROVED" if body.decision == "APPROVE" else "REJECTED"
    run.revision += 1
    if body.decision == "APPROVE":
        access.authenticated.session.add(
            ActionReceipt(
                organization_id=access.context.organization_id,
                run_id=run.id,
                reviewed_by=access.authenticated.user_id,
                artifact_hash=body.artifact_hash,
            )
        )
    audit(access, "run." + run.status.lower(), run.id, run.revision)
    return run


@router.get("/runs/{run_id}/receipt", response_model=ReceiptResponse)
def receipt(run_id: UUID, access: Read) -> ActionReceipt:
    get_run(access, run_id)
    result = access.authenticated.session.scalar(
        select(ActionReceipt).where(
            ActionReceipt.run_id == run_id,
            ActionReceipt.organization_id == access.context.organization_id,
        )
    )
    if result is None:
        raise HTTPException(404)
    return result


@router.get("/audit", response_model=list[dict[str, object]])
def audit_events(
    access: Audit, limit: int = Query(50, ge=1, le=100), offset: int = Query(0, ge=0)
) -> list[dict[str, object]]:
    rows = access.authenticated.session.scalars(
        select(AuditEvent)
        .where(AuditEvent.organization_id == access.context.organization_id)
        .order_by(AuditEvent.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return [
        {
            "id": row.id,
            "action": row.action,
            "resource_id": row.resource_id,
            "created_at": row.created_at,
            "metadata": row.safe_metadata,
        }
        for row in rows
    ]


@router.post("/runs/{run_id}/clarify", response_model=RunResponse)
def clarify(run_id: UUID, body: Clarification, access: Write) -> TaskRun:
    run = get_run(access, run_id, True)
    if run.status != "NEEDS_CLARIFICATION" or run.revision != body.expected_revision:
        raise HTTPException(409)
    request = run.request_text + "\nAdditional facts: " + body.additional_facts
    if len(request) > 4000:
        raise HTTPException(422)
    run.request_text = request
    run.status = "QUEUED"
    run.output = {}
    run.source_ids = []
    run.artifact_hash = None
    run.review_expires_at = None
    run.error_code = None
    run.revision += 1
    audit(access, "run.clarified", run.id, run.revision)
    return run


@router.get("/capabilities", response_model=ExecutionCapabilities)
def capabilities(access: Read, request: Request) -> dict[str, object]:
    from orqentra.sandbox.routes import runtime_available

    runtime = access.authenticated.session.scalar(select(WorkerRuntime))
    return {
        "model_provider": "openai",
        "model_configured": bool(request.app.state.settings.openai_api_key),
        "delivery_mode": "SIMULATED",
        "knowledge_format": "UTF-8 text",
        "workflow_engine": "LangGraph",
        "checkpoint_storage": "tenant-scoped PostgreSQL",
        "worker_online": bool(
            runtime and runtime.last_seen > datetime.now(UTC) - timedelta(seconds=180)
        ),
        "worker_last_seen": runtime.last_seen if runtime else None,
        "sandbox_execution_available": runtime_available(runtime),
    }
