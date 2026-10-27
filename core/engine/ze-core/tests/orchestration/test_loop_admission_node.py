"""write_memory hands the loop commit of the single commitment intake to a background task (phase 173)."""

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
from tests.support.judgments import make_judgment


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


DECISION = SimpleNamespace(kind="create_suspected", reason="implied")
SOURCE = SimpleNamespace(inflow="conversation", ref="t1")


def _loop_part(kind="create_suspected"):
    return SimpleNamespace(
        decision=SimpleNamespace(kind=kind, reason="implied"),
        text="I need to renew my passport",
        inflow="conversation",
        source=SOURCE,
    )


def _intake_result(
    outcome="ok", with_judgment=True, loop=True, kind="create_suspected"
):
    judgment = SystemOneResult(
        outcome=outcome,
        skip_reason="timeout" if outcome == "skip" else None,
        answers={"is_open_concern": SystemOneAnswer(type="noul", noul=0.9)},
        latency_ms=3,
    )
    record = make_judgment(
        "commitment_intake",
        judgment,
        {"is_open_concern": "noul"},
        consumed=frozenset({"is_open_concern"}),
        skip_reason=judgment.skip_reason,
    )
    return SimpleNamespace(
        fact=SimpleNamespace(facts=[], path="none"),
        loop=_loop_part(kind) if loop else None,
        link=None,
        judgment=record if with_judgment else None,
    )


def _setup(thread_id="t1", **extra):
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
        agent_result=AgentResult(agent="companion", response="ok", tool_calls=[]),
        message_trace=_trace(
            [JudgmentTrace(question_id="embed_route", kind="noul", latency_ms=1)]
        ),
    )
    return state, cfg


async def test_intake_rows_append_after_existing_rows_and_commit_fires():
    committed = asyncio.Event()

    async def commit(decision, **kw):
        committed.set()
        return None

    intake = AsyncMock(return_value=_intake_result())
    state, cfg = _setup(commitment_intake=intake, loop_commit=commit)
    out = await memory.write_memory(state, cfg)
    ids = [r.question_id for r in out["message_trace"].judgments]
    assert ids == ["embed_route", "is_open_concern"]
    assert out["message_trace"].judgments[1].consumed is True
    await asyncio.wait_for(committed.wait(), 1)
    intake.assert_awaited_once()
    kwargs = intake.await_args.kwargs
    assert kwargs["prompt"] == "I need to renew my passport"
    assert kwargs["response"] == "ok"
    assert kwargs["agent"] == "companion"
    assert kwargs["tool_calls"] == []


async def test_skip_reason_rides_on_rows():
    state, cfg = _setup(
        commitment_intake=AsyncMock(return_value=_intake_result(outcome="skip"))
    )
    out = await memory.write_memory(state, cfg)
    assert out["message_trace"].judgments[-1].skip_reason == "timeout"


async def test_no_judgment_means_no_rows_and_no_commit():
    state, cfg = _setup(
        commitment_intake=AsyncMock(return_value=_intake_result(with_judgment=False))
    )
    out = await memory.write_memory(state, cfg)
    assert "message_trace" not in out


@pytest.mark.parametrize("thread_id,retry", [("eval-1", False), ("t1", True)])
async def test_no_intake_on_eval_or_retry(thread_id, retry):
    intake = AsyncMock(return_value=_intake_result())
    state, cfg = _setup(thread_id=thread_id, commitment_intake=intake)
    if retry:
        cfg["configurable"]["retry_mode"] = True
    await memory.write_memory(state, cfg)
    intake.assert_not_awaited()


async def test_intake_exception_does_not_fail_turn():
    state, cfg = _setup(commitment_intake=AsyncMock(side_effect=RuntimeError("boom")))
    out = await memory.write_memory(state, cfg)
    assert "messages" in out
    assert "message_trace" not in out


async def test_no_intake_key_runs_the_fact_extractor_alone():
    fact_extractor = AsyncMock(return_value=SimpleNamespace(facts=[], path="haiku"))
    state, cfg = _setup(fact_extractor=fact_extractor)
    out = await memory.write_memory(state, cfg)
    assert "messages" in out
    fact_extractor.assert_awaited_once()


async def test_intake_replaces_the_fact_extractor():
    fact_extractor = AsyncMock()
    state, cfg = _setup(
        commitment_intake=AsyncMock(return_value=_intake_result()),
        fact_extractor=fact_extractor,
    )
    await memory.write_memory(state, cfg)
    fact_extractor.assert_not_awaited()


async def _drain():
    current = asyncio.current_task()
    pending = [t for t in asyncio.all_tasks() if t is not current]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)


def _recording_commit():
    received: list = []

    async def commit(decision, *, text, inflow, evidence=(), source=None):
        received.append(list(evidence))
        return None

    return commit, received


async def test_commit_receives_the_turn_episode_ref():
    commit, received = _recording_commit()
    episode_id = uuid4()
    state, cfg = _setup(
        commitment_intake=AsyncMock(return_value=_intake_result()), loop_commit=commit
    )
    cfg["configurable"]["memory_store"].write_episode = AsyncMock(
        return_value=episode_id
    )

    await memory.write_memory(state, cfg)
    await _drain()

    assert received == [[EvidenceRef(kind="episode", id=episode_id)]]


@pytest.mark.parametrize("outcome", ["none", "raises"])
async def test_commit_receives_no_refs_when_the_episode_write_fails(outcome):
    commit, received = _recording_commit()
    state, cfg = _setup(
        commitment_intake=AsyncMock(return_value=_intake_result()), loop_commit=commit
    )
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

    state, cfg = _setup(
        commitment_intake=AsyncMock(return_value=_intake_result()), loop_commit=commit
    )
    cfg["configurable"]["memory_store"].write_episode = slow_write_episode

    out = await asyncio.wait_for(memory.write_memory(state, cfg), 2)

    assert "messages" in out
    assert received == []
    release.set()
    await _drain()
    assert len(received) == 1 and len(received[0]) == 1


async def test_commit_receives_the_decision_text_inflow_and_source():
    calls: list = []

    async def commit(decision, **kw):
        calls.append((decision, kw))

    episode_id = uuid4()
    state, cfg = _setup(
        commitment_intake=AsyncMock(return_value=_intake_result()), loop_commit=commit
    )
    cfg["configurable"]["memory_store"].write_episode = AsyncMock(
        return_value=episode_id
    )

    await memory.write_memory(state, cfg)
    await _drain()

    [(decision, kw)] = calls
    assert decision.kind == "create_suspected"
    assert kw == {
        "text": "I need to renew my passport",
        "inflow": "conversation",
        "evidence": [EvidenceRef(kind="episode", id=episode_id)],
        "source": SOURCE,
    }


async def test_a_hold_decision_commits_nothing():
    commit, received = _recording_commit()
    state, cfg = _setup(
        commitment_intake=AsyncMock(return_value=_intake_result(kind="hold")),
        loop_commit=commit,
    )

    await memory.write_memory(state, cfg)
    await _drain()

    assert received == []


async def test_no_loop_commit_key_commits_nothing():
    state, cfg = _setup(commitment_intake=AsyncMock(return_value=_intake_result()))

    out = await memory.write_memory(state, cfg)
    await _drain()

    assert "messages" in out
