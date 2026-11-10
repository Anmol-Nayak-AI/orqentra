from concurrent.futures import ThreadPoolExecutor
from uuid import UUID, uuid4

from sqlalchemy import Engine
from test_identity_authorization import add_existing_member, call
from test_rag_chat import chat_fixture

from orqentra.rag.chat_worker import chat_tick


def test_handoff_privacy_claim_reply_resume(db: tuple[Engine, Engine]) -> None:
    requester, base, _, chat = chat_fixture(db)
    tenant = UUID(base.split("/")[4])
    admin, other_admin, member = ["user_" + uuid4().hex for _ in range(3)]
    for subject, role in [(admin, "ADMIN"), (other_admin, "ADMIN"), (member, "MEMBER")]:
        add_existing_member(db, tenant, subject, role)
    path = f"{base}/chats/{chat}"
    assert call(db, admin, path + "/messages")[0] == 404
    assert call(db, member, base + "/support/chats")[0] == 403
    assert (
        call(
            db,
            requester,
            path + "/messages",
            "POST",
            {"question": "Question to cancel safely", "idempotency_key": uuid4().hex},
        )[0]
        == 202
    )
    assert call(db, requester, path + "/handoff", "POST")[1]["support_state"] == "WAITING"
    assert not chat_tick(db[1], tenant, "synthetic-key")
    assert call(db, requester, path + "/messages")[1][0]["error_code"] == "human_handoff_requested"
    assert call(db, admin, path + "/messages")[0] == 200
    assert call(db, member, path + "/messages")[0] == 404
    assert call(db, requester, path + "/claim", "POST")[0] == 409
    assert len(call(db, admin, base + "/support/chats")[1]) == 1
    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(
            pool.map(
                lambda subject: (subject, call(db, subject, path + "/claim", "POST")[0]),
                [admin, other_admin],
            )
        )
    assert sorted(code for _, code in claims) == [200, 409]
    winner = next(subject for subject, code in claims if code == 200)
    loser = next(subject for subject, code in claims if code == 409)
    body = {"content": "A real support reply", "idempotency_key": uuid4().hex}
    assert call(db, loser, path + "/human-messages", "POST", body)[0] == 403
    code, response = call(db, winner, path + "/human-messages", "POST", body)
    assert code == 201 and response["sender_role"] == "SUPPORT"
    assert call(db, winner, path + "/human-messages", "POST", body)[1] == response
    assert call(db, requester, path + "/human-messages")[1][0]["content"] == body["content"]
    assert (
        call(
            db,
            requester,
            path + "/messages",
            "POST",
            {"question": "AI must pause", "idempotency_key": uuid4().hex},
        )[0]
        == 409
    )
    assert call(db, loser, path + "/resume", "POST")[0] == 403
    assert call(db, requester, path + "/resume", "POST")[1]["support_state"] == "AI"
    assert call(db, winner, path + "/messages")[0] == 404
    assert call(db, requester, path + "/human-messages")[1][0]["content"] == body["content"]
    assert call(db, None, path + "/handoff", "POST")[0] == 401
    _, other_base, _, _ = chat_fixture(db)
    add_existing_member(db, UUID(other_base.split("/")[4]), requester, "ADMIN")
    assert call(db, requester, other_base + f"/chats/{chat}/human-messages")[0] == 404


def test_handoff_fences_an_inflight_ai_reply(db: tuple[Engine, Engine], monkeypatch) -> None:
    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from orqentra.persistence.models import KnowledgeChunk
    from orqentra.rag.provider import ChatAnswer

    requester, base, document, chat = chat_fixture(db)
    path = f"{base}/chats/{chat}"
    with Session(db[0]) as session:
        chunk = session.scalar(
            select(KnowledgeChunk).where(KnowledgeChunk.document_id == UUID(document["id"]))
        )
        result = ChatAnswer.model_validate(
            {
                "answer": "An answer that must not publish after handoff",
                "insufficient_evidence": False,
                "citations": [{"chunk_id": str(chunk.id), "quote": chunk.content[:50]}],
            }
        )

    def interrupt(*args):
        assert call(db, requester, path + "/handoff", "POST")[0] == 200
        return result, {}

    monkeypatch.setattr("orqentra.rag.chat_worker.answer", interrupt)
    assert (
        call(
            db,
            requester,
            path + "/messages",
            "POST",
            {"question": "What should I verify?", "idempotency_key": uuid4().hex},
        )[0]
        == 202
    )
    assert chat_tick(db[1], UUID(base.split("/")[4]), "synthetic-key")
    message = call(db, requester, path + "/messages")[1][0]
    assert message["status"] == "FAILED" and message["answer"] == ""
    assert message["error_code"] == "human_handoff_requested"
