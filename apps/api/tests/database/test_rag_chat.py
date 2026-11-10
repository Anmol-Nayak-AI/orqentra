from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session
from test_execution import queued
from test_identity_authorization import add_existing_member, call

from orqentra.persistence.models import DemoMember, KnowledgeChunk, OrganizationMembership, User
from orqentra.rag.chat_worker import chat_tick
from orqentra.rag.provider import ChatAnswer
from orqentra.rag.service import retrieve


def chat_fixture(db: tuple[Engine, Engine]) -> tuple[str, str, dict[str, object], str]:
    subject, base, data = queued(db)
    doc = data["document"]
    assert isinstance(doc, dict)
    code, chat = call(db, subject, base + "/chats", "POST", {"workspace_id": doc["workspace_id"]})
    assert code == 201 and isinstance(chat, dict)
    return subject, base, doc, str(chat["id"])


def test_vector_retrieval_scope_ranking_and_revocation(db: tuple[Engine, Engine]) -> None:
    subject, base, data = queued(db)
    doc = data["document"]
    assert isinstance(doc, dict)
    _, other_base, _ = queued(db)
    tenant = UUID(base.split("/")[4])
    workspace = UUID(str(doc["workspace_id"]))
    found = retrieve(
        db[1], tenant, workspace, "What should onboarding teams verify?", "synthetic-key"
    )
    assert found and {r["document_id"] for r in found} == {doc["id"]}
    assert (
        retrieve(db[1], UUID(other_base.split("/")[4]), workspace, "Onboarding", "synthetic-key")
        == []
    )
    assert call(db, subject, f"{base}/knowledge/{doc['id']}", "DELETE")[0] == 200
    assert retrieve(db[1], tenant, workspace, "Onboarding", "synthetic-key") == []


