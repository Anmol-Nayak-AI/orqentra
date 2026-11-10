from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import Field
from sqlalchemy import select, text

from orqentra.auth.dependencies import AuthorizedOrganization, OrganizationPermission
from orqentra.billing.service import reserve_intake
from orqentra.execution.routes import audit
from orqentra.organizations.schemas import Contract
from orqentra.persistence.models import (
    ChatConversation,
    ChatExchange,
    DemoMember,
    HumanChatMessage,
    KnowledgeDocument,
    Workspace,
)

router = APIRouter(
    prefix="/api/v1/organizations/{organization_id}", tags=["RAG chat and demo roster"]
)
Read = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("agent.read"))]
Manage = Annotated[AuthorizedOrganization, Depends(OrganizationPermission("agent.publish"))]


class ConversationCreate(Contract):
    workspace_id: UUID


class ConversationResponse(Contract):
    id: UUID
    workspace_id: UUID
    title: str
    created_at: datetime
    support_state: str
    assigned_to: UUID | None


class MessageCreate(Contract):
    question: str = Field(min_length=3, max_length=2000, pattern=r"\S")
    idempotency_key: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")


class MessageResponse(Contract):
    id: UUID
    question: str
    answer: str
    citations: list[dict[str, str]]
    status: str
    error_code: str | None
    created_at: datetime


class DemoMemberResponse(Contract):
    id: UUID
    display_name: str
    email: str
    job_title: str
    demo_role: str


def conversation(
    access: AuthorizedOrganization, conversation_id: UUID, lock: bool = False, support: bool = False
) -> ChatConversation:
    query = select(ChatConversation).where(
        ChatConversation.id == conversation_id,
        ChatConversation.organization_id == access.context.organization_id,
    )
    if support and access.role.value in {"OWNER", "ADMIN"}:
        query = query.where(
            (ChatConversation.created_by == access.authenticated.user_id)
            | (ChatConversation.support_state.in_(["WAITING", "HUMAN"]))
        )
    else:
        query = query.where(ChatConversation.created_by == access.authenticated.user_id)
    if lock:
        query = query.with_for_update()
    result = access.authenticated.session.scalar(query)
    if result is None:
        raise HTTPException(404)
    return result


@router.get("/demo-members", response_model=list[DemoMemberResponse])
def demo_members(access: Read) -> list[DemoMember]:
    return list(
        access.authenticated.session.scalars(
            select(DemoMember)
            .where(DemoMember.organization_id == access.context.organization_id)
            .order_by(DemoMember.display_name)
            .limit(50)
        )
    )


@router.get("/chats", response_model=list[ConversationResponse])
def chats(access: Read) -> list[ChatConversation]:
    return list(
        access.authenticated.session.scalars(
            select(ChatConversation)
            .where(
                ChatConversation.organization_id == access.context.organization_id,
                ChatConversation.created_by == access.authenticated.user_id,
            )
            .order_by(ChatConversation.created_at.desc())
            .limit(50)
        )
    )


@router.post("/chats", response_model=ConversationResponse, status_code=201)
def create_chat(body: ConversationCreate, access: Read) -> ChatConversation:
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
    item = ChatConversation(
        organization_id=access.context.organization_id,
        workspace_id=body.workspace_id,
        created_by=access.authenticated.user_id,
    )
    session.add(item)
    session.flush()
    audit(access, "chat.created", item.id)
    return item


@router.get("/chats/{conversation_id}/messages", response_model=list[MessageResponse])
def messages(conversation_id: UUID, access: Read) -> list[dict[str, object]]:
    conversation(access, conversation_id, support=True)
    session = access.authenticated.session
    active = set(
        str(i)
        for i in session.scalars(
            select(KnowledgeDocument.id).where(KnowledgeDocument.status == "ACTIVE")
        )
    )
    result = []
    rows = session.scalars(
        select(ChatExchange)
        .where(
            ChatExchange.conversation_id == conversation_id,
            ChatExchange.organization_id == access.context.organization_id,
        )
        .order_by(ChatExchange.created_at, ChatExchange.id)
        .limit(100)
    )
    for item in rows:
        redacted = any(cite.get("document_id") not in active for cite in item.citations)
        result.append(
            {
                "id": item.id,
                "question": item.question,
                "answer": "A source was revoked; this answer is no longer available."
                if redacted
                else item.answer,
                "citations": [] if redacted else item.citations,
                "status": "REDACTED" if redacted else item.status,
                "error_code": item.error_code,
                "created_at": item.created_at,
            }
        )
    return result


