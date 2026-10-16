"""write_memory runs the duck-typed loop gate beside the fact extractor (phase 168)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from uuid import uuid4
from unittest.mock import AsyncMock

import pytest
from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_agents.types import AgentContext, AgentResult
from ze_core.conversation.messages.types import JudgmentTrace, MessageTrace
from ze_core.orchestration.nodes import memory
from ze_memory.types import MemoryContext
from ze_plugin.contribution import EvidenceRef

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
    tool_calls = extra.pop("tool_calls", None)
    cfg = make_config()
    cfg["configurable"]["thread_id"] = thread_id
    cfg["configurable"].update(extra)
    ctx = AgentContext(
        session_id="s1",
        prompt="I need to renew my passport",
        memory=MemoryContext(),
    )
    state = base_state(
        agent_context=ctx,
        agent_result=AgentResult(
            agent="companion", response="ok", tool_calls=tool_calls or []
        ),
        message_trace=_trace(
            [JudgmentTrace(question_id="embed_route", kind="noul", latency_ms=1)]
        ),
    )
    return state, cfg


def _track_call(result, name="track_loop"):
    from ze_agents.types import ToolCall

    return ToolCall(
        tool_name=name, args={}, result=result, duration_ms=1, success=True
    )


async def test_loop_rows_append_after_existing_rows_and_commit_fires():
    committed = asyncio.Event()

    async def commit(evidence):
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


async def test_successful_track_loop_skips_the_loop_gate():
    admission = AsyncMock(return_value=_loop_result())
    fact_extractor = AsyncMock(return_value=_fact_result())
    state, cfg = _setup(
        loop_admission=admission,
        fact_extractor=fact_extractor,
        tool_calls=[_track_call({"ok": True, "id": "loop-1", "outcome": "created"})],
    )

    out = await memory.write_memory(state, cfg)

    admission.assert_not_awaited()
    fact_extractor.assert_awaited_once()
    trace = out.get("message_trace")
    if trace is not None:
        assert [r.question_id for r in trace.judgments] == ["embed_route"]


async def test_successful_confirm_loop_skips_the_loop_gate():
    admission = AsyncMock(return_value=_loop_result())
    state, cfg = _setup(
        loop_admission=admission,
        tool_calls=[
            _track_call({"ok": True, "id": "loop-1", "state": "active"}, "confirm_loop")
        ],
    )

    await memory.write_memory(state, cfg)

    admission.assert_not_awaited()


async def test_failed_confirm_loop_still_runs_the_gate():
    admission = AsyncMock(return_value=_loop_result())
    state, cfg = _setup(
        loop_admission=admission,
        tool_calls=[_track_call({"ok": False, "error": "nope"}, "confirm_loop")],
    )

    await memory.write_memory(state, cfg)

    admission.assert_awaited_once()


async def test_failed_track_loop_still_runs_the_gate():
    admission = AsyncMock(return_value=_loop_result())
    state, cfg = _setup(
        loop_admission=admission,
        tool_calls=[_track_call({"ok": False, "error": "db down"})],
    )

    await memory.write_memory(state, cfg)

    admission.assert_awaited_once()


async def test_nested_successful_track_loop_skips_the_loop_gate():
    admission = AsyncMock(return_value=_loop_result())
    delegate = _track_call(
        {
            "tool_calls": [
                {
                    "tool_name": "track_loop",
                    "args": {},
                    "result": {"ok": True, "id": "loop-1"},
                    "duration_ms": 1,
                    "success": True,
                }
            ]
        },
        name="delegate_to_agent",
    )
    state, cfg = _setup(loop_admission=admission, tool_calls=[delegate])

    await memory.write_memory(state, cfg)

    admission.assert_not_awaited()


async def test_no_tool_calls_still_runs_the_gate():
    admission = AsyncMock(return_value=_loop_result())
    state, cfg = _setup(loop_admission=admission)

    await memory.write_memory(state, cfg)

    admission.assert_awaited_once()


@pytest.mark.parametrize("thread_id,retry", [("eval-1", False), ("t1", True)])
async def test_track_loop_does_not_reopen_eval_or_retry_gate(thread_id, retry):
    admission = AsyncMock(return_value=_loop_result())
    state, cfg = _setup(
        thread_id=thread_id,
        loop_admission=admission,
        tool_calls=[_track_call({"ok": True, "id": "loop-1"})],
    )
    if retry:
        cfg["configurable"]["retry_mode"] = True

    await memory.write_memory(state, cfg)

    admission.assert_not_awaited()


async def _drain():
    current = asyncio.current_task()
    pending = [t for t in asyncio.all_tasks() if t is not current]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


def _recording_commit():
    received: list = []

    async def commit(evidence):
        received.append(list(evidence))
        return []

    return commit, received


async def test_commit_receives_the_turn_episode_ref():
    commit, received = _recording_commit()
    episode_id = uuid4()
    state, cfg = _setup(loop_admission=AsyncMock(return_value=_loop_result(commit=commit)))
    cfg["configurable"]["memory_store"].write_episode = AsyncMock(return_value=episode_id)

    await memory.write_memory(state, cfg)
    await _drain()

    assert received == [[EvidenceRef(kind="episode", id=episode_id)]]


@pytest.mark.parametrize("outcome", ["none", "raises"])
async def test_commit_receives_no_refs_when_the_episode_write_fails(outcome):
    commit, received = _recording_commit()
    state, cfg = _setup(loop_admission=AsyncMock(return_value=_loop_result(commit=commit)))
    cfg["configurable"]["memory_store"].write_episode = AsyncMock(
        return_value=None if outcome == "none" else None,
        side_effect=RuntimeError("db") if outcome == "raises" else None,
    )

    await memory.write_memory(state, cfg)
    await _drain()

    assert received == [[]]


async def test_node_returns_before_a_slow_episode_write_finishes():
    commit, received = _recording_commit()
    release = asyncio.Event()

    async def slow_write_episode(**kw):
        await release.wait()
        return uuid4()

    state, cfg = _setup(loop_admission=AsyncMock(return_value=_loop_result(commit=commit)))
    cfg["configurable"]["memory_store"].write_episode = slow_write_episode

    out = await asyncio.wait_for(memory.write_memory(state, cfg), 2)

    assert "messages" in out
    assert received == []
    release.set()
    await _drain()
    assert len(received) == 1 and len(received[0]) == 1
