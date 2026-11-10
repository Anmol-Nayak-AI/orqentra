from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, text
from test_agents import setup_agent
from test_identity_authorization import call

from orqentra.execution.schemas import OnboardingPlan
from orqentra.execution.worker import tick
from orqentra.persistence.session import TrustedOrganizationContext, transaction


def queued(
    db: tuple[Engine, Engine],
    request_text: str | None = None,
    source_text: str | None = None,
    workflow: str = "onboarding.v1",
) -> tuple[str, str, dict[str, object]]:
    subject, agents, body = setup_agent(db)
    body["configuration"] = {
        "instructions": "Use approved sources and request missing details before drafting.",
        "tools": ["knowledge.search", "draft.compose"],
        "workflow": workflow,
        "output_schema": "python_analysis_plan.v1"
        if workflow == "python-analysis.v1"
        else "onboarding_plan.v1",
    }
    code, agent = call(db, subject, agents, "POST", body)
    assert code == 201 and isinstance(agent, dict)
    code, version = call(
        db, subject, f"{agents}/{agent['id']}/publish", "POST", {"expected_revision": 1}
    )
    assert code == 201 and isinstance(version, dict)
    base = agents.removesuffix("/agents")
    code, doc = call(
        db,
        subject,
        base + "/knowledge",
        "POST",
        {
            "workspace_id": body["workspace_id"],
            "title": "Approved guide",
            "content": source_text
            or ("Every onboarding team must verify customer identity before account provisioning."),
        },
    )
    assert code == 201 and isinstance(doc, dict)
    from orqentra.rag.service import index_next

    assert index_next(
        db[1],
        UUID(base.split("/")[4]),
        __import__("os").environ.get("OPENAI_API_KEY", "synthetic-test-key"),
    )
    request = {
        "agent_version_id": version["id"],
        "idempotency_key": uuid4().hex,
        "request_text": request_text
        or "Prepare a customer onboarding plan for an enterprise customer.",
    }
    code, run = call(db, subject, base + "/runs", "POST", request)
    assert code == 202 and isinstance(run, dict)
    assert call(db, subject, base + "/runs", "POST", request)[1] == run
    assert (
        call(
            db,
            subject,
            base + "/runs",
            "POST",
            dict(request, request_text="Different customer request."),
        )[0]
        == 409
    )
    return subject, base, {"run": run, "document": doc}


def fixture_plan(document_id: object) -> OnboardingPlan:
    return OnboardingPlan.model_validate(
        {
            "summary": "Synthetic provider test output",
            "checklist": [
                {
                    "task": "Verify identity",
                    "evidence": [
                        {
                            "document_id": document_id,
                            "quote": "verify customer identity before account provisioning",
                        }
                    ],
                }
            ],
            "missing_information": [],
            "draft_reply": "Please verify customer identity before provisioning.",
        }
    )


