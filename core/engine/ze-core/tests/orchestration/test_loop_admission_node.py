"""write_memory runs the duck-typed loop gate beside the fact extractor (phase 168)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_agents.types import AgentContext, AgentResult
from ze_core.conversation.messages.types import JudgmentTrace, MessageTrace
from ze_core.orchestration.nodes import memory
from ze_memory.types import MemoryContext

from tests.orchestration.test_nodes import base_state, make_config


def _trace(rows=None) -> MessageTrace:
    return MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.1,
        is_compound=False,
        subtasks=[],
        judgments=list(rows or []),
    )


def _loop_result(skip_reason=None, commit=None, outcome="ok"):
    judgment = SystemOneResult(
        outcome=outcome,
        skip_reason="timeout" if outcome == "skip" else None,
        answers={"is_open_concern": SystemOneAnswer(type="noul", noul=0.9)},
        latency_ms=3,
    )
    return SimpleNamespace(
        judgment=judgment,
        question_kinds={"is_open_concern": "noul"},
        consumed=frozenset({"is_open_concern"}),
        skip_reason=skip_reason,
        commit=commit,
    )


def _fact_result(judgment=None):
    return SimpleNamespace(
        facts=[],
        path="system_one" if judgment else "none",
        judgment=judgment,
        question_ids=("biography",),
        consumed=frozenset(),
        skip_reason=None,
    )


def _setup(thread_id="t1", **extra):
    cfg = make_config()
    cfg["configurable"]["thread_id"] = thread_id
    cfg["configurable"].update(extra)
    ctx = AgentContext(
        session_id="s1",
        prompt="I need to renew my passport",
        intent="read",
        memory=MemoryContext(),
    )
    state = base_state(
        agent_context=ctx,
        agent_result=AgentResult(agent="companion", response="ok"),
        message_trace=_trace(
            [JudgmentTrace(question_id="embed_route", kind="noul", latency_ms=1)]
        ),
    )
    return state, cfg


async def test_loop_rows_append_after_existing_rows_and_commit_fires():
    committed = asyncio.Event()

    async def commit():
        committed.set()
        return []

    admission = AsyncMock(return_value=_loop_result(commit=commit))
    state, cfg = _setup(loop_admission=admission)
    out = await memory.write_memory(state, cfg)
    ids = [r.question_id for r in out["message_trace"].judgments]
    assert ids == ["embed_route", "is_open_concern"]
    assert out["message_trace"].judgments[1].consumed is True
    await asyncio.wait_for(committed.wait(), 1)
    admission.assert_awaited_once()
    assert admission.await_args.kwargs == {"prompt": "I need to renew my passport"}


async def test_fact_rows_and_loop_rows_merge_in_one_replace():
    fact_judgment = SystemOneResult(
        outcome="ok",
        answers={"biography": SystemOneAnswer(type="noul", noul=0.1)},
    )
    fact_extractor = AsyncMock(return_value=_fact_result(fact_judgment))
    state, cfg = _setup(
        fact_extractor=fact_extractor,
        loop_admission=AsyncMock(return_value=_loop_result()),
    )
    out = await memory.write_memory(state, cfg)
    ids = [r.question_id for r in out["message_trace"].judgments]
    assert ids == ["embed_route", "biography", "is_open_concern"]


async def test_skip_reason_rides_on_rows():
    state, cfg = _setup(
        loop_admission=AsyncMock(
            return_value=_loop_result(skip_reason="uncalibrated", outcome="skip")
        )
    )
    out = await memory.write_memory(state, cfg)
    assert out["message_trace"].judgments[-1].skip_reason == "timeout"


async def test_no_judgment_means_no_rows_and_no_commit():
    result = _loop_result()
    result.judgment = None
    state, cfg = _setup(loop_admission=AsyncMock(return_value=result))
    out = await memory.write_memory(state, cfg)
    assert "message_trace" not in out


@pytest.mark.parametrize("thread_id,retry", [("eval-1", False), ("t1", True)])
async def test_no_loop_gate_on_eval_or_retry(thread_id, retry):
    admission = AsyncMock(return_value=_loop_result())
    state, cfg = _setup(thread_id=thread_id, loop_admission=admission)
    if retry:
        cfg["configurable"]["retry_mode"] = True
    await memory.write_memory(state, cfg)
    admission.assert_not_awaited()


async def test_loop_admission_exception_does_not_fail_turn():
    state, cfg = _setup(loop_admission=AsyncMock(side_effect=RuntimeError("boom")))
    out = await memory.write_memory(state, cfg)
    assert "messages" in out
    assert "message_trace" not in out


async def test_fact_and_loop_calls_run_concurrently():
    order = []
    gate = asyncio.Event()

    async def fact_extractor(configurable, **kw):
        order.append("fact_start")
        await asyncio.wait_for(gate.wait(), 1)
        order.append("fact_end")
        return _fact_result()

    async def loop_admission(configurable, *, prompt):
        order.append("loop_start")
        gate.set()
        return _loop_result()

    state, cfg = _setup(fact_extractor=fact_extractor, loop_admission=loop_admission)
    await memory.write_memory(state, cfg)
    assert order == ["fact_start", "loop_start", "fact_end"]


async def test_no_loop_admission_key_is_no_loop_gate():
    state, cfg = _setup()
    out = await memory.write_memory(state, cfg)
    assert "messages" in out