def test_chat_citations_private_history_and_redaction(
    db: tuple[Engine, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    subject, base, doc, chat = chat_fixture(db)
    tenant = UUID(base.split("/")[4])
    path = f"{base}/chats/{chat}/messages"
    with Session(db[0]) as session:
        chunk = session.scalar(
            select(KnowledgeChunk).where(KnowledgeChunk.document_id == UUID(str(doc["id"])))
        )
        assert chunk is not None
        chunk_id = chunk.id
    result = ChatAnswer.model_validate(
        {
            "answer": "Verify customer identity before provisioning.",
            "citations": [
                {
                    "chunk_id": chunk_id,
                    "quote": "verify customer identity before account provisioning",
                }
            ],
            "insufficient_evidence": False,
        }
    )
    monkeypatch.setattr(
        "orqentra.rag.chat_worker.answer",
        lambda *args: (result, {"input_tokens": 10, "output_tokens": 10}),
    )
    body = {"question": "What must we verify before onboarding?", "idempotency_key": uuid4().hex}
    code, message = call(db, subject, path, "POST", body)
    assert code == 202 and isinstance(message, dict)
    assert call(db, subject, path, "POST", body)[1] == message
    assert call(db, subject, path, "POST", dict(body, question="A different question?"))[0] == 409
    assert chat_tick(db[1], tenant, "synthetic-key")
    code, messages = call(db, subject, path)
    assert (
        code == 200
        and isinstance(messages, list)
        and messages[0]["status"] == "COMPLETED"
        and messages[0]["citations"][0]["document_id"] == doc["id"]
    )
    other = "user_" + uuid4().hex
    add_existing_member(db, tenant, other, "MEMBER")
    assert call(db, other, path)[0] == 404
    assert call(db, subject, f"{base}/knowledge/{doc['id']}", "DELETE")[0] == 200
    _, messages = call(db, subject, path)
    assert (
        isinstance(messages, list)
        and messages[0]["status"] == "REDACTED"
        and messages[0]["citations"] == []
    )
    assert "Verify customer identity" not in messages[0]["answer"]


def test_chat_rejects_fabricated_citations(
    db: tuple[Engine, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    subject, base, doc, chat = chat_fixture(db)
    result = ChatAnswer.model_validate(
        {
            "answer": "Untrusted unsupported answer",
            "citations": [{"chunk_id": uuid4(), "quote": "invented quote not found anywhere"}],
            "insufficient_evidence": False,
        }
    )
    monkeypatch.setattr("orqentra.rag.chat_worker.answer", lambda *args: (result, {}))
    path = f"{base}/chats/{chat}/messages"
    assert (
        call(
            db,
            subject,
            path,
            "POST",
            {"question": "What is the policy?", "idempotency_key": uuid4().hex},
        )[0]
        == 202
    )
    assert chat_tick(db[1], UUID(base.split("/")[4]), "synthetic-key")
    _, messages = call(db, subject, path)
    assert (
        isinstance(messages, list)
        and messages[0]["status"] == "FAILED"
        and messages[0]["answer"] == ""
        and messages[0]["error_code"] == "unsupported_chat_citation"
    )


def test_demo_roster_never_grants_access(db: tuple[Engine, Engine]) -> None:
    subject, base, data = queued(db)
    tenant = UUID(base.split("/")[4])
    with Session(db[0]) as session, session.begin():
        before_users = session.query(User).count()
        before_members = session.query(OrganizationMembership).count()
        session.add(
            DemoMember(
                organization_id=tenant,
                display_name="Demo Person",
                email="demo.person@example.invalid",
                job_title="Fictional analyst",
                demo_role="ADMIN",
            )
        )
    code, roster = call(db, subject, base + "/demo-members")
    assert code == 200 and isinstance(roster, list) and roster[0]["display_name"] == "Demo Person"
    with Session(db[0]) as session:
        assert (
            session.query(User).count() == before_users
            and session.query(OrganizationMembership).count() == before_members
        )
    assert call(db, None, base + "/demo-members")[0] == 401


def test_live_vector_chat_opt_in(db: tuple[Engine, Engine]) -> None:
    import os

    if os.environ.get("ORQENTRA_LIVE_MODEL_TEST") != "1":
        pytest.skip("Explicit opt-in: real embeddings and OpenAI RAG answer.")
    key = os.environ.get("OPENAI_API_KEY")
    assert key
    subject, base, doc, chat = chat_fixture(db)
    path = f"{base}/chats/{chat}/messages"
    assert (
        call(
            db,
            subject,
            path,
            "POST",
            {
                "question": (
                    "According to the approved guide, what must we verify "
                    "before account provisioning?"
                ),
                "idempotency_key": uuid4().hex,
            },
        )[0]
        == 202
    )
    assert chat_tick(db[1], UUID(base.split("/")[4]), key)
    code, messages = call(db, subject, path)
    assert code == 200 and isinstance(messages, list)
    assert messages[0]["status"] == "COMPLETED" and messages[0]["citations"]
    assert all(
        c["document_id"] == doc["id"] and c["quote"] in doc["content"]
        for c in messages[0]["citations"]
    )


def test_topic_change_retrieves_current_question_not_old_topics(
    db: tuple[Engine, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    from orqentra.persistence.models import ChatExchange

    requester, base, _, chat = chat_fixture(db)
    path = f"{base}/chats/{chat}/messages"
    old = call(
        db,
        requester,
        path,
        "POST",
        {"question": "Old topic: demo support hours", "idempotency_key": uuid4().hex},
    )[1]
    with Session(db[0]) as session, session.begin():
        exchange = session.get(ChatExchange, UUID(old["id"]))
        exchange.status = "COMPLETED"
    current = "How do I use Orqentra chat?"
    assert (
        call(db, requester, path, "POST", {"question": current, "idempotency_key": uuid4().hex})[0]
        == 202
    )
    searched = []

    def search(engine, organization_id, workspace_id, question, key):
        searched.append(question)
        return []

    monkeypatch.setattr("orqentra.rag.chat_worker.retrieve", search)
    assert chat_tick(db[1], UUID(base.split("/")[4]), "synthetic-key")
    assert searched == [current]
