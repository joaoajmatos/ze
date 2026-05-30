"""Workflow graph nodes, edge functions, and graph builder.

Transitional location — will move to ze_personal/graph/workflow.py in the
ze-personal package once that package is created (arch-package-reorg step 4).
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from langchain_core.runnables import RunnableConfig

from ze_core.capability.types import GateDecision
from ze_core.defaults import MODEL_WORKFLOW_VERIFY
from ze_core.logging import get_logger
from ze_core.orchestration.state import AgentState
from ze_core.telemetry.context import set_agent_context
from ze_personal.workflow.store import WorkflowStore
from ze_personal.workflow.types import StepResult, WorkflowStep

log = get_logger(__name__)


# ── Graph nodes ───────────────────────────────────────────────────────────────

async def load_workflow_step(state: AgentState, config: RunnableConfig) -> dict:
    """Set prompt to the current step's task and reset all per-step state."""
    steps: list[WorkflowStep] = state["workflow_steps"]
    idx: int = state.get("current_step_index", 0)
    step = steps[idx]

    log.info(
        "workflow_step_start",
        step_index=idx,
        total=len(steps),
        task=step.task[:80],
        execution_id=str(state.get("workflow_execution_id")),
    )

    return {
        "prompt": step.task,
        "envelope": None,
        "memory_context": None,
        "agent_context": None,
        "gate_decision": None,
        "agent_result": None,
    }


async def verify_step(state: AgentState, config: RunnableConfig) -> dict:
    """Validate step output; append StepResult and advance index."""
    store: WorkflowStore = config["configurable"]["workflow_store"]
    client: Any = config["configurable"]["openrouter_client"]
    model = _resolve_verify_model(config)

    steps: list[WorkflowStep] = state["workflow_steps"]
    idx: int = state.get("current_step_index", 0)
    step = steps[idx]
    execution_id = state.get("workflow_execution_id")
    result = state.get("agent_result")

    if result and result.tool_calls:
        failed = [tc for tc in result.tool_calls if not tc.success and not getattr(tc, "is_draft", False)]
        if failed:
            return _fail_step(store, execution_id, state, idx, step.task, "", f"Tool {failed[0].tool_name} failed: {failed[0].error}")

    output = result.response if result else ""
    if not output.strip():
        return _fail_step(store, execution_id, state, idx, step.task, "", "Step produced empty output")

    if step.verify:
        set_agent_context("workflow_verify")
        try:
            raw = await client.complete(
                messages=[{
                    "role": "user",
                    "content": (
                        f"Step output:\n{output}\n\n"
                        f"Verification criteria: {step.verify}\n\n"
                        'Does the output meet the criteria? Reply with JSON only: {"pass": true, "reason": "..."}'
                    ),
                }],
                model=model,
            )
            verdict = json.loads(raw)
            if not verdict.get("pass", True):
                reason = verdict.get("reason", "Verification failed")
                return _fail_step(store, execution_id, state, idx, step.task, output, reason)
        except Exception as exc:
            log.warning("workflow_verify_error", step_index=idx, error=str(exc))

    step_result = StepResult(
        step_index=idx,
        task=step.task,
        output=output,
        success=True,
        error=None,
        duration_ms=0,
    )
    asyncio.create_task(store.record_step(execution_id, step_result))

    prior = list(state.get("workflow_step_results") or [])
    log.info("workflow_step_complete", step_index=idx, task=step.task[:60])
    return {
        "workflow_step_results": prior + [step_result],
        "current_step_index": idx + 1,
    }


async def workflow_synthesize(state: AgentState, config: RunnableConfig) -> dict:
    """Merge all step outputs into a final response and mark execution complete."""
    store: WorkflowStore = config["configurable"]["workflow_store"]
    client: Any = config["configurable"]["openrouter_client"]
    model = _resolve_verify_model(config)

    step_results: list[StepResult] = state.get("workflow_step_results") or []
    execution_id = state.get("workflow_execution_id")

    parts = "\n\n".join(
        f"Step {r.step_index + 1} — {r.task}:\n{r.output}"
        for r in step_results
        if r.success and r.output
    )

    if parts:
        set_agent_context("workflow_synthesize")
        response = await client.complete(
            messages=[{
                "role": "user",
                "content": f"Summarize the following workflow results concisely:\n\n{parts}",
            }],
            model=model,
        )
    else:
        response = "Workflow completed with no output."

    if execution_id:
        asyncio.create_task(store.finish_execution(execution_id, "completed"))

    log.info("workflow_complete", execution_id=str(execution_id), steps=len(step_results))
    return {"final_response": response}