def test_durable_task_review_and_simulated_receipt(
    db: tuple[Engine, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    subject, base, data = queued(db)
    run = data["run"]
    doc = data["document"]
    assert isinstance(run, dict) and isinstance(doc, dict)
    monkeypatch.setattr(
        "orqentra.execution.worker.generate",
        lambda *args: (
            fixture_plan(doc["id"]),
            {"input_tokens": 100, "output_tokens": 50, "provider": "synthetic_test"},
        ),
    )
    org = UUID(base.split("/")[4])
    assert tick(db[1], org, "synthetic-test-key")
    path = f"{base}/runs/{run['id']}"
    code, result = call(db, subject, path)
    assert code == 200 and isinstance(result, dict) and result["status"] == "AWAITING_REVIEW"
    decision = {
        "expected_revision": result["revision"],
        "artifact_hash": result["artifact_hash"],
        "decision": "APPROVE",
    }
    assert (
        call(db, subject, path + "/review", "POST", dict(decision, expected_revision=1))[0] == 409
    )
    assert call(db, subject, path + "/review", "POST", decision)[0] == 200
    assert call(db, subject, path + "/review", "POST", decision)[0] == 409
    code, receipt = call(db, subject, path + "/receipt")
    assert code == 200 and isinstance(receipt, dict) and receipt["mode"] == "SIMULATED"
    with db[0].begin() as c:
        assert (
            c.scalar(
                text("SELECT count(*) FROM action_receipts WHERE run_id=:id"),
                {"id": UUID(str(run["id"]))},
            )
            == 1
        )


def test_source_revocation_blocks_review(
    db: tuple[Engine, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    subject, base, data = queued(db)
    run = data["run"]
    doc = data["document"]
    assert isinstance(run, dict) and isinstance(doc, dict)
    monkeypatch.setattr(
        "orqentra.execution.worker.generate", lambda *args: (fixture_plan(doc["id"]), {})
    )
    assert tick(db[1], UUID(base.split("/")[4]), "synthetic-test-key")
    path = f"{base}/runs/{run['id']}"
    _, result = call(db, subject, path)
    assert isinstance(result, dict)
    assert call(db, subject, f"{base}/knowledge/{doc['id']}", "DELETE")[0] == 200
    assert (
        call(
            db,
            subject,
            path + "/review",
            "POST",
            {
                "expected_revision": result["revision"],
                "artifact_hash": result["artifact_hash"],
                "decision": "APPROVE",
            },
        )[0]
        == 409
    )


def test_cancel_and_rls_new_tables(db: tuple[Engine, Engine]) -> None:
    subject, base, data = queued(db)
    run = data["run"]
    assert isinstance(run, dict)
    assert call(db, subject, f"{base}/runs/{run['id']}/cancel", "POST")[0] == 200
    assert not tick(db[1], UUID(base.split("/")[4]), "synthetic-test-key")
    other, other_base, other_data = queued(db)
    assert call(db, other, f"{base}/runs/{run['id']}")[0] == 403
    assert call(db, other, f"{other_base}/runs/{run['id']}")[0] == 404
    context = TrustedOrganizationContext(UUID(other_base.split("/")[4]), UUID(int=0), uuid4())
    with transaction(db[1], context) as session:
        for table in ("knowledge_documents", "task_runs", "action_receipts"):
            assert set(session.scalars(text(f"SELECT organization_id FROM {table}"))) <= {
                context.organization_id
            }
    with db[1].connect() as connection:
        for table in ("knowledge_documents", "task_runs", "action_receipts"):
            assert connection.scalar(text(f"SELECT count(*) FROM {table}")) == 0


def test_cancellation_during_model_call_discards_output(
    db: tuple[Engine, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    subject, base, data = queued(db)
    run = data["run"]
    doc = data["document"]
    assert isinstance(run, dict) and isinstance(doc, dict)
    path = f"{base}/runs/{run['id']}"

    def provider(*args: object) -> tuple[OnboardingPlan, dict[str, object]]:
        assert call(db, subject, path + "/cancel", "POST")[0] == 200
        return fixture_plan(doc["id"]), {}

    monkeypatch.setattr("orqentra.execution.worker.generate", provider)
    assert tick(db[1], UUID(base.split("/")[4]), "synthetic-test-key")
    _, result = call(db, subject, path)
    assert isinstance(result, dict) and result["status"] == "CANCELLED" and result["output"] == {}


def test_unsupported_quotes_fail_closed(
    db: tuple[Engine, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    subject, base, data = queued(db)
    run = data["run"]
    doc = data["document"]
    assert isinstance(run, dict) and isinstance(doc, dict)
    plan = fixture_plan(doc["id"])
    plan.checklist[0].evidence[0].quote = "Fabricated source quote that is not in the document."
    monkeypatch.setattr("orqentra.execution.worker.generate", lambda *args: (plan, {}))
    assert tick(db[1], UUID(base.split("/")[4]), "synthetic-test-key")
    _, result = call(db, subject, f"{base}/runs/{run['id']}")
    assert (
        isinstance(result, dict)
        and result["status"] == "FAILED"
        and result["error_code"] == "unsupported_evidence"
    )


def test_worker_recovers_expired_claim_with_new_fence(
    db: tuple[Engine, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    subject, base, data = queued(db)
    run = data["run"]
    doc = data["document"]
    assert isinstance(run, dict) and isinstance(doc, dict)
    old_claim = uuid4()
    with db[0].begin() as connection:
        connection.execute(
            text(
                "UPDATE task_runs SET status='RUNNING',claim_token=:claim,"
                "lease_until=now()-interval '1 minute',attempts=1,usage='{}' WHERE id=:id"
            ),
            {"claim": old_claim, "id": UUID(str(run["id"]))},
        )
    monkeypatch.setattr(
        "orqentra.execution.worker.generate", lambda *args: (fixture_plan(doc["id"]), {})
    )
    assert tick(db[1], UUID(base.split("/")[4]), "synthetic-test-key")
    _, result = call(db, subject, f"{base}/runs/{run['id']}")
    assert (
        isinstance(result, dict)
        and result["status"] == "AWAITING_REVIEW"
        and result["attempts"] == 2
    )


def test_worker_retry_is_bounded_and_delayed(
    db: tuple[Engine, Engine], monkeypatch: pytest.MonkeyPatch
) -> None:
    from orqentra.execution.provider import ProviderFailure

    subject, base, data = queued(db)
    run = data["run"]
    assert isinstance(run, dict)

    def unavailable(*args: object) -> None:
        raise ProviderFailure("provider_retryable")

    monkeypatch.setattr("orqentra.execution.worker.generate", unavailable)
    tenant = UUID(base.split("/")[4])
    assert tick(db[1], tenant, "synthetic-test-key")
    _, result = call(db, subject, f"{base}/runs/{run['id']}")
    assert isinstance(result, dict) and result["status"] == "QUEUED"
    assert not tick(db[1], tenant, "synthetic-test-key")
    with db[0].begin() as connection:
        connection.execute(
            text(
                "UPDATE task_runs SET lease_until=now()-interval '1 minute',attempts=3 WHERE id=:id"
            ),
            {"id": UUID(str(run["id"]))},
        )
    assert tick(db[1], tenant, "synthetic-test-key")
    _, result = call(db, subject, f"{base}/runs/{run['id']}")
    assert isinstance(result, dict) and result["status"] == "FAILED"


def test_live_openai_durable_journey_opt_in(db: tuple[Engine, Engine]) -> None:
    import os

    if os.environ.get("ORQENTRA_LIVE_MODEL_TEST") != "1":
        pytest.skip("Explicit opt-in only: makes a real bounded OpenAI development call.")
    key = os.environ.get("OPENAI_API_KEY")
    assert key, "Backend-only development key required."
    subject, base, data = queued(
        db,
        request_text=(
            "The customer is Synthetic Example Ltd and requests the EU workspace region. "
            "Prepare only the required checklist and draft reply for human review. "
            "All customer facts needed for this limited policy are supplied."
        ),
        source_text=(
            "Before provisioning a new customer account, verify the customer company name "
            "and confirm the requested workspace region. The onboarding owner must review "
            "the account setup checklist before activation."
        ),
    )
    run = data["run"]
    assert isinstance(run, dict)
    path = f"{base}/runs/{run['id']}"
    assert tick(db[1], UUID(base.split("/")[4]), key)
    code, result = call(db, subject, path)
    assert code == 200 and isinstance(result, dict)
    if result["status"] == "NEEDS_CLARIFICATION":
        assert (
            call(
                db,
                subject,
                path + "/clarify",
                "POST",
                {
                    "expected_revision": result["revision"],
                    "additional_facts": (
                        "This is a synthetic development exercise. The customer identity "
                        "has been verified. The onboarding owner is the designated reviewer. "
                        "Prepare the steps specified by the supplied policy only."
                    ),
                },
            )[0]
            == 200
        )
        assert tick(db[1], UUID(base.split("/")[4]), key)
        _, result = call(db, subject, path)
        assert isinstance(result, dict)
    assert result["status"] == "AWAITING_REVIEW", str(result.get("error_code"))
    assert result["usage"]["provider"] == "openai"
    assert (
        call(
            db,
            subject,
            path + "/review",
            "POST",
            {
                "expected_revision": result["revision"],
                "artifact_hash": result["artifact_hash"],
                "decision": "APPROVE",
            },
        )[0]
        == 200
    )
    code, receipt = call(db, subject, path + "/receipt")
    assert code == 200 and isinstance(receipt, dict) and receipt["mode"] == "SIMULATED"
