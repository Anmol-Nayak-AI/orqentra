from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field

from orqentra.organizations.schemas import Contract


class DocumentCreate(Contract):
    workspace_id: UUID
    title: str = Field(min_length=1, max_length=200, pattern=r"\S")
    content: str = Field(min_length=1, max_length=24000, pattern=r"\S")


class DocumentResponse(Contract):
    id: UUID
    workspace_id: UUID
    title: str
    content: str
    content_hash: str
    index_status: str
    index_error: str | None
    status: str


class RunCreate(Contract):
    agent_version_id: UUID
    idempotency_key: str = Field(min_length=8, max_length=100, pattern=r"^[a-zA-Z0-9_-]+$")
    request_text: str = Field(min_length=10, max_length=4000)


class RunResponse(Contract):
    id: UUID
    workspace_id: UUID
    agent_version_id: UUID
    status: str
    request_text: str
    revision: int
    attempts: int
    output: dict[str, Any]
    usage: dict[str, Any]
    error_code: str | None
    artifact_hash: str | None
    review_expires_at: datetime | None
    created_at: datetime


class Evidence(Contract):
    document_id: UUID
    quote: str = Field(min_length=10, max_length=1000)


class ChecklistItem(Contract):
    task: str = Field(min_length=1, max_length=1000)
    evidence: list[Evidence] = Field(min_length=1, max_length=5)


class OnboardingPlan(Contract):
    summary: str = Field(min_length=1, max_length=2000)
    checklist: list[ChecklistItem] = Field(max_length=20)
    missing_information: list[str] = Field(max_length=10)
    draft_reply: str = Field(max_length=4000)


class ReviewDecision(Contract):
    expected_revision: int = Field(ge=1)
    artifact_hash: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision: Literal["APPROVE", "REJECT"]


class ReceiptResponse(Contract):
    id: UUID
    run_id: UUID
    reviewed_by: UUID
    artifact_hash: str
    mode: Literal["SIMULATED"]
    created_at: datetime


class Clarification(Contract):
    expected_revision: int = Field(ge=1)
    additional_facts: str = Field(min_length=10, max_length=1000)


class ExecutionCapabilities(Contract):
    model_provider: Literal["openai"]
    model_configured: bool
    delivery_mode: Literal["SIMULATED"]
    knowledge_format: str
    workflow_engine: str
    checkpoint_storage: str
    worker_online: bool
    worker_last_seen: datetime | None
    sandbox_execution_available: bool


class PythonAnalysisPlan(OnboardingPlan):
    proposed_python: str = Field(max_length=16384)