async def workflow_failed(state: AgentState, config: RunnableConfig) -> dict:
    """Record execution failure and build a user-facing error message."""
    store: WorkflowStore = config["configurable"]["workflow_store"]

    step_results: list[StepResult] = state.get("workflow_step_results") or []
    execution_id = state.get("workflow_execution_id")

    failed = [r for r in step_results if not r.success]
    if failed:
        last = failed[-1]
        error_msg = f"Step {last.step_index + 1} ({last.task}) failed: {last.error}"
    else:
        error_msg = state.get("error") or "Workflow failed"

    if execution_id:
        asyncio.create_task(store.finish_execution(execution_id, "failed", error=error_msg))

    log.warning("workflow_failed", execution_id=str(execution_id), error=error_msg)
    return {"final_response": f"Workflow failed: {error_msg}"}


# ── Edge functions ────────────────────────────────────────────────────────────

def after_capability_check_workflow(state: AgentState) -> str:
    """In workflow mode all steps execute directly — workflow creation was the gate."""
    decision = state.get("gate_decision")
    if decision == GateDecision.BLOCKED:
        return "workflow_failed"
    return "execute_tool"


def after_verify_step(state: AgentState) -> str:
    step_results = state.get("workflow_step_results") or []
    if step_results and not step_results[-1].success:
        return "workflow_failed"
    steps = state.get("workflow_steps") or []
    if state.get("current_step_index", 0) >= len(steps):
        return "workflow_synthesize"
    return "load_workflow_step"


# ── Graph builder ─────────────────────────────────────────────────────────────

def build_workflow_graph(checkpointer: Any, plugins: list | None = None) -> Any:
    """Build and compile the workflow execution graph."""
    from langgraph.constants import END

    from ze_core.orchestration.graph import graph_builder
    from ze_core.orchestration.state import build_state_type

    state_type = build_state_type(plugins or [])
    builder = graph_builder(state_type=state_type)

    builder.add_node("load_workflow_step", load_workflow_step)
    builder.add_node("verify_step",        verify_step)
    builder.add_node("workflow_synthesize", workflow_synthesize)
    builder.add_node("workflow_failed",    workflow_failed)

    builder.set_entry_point("load_workflow_step")

    builder.add_edge("load_workflow_step", "embed_route")
    builder.add_edge("embed_route",        "fetch_context")
    builder.add_edge("fetch_context",      "capability_check")
    builder.add_conditional_edges(
        "capability_check",
        after_capability_check_workflow,
        {"execute_tool": "execute_tool", "workflow_failed": "workflow_failed"},
    )
    builder.add_edge("execute_tool",  "write_memory")
    builder.add_edge("write_memory",  "verify_step")
    builder.add_conditional_edges(
        "verify_step",
        after_verify_step,
        {
            "load_workflow_step":  "load_workflow_step",
            "workflow_synthesize": "workflow_synthesize",
            "workflow_failed":     "workflow_failed",
        },
    )
    builder.add_edge("workflow_synthesize", END)
    builder.add_edge("workflow_failed",     END)

    for plugin in (plugins or []):
        for name, fn in plugin.graph_nodes().items():
            builder.add_node(name, fn)
        plugin.graph_edges(builder)

    return builder.compile(checkpointer=checkpointer)


# ── Private helpers ───────────────────────────────────────────────────────────

def _resolve_verify_model(config: RunnableConfig) -> str:
    cfg = config["configurable"].get("settings")
    if cfg is None:
        return MODEL_WORKFLOW_VERIFY
    models = (
        cfg.get("models", {})
        if isinstance(cfg, dict)
        else getattr(cfg, "config", {}).get("models", {})
    )
    return models.get("workflow_verify", MODEL_WORKFLOW_VERIFY)


def _fail_step(
    store: WorkflowStore,
    execution_id: Any,
    state: AgentState,
    idx: int,
    task: str,
    output: str,
    error: str,
) -> dict:
    step_result = StepResult(
        step_index=idx,
        task=task,
        output=output,
        success=False,
        error=error,
        duration_ms=0,
    )
    asyncio.create_task(store.record_step(execution_id, step_result))
    prior = list(state.get("workflow_step_results") or [])
    log.warning("workflow_step_failed", step_index=idx, error=error)
    return {
        "workflow_step_results": prior + [step_result],
        "current_step_index": idx + 1,
    }
