"""Persistent retrieve/draft/validate graph; approval remains an application authority."""

from collections.abc import Callable
from typing import Any, TypedDict
from uuid import UUID

from langgraph.graph import END, START, StateGraph
from langsmith import tracing_context
from sqlalchemy import Engine

from orqentra.execution.provider import ProviderFailure
from orqentra.execution.routes import digest
from orqentra.execution.schemas import OnboardingPlan
from orqentra.orchestration.checkpoints import TenantSaver


class State(TypedDict, total=False):
    sources: list[dict[str, str]]
    output: dict[str, Any]
    usage: dict[str, Any]
    meter_claim: str


def run_workflow(
    engine: Engine,
    organization_id: UUID,
    run_id: UUID,
    claim: UUID,
    identity: dict[str, Any],
    retrieve: Callable[[], list[dict[str, str]]],
    generate: Callable[[list[dict[str, str]]], tuple[OnboardingPlan, dict[str, Any]]],
    validate: Callable[[OnboardingPlan, list[dict[str, str]]], bool],
    plan_type: type[OnboardingPlan] = OnboardingPlan,
) -> tuple[OnboardingPlan, dict[str, Any]]:
    # Namespace is derived from immutable version + request, never a caller's thread identifier.
    namespace = "onboarding.v2:" + digest(identity)
    saver = TenantSaver(engine, organization_id, run_id, claim, namespace)

    def search(state: State) -> State:
        return {"sources": retrieve()}

    def draft(state: State) -> State:
        plan, usage = generate(state["sources"])
        return {"output": plan.model_dump(mode="json"), "usage": usage, "meter_claim": str(claim)}

    def verify(state: State) -> State:
        if not validate(plan_type.model_validate(state["output"]), state["sources"]):
            raise ProviderFailure("unsupported_evidence")
        return {}

    graph = StateGraph(State)
    graph.add_node("retrieve", search)
    graph.add_node("draft", draft)
    graph.add_node("validate", verify)
    graph.add_node("review", lambda state: {})
    graph.add_edge(START, "retrieve")
    graph.add_edge("retrieve", "draft")
    graph.add_edge("draft", "validate")
    graph.add_edge("validate", "review")
    graph.add_edge("review", END)
    app = graph.compile(checkpointer=saver, interrupt_before=["review"])
    config: Any = {**saver.config(), "recursion_limit": 8, "callbacks": []}
    # Never export private graph state through inherited tracing environment flags.
    with tracing_context(enabled=False):
        saved = app.get_state(config)
        if saved.values.get("output") and (saved.next == ("review",) or not saved.next):
            state = saved.values
        else:
            state = app.invoke(None if saved.values else {}, config, durability="sync")
    usage = {**state.get("usage", {}), "_meter_claim": state.get("meter_claim", str(claim))}
    return plan_type.model_validate(state["output"]), usage
