"""Conductor time budget: a slow delegate ends in an honest answer, not silence."""

import asyncio

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.budget import (
    BUDGET_EXHAUSTED_ERROR,
    conductor_budget,
    partial_answer,
    set_soft_deadline,
)
from ze_agents.delegate import run_delegate
from ze_agents.registry import agent, clear_registry, register_instance
from ze_agents.tool import clear_tool_registry
from ze_agents.types import AgentContext, AgentResult


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    yield
    clear_registry()
    clear_tool_registry()


def _register_slow(name: str, seconds: float) -> None:
    async def _run(self, ctx: AgentContext) -> AgentResult:
        await asyncio.sleep(seconds)
        return AgentResult(agent=name, response="late")

    cls = type(
        f"_Slow_{name}",
        (BaseAgent,),
        {"name": name, "description": name, "tools": [], "run": _run},
    )
    agent(cls)
    register_instance(name, cls())


def test_conductor_budget_reads_config_and_keeps_reserve_inside_budget():
    assert conductor_budget(
        {"conductor": {"budget_seconds": 90, "reserve_seconds": 20}}
    ) == (90, 20)
    assert conductor_budget({}) == (110, 25)
    assert conductor_budget(
        {"conductor": {"budget_seconds": 10, "reserve_seconds": 40}}
    ) == (10, 9)


def test_partial_answer_names_done_open_and_offers_to_continue():
    text = partial_answer(
        [
            {"agent": "research", "status": "done"},
            {"agent": "calendar", "status": "stalled"},
        ]
    )
    assert "Finished: research." in text
    assert "calendar." in text and "Not finished" in text
    assert "continue" in text


async def test_delegate_over_the_remaining_budget_fails_with_the_wrap_up_error():
    _register_slow("research", 5)
    ctx = AgentContext(session_id="s", prompt="p")
    set_soft_deadline(ctx, 0.05)

    call = await run_delegate(
        {"agent_name": "research", "objective": "find it"},
        ctx,
        iteration=0,
        caller_name="companion",
    )

    assert not call.success
    assert BUDGET_EXHAUSTED_ERROR in call.error
    assert ctx.conductor_ledger[-1] == {"agent": "research", "status": "stalled"}


async def test_delegate_after_the_deadline_does_not_start_the_specialist():
    _register_slow("research", 5)
    ctx = AgentContext(session_id="s", prompt="p")
    set_soft_deadline(ctx, -1)

    call = await run_delegate(
        {"agent_name": "research", "objective": "find it"},
        ctx,
        iteration=0,
        caller_name="companion",
    )

    assert call.error == BUDGET_EXHAUSTED_ERROR


async def test_specialist_own_timeout_with_budget_left_is_a_plain_failure():
    async def _run(self, ctx: AgentContext) -> AgentResult:
        raise TimeoutError("gmail read timed out")

    cls = type(
        "_Flaky",
        (BaseAgent,),
        {"name": "messenger", "description": "m", "tools": [], "run": _run},
    )
    agent(cls)
    register_instance("messenger", cls())
    ctx = AgentContext(session_id="s", prompt="p")
    set_soft_deadline(ctx, 60)

    call = await run_delegate(
        {"agent_name": "messenger", "objective": "read mail"},
        ctx,
        iteration=0,
        caller_name="companion",
    )

    assert not call.success
    assert call.error == "gmail read timed out"
    assert BUDGET_EXHAUSTED_ERROR not in call.error


async def test_cancelled_specialist_is_reported_as_possibly_partly_run():
    _register_slow("messenger", 5)
    ctx = AgentContext(session_id="s", prompt="p")
    set_soft_deadline(ctx, 0.05)

    call = await run_delegate(
        {"agent_name": "messenger", "objective": "send it"},
        ctx,
        iteration=0,
        caller_name="companion",
    )

    assert "may have partly run" in call.error
    assert call.result == {"tool_calls": []}


def test_invalid_budget_config_falls_back_per_field():
    assert conductor_budget({"conductor": {"budget_seconds": "soon"}}) == (110, 25)
    assert conductor_budget({"conductor": {"budget_seconds": 0}}) == (1, 0)


async def test_specialist_timeout_without_any_budget_is_a_plain_failure():
    async def _run(self, ctx: AgentContext) -> AgentResult:
        raise TimeoutError("socket timed out")

    cls = type(
        "_NoBudget",
        (BaseAgent,),
        {"name": "calendar", "description": "c", "tools": [], "run": _run},
    )
    agent(cls)
    register_instance("calendar", cls())

    call = await run_delegate(
        {"agent_name": "calendar", "objective": "list events"},
        AgentContext(session_id="s", prompt="p"),
        iteration=0,
        caller_name="companion",
    )

    assert call.error == "socket timed out"