@router.post("/chats/{conversation_id}/messages", response_model=MessageResponse, status_code=202)
def send_message(
    conversation_id: UUID, body: MessageCreate, access: Read, request: Request
) -> ChatExchange:
    chat = conversation(access, conversation_id, True)
    session = access.authenticated.session
    old = session.scalar(
        select(ChatExchange).where(
            ChatExchange.conversation_id == chat.id,
            ChatExchange.idempotency_key == body.idempotency_key,
        )
    )
    if old:
        if old.question != body.question:
            raise HTTPException(409)
        return old
    if chat.support_state != "AI":
        raise HTTPException(409, "AI is paused during human support.")
    # A single pending turn preserves conversational order; serialize the tenant quota.
    session.execute(
        text("SELECT id FROM organizations WHERE id=:id FOR UPDATE"),
        {"id": access.context.organization_id},
    )
    if session.scalar(
        select(ChatExchange.id).where(
            ChatExchange.conversation_id == chat.id, ChatExchange.status.in_(["QUEUED", "RUNNING"])
        )
    ):
        raise HTTPException(409)
    item = ChatExchange(
        organization_id=access.context.organization_id,
        conversation_id=chat.id,
        question=body.question,
        idempotency_key=body.idempotency_key,
    )
    from uuid import uuid4

    item.id = uuid4()
    reserve_intake(
        session,
        access.context.organization_id,
        request.app.state.settings.environment,
        "chat_turns",
        f"chat:{chat.id}:{body.idempotency_key}",
        item.id,
    )
    chat.title = body.question[:100]
    session.add(item)
    session.flush()
    audit(access, "chat.message_queued", item.id)
    return item


@router.post("/knowledge/{document_id}/reindex", response_model=dict[str, str])
def reindex(document_id: UUID, access: Manage) -> dict[str, str]:
    doc = access.authenticated.session.scalar(
        select(KnowledgeDocument)
        .where(
            KnowledgeDocument.id == document_id,
            KnowledgeDocument.organization_id == access.context.organization_id,
            KnowledgeDocument.status == "ACTIVE",
        )
        .with_for_update()
    )
    if doc is None:
        raise HTTPException(404)
    if doc.index_status == "INDEXING":
        raise HTTPException(409)
    doc.index_status = "PENDING"
    doc.index_attempts = 0
    doc.index_error = None
    doc.index_token = None
    audit(access, "knowledge.reindex_requested", doc.id)
    return {"index_status": "PENDING"}


class HumanMessageCreate(Contract):
    content: str = Field(min_length=1, max_length=4000, pattern=r"\S")
    idempotency_key: str = Field(min_length=8, max_length=100, pattern=r"^[A-Za-z0-9_-]+$")


class HumanMessageResponse(Contract):
    id: UUID
    sender_role: str
    content: str
    created_at: datetime


@router.get("/support/chats", response_model=list[ConversationResponse])
def support_queue(access: Manage) -> list[ChatConversation]:
    return list(
        access.authenticated.session.scalars(
            select(ChatConversation)
            .where(
                ChatConversation.organization_id == access.context.organization_id,
                ChatConversation.support_state.in_(["WAITING", "HUMAN"]),
            )
            .order_by(ChatConversation.created_at)
            .limit(100)
        )
    )


@router.get("/chats/{conversation_id}", response_model=ConversationResponse)
def get_chat(conversation_id: UUID, access: Read) -> ChatConversation:
    return conversation(access, conversation_id, support=True)


