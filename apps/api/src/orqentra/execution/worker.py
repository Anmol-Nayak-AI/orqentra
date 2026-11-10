"""Tenant-allowlisted durable worker; uses the same non-bypass RLS runtime role."""

import argparse
import os
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import Engine, or_, select, text
from sqlalchemy.orm import Session

from orqentra.agents.schemas import TeammateConfiguration
from orqentra.billing.service import record_generation
from orqentra.core.config import Settings
from orqentra.execution.policy import eligible
from orqentra.execution.provider import ProviderFailure, generate
from orqentra.execution.routes import digest
from orqentra.execution.schemas import OnboardingPlan, PythonAnalysisPlan
from orqentra.orchestration.checkpoints import CheckpointFence
from orqentra.orchestration.workflow import run_workflow
from orqentra.persistence.models import (
    AgentVersion,
    AuditEvent,
    KnowledgeDocument,
    TaskRun,
)
from orqentra.persistence.session import TrustedOrganizationContext, database_engine, transaction
from orqentra.rag.chat_worker import chat_tick
from orqentra.rag.service import index_next, retrieve
from orqentra.sandbox.worker import code_tick, heartbeat


def evidence_valid(plan: OnboardingPlan, sources: list[dict[str, str]]) -> bool:
    return all(
        any(
            str(e.document_id) == source["document_id"] and e.quote in source["content"]
            for source in sources
        )
        for item in plan.checklist
        for e in item.evidence
    )


def record_transition(session: Session, run: TaskRun) -> None:
    if run.status not in {"RUNNING", "QUEUED"}:
        run.claim_token = None
        run.lease_until = None
    session.add(
        AuditEvent(
            organization_id=run.organization_id,
            actor_user_id=run.created_by,
            action="run." + run.status.lower(),
            resource_type="run",
            resource_id=run.id,
            correlation_id=uuid4(),
            safe_metadata={"revision": run.revision},
        )
    )


