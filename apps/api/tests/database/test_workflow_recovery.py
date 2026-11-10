"""Fault-injection evidence with synthetic model output, never live provider acceptance."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from test_execution import fixture_plan, queued
from test_identity_authorization import call

from orqentra.execution.worker import tick
from orqentra.orchestration.checkpoints import CheckpointFence, TenantSaver
from orqentra.persistence.models import TaskRun, UsageEvent, WorkflowCheckpoint
from orqentra.persistence.session import TrustedOrganizationContext, transaction


def test_checkpoint_recovery_does_not_repeat_completed_model_step(
    db: tuple[Engine, Engine], monkeypatch
):
    subject, base, data = queued(db)
    run_id = UUID(data["run"]["id"])
    org = UUID(base.split("/")[4])
    calls = []

    def generate(*args):
        calls.append(True)
        return fixture_plan(data["document"]["id"]), {"input_tokens": 100, "output_tokens": 50}

    monkeypatch.setattr("orqentra.execution.worker.generate", generate)
    import orqentra.execution.worker as worker

    record = worker.record_generation

    def crash(*args):
        raise RuntimeError("synthetic_process_crash_after_checkpoint")

    monkeypatch.setattr(worker, "record_generation", crash)
    with pytest.raises(RuntimeError, match="synthetic_process_crash"):
        tick(db[1], org, "synthetic-test-key")
    with Session(db[0]) as s, s.begin():
        row = s.get(TaskRun, run_id)
        assert row.status == "RUNNING"
        row.lease_until = datetime.now(UTC) - timedelta(seconds=1)
        assert (
            s.scalar(
                select(func.count())
                .select_from(WorkflowCheckpoint)
                .where(WorkflowCheckpoint.run_id == run_id)
            )
            >= 4
        )
    monkeypatch.setattr(worker, "record_generation", record)
    assert tick(db[1], org, "synthetic-test-key")
    assert len(calls) == 1
    assert call(db, subject, base + f"/runs/{run_id}")[1]["status"] == "AWAITING_REVIEW"
    with Session(db[0]) as s:
        assert (
            s.scalar(
                select(func.sum(UsageEvent.amount)).where(
                    UsageEvent.resource_id == run_id, UsageEvent.metric == "input_tokens"
                )
            )
            == 100
        )
        checkpoint = s.scalar(select(WorkflowCheckpoint).where(WorkflowCheckpoint.run_id == run_id))
        namespace = checkpoint.namespace
        with pytest.raises(DBAPIError):
            s.execute(
                text("UPDATE workflow_checkpoints SET payload='{}'::jsonb WHERE id=:id"),
                {"id": checkpoint.id},
            )
    wrong = TrustedOrganizationContext(uuid4(), UUID(int=0), uuid4())
    with transaction(db[1], wrong) as s:
        assert s.scalar(select(func.count()).select_from(WorkflowCheckpoint)) == 0
    with db[1].connect() as c:
        assert c.scalar(text("SELECT count(*) FROM workflow_checkpoints")) == 0
    saver = TenantSaver(db[1], org, run_id, uuid4(), namespace)
    with pytest.raises(CheckpointFence):
        saver.get_tuple({"configurable": {"thread_id": str(uuid4())}})
    with transaction(db[1], saver.context) as s, pytest.raises(CheckpointFence):
        saver.guard(s)


def test_pending_writes_can_commit_before_checkpoint_without_losing_tenant_binding(db):
    from langgraph.checkpoint.base import empty_checkpoint

    _, base, data = queued(db)
    run_id, tenant, claim = UUID(data["run"]["id"]), UUID(base.split("/")[4]), uuid4()
    with Session(db[0]) as s, s.begin():
        row = s.get(TaskRun, run_id)
        row.status, row.claim_token = "RUNNING", claim
        row.lease_until = datetime.now(UTC) + timedelta(minutes=2)
    saver = TenantSaver(db[1], tenant, run_id, claim, "pending-order-regression")
    checkpoint = empty_checkpoint()
    config = saver.config(checkpoint["id"])
    # This is a supported LangGraph ordering, not orphan tenant data.
    saver.put_writes(config, [("sources", ["synthetic staged source"])], "task-unit")
    assert saver.get_tuple(config) is None
    saver.put(saver.config(), checkpoint, {"step": 0, "source": "loop", "parents": {}}, {})
    restored = saver.get_tuple(config)
    assert restored is not None
    assert restored.pending_writes == [("task-unit", "sources", ["synthetic staged source"])]
