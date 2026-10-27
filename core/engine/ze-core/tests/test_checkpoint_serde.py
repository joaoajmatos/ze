"""Tests for automatic checkpoint serde allowlist construction."""

from __future__ import annotations

from ze_core.checkpoint_serde import (
    CORE_CHECKPOINT_MODULES,
    build_checkpoint_serde,
    collect_checkpoint_allowlist,
    collect_plugin_serde_modules,
    collect_types_from_module,
)
from ze_automation.workflow.types import StepResult, WorkflowStep


class _PluginWithWorkflowTypes:
    def checkpoint_serde_modules(self) -> tuple[str, ...]:
        return ("ze_automation.workflow.types",)


def test_collect_types_from_module_finds_dataclasses_and_enums() -> None:
    types = collect_types_from_module("ze_agents.types")
    assert ("ze_agents.types", "AgentResult") in types
    assert ("ze_agents.types", "ToolCall") in types


def test_collect_types_from_module_skips_imported_reexports() -> None:
    types = collect_types_from_module("ze_memory.types")
    assert ("ze_agents.types", "RetrievalRequest") not in types
    assert ("ze_memory.types", "Fact") in types


def test_collect_plugin_serde_modules_deduplicates() -> None:
    plugin = _PluginWithWorkflowTypes()
    assert collect_plugin_serde_modules([plugin, plugin]) == (
        "ze_automation.workflow.types",
    )


def test_collect_checkpoint_allowlist_includes_core_and_plugin_types() -> None:
    allowlist = set(collect_checkpoint_allowlist([_PluginWithWorkflowTypes()]))
    assert ("ze_memory.types", "MemoryContext") in allowlist
    assert ("ze_automation.workflow.types", "WorkflowStep") in allowlist
    assert ("ze_automation.workflow.types", "StepResult") in allowlist
    assert ("asyncpg.pgproto.pgproto", "UUID") in allowlist


def test_core_modules_cover_routing_and_memory() -> None:
    allowlist = set(collect_checkpoint_allowlist(plugins=[]))
    for module in CORE_CHECKPOINT_MODULES:
        assert any(entry[0] == module for entry in allowlist)


def test_workflow_types_round_trip_through_built_serde() -> None:
    serde = build_checkpoint_serde(plugins=[_PluginWithWorkflowTypes()])
    original = WorkflowStep(task="send email", agent_hint="email")
    type_, data = serde.dumps_typed(original)
    restored = serde.loads_typed((type_, data))
    assert isinstance(restored, WorkflowStep)
    assert restored.task == original.task
    assert restored.agent_hint == original.agent_hint

    result = StepResult(
        step_index=0,
        task="send email",
        output="done",
        success=True,
        error=None,
        duration_ms=42,
    )
    type_, data = serde.dumps_typed(result)
    restored_result = serde.loads_typed((type_, data))
    assert isinstance(restored_result, StepResult)
    assert restored_result.output == "done"


def test_allowlist_covers_judgment_record_and_system_one_result() -> None:
    allowlist = set(collect_checkpoint_allowlist(plugins=[]))
    assert ("ze_agents.judgment", "Judgment") in allowlist
    assert ("ze_agents.judgment", "SurfaceBar") in allowlist
    assert ("ze_agents.system_one", "SystemOneResult") in allowlist


def test_routing_envelope_with_judgment_round_trips() -> None:
    from ze_agents.judgment import Judgment, SurfaceBar
    from ze_agents.system_one import SystemOneAnswer, SystemOneResult
    from ze_core.routing.types import RoutingEnvelope

    judgment = Judgment(
        surface="routing",
        result=SystemOneResult(
            outcome="ok",
            model="m",
            answers={
                "agent": SystemOneAnswer(
                    type="choice",
                    choice="research",
                    confidence=0.8,
                    probabilities={"research": 0.9, "none": 0.1},
                )
            },
        ),
        question_kinds={"agent": "choice"},
        consumed=frozenset({"agent"}),
        skip_reason=None,
        bars={"agent": SurfaceBar("choice_trust", 0.5)},
    )
    envelope = RoutingEnvelope(
        primary_agent="research",
        confidence=0.9,
        score_gap=0.2,
        routing_method="embedding",
        is_compound=False,
        subtasks=[],
        requires_synthesis=False,
    )
    envelope.judgment = judgment

    serde = build_checkpoint_serde(plugins=[])
    restored = serde.loads_typed(serde.dumps_typed(envelope))

    assert isinstance(restored, RoutingEnvelope)
    assert restored.judgment == judgment
