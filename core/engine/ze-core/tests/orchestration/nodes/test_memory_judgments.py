"""write_memory — consumes FactAdmission and merges judgments into message_trace."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from ze_agents.system_one import SystemOneAnswer, SystemOneResult
from ze_agents.types import AgentContext, AgentResult, ToolCall
from ze_core.conversation.messages.types import JudgmentTrace, MessageTrace
from ze_core.orchestration.nodes.memory import write_memory
from ze_memory.types import Fact, FactAdmission, MemoryContext

from tests.support.judgments import make_judgment


def _ctx(prompt: str = "I prefer aisle seats") -> AgentContext:
    return AgentContext(
        session_id="s1",
        prompt=prompt,
        memory=MemoryContext(),
        messages=[],
    )


def _config(extractor, *, thread_id: str = "s1") -> dict:
    store = AsyncMock()
    store.write_episode = AsyncMock()
    embedder = MagicMock()
    embedder.encode_passage = embedder.encode_query = MagicMock(return_value=[0.1, 0.2])
    return {
        "configurable": {
            "memory_store": store,
            "embedder": embedder,
            "thread_id": thread_id,
            "fact_extractor": extractor,
        }
    }


def _trace(judgments=None) -> MessageTrace:
    return MessageTrace(
        agent="companion",
        routing_method="embedding",
        confidence=0.9,
        score_gap=0.3,
        is_compound=False,
        subtasks=[],
        judgments=list(judgments or []),
    )


def _state(trace, prompt: str = "I prefer aisle seats", tool_calls=None) -> dict:
    return {
        "session_id": "s1",
        "agent_context": _ctx(prompt),
        "agent_result": AgentResult(
            agent="companion", response="Noted.", tool_calls=tool_calls or []
        ),
        "subtask_results": [],
        "messages": [],
        "input_modality": "text",
        "message_trace": trace,
    }


def _ok_result() -> SystemOneResult:
    return SystemOneResult(
        outcome="ok",
        model="jev",
        input_tokens=10,
        latency_ms=5,
        answers={
            "family": SystemOneAnswer(
                type="choice",
                choice="preference",
                confidence=0.9,
                probabilities={"preference": 0.9},
            ),
            "biography": SystemOneAnswer(type="noul", noul=0.9),
        },
    )


_IDS = ("family", "biography")


def _persist_admission(facts=None) -> FactAdmission:
    return FactAdmission(
        facts=facts
        if facts is not None
        else [Fact(predicate="preference", value="aisle seats")],
        path="system_one",
    )


def _ok_judgment():
    return make_judgment(
        "commitment_intake",
        _ok_result(),
        {"family": "choice", "biography": "noul"},
        consumed=frozenset(_IDS),
    )


async def _run(admission, trace, **kw):
    async def extractor(_cfg, **_kwargs):
        return admission

    with patch(
        "ze_core.orchestration.nodes.memory.submit_perception_facts",
        new_callable=AsyncMock,
    ) as submit:
        out = await write_memory(_state(trace, **kw), _config(extractor))
    return out, submit


async def test_submits_admission_facts():
    out, submit = await _run(_persist_admission(), _trace())
    facts = [i.fact for i in submit.await_args.args[1]]
    assert [(f.predicate, f.value) for f in facts] == [("preference", "aisle seats")]


async def test_no_judgment_leaves_trace_unchanged():
    admission = FactAdmission(facts=[], path="haiku")
    out, _ = await _run(admission, _trace())
    assert "message_trace" not in out


async def test_ok_judgment_appends_rows_after_existing():
    existing = JudgmentTrace(question_id="routing", kind="choice", latency_ms=1)
    trace = _trace([existing])
    out, _, _ = await _run_intake(AsyncMock(return_value=_intake_admission()), trace)
    rows = out["message_trace"].judgments
    assert rows[0] is existing
    assert [r.question_id for r in rows[1:]] == list(_INTAKE_KINDS)
    assert {r.question_id for r in rows[1:] if r.consumed} == set(_IDS)
    assert trace.judgments == [existing]


async def test_trace_merge_also_in_compaction_branch():
    state = _state(_trace())
    state["messages"] = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"}
        for i in range(60)
    ]
    config = _config(AsyncMock())
    config["configurable"]["commitment_intake"] = AsyncMock(
        return_value=_intake_admission()
    )
    config["configurable"]["openrouter_client"] = AsyncMock()
    config["configurable"]["openrouter_client"].complete = AsyncMock(return_value="sum")
    with (
        patch(
            "ze_core.orchestration.nodes.memory.submit_perception_facts",
            new_callable=AsyncMock,
        ),
        patch("ze_core.orchestration.nodes.memory._should_compact", return_value=True),
    ):
        out = await write_memory(state, config)
    assert out["messages"][0]["compaction_summary"] is True
    assert len(out["message_trace"].judgments) == len(_INTAKE_KINDS)


async def test_missing_message_trace_does_not_crash():
    out, submit = await _run(_persist_admission(), None)
    assert "message_trace" not in out
    submit.assert_awaited_once()


async def test_eval_thread_never_calls_extractor():
    extractor = AsyncMock()
    state = _state(_trace())
    with patch(
        "ze_core.orchestration.nodes.memory.submit_perception_facts",
        new_callable=AsyncMock,
    ):
        out = await write_memory(state, _config(extractor, thread_id="eval-1"))
    extractor.assert_not_awaited()
    assert "message_trace" not in out


async def test_haiku_path_admission_has_no_duplicate_identity():
    admission = FactAdmission(
        facts=[
            Fact(predicate="preference", value="aisle seats"),
            Fact(predicate="preference", value="window"),
        ],
        path="haiku",
    )
    remembered = ToolCall(
        tool_name="remember_fact",
        args={"predicate": "preference", "value": "aisle seats"},
        result={"ok": True},
        duration_ms=1,
        success=True,
    )
    out, submit = await _run(admission, _trace(), tool_calls=[remembered])
    facts = [i.fact for i in submit.await_args.args[1]]
    assert [(f.predicate, f.value) for f in facts] == [("preference", "window")]
    assert "message_trace" not in out


# --- phase 173: single commitment intake ---------------------------------------------

_INTAKE_KINDS = {"commitment": "choice", "family": "choice", "biography": "noul"}


def _intake_admission(**over):
    from types import SimpleNamespace

    base = dict(
        fact=_persist_admission(),
        loop=None,
        link=None,
        judgment=make_judgment(
            "commitment_intake",
            _ok_result(),
            _INTAKE_KINDS,
            consumed=frozenset({"family", "biography"}),
        ),
    )
    base.update(over)
    return SimpleNamespace(**base)


async def _run_intake(intake, trace, *, extractor=None, **kw):
    config = _config(extractor or AsyncMock())
    config["configurable"]["commitment_intake"] = intake
    with patch(
        "ze_core.orchestration.nodes.memory.submit_perception_facts",
        new_callable=AsyncMock,
    ) as submit:
        out = await write_memory(_state(trace, **kw), config)
    return out, submit, config


async def test_intake_replaces_fact_extractor_and_makes_one_call():
    intake = AsyncMock(return_value=_intake_admission())
    extractor = AsyncMock()
    out, submit, _ = await _run_intake(intake, _trace(), extractor=extractor)
    intake.assert_awaited_once()
    extractor.assert_not_awaited()
    facts = [i.fact for i in submit.await_args.args[1]]
    assert [(f.predicate, f.value) for f in facts] == [("preference", "aisle seats")]


async def test_intake_receives_turn_inputs():
    call = ToolCall(
        tool_name="set_reminder",
        args={},
        result={"id": "r1"},
        duration_ms=1,
        success=True,
    )
    intake = AsyncMock(return_value=_intake_admission())
    await _run_intake(intake, _trace(), tool_calls=[call])
    kwargs = intake.await_args.kwargs
    assert kwargs["prompt"] == "I prefer aisle seats"
    assert kwargs["response"] == "Noted."
    assert kwargs["agent"] == "companion"
    assert kwargs["tool_calls"] == [call]


async def test_intake_rows_come_from_the_single_judgment():
    out, _, _ = await _run_intake(AsyncMock(return_value=_intake_admission()), _trace())
    rows = out["message_trace"].judgments
    assert [r.question_id for r in rows] == ["family", "biography"] or {
        r.question_id for r in rows
    } == set(_INTAKE_KINDS)
    consumed = {r.question_id for r in rows if r.consumed}
    assert consumed == {"family", "biography"}


async def test_intake_skip_rows_carry_reason():
    skip = SystemOneResult(outcome="skip", skip_reason="timeout", latency_ms=2000)
    adm = _intake_admission(
        fact=FactAdmission(facts=[], path="haiku"),
        judgment=make_judgment(
            "commitment_intake", skip, _INTAKE_KINDS, skip_reason="timeout"
        ),
    )
    out, _, _ = await _run_intake(AsyncMock(return_value=adm), _trace())
    rows = out["message_trace"].judgments
    assert {r.question_id for r in rows} == set(_INTAKE_KINDS)
    assert all(r.skip_reason == "timeout" and not r.consumed for r in rows)


async def test_intake_failure_never_fails_the_turn():
    intake = AsyncMock(side_effect=RuntimeError("boom"))
    out, submit, _ = await _run_intake(intake, _trace())
    assert "message_trace" not in out
    submit.assert_not_awaited()


async def test_loop_commit_runs_once_from_intake():
    commit = AsyncMock()
    loop = MagicMock()
    loop.commit = commit
    adm = _intake_admission(loop=loop, fact=FactAdmission(facts=[], path="system_one"))
    with patch("ze_core.orchestration.nodes.memory.fire_and_forget") as ff:
        ff.side_effect = lambda coro, label: coro.close() or MagicMock()
        await _run_intake(AsyncMock(return_value=adm), _trace())
    labels = [c.kwargs["label"] for c in ff.call_args_list]
    assert labels.count("loop_commit") == 1


async def test_intake_not_run_for_eval_threads():
    intake = AsyncMock()
    config = _config(AsyncMock(), thread_id="eval-1")
    config["configurable"]["commitment_intake"] = intake
    await write_memory(_state(_trace()), config)
    intake.assert_not_awaited()


async def test_outcome_row_shows_link_and_waiting_on():
    from ze_worldstate.commitment_judge import IntakeOutcome

    for outcome, expected in (
        (
            IntakeOutcome("link", "turn_created", link_kind="reminder"),
            "link:turn_created:reminder",
        ),
        (IntakeOutcome("hold", "waiting_on"), "hold:waiting_on"),
    ):
        adm = _intake_admission(outcome=outcome)
        out, _, _ = await _run_intake(AsyncMock(return_value=adm), _trace())
        row = out["message_trace"].judgments[-1]
        assert (row.question_id, row.answer, row.consumed) == (
            "intake_outcome",
            expected,
            True,
        )


async def test_no_outcome_row_without_a_request():
    from ze_worldstate.commitment_judge import IntakeOutcome

    adm = _intake_admission(outcome=IntakeOutcome("hold", "trivial"), judgment=None)
    out, _, _ = await _run_intake(AsyncMock(return_value=adm), _trace())
    assert "message_trace" not in out