def tick(engine: Engine, organization_id: UUID, key: str | None) -> bool:
    if not key:
        return False
    claim = uuid4()
    context = TrustedOrganizationContext(organization_id, UUID(int=0), uuid4())
    with transaction(engine, context) as session:
        flags = session.execute(
            text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
        ).one()
        if any(flags):
            raise RuntimeError("Unsafe worker role.")
        run = session.scalar(
            select(TaskRun)
            .where(
                TaskRun.organization_id == organization_id,
                or_(
                    (TaskRun.status == "QUEUED")
                    & or_(TaskRun.lease_until.is_(None), TaskRun.lease_until < datetime.now(UTC)),
                    (TaskRun.status == "RUNNING") & (TaskRun.lease_until < datetime.now(UTC)),
                ),
            )
            .order_by(TaskRun.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if run is None:
            return False
        version = session.get(AgentVersion, run.agent_version_id)
        if version is None:
            raise RuntimeError("Missing immutable version.")
        config = TeammateConfiguration.model_validate(
            version.configuration_snapshot["configuration"]
        )
        if not eligible(session, run):
            run.status = "CANCELLED"
            run.revision += 1
            record_transition(session, run)
            return True
        ready = session.scalar(
            select(KnowledgeDocument.id)
            .where(
                KnowledgeDocument.organization_id == organization_id,
                KnowledgeDocument.workspace_id == run.workspace_id,
                KnowledgeDocument.status == "ACTIVE",
                KnowledgeDocument.index_status == "READY",
            )
            .limit(1)
        )
        pending = session.scalar(
            select(KnowledgeDocument.id)
            .where(
                KnowledgeDocument.workspace_id == run.workspace_id,
                KnowledgeDocument.status == "ACTIVE",
                KnowledgeDocument.index_status.in_(["PENDING", "INDEXING"]),
            )
            .limit(1)
        )
        if not ready and pending:
            return False
        if not ready or not {"knowledge.search", "draft.compose"}.issubset(config.tools):
            run.status = "NEEDS_CLARIFICATION"
            run.output = {
                "missing_information": [
                    "Add approved indexed knowledge and enable the required tools."
                ]
            }
            run.revision += 1
            record_transition(session, run)
            return True
        reserved = int(run.usage.get("reserved_cents", 0))
        if (
            run.attempts >= min(config.max_model_calls, 3)
            or reserved + 100 > config.max_run_cost_cents
        ):
            run.status = "FAILED"
            run.error_code = "run_budget_or_attempt_limit"
            run.revision += 1
            record_transition(session, run)
            return True
        # Serialize per-tenant daily reservations. Reserve a conservative $1 for each bounded call.
        session.execute(
            text("SELECT id FROM organizations WHERE id=:id FOR UPDATE"), {"id": organization_id}
        )
        total = session.scalar(
            text(
                "SELECT COALESCE(sum((usage->>'daily_reserved_cents')::int),0) FROM task_runs "
                "WHERE organization_id=:id AND "
                "usage->>'reservation_day'=to_char(now(),'YYYY-MM-DD')"
            ),
            {"id": organization_id},
        )
        if total is not None and total + 100 > 1000:
            run.status = "FAILED"
            run.error_code = "tenant_daily_reservation_limit"
            run.revision += 1
            record_transition(session, run)
            return True
        run.status = "RUNNING"
        run.error_code = None
        run.claim_token = claim
        run.lease_until = datetime.now(UTC) + timedelta(minutes=2)
        run.attempts += 1
        run.revision += 1
        today = datetime.now(UTC).date().isoformat()
        daily = (
            int(run.usage.get("daily_reserved_cents", 0))
            if run.usage.get("reservation_day") == today
            else 0
        )
        run.usage = {
            **run.usage,
            "reserved_cents": reserved + 100,
            "reservation_day": today,
            "daily_reserved_cents": daily + 100,
        }
        run_id = run.id
        request = run.request_text
        actor = run.created_by
        workspace_id = run.workspace_id
    output: dict[str, Any] = {}
    usage: dict[str, Any] = {}
    failure = None
    try:
        plan_type = (
            PythonAnalysisPlan if config.workflow == "python-analysis.v1" else OnboardingPlan
        )

        def compose(sources: list[dict[str, str]]) -> tuple[OnboardingPlan, dict[str, Any]]:
            usage: dict[str, Any] = {}
            if not sources or "draft.compose" not in config.tools:
                plan = OnboardingPlan(
                    summary="Approved knowledge and draft tools are required.",
                    checklist=[],
                    missing_information=[
                        "Provide approved workspace sources and enable knowledge.search and "
                        "draft.compose."
                    ],
                    draft_reply="",
                )
            else:
                args = (
                    key,
                    config.model.removeprefix("openai:"),
                    config.instructions,
                    request,
                    [
                        {
                            "document_id": source["document_id"],
                            "title": source["title"],
                            "content": source["content"],
                        }
                        for source in sources
                    ],
                )
                plan, usage = (
                    generate(*args, plan_type=plan_type)
                    if plan_type is PythonAnalysisPlan
                    else generate(*args)
                )
            if plan_type is PythonAnalysisPlan and not isinstance(plan, PythonAnalysisPlan):
                plan = PythonAnalysisPlan(**plan.model_dump(), proposed_python="")
            return plan, usage

        plan, usage = run_workflow(
            engine,
            organization_id,
            run_id,
            claim,
            {"version": str(run.agent_version_id), "request": request},
            lambda: retrieve(engine, organization_id, workspace_id, request, key),
            compose,
            evidence_valid,
            plan_type,
        )
        output = plan.model_dump(mode="json")
    except CheckpointFence:
        # A new claim/cancellation wins. Leave the expired job to the normal recovery loop.
        return True
    except ProviderFailure as error:
        failure = str(error)
    with transaction(engine, context) as session:
        run = session.scalar(select(TaskRun).where(TaskRun.id == run_id).with_for_update())
        record_generation(
            session, organization_id, run_id, UUID(usage.pop("_meter_claim", str(claim))), usage
        )
        if run is None or run.status != "RUNNING" or run.claim_token != claim:
            return True
        if not eligible(session, run):
            run.status = "CANCELLED"
        elif failure:
            run.status = (
                "QUEUED"
                if failure == "provider_retryable"
                and run.attempts < min(config.max_model_calls, 3)
                and int(run.usage.get("reserved_cents", 0)) + 100 <= config.max_run_cost_cents
                else "FAILED"
            )
            run.error_code = failure
        else:
            ids = {
                e["document_id"] for item in output.get("checklist", []) for e in item["evidence"]
            }
            active = set(
                str(i)
                for i in session.scalars(
                    select(KnowledgeDocument.id)
                    .where(
                        KnowledgeDocument.id.in_([UUID(i) for i in ids]),
                        KnowledgeDocument.status == "ACTIVE",
                    )
                    .with_for_update()
                )
            )
            if active != ids:
                run.status = "FAILED"
                run.error_code = "source_revoked"
            else:
                run.output = output
                run.source_ids = sorted(ids)
                run.usage = {
                    **run.usage,
                    **usage,
                    "prompt_version": config.workflow,
                    "workflow_version": "langgraph." + config.workflow,
                    "retrieval_version": "pgvector-cosine.v1",
                }
                run.artifact_hash = digest(output)
                run.status = (
                    "NEEDS_CLARIFICATION"
                    if output.get("missing_information") or not output.get("checklist")
                    else "AWAITING_REVIEW"
                )
                run.review_expires_at = datetime.now(UTC) + timedelta(days=7)
        run.revision += 1
        run.claim_token = None
        run.lease_until = (
            datetime.now(UTC) + timedelta(seconds=10 * run.attempts)
            if run.status == "QUEUED"
            else None
        )
        session.add(
            AuditEvent(
                organization_id=organization_id,
                actor_user_id=actor,
                action="run." + run.status.lower(),
                resource_type="run",
                resource_id=run.id,
                correlation_id=uuid4(),
                safe_metadata={"revision": run.revision},
            )
        )
    return True


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--organization", type=UUID, action="append")
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    organizations = args.organization or [
        UUID(value.strip())
        for value in os.environ.get("ORQENTRA_WORKER_ORGANIZATIONS", "").split(",")
        if value.strip()
    ]
    if not organizations:
        raise SystemExit("Configure an explicit worker organization allowlist.")
    config = Settings()
    if not config.database_url or not config.openai_api_key:
        raise SystemExit("Configure restricted runtime database and backend-only provider key.")
    engine = database_engine(config.database_url.get_secret_value())
    with engine.connect() as connection:
        flags = connection.execute(
            text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=current_user")
        ).one()
        if any(flags):
            raise SystemExit("Unsafe worker database role.")
    try:
        while True:
            for organization_id in organizations:
                heartbeat(engine, organization_id, config)
                code_tick(engine, organization_id, config)
                index_next(engine, organization_id, config.openai_api_key.get_secret_value())
                Path("/tmp/orqentra-worker-heartbeat").write_text(str(time.time()))
                chat_tick(engine, organization_id, config.openai_api_key.get_secret_value())
                Path("/tmp/orqentra-worker-heartbeat").write_text(str(time.time()))
                tick(engine, organization_id, config.openai_api_key.get_secret_value())
            Path("/tmp/orqentra-worker-heartbeat").write_text(str(time.time()))
            if args.once:
                break
            time.sleep(2)
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
