"""Application flow with synthetic identity/model/sandbox transports, never paid resources."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session
from test_execution import fixture_plan, queued
from test_identity_authorization import add_existing_member, call, org

from orqentra.core.config import Settings
from orqentra.execution.worker import tick
from orqentra.persistence.models import CodeExecution, UsageEvent
from orqentra.sandbox.worker import code_tick, heartbeat


def prepared(db, monkeypatch, analysis=False):
    owner, base, data = queued(db, workflow="python-analysis.v1" if analysis else "onboarding.v1")
    from orqentra.execution.schemas import PythonAnalysisPlan

    plan = fixture_plan(data["document"]["id"])
    if analysis:
        plan = PythonAnalysisPlan(**plan.model_dump(), proposed_python="print(2 + 2)")
    monkeypatch.setattr("orqentra.execution.worker.generate", lambda *args, **kwargs: (plan, {}))
    tenant = UUID(base.split("/")[4])
    assert tick(db[1], tenant, "synthetic-test-key")
    run = call(db, owner, base + "/runs/" + data["run"]["id"])[1]
    assert (
        call(
            db,
            owner,
            base + "/runs/" + run["id"] + "/review",
            "POST",
            {
                "expected_revision": run["revision"],
                "artifact_hash": run["artifact_hash"],
                "decision": "APPROVE",
            },
        )[0]
        == 200
    )
    reviewer = "user_" + uuid4().hex
    add_existing_member(db, tenant, reviewer, "ADMIN")
    body = {
        "run_id": run["id"],
        "title": "Approved analysis",
        "code": run["output"].get("proposed_python", "print(2 + 2)"),
        "idempotency_key": uuid4().hex,
    }
    code, item = call(db, owner, base + "/code-executions", "POST", body)
    assert code == 201
    assert call(db, owner, base + "/code-executions", "POST", body)[1]["id"] == item["id"]
    return owner, reviewer, base, item


def approve(db, reviewer, base, item):
    return call(
        db,
        reviewer,
        base + f"/code-executions/{item['id']}/review",
        "POST",
        {
            "expected_revision": item["revision"],
            "code_hash": item["code_hash"],
            "decision": "APPROVE",
        },
    )


def config():
    return Settings(
        sandbox_provider="e2b",
        sandbox_execution_approved=True,
        E2B_API_KEY="synthetic-not-real",
        e2b_template_id="synthetic",
    )


def test_worker_replicas_respect_tenant_execution_limit(db, monkeypatch):
    owner, reviewer, base, first = prepared(db, monkeypatch)
    tenant = UUID(base.split("/")[4])
    first = approve(db, reviewer, base, first)[1]
    code, second = call(
        db,
        owner,
        base + "/code-executions",
        "POST",
        {
            "run_id": first["run_id"],
            "title": "Second independently approved attempt",
            "code": "print(3 + 3)",
            "idempotency_key": uuid4().hex,
        },
    )
    assert code == 201
    second = approve(db, reviewer, base, second)[1]
    heartbeat(db[1], tenant, config())
    for item in (first, second):
        assert (
            call(
                db,
                owner,
                base + f"/code-executions/{item['id']}/start",
                "POST",
                {
                    "expected_revision": item["revision"],
                    "code_hash": item["code_hash"],
                },
            )[0]
            == 200
        )
    entered, release = Event(), Event()
    attempts = []

    class ControlledTransport:
        def execute(self, code, permit):
            attempts.append(permit.approval_id)
            entered.set()
            assert release.wait(10)
            return "synthetic concurrency result"

    monkeypatch.setattr("orqentra.sandbox.worker.provider", lambda *_: ControlledTransport())
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(code_tick, db[1], tenant, config())
        try:
            assert entered.wait(10)
            # Another worker sees the committed in-flight job and must leave the next queued.
            assert code_tick(db[1], tenant, config()) is False
            assert len(attempts) == 1
        finally:
            release.set()
        assert pending.result(timeout=10)
    assert code_tick(db[1], tenant, config())
    assert len(attempts) == 2


def test_code_review_execution_and_tenant_boundaries(db: tuple[Engine, Engine], monkeypatch):
    owner, reviewer, base, item = prepared(db, monkeypatch)
    assert approve(db, owner, base, item)[0] == 403
    assert approve(db, reviewer, base, dict(item, code_hash="0" * 64))[0] == 409
    code, item = approve(db, reviewer, base, item)
    assert code == 200 and item["status"] == "APPROVED"
    path = base + f"/code-executions/{item['id']}"
    start = {"expected_revision": item["revision"], "code_hash": item["code_hash"]}
    assert call(db, owner, path + "/start", "POST", start)[0] == 503
    tenant = UUID(base.split("/")[4])
    heartbeat(db[1], tenant, config())
    code, queued_item = call(db, owner, path + "/start", "POST", start)
    assert code == 200 and queued_item["status"] == "QUEUED"
    assert call(db, owner, path + "/start", "POST", start)[1]["status"] == "QUEUED"
    calls = []

    class Transport:
        def __init__(self, audit):
            self.audit = audit

        def execute(self, code, permit):
            self.audit({"outcome": "requested"})
            calls.append(permit)
            assert code == "print(2 + 2)" and permit.approval_id == UUID(item["id"])
            self.audit({"outcome": "completed"})
            return "synthetic output: 4"

    monkeypatch.setattr(
        "orqentra.sandbox.worker.provider", lambda settings, audit: Transport(audit)
    )
    assert code_tick(db[1], tenant, config())
    assert not code_tick(db[1], tenant, config())
    result = next(x for x in call(db, owner, base + "/code-executions")[1] if x["id"] == item["id"])
    assert result["status"] == "COMPLETED" and result["output"] == "synthetic output: 4"
    assert len(calls) == 1
    with Session(db[0]) as s:
        assert (
            s.scalar(
                select(func.sum(UsageEvent.amount)).where(
                    UsageEvent.resource_id == UUID(item["id"]), UsageEvent.metric == "sandbox_runs"
                )
            )
            == 1
        )
    stranger = "user_" + uuid4().hex
    another = org(db, stranger)
    assert call(db, stranger, base + "/code-executions")[0] == 403
    assert (
        call(
            db,
            stranger,
            f"/api/v1/organizations/{another['id']}/code-executions/{item['id']}/start",
            "POST",
            start,
        )[0]
        == 404
    )


def test_expired_code_attempt_becomes_unknown_without_retry(db, monkeypatch):
    owner, reviewer, base, item = prepared(db, monkeypatch)
    item = approve(db, reviewer, base, item)[1]
    tenant = UUID(base.split("/")[4])
    with Session(db[0]) as s, s.begin():
        row = s.get(CodeExecution, UUID(item["id"]))
        row.status, row.claim_token = "RUNNING", uuid4()
        row.lease_until = datetime.now(UTC) - timedelta(seconds=1)
    monkeypatch.setattr(
        "orqentra.sandbox.worker.provider", lambda *args: pytest.fail("must never retry")
    )
    assert code_tick(db[1], tenant, Settings())
    assert not code_tick(db[1], tenant, Settings())
    result = call(db, owner, base + "/code-executions")[1][0]
    assert result["status"] == "UNKNOWN"
    assert result["error_code"] == "worker_lost_execution_uncertain"


def test_queued_code_with_changed_payload_is_cancelled_before_provider(db, monkeypatch):
    owner, reviewer, base, item = prepared(db, monkeypatch)
    item = approve(db, reviewer, base, item)[1]
    tenant = UUID(base.split("/")[4])
    heartbeat(db[1], tenant, config())
    assert (
        call(
            db,
            owner,
            base + f"/code-executions/{item['id']}/start",
            "POST",
            {"expected_revision": item["revision"], "code_hash": item["code_hash"]},
        )[0]
        == 200
    )
    with Session(db[0]) as s, s.begin():
        s.get(CodeExecution, UUID(item["id"])).code = "print('changed after review')"
    monkeypatch.setattr(
        "orqentra.sandbox.worker.provider",
        lambda *args: pytest.fail("must not execute altered code"),
    )
    assert code_tick(db[1], tenant, config())
    assert call(db, owner, base + "/code-executions")[1][0]["status"] == "CANCELLED"


def test_ai_python_proposal_flows_to_separate_review_without_execution(db, monkeypatch):
    owner, reviewer, base, item = prepared(db, monkeypatch, analysis=True)
    run = call(db, owner, base + "/runs/" + item["run_id"])[1]
    assert run["output"]["proposed_python"] == item["code"] == "print(2 + 2)"
    assert item["status"] == "AWAITING_REVIEW" and item["reviewed_by"] is None
    assert approve(db, owner, base, item)[0] == 403
    assert approve(db, reviewer, base, item)[1]["status"] == "APPROVED"


def test_live_python_analysis_produces_code_proposal_only(db):
    import os

    if os.environ.get("ORQENTRA_LIVE_PYTHON_ANALYSIS") != "1" or not os.environ.get(
        "OPENAI_API_KEY"
    ):
        pytest.skip("Opt-in: real embeddings and OpenAI analysis proposal; no code execution.")
    owner, base, data = queued(
        db,
        workflow="python-analysis.v1",
        source_text=(
            "Synthetic development support request counts: Monday 3, Tuesday 5, "
            "Wednesday 2. The total is 10 requests."
        ),
        request_text=(
            "Prepare Python that sums the daily support counts from the approved guide "
            "and prints the total. Do not execute the code."
        ),
    )
    assert tick(db[1], UUID(base.split("/")[4]), os.environ["OPENAI_API_KEY"])
    result = call(db, owner, base + "/runs/" + data["run"]["id"])[1]
    assert result["status"] == "AWAITING_REVIEW", result.get("error_code")
    assert result["output"]["proposed_python"].strip()
    assert result["usage"]["provider"] == "openai"
    assert call(db, owner, base + "/code-executions")[1] == []
