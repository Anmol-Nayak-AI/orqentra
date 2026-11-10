"""Synchronous RLS checkpointer. Never calls vendor setup or grants a bypass role."""

import base64
import json
from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import WRITES_IDX_MAP, BaseCheckpointSaver, CheckpointTuple
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from orqentra.persistence.models import TaskRun, WorkflowCheckpoint, WorkflowWrite
from orqentra.persistence.session import TrustedOrganizationContext, transaction
from orqentra.rag.service import require_restricted


class CheckpointFence(RuntimeError):
    pass


class TenantSaver(BaseCheckpointSaver[int]):
    def __init__(
        self, engine: Engine, organization_id: UUID, run_id: UUID, claim: UUID, namespace: str
    ):
        super().__init__(
            serde=JsonPlusSerializer(
                pickle_fallback=False, allowed_json_modules=[], allowed_msgpack_modules=[]
            )
        )
        self.engine, self.organization_id, self.run_id, self.claim = (
            engine,
            organization_id,
            run_id,
            claim,
        )
        self.namespace = namespace
        self.context = TrustedOrganizationContext(organization_id, UUID(int=0), uuid4())

    def config(self, checkpoint_id: str | None = None) -> RunnableConfig:
        value: dict[str, Any] = {"thread_id": str(self.run_id), "checkpoint_ns": ""}
        if checkpoint_id:
            value["checkpoint_id"] = checkpoint_id
        return {"configurable": value}

    def validate(self, config: Any) -> None:
        conf = config.get("configurable", {})
        if conf.get("thread_id") != str(self.run_id) or conf.get("checkpoint_ns", "") != "":
            raise CheckpointFence("checkpoint_context_mismatch")

    def guard(self, session: Session) -> None:
        run = session.scalar(select(TaskRun).where(TaskRun.id == self.run_id).with_for_update())
        if (
            run is None
            or run.status != "RUNNING"
            or run.claim_token != self.claim
            or run.lease_until is None
            or run.lease_until <= datetime.now(UTC)
        ):
            raise CheckpointFence("checkpoint_lease_lost")

    def encode(self, value: Any) -> dict[str, Any]:
        kind, raw = self.serde.dumps_typed(value)
        if len(raw) > 2_000_000:
            raise CheckpointFence("checkpoint_too_large")
        return {"kind": kind, "data": base64.b64encode(raw).decode()}

    def decode(self, value: dict[str, Any]) -> Any:
        return self.serde.loads_typed(
            (value["kind"], base64.b64decode(value["data"], validate=True))
        )

    def get_tuple(self, config: Any) -> CheckpointTuple | None:
        self.validate(config)
        with transaction(self.engine, self.context) as session:
            require_restricted(session)
            query = select(WorkflowCheckpoint).where(
                WorkflowCheckpoint.run_id == self.run_id,
                WorkflowCheckpoint.namespace == self.namespace,
            )
            checkpoint_id = config["configurable"].get("checkpoint_id")
            if checkpoint_id:
                query = query.where(WorkflowCheckpoint.checkpoint_id == checkpoint_id)
            row = session.scalar(query.order_by(WorkflowCheckpoint.checkpoint_id.desc()).limit(1))
            if row is None:
                return None
            writes = session.scalars(
                select(WorkflowWrite)
                .where(
                    WorkflowWrite.run_id == self.run_id,
                    WorkflowWrite.namespace == self.namespace,
                    WorkflowWrite.checkpoint_id == row.checkpoint_id,
                )
                .order_by(WorkflowWrite.task_path, WorkflowWrite.task_id, WorkflowWrite.write_index)
            )
            return CheckpointTuple(
                config=self.config(row.checkpoint_id),
                checkpoint=self.decode(row.payload["checkpoint"]),
                metadata=self.decode(row.payload["metadata"]),
                parent_config=self.config(row.parent_id) if row.parent_id else None,
                pending_writes=[(w.task_id, w.channel, self.decode(w.payload)) for w in writes],
            )

    def put(self, config: Any, checkpoint: Any, metadata: Any, new_versions: Any) -> Any:
        self.validate(config)
        payload = {"checkpoint": self.encode(checkpoint), "metadata": self.encode(metadata)}
        if len(json.dumps(payload)) > 3_000_000:
            raise CheckpointFence("checkpoint_too_large")
        with transaction(self.engine, self.context) as session:
            require_restricted(session)
            self.guard(session)
            count = session.scalar(
                select(func.count())
                .select_from(WorkflowCheckpoint)
                .where(WorkflowCheckpoint.run_id == self.run_id)
            )
            if count is not None and count >= 128:
                raise CheckpointFence("checkpoint_step_limit")
            session.add(
                WorkflowCheckpoint(
                    organization_id=self.organization_id,
                    run_id=self.run_id,
                    namespace=self.namespace,
                    checkpoint_id=checkpoint["id"],
                    parent_id=config["configurable"].get("checkpoint_id"),
                    payload=payload,
                )
            )
        return self.config(checkpoint["id"])

    def put_writes(
        self, config: Any, writes: Sequence[tuple[str, Any]], task_id: str, task_path: str = ""
    ) -> None:
        self.validate(config)
        with transaction(self.engine, self.context) as session:
            require_restricted(session)
            self.guard(session)
            for index, (channel, value) in enumerate(writes):
                idx = WRITES_IDX_MAP.get(channel, index)
                row = session.scalar(
                    select(WorkflowWrite).where(
                        WorkflowWrite.run_id == self.run_id,
                        WorkflowWrite.namespace == self.namespace,
                        WorkflowWrite.checkpoint_id == config["configurable"]["checkpoint_id"],
                        WorkflowWrite.task_id == task_id,
                        WorkflowWrite.write_index == idx,
                    )
                )
                if row:
                    if idx < 0:
                        row.payload = self.encode(value)
                    continue
                session.add(
                    WorkflowWrite(
                        organization_id=self.organization_id,
                        run_id=self.run_id,
                        namespace=self.namespace,
                        checkpoint_id=config["configurable"]["checkpoint_id"],
                        task_id=task_id,
                        task_path=task_path,
                        write_index=idx,
                        channel=channel,
                        payload=self.encode(value),
                    )
                )

    def list(
        self, config: Any, *, filter: Any = None, before: Any = None, limit: int | None = None
    ) -> Iterator[CheckpointTuple]:
        # History is internal, bounded and scoped. No client-selectable thread enumeration.
        self.validate(config)
        with transaction(self.engine, self.context) as session:
            require_restricted(session)
            query = select(WorkflowCheckpoint.checkpoint_id).where(
                WorkflowCheckpoint.run_id == self.run_id,
                WorkflowCheckpoint.namespace == self.namespace,
            )
            if before:
                self.validate(before)
                query = query.where(
                    WorkflowCheckpoint.checkpoint_id < before["configurable"]["checkpoint_id"]
                )
            ids = list(
                session.scalars(
                    query.order_by(WorkflowCheckpoint.checkpoint_id.desc()).limit(
                        min(limit or 128, 128)
                    )
                )
            )
        for value in ids:
            item = self.get_tuple(self.config(value))
            if item and (not filter or all(item.metadata.get(k) == v for k, v in filter.items())):
                yield item
