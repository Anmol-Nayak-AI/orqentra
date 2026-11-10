from datetime import UTC, datetime, timedelta
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import Engine, or_, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from orqentra.execution.provider import ProviderFailure
from orqentra.persistence.models import KnowledgeChunk, KnowledgeDocument
from orqentra.persistence.session import TrustedOrganizationContext, transaction
from orqentra.rag.provider import EMBEDDING_MODEL, embed


def require_restricted(session: Session) -> None:
    flags = session.execute(
        text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
    ).one()
    if any(flags):
        raise RuntimeError("Unsafe RAG runtime role.")


def chunks(text: str) -> list[str]:
    # Deterministic overlap; each excerpt stays small enough for citations and embeddings.
    return [
        text[start : start + 1500]
        for start in range(0, len(text), 1350)
        if text[start : start + 1500].strip()
    ]


def index_next(engine: Engine, organization_id: UUID, key: str) -> bool:
    context = TrustedOrganizationContext(organization_id, UUID(int=0), uuid4())
    token = uuid4()
    with transaction(engine, context) as session:
        require_restricted(session)
        document = session.scalar(
            select(KnowledgeDocument)
            .where(
                KnowledgeDocument.organization_id == organization_id,
                KnowledgeDocument.status == "ACTIVE",
                or_(
                    KnowledgeDocument.index_status == "PENDING",
                    (KnowledgeDocument.index_status == "INDEXING")
                    & (KnowledgeDocument.index_lease_until < datetime.now(UTC)),
                ),
            )
            .order_by(KnowledgeDocument.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if document is None:
            return False
        if document.index_attempts >= 3:
            document.index_status = "FAILED"
            document.index_error = "index_attempt_limit"
            return True
        document.index_status = "INDEXING"
        document.index_token = token
        document.index_attempts += 1
        document.index_lease_until = datetime.now(UTC) + timedelta(minutes=2)
        document_id = document.id
        workspace_id = document.workspace_id
        text = document.content
        content_hash = document.content_hash
    error = None
    vectors = []
    parts = chunks(text)
    try:
        vectors = embed(key, parts)
    except ProviderFailure as exc:
        error = str(exc)
    with transaction(engine, context) as session:
        require_restricted(session)
        document = session.scalar(
            select(KnowledgeDocument).where(KnowledgeDocument.id == document_id).with_for_update()
        )
        if (
            document is None
            or document.status != "ACTIVE"
            or document.index_token != token
            or document.content_hash != content_hash
        ):
            return True
        if error:
            document.index_status = "FAILED"
            document.index_error = error
        else:
            for ordinal, (part, vector) in enumerate(zip(parts, vectors, strict=True)):
                statement = insert(KnowledgeChunk).values(
                    id=uuid4(),
                    organization_id=organization_id,
                    workspace_id=workspace_id,
                    document_id=document_id,
                    ordinal=ordinal,
                    content=part,
                    embedding=vector,
                    embedding_model=EMBEDDING_MODEL,
                )
                session.execute(
                    statement.on_conflict_do_update(
                        index_elements=["document_id", "ordinal"],
                        set_={
                            "content": part,
                            "embedding": vector,
                            "embedding_model": EMBEDDING_MODEL,
                        },
                    )
                )
            document.index_status = "READY"
            document.index_error = None
        document.index_token = None
        document.index_lease_until = None
    return True


def retrieve(
    engine: Engine, organization_id: UUID, workspace_id: UUID, question: str, key: str
) -> list[dict[str, str]]:
    vector = embed(key, [question[:4000]])[0]
    context = TrustedOrganizationContext(organization_id, UUID(int=0), uuid4())
    with transaction(engine, context) as session:
        require_restricted(session)
        distance = KnowledgeChunk.embedding.cosine_distance(vector)
        rows = session.execute(
            select(KnowledgeChunk, KnowledgeDocument.title, distance.label("distance"))
            .join(KnowledgeDocument, KnowledgeChunk.document_id == KnowledgeDocument.id)
            .where(
                KnowledgeChunk.organization_id == organization_id,
                KnowledgeChunk.workspace_id == workspace_id,
                KnowledgeChunk.embedding_model == EMBEDDING_MODEL,
                KnowledgeDocument.organization_id == organization_id,
                KnowledgeDocument.workspace_id == workspace_id,
                KnowledgeDocument.status == "ACTIVE",
                KnowledgeDocument.index_status == "READY",
            )
            .order_by(distance, KnowledgeChunk.id)
            .limit(5)
        ).all()
        return [
            {
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "title": title,
                "content": chunk.content,
                "score": str(round(1 - float(score), 5)),
            }
            for chunk, title, score in cast(list[tuple[KnowledgeChunk, str, float]], rows)
            if 1 - float(score) >= 0.25
        ]
