"""Persisted code review; no code or remote SDK call runs in the API process."""

import hashlib
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field
from sqlalchemy import select

from orqentra.auth.dependencies import AuthorizedOrganization, OrganizationPermission
from orqentra.billing.service import reserve_intake
from orqentra.execution.policy import approved_sources_active, eligible
from orqentra.execution.routes import audit, digest, get_run
from orqentra.organizations.schemas import Contract
from orqentra.persistence.models import (
    CodeExecution,
    OrganizationMembership,
    TaskRun,
    WorkerRuntime,
)

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}", tags=["code review and isolated execution"]
)
Read = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("agent.read"))]
Write = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("agent.create"))]
Manage = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("agent.publish"))]


class CodeProposal(Contract):
    run_id: UUID
    title: str = Field(min_length=1, max_length=200, pattern=r"\S")
    code: str = Field(min_length=1, max_length=16384, pattern=r"\S")
    idempotency_key: str = Field(min_length=16, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")


class CodeDecision(Contract):
    expected_revision: int = Field(ge=1)
    code_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal["APPROVE", "REJECT"]


class CodeStart(Contract):
    expected_revision: int = Field(ge=1)
    code_hash: str = Field(pattern=r"^[a-f0-9]{64}$")


class CodeResult(Contract):
    id: UUID
    run_id: UUID
    created_by: UUID
    reviewed_by: UUID | None
    title: str
    code: str
    code_hash: str
    status: str
    revision: int
    approval_expires_at: datetime | None
    error_code: str | None
    output: str
    external_sandbox_id: str | None
    created_at: datetime


def code_hash(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def runtime_available(row: WorkerRuntime | None) -> bool:
    return bool(
        row and row.sandbox_available and row.last_seen > datetime.now(UTC) - timedelta(seconds=180)
    )


def parent_valid(access: AuthorizedOrganization, run_id: UUID) -> TaskRun:
    run = get_run(access, run_id, True)
    if (
        run.status != "APPROVED"
        or run.artifact_hash != digest(run.output)
        or not eligible(access.authenticated.session, run)
        or not approved_sources_active(access.authenticated.session, run)
    ):
        raise HTTPException(409)
    return run


def visible(access: AuthorizedOrganization, item_id: UUID) -> CodeExecution:
    query = select(CodeExecution).where(CodeExecution.id == item_id).with_for_update()
    if access.role not in {"OWNER", "ADMIN"}:
        query = query.where(CodeExecution.created_by == access.authenticated.user_id)
    row = access.authenticated.session.scalar(query)
    if row is None:
        raise HTTPException(404)
    return row


def current_member(access: AuthorizedOrganization) -> str:
    member = access.authenticated.session.scalar(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.user_id == access.authenticated.user_id,
            OrganizationMembership.status == "ACTIVE",
        )
        .execution_options(populate_existing=True)
    )
    if member is None:
        raise HTTPException(403)
    return member.role


@router.get("/code-executions", response_model=list[CodeResult])
def list_code(access: Read, limit: int = Query(50, ge=1, le=100)) -> list[CodeExecution]:
    query = select(CodeExecution)
    if access.role not in {"OWNER", "ADMIN"}:
        query = query.where(CodeExecution.created_by == access.authenticated.user_id)
    return list(
        access.authenticated.session.scalars(
            query.order_by(CodeExecution.created_at.desc()).limit(limit)
        )
    )


@router.post("/code-executions", response_model=CodeResult, status_code=201)
def propose(body: CodeProposal, access: Write) -> CodeExecution:
    if len(body.code.encode()) > 16384:
        raise HTTPException(422)
    parent_valid(access, body.run_id)
    if current_member(access) not in {"OWNER", "ADMIN", "MEMBER"}:
        raise HTTPException(403)
    session = access.authenticated.session
    old = session.scalar(
        select(CodeExecution).where(CodeExecution.idempotency_key == body.idempotency_key)
    )
    if old:
        if (
            old.created_by != access.authenticated.user_id
            or old.run_id != body.run_id
            or old.code != body.code
            or old.title != body.title
        ):
            raise HTTPException(409)
        return old
    count = session.scalar(
        select(CodeExecution.id).where(CodeExecution.run_id == body.run_id).offset(19).limit(1)
    )
    if count:
        raise HTTPException(409)
    item = CodeExecution(
        organization_id=access.context.organization_id,
        run_id=body.run_id,
        created_by=access.authenticated.user_id,
        title=body.title,
        code=body.code,
        code_hash=code_hash(body.code),
        idempotency_key=body.idempotency_key,
    )
    session.add(item)
    session.flush()
    audit(access, "code.proposed", item.id)
    return item


@router.post("/code-executions/{item_id}/review", response_model=CodeResult)
def review(item_id: UUID, body: CodeDecision, access: Manage) -> CodeExecution:
    item = visible(access, item_id)
    parent_valid(access, item.run_id)
    if (
        current_member(access) not in {"OWNER", "ADMIN"}
        or item.created_by == access.authenticated.user_id
    ):
        raise HTTPException(403)
    if (
        item.status != "AWAITING_REVIEW"
        or item.revision != body.expected_revision
        or item.code_hash != body.code_hash
        or code_hash(item.code) != item.code_hash
    ):
        raise HTTPException(409)
    item.status = "APPROVED" if body.decision == "APPROVE" else "REJECTED"
    item.reviewed_by = access.authenticated.user_id
    item.approval_expires_at = (
        datetime.now(UTC) + timedelta(hours=1) if item.status == "APPROVED" else None
    )
    item.revision += 1
    audit(access, "code." + item.status.lower(), item.id, item.revision)
    return item


@router.post("/code-executions/{item_id}/start", response_model=CodeResult)
def start(item_id: UUID, body: CodeStart, access: Write, request: Request) -> CodeExecution:
    item = visible(access, item_id)
    parent_valid(access, item.run_id)
    if current_member(access) not in {"OWNER", "ADMIN", "MEMBER"}:
        raise HTTPException(403)
    if item.code_hash != body.code_hash or code_hash(item.code) != item.code_hash:
        raise HTTPException(409)
    # A repeated start for the same accepted attempt does not queue/consume again.
    if item.status in {"QUEUED", "RUNNING", "COMPLETED", "UNKNOWN", "FAILED"}:
        return item
    if (
        item.status != "APPROVED"
        or item.revision != body.expected_revision
        or not item.approval_expires_at
        or item.approval_expires_at <= datetime.now(UTC)
    ):
        raise HTTPException(409)
    reviewer = access.authenticated.session.scalar(
        select(OrganizationMembership.id).where(
            OrganizationMembership.user_id == item.reviewed_by,
            OrganizationMembership.status == "ACTIVE",
            OrganizationMembership.role.in_(["OWNER", "ADMIN"]),
        )
    )
    if reviewer is None:
        raise HTTPException(409)
    state = access.authenticated.session.scalar(select(WorkerRuntime))
    if not runtime_available(state):
        raise HTTPException(503)
    reserve_intake(
        access.authenticated.session,
        access.context.organization_id,
        request.app.state.settings.environment,
        "sandbox_runs",
        "sandbox:" + str(item.id),
        item.id,
    )
    item.status = "QUEUED"
    item.revision += 1
    audit(access, "code.queued", item.id, item.revision)
    return item


@router.post("/code-executions/{item_id}/cancel", response_model=CodeResult)
def cancel(item_id: UUID, access: Write) -> CodeExecution:
    item = visible(access, item_id)
    parent_valid(access, item.run_id)
    if item.status not in {"AWAITING_REVIEW", "APPROVED", "QUEUED"}:
        # A started remote call cannot be represented as cancelled locally.
        raise HTTPException(409)
    item.status = "CANCELLED"
    item.revision += 1
    audit(access, "code.cancelled", item.id, item.revision)
    return item
