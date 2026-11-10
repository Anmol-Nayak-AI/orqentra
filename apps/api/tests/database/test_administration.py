from uuid import UUID, uuid4

from sqlalchemy import Engine
from sqlalchemy.orm import Session
from test_identity_authorization import add_existing_member, call
from test_rag_chat import chat_fixture

from orqentra.persistence.models import ChatExchange


def test_administration_is_scoped_and_name_updates_conflict(db: tuple[Engine, Engine]) -> None:
    owner, base, _, chat = chat_fixture(db)
    other, other_base, _, other_chat = chat_fixture(db)
    tenant = UUID(base.split("/")[4])
    for organization_id, chat_id, tokens in [
        (tenant, chat, 12),
        (UUID(other_base.split("/")[4]), other_chat, 99999),
    ]:
        with Session(db[0]) as session, session.begin():
            session.add(
                ChatExchange(
                    organization_id=organization_id,
                    conversation_id=UUID(chat_id),
                    idempotency_key=uuid4().hex,
                    question="Synthetic usage only",
                    status="COMPLETED",
                    usage={"input_tokens": tokens, "output_tokens": 3},
                )
            )
    status, overview = call(db, owner, base + "/administration")
    assert status == 200 and overview["active_members"] == 1
    assert overview["recorded_input_tokens"] == 12 and overview["recorded_output_tokens"] == 3
    assert overview["chat_turns"] == 1
    assert "not an invoice" in overview["usage_notice"]
    viewer = "user_" + uuid4().hex
    add_existing_member(db, tenant, viewer, "VIEWER")
    assert call(db, viewer, base + "/administration")[0] == 403
    assert call(db, other, base + "/administration")[0] == 403
    assert call(db, None, base + "/administration")[0] == 401
    update = {"name": "Renamed team", "expected_updated_at": overview["updated_at"]}
    assert call(db, owner, base + "/administration/name", "PATCH", update)[0] == 200
    assert (
        call(
            db, owner, base + "/administration/name", "PATCH", dict(update, name="Stale overwrite")
        )[0]
        == 409
    )
    assert call(db, viewer, base + "/administration/name", "PATCH", update)[0] == 403
    status, exported = call(db, owner, base + "/administration/audit-export?limit=1")
    assert status == 200 and len(exported["events"]) == 1
    assert exported["next_before"] and exported["next_before_id"]
    from urllib.parse import urlencode

    next_url = (
        base
        + "/administration/audit-export?"
        + urlencode(
            {
                "before": exported["next_before"],
                "before_id": exported["next_before_id"],
                "limit": 100,
            }
        )
    )
    code, page = call(db, owner, next_url)
    assert code == 200 and page["events"]
    assert exported["events"][0]["id"] not in {event["id"] for event in page["events"]}
    assert any(
        event["action"] == "organization.renamed" for event in exported["events"] + page["events"]
    )
    assert call(db, viewer, base + "/administration/audit-export")[0] == 403
    assert (
        call(db, owner, base + "/administration/audit-export?before_id=" + str(uuid4()))[0] == 422
    )