@router.post("/chats/{conversation_id}/handoff", response_model=ConversationResponse)
def request_handoff(conversation_id: UUID, access: Read) -> ChatConversation:
    chat = conversation(access, conversation_id, True)
    if chat.support_state != "AI":
        return chat
    chat.support_state = "WAITING"
    chat.assigned_to = None
    # Fence off queued/in-flight AI output. Keep every question and previous reply.
    turns = access.authenticated.session.scalars(
        select(ChatExchange)
        .where(
            ChatExchange.conversation_id == chat.id,
            ChatExchange.status.in_(["QUEUED", "RUNNING"]),
        )
        .with_for_update()
    )
    for turn in turns:
        turn.status = "FAILED"
        turn.error_code = "human_handoff_requested"
        turn.claim_token = None
        turn.lease_until = None
    audit(access, "chat.handoff_requested", chat.id)
    return chat


@router.post("/chats/{conversation_id}/claim", response_model=ConversationResponse)
def claim_handoff(conversation_id: UUID, access: Manage) -> ChatConversation:
    chat = conversation(access, conversation_id, True, support=True)
    if chat.support_state == "AI" or chat.created_by == access.authenticated.user_id:
        raise HTTPException(409)
    if chat.assigned_to and chat.assigned_to != access.authenticated.user_id:
        raise HTTPException(409, "Another support teammate has claimed this conversation.")
    if chat.support_state != "HUMAN":
        chat.support_state = "HUMAN"
        chat.assigned_to = access.authenticated.user_id
        audit(access, "chat.handoff_claimed", chat.id)
    return chat


@router.post("/chats/{conversation_id}/resume", response_model=ConversationResponse)
def resume_ai(conversation_id: UUID, access: Read) -> ChatConversation:
    chat = conversation(access, conversation_id, True, support=True)
    if (
        chat.created_by != access.authenticated.user_id
        and chat.assigned_to != access.authenticated.user_id
    ):
        raise HTTPException(403)
    if chat.support_state != "AI":
        chat.support_state = "AI"
        chat.assigned_to = None
        audit(access, "chat.handoff_resolved", chat.id)
    return chat


@router.get("/chats/{conversation_id}/human-messages", response_model=list[HumanMessageResponse])
def human_messages(conversation_id: UUID, access: Read) -> list[HumanChatMessage]:
    chat = conversation(access, conversation_id, support=True)
    rows = list(
        access.authenticated.session.scalars(
            select(HumanChatMessage)
            .where(
                HumanChatMessage.conversation_id == chat.id,
            )
            .order_by(HumanChatMessage.created_at.desc(), HumanChatMessage.id.desc())
            .limit(100)
        )
    )
    return list(reversed(rows))


@router.post(
    "/chats/{conversation_id}/human-messages", response_model=HumanMessageResponse, status_code=201
)
def send_human_message(
    conversation_id: UUID, body: HumanMessageCreate, access: Read
) -> HumanChatMessage:
    chat = conversation(access, conversation_id, True, support=True)
    sender = access.authenticated.user_id
    if chat.support_state == "AI":
        raise HTTPException(409)
    if sender == chat.created_by:
        role = "REQUESTER"
    elif (
        access.role.value in {"OWNER", "ADMIN"}
        and chat.assigned_to == sender
        and chat.support_state == "HUMAN"
    ):
        role = "SUPPORT"
    else:
        raise HTTPException(403)
    old = access.authenticated.session.scalar(
        select(HumanChatMessage).where(
            HumanChatMessage.conversation_id == chat.id,
            HumanChatMessage.idempotency_key == body.idempotency_key,
        )
    )
    if old:
        if old.sender_id != sender or old.content != body.content:
            raise HTTPException(409)
        return old
    item = HumanChatMessage(
        organization_id=access.context.organization_id,
        conversation_id=chat.id,
        sender_id=sender,
        sender_role=role,
        content=body.content,
        idempotency_key=body.idempotency_key,
    )
    access.authenticated.session.add(item)
    access.authenticated.session.flush()
    audit(access, "chat.human_message_sent", item.id)
    return item
