from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Engine, or_, select

from orqentra.billing.service import record_generation
from orqentra.execution.provider import ProviderFailure
from orqentra.persistence.models import (
    AuditEvent,
    ChatConversation,
    ChatExchange,
    KnowledgeDocument,
    OrganizationMembership,
    Workspace,
)
from orqentra.persistence.session import TrustedOrganizationContext, transaction
from orqentra.rag.provider import answer
from orqentra.rag.service import require_restricted, retrieve


def chat_tick(engine: Engine, organization_id: UUID, key: str) -> bool:
    context = TrustedOrganizationContext(organization_id, UUID(int=0), uuid4())
    token = uuid4()
    with transaction(engine, context) as session:
        require_restricted(session)
        turn = session.scalar(
            select(ChatExchange)
            .where(
                ChatExchange.organization_id == organization_id,
                or_(
                    ChatExchange.status == "QUEUED",
                    (ChatExchange.status == "RUNNING")
                    & (ChatExchange.lease_until < datetime.now(UTC)),
                ),
            )
            .order_by(ChatExchange.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if turn is None:
            return False
        chat = session.get(ChatConversation, turn.conversation_id)
        assert chat is not None
        if chat.support_state != "AI":
            turn.status = "FAILED"
            turn.error_code = "human_handoff_requested"
            turn.claim_token = None
            turn.lease_until = None
            return True
        active = session.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.user_id == chat.created_by,
                OrganizationMembership.status == "ACTIVE",
            )
        )
        workspace = session.scalar(
            select(Workspace.id).where(
                Workspace.id == chat.workspace_id, Workspace.status == "ACTIVE"
            )
        )
        if not active or not workspace or turn.attempts >= 3:
            turn.status = "FAILED"
            turn.error_code = "chat_policy_or_attempt_limit"
            return True
        pending = session.scalar(
            select(KnowledgeDocument.id)
            .where(
                KnowledgeDocument.workspace_id == chat.workspace_id,
                KnowledgeDocument.status == "ACTIVE",
                KnowledgeDocument.index_status.in_(["PENDING", "INDEXING"]),
            )
            .limit(1)
        )
        if pending:
            return False
        turn.status = "RUNNING"
        turn.claim_token = token
        turn.lease_until = datetime.now(UTC) + timedelta(minutes=2)
        turn.attempts += 1
        turn_id = turn.id
        workspace_id = chat.workspace_id
        actor = chat.created_by
        question = turn.question
        history = list(
            session.scalars(
                select(ChatExchange.question)
                .where(
                    ChatExchange.conversation_id == chat.id,
                    ChatExchange.id != turn.id,
                    ChatExchange.status == "COMPLETED",
                )
                .order_by(ChatExchange.created_at.desc())
                .limit(3)
            )
        )
    failure = None
    citations = []
    output = ""
    usage: dict[str, Any] = {}
    try:
        sources = retrieve(
            engine,
            organization_id,
            workspace_id,
            question,
            key,
        )
        if not sources:
            output = (
                "I could not find relevant approved sources in this workspace. "
                "Add or index suitable knowledge before asking again."
            )
        else:
            result, usage = answer(key, question, sources, list(reversed(history)))
            allowed = {source["chunk_id"]: source for source in sources}
            if any(
                str(cite.chunk_id) not in allowed
                or cite.quote not in allowed[str(cite.chunk_id)]["content"]
                for cite in result.citations
            ):
                raise ProviderFailure("unsupported_chat_citation")
            if result.insufficient_evidence or not result.citations:
                output = (
                    "The approved sources do not contain enough evidence to answer this question. "
                    "Please provide a more specific question or add an approved source."
                )
            else:
                output = result.answer
                citations = [
                    {
                        "chunk_id": str(c.chunk_id),
                        "document_id": allowed[str(c.chunk_id)]["document_id"],
                        "title": allowed[str(c.chunk_id)]["title"],
                        "quote": c.quote,
                    }
                    for c in result.citations
                ]
    except ProviderFailure as exc:
        failure = str(exc)
    with transaction(engine, context) as session:
        require_restricted(session)
        turn = session.scalar(
            select(ChatExchange).where(ChatExchange.id == turn_id).with_for_update()
        )
        record_generation(session, organization_id, turn_id, token, usage)
        if turn is None or turn.status != "RUNNING" or turn.claim_token != token:
            return True
        active = session.scalar(
            select(OrganizationMembership.id).where(
                OrganizationMembership.organization_id == organization_id,
                OrganizationMembership.user_id == actor,
                OrganizationMembership.status == "ACTIVE",
            )
        )
        ids = {UUID(cite["document_id"]) for cite in citations}
        approved = set(
            session.scalars(
                select(KnowledgeDocument.id)
                .where(
                    KnowledgeDocument.id.in_(ids),
                    KnowledgeDocument.status == "ACTIVE",
                    KnowledgeDocument.workspace_id == workspace_id,
                )
                .with_for_update()
            )
        )
        if not active:
            failure = "membership_revoked"
        if ids != approved:
            failure = "chat_source_revoked"
        turn.status = "FAILED" if failure else "COMPLETED"
        turn.error_code = failure
        turn.claim_token = None
        turn.lease_until = None
        if not failure:
            turn.answer = output
            turn.citations = citations
            turn.usage = usage
        session.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor,
                action="chat." + turn.status.lower(),
                resource_type="chat",
                resource_id=turn.id,
                correlation_id=uuid4(),
                safe_metadata={},
            )
        )
    return True
