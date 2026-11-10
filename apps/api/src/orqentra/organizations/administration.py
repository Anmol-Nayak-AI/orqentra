"""Tenant administration with bounded exports and honest recorded-usage reporting."""

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import Field
from sqlalchemy import BigInteger, cast, func, select

from orqentra.auth.dependencies import AuthorizedOrganization, OrganizationPermission
from orqentra.execution.routes import audit
from orqentra.organizations.schemas import Contract
from orqentra.persistence.models import (
    AgentDefinition,
    AuditEvent,
    ChatConversation,
    ChatExchange,
    KnowledgeDocument,
    Organization,
    OrganizationMembership,
    TaskRun,
    Workspace,
)

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}/administration",
    tags=["organization administration"],
)
Manage = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("organization.update"))]
Audit = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("audit.read"))]


class AdministrationResponse(Contract):
    name: str
    slug: str
    status: str
    updated_at: datetime
    period_start: datetime
    period_end: datetime
    active_members: int
    active_workspaces: int
    active_documents: int
    indexed_documents: int
    teammates: int
    chat_turns: int
    task_runs: int
    recorded_input_tokens: int
    recorded_output_tokens: int
    pending_human_requests: int
    service_status: dict[str, str]
    usage_notice: str


class OrganizationNameUpdate(Contract):
    name: str = Field(min_length=1, max_length=200, pattern=r"\S")
    expected_updated_at: datetime


def organization(access: AuthorizedOrganization, lock: bool = False) -> Organization:
    statement = select(Organization).where(Organization.id == access.context.organization_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    item = access.authenticated.session.scalar(statement)
    if item is None:
        raise HTTPException(404)
    return item


@router.get("", response_model=AdministrationResponse)
def administration(access: Manage, request: Request) -> dict[str, object]:
    session = access.authenticated.session
    item = organization(access)
    end = datetime.now(UTC)
    start = end - timedelta(days=30)

    def count(model: Any, *criteria: Any) -> int:
        return int(
            session.scalar(
                select(func.count())
                .select_from(model)
                .where(model.organization_id == item.id, *criteria)
            )
            or 0
        )

    input_tokens = output_tokens = 0
    for model in (ChatExchange, TaskRun):
        values = session.execute(
            select(
                func.coalesce(func.sum(cast(model.usage["input_tokens"].astext, BigInteger)), 0),
                func.coalesce(func.sum(cast(model.usage["output_tokens"].astext, BigInteger)), 0),
            ).where(
                model.organization_id == item.id, model.created_at >= start, model.created_at <= end
            )
        ).one()
        input_tokens += int(values[0])
        output_tokens += int(values[1])
    return {
        "name": item.name,
        "slug": item.slug,
        "status": item.status,
        "updated_at": item.updated_at,
        "period_start": start,
        "period_end": end,
        "active_members": count(OrganizationMembership, OrganizationMembership.status == "ACTIVE"),
        "active_workspaces": count(Workspace, Workspace.status == "ACTIVE"),
        "active_documents": count(KnowledgeDocument, KnowledgeDocument.status == "ACTIVE"),
        "indexed_documents": count(
            KnowledgeDocument,
            KnowledgeDocument.status == "ACTIVE",
            KnowledgeDocument.index_status == "READY",
        ),
        "teammates": count(AgentDefinition),
        "chat_turns": count(
            ChatExchange, ChatExchange.created_at >= start, ChatExchange.created_at <= end
        ),
        "task_runs": count(TaskRun, TaskRun.created_at >= start, TaskRun.created_at <= end),
        "recorded_input_tokens": input_tokens,
        "recorded_output_tokens": output_tokens,
        "pending_human_requests": count(
            ChatConversation, ChatConversation.support_state.in_(["WAITING", "HUMAN"])
        ),
        "service_status": {
            "Payments": "Disabled — no checkout or live charges"
            if request.app.state.settings.billing_provider == "disabled"
            else "Test callbacks only — no checkout or live charges",
            "Isolated code execution": (
                "Unavailable — E2B requires verification and code-specific approval"
            ),
        },
        "usage_notice": (
            "Recorded generation usage only, not an invoice: excludes embeddings, "
            "failed/uncertain calls and earlier attempts overwritten by later usage. "
            "Counts cover the rolling 30-day period; resource counts are current."
        ),
    }


@router.patch("/name", response_model=dict[str, str])
def rename(body: OrganizationNameUpdate, access: Manage) -> dict[str, str]:
    item = organization(access, True)
    # Membership changes use the same organization lock: recheck after acquiring it.
    member = access.authenticated.session.scalar(
        select(OrganizationMembership)
        .where(
            OrganizationMembership.organization_id == item.id,
            OrganizationMembership.user_id == access.authenticated.user_id,
            OrganizationMembership.status == "ACTIVE",
        )
        .execution_options(populate_existing=True)
    )
    if member is None or member.role not in {"OWNER", "ADMIN"}:
        raise HTTPException(403)
    if item.updated_at != body.expected_updated_at:
        raise HTTPException(409)
    value = body.name.strip()
    if item.name != value:
        item.name = value
        audit(access, "organization.renamed", item.id)
        access.authenticated.session.flush()
    return {"name": item.name}


class ExportEvent(Contract):
    id: UUID
    created_at: datetime
    action: str
    resource_type: str
    resource_id: UUID
    actor_user_id: UUID
    correlation_id: UUID


class AuditExport(Contract):
    events: list[ExportEvent]
    next_before: datetime | None
    next_before_id: UUID | None


@router.get("/audit-export", response_model=AuditExport)
def export_audit(
    access: Audit,
    before: datetime | None = None,
    before_id: UUID | None = None,
    limit: int = Query(default=500, ge=1, le=1000),
) -> dict[str, object]:
    if (before is None) != (before_id is None):
        raise HTTPException(422)
    query = select(AuditEvent).where(AuditEvent.organization_id == access.context.organization_id)
    if before is not None:
        query = query.where(
            (AuditEvent.created_at < before)
            | ((AuditEvent.created_at == before) & (AuditEvent.id < before_id))
        )
    rows = list(
        access.authenticated.session.scalars(
            query.order_by(AuditEvent.created_at.desc(), AuditEvent.id.desc()).limit(limit + 1)
        )
    )
    more = len(rows) > limit
    visible = rows[:limit]
    return {
        "events": visible,
        "next_before": visible[-1].created_at if more else None,
        "next_before_id": visible[-1].id if more else None,
    }
