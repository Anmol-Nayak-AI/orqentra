from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import Field, model_validator

from orqentra.organizations.schemas import Contract


def default_tools() -> list[Literal["knowledge.search", "draft.compose"]]:
    return ["knowledge.search", "draft.compose"]


class TeammateConfiguration(Contract):
    instructions: str = Field(min_length=20, max_length=12000, pattern=r"\S")
    model: Literal["openai:gpt-4.1-mini", "openai:gpt-4.1"] = "openai:gpt-4.1-mini"
    workflow: Literal["onboarding.v1", "python-analysis.v1"] = "onboarding.v1"
    output_schema: Literal["onboarding_plan.v1", "python_analysis_plan.v1"] = "onboarding_plan.v1"
    max_run_cost_cents: int = Field(default=300, ge=1, le=1000)
    max_model_calls: int = Field(default=3, ge=1, le=4)
    tools: list[Literal["knowledge.search", "draft.compose"]] = Field(
        default_factory=default_tools, max_length=2
    )

    @model_validator(mode="after")
    def consistent_workflow(self) -> "TeammateConfiguration":
        expected = (
            "python_analysis_plan.v1"
            if self.workflow == "python-analysis.v1"
            else "onboarding_plan.v1"
        )
        if self.output_schema != expected:
            raise ValueError("Workflow and output schema must match.")
        return self


class AgentCreate(Contract):
    workspace_id: UUID
    name: str = Field(min_length=1, max_length=200, pattern=r"\S")
    slug: str = Field(min_length=1, max_length=100, pattern=r"^[a-z0-9]+(-[a-z0-9]+)*$")
    configuration: TeammateConfiguration


class AgentUpdate(Contract):
    expected_revision: int = Field(ge=1)
    configuration: TeammateConfiguration


class AgentRevision(Contract):
    expected_revision: int = Field(ge=1)


class AgentResponse(Contract):
    id: UUID
    organization_id: UUID
    workspace_id: UUID
    name: str
    slug: str
    lifecycle_status: str
    revision: int
    draft_configuration: dict[str, Any]


class AgentVersionResponse(Contract):
    id: UUID
    agent_definition_id: UUID
    version_number: int
    configuration_snapshot: dict[str, Any]
    published_at: datetime
