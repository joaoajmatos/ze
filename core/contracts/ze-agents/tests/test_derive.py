from __future__ import annotations

from unittest.mock import MagicMock

from ze_agents.derive import (
    RuntimeHandles,
    for_action,
    for_delegate,
    for_subtask,
    for_unattended,
    outcome_of,
)
from ze_agents.park import ParkedLoop
from ze_agents.types import (
    AgentContext,
    ConductorState,
    DelegateTally,
    ProcedureInvocation,
    WriteGateState,
)


def _turn(**kw) -> AgentContext:
    base = dict(
        session_id="s1",
        prompt="turn prompt",
        memory=object(),
        contacts=object(),
        persona={"humor": 3},
        timezone="Europe/Lisbon",
        extensions={"user_message_id": "m1"},
        screen_context_note="screen",
        preset_note="preset",
        resume_recap="recap",
        open_priorities_note="open",
        preset="slipping",
        active_skills=["skill"],
        skill_tool_names=["a"],
        procedure_guidance="guide",
        procedure_matches=["m"],
        memory_store=object(),
        embed_fn=lambda t: t,
        reporter=MagicMock(),
        identity_builder=MagicMock(),
        abort_token=MagicMock(),
        tool_sink=MagicMock(),
        script_runner=MagicMock(),
        token_sink=MagicMock(),
        write_gate=WriteGateState(
            retry_mode=True,
            pre_approved=frozenset({"w"}),
            decisions={},
            round=2,
            approval_request_id="req",
            loop_active=True,
        ),
        conductor=ConductorState(
            hint=[{"agent": "a", "prompt": "p"}],
            ledger=[{"agent": "a", "status": "planned"}],
            deadline=123.0,
            stalls={"a": "x"},
        ),
    )
    base.update(kw)
    return AgentContext(**base)


def _subtask(turn: AgentContext, **kw) -> AgentContext:
    args = dict(
        prompt="sub prompt",
        model="m/x",
        messages=[{"role": "user", "content": "sub prompt"}],
        runtime=RuntimeHandles(),
        gate=WriteGateState(),
        conductor=ConductorState(),
        procedure=None,
    )
    args.update(kw)
    return for_subtask(turn, **args)


class TestForSubtask:
    def test_inherits_the_turn_facts(self) -> None:
        turn = _turn()
        ctx = _subtask(turn)
        assert ctx.timezone == "Europe/Lisbon"
        assert ctx.extensions == {"user_message_id": "m1"}
        assert ctx.memory is turn.memory and ctx.persona is turn.persona
        assert ctx.memory_store is turn.memory_store
        for name in (
            "screen_context_note",
            "preset_note",
            "resume_recap",
            "open_priorities_note",
            "preset",
            "active_skills",
            "skill_tool_names",
            "procedure_guidance",
            "procedure_matches",
        ):
            assert getattr(ctx, name) == getattr(turn, name), name

    def test_extensions_are_a_copy(self) -> None:
        turn = _turn()
        ctx = _subtask(turn)
        ctx.extensions["goal"] = "x"
        assert "goal" not in turn.extensions

    def test_takes_run_inputs_from_its_arguments(self) -> None:
        sink = MagicMock()
        gate = WriteGateState(round=1)
        conductor = ConductorState(ledger=[{"agent": "b", "status": "x"}])
        proc = ProcedureInvocation("i", "p", "v")
        ctx = _subtask(
            _turn(),
            runtime=RuntimeHandles(token_sink=sink),
            gate=gate,
            conductor=conductor,
            procedure=proc,
        )
        assert ctx.prompt == "sub prompt" and ctx.model == "m/x"
        assert ctx.token_sink is sink
        assert ctx.write_gate.round == 1
        assert ctx.conductor.ledger == [{"agent": "b", "status": "x"}]
        assert ctx.procedure_invocation is proc
        assert ctx.reporter is None  # the turn's handle is not inherited

    def test_loop_active_starts_false(self) -> None:
        ctx = _subtask(_turn(), gate=WriteGateState(loop_active=True))
        assert ctx.write_gate.loop_active is False

    def test_fresh_run_lists(self) -> None:
        turn = _turn()
        ctx = _subtask(turn)
        assert ctx.tool_calls == [] and ctx.sources == []


class TestForDelegate:
    def test_inherits_time_extensions_and_handles(self) -> None:
        caller = _turn()
        ctx = for_delegate(caller, prompt="brief", resume=None)
        assert ctx.timezone == "Europe/Lisbon"
        assert ctx.extensions == {"user_message_id": "m1", "_delegate_depth": 1}
        assert caller.extensions == {"user_message_id": "m1"}
        assert ctx.embed_fn is caller.embed_fn
        assert ctx.memory_store is caller.memory_store
        for name in (
            "reporter",
            "identity_builder",
            "abort_token",
            "tool_sink",
            "script_runner",
        ):
            assert getattr(ctx, name) is getattr(caller, name), name
        assert ctx.messages == [{"role": "user", "content": "brief"}]
        assert ctx.prompt == "brief" and ctx.model is None

    def test_depth_grows_from_the_caller(self) -> None:
        caller = _turn(extensions={"_delegate_depth": 1})
        ctx = for_delegate(caller, prompt="b", resume=None)
        assert ctx.extensions["_delegate_depth"] == 2

    def test_resets_what_a_delegate_must_not_inherit(self) -> None:
        ctx = for_delegate(_turn(), prompt="b", resume=None)
        assert ctx.token_sink is None
        for name in (
            "screen_context_note",
            "preset_note",
            "resume_recap",
            "open_priorities_note",
            "preset",
            "procedure_guidance",
            "procedure_matches",
            "skill_tool_names",
        ):
            assert getattr(ctx, name) is None, name
        assert ctx.active_skills == []
        assert ctx.procedure_invocation is None
        assert ctx.conductor.deadline is None and ctx.conductor.hint is None
        assert ctx.conductor.ledger == [] and ctx.conductor.stalls == {}

    def test_write_gate_is_inherited_with_the_resume_argument(self) -> None:
        loop = MagicMock(spec=ParkedLoop)
        ctx = for_delegate(_turn(), prompt="b", resume=loop)
        gate = ctx.write_gate
        assert gate.retry_mode is True
        assert gate.pre_approved == frozenset({"w"})
        assert gate.round == 2 and gate.approval_request_id == "req"
        assert gate.resume is loop
        assert gate.loop_active is False


class TestForUnattended:
    def test_gives_only_the_milestone_inputs(self) -> None:
        store = object()
        ctx = for_unattended(
            session_id="goal:1",
            prompt="do it",
            timezone="Europe/Lisbon",
            memory_store=store,
            extensions={"goal_id": "1"},
            pre_approved=frozenset({"w"}),
        )
        assert ctx.session_id == "goal:1" and ctx.prompt == "do it"
        assert ctx.timezone == "Europe/Lisbon" and ctx.memory_store is store
        assert ctx.extensions == {"goal_id": "1"}
        assert ctx.write_gate.pre_approved == frozenset({"w"})
        assert ctx.write_gate.retry_mode is False
        assert ctx.screen_context_note is None and ctx.token_sink is None
        assert ctx.reporter is None and ctx.embed_fn is None

    def test_keeps_a_held_resume_but_never_retry(self) -> None:
        held = WriteGateState(approval_request_id="r", round=1, retry_mode=True)
        ctx = for_unattended(
            session_id="goal:1",
            prompt="p",
            timezone="UTC",
            memory_store=None,
            extensions={},
            pre_approved=frozenset({"w"}),
            resume=held,
        )
        assert ctx.write_gate.approval_request_id == "r" and ctx.write_gate.round == 1
        assert ctx.write_gate.retry_mode is False
        assert ctx.write_gate.pre_approved == frozenset({"w"})


class TestForAction:
    def test_sets_only_the_session_id(self) -> None:
        ctx = for_action("t1")
        assert ctx == AgentContext(session_id="t1", prompt="")
        assert ctx.write_gate.retry_mode is False


class TestOutcomeOf:
    def test_stamps_the_subtask_and_keeps_the_shared_tally(self) -> None:
        tally = DelegateTally(counts={"a": 1}, total=1)
        ctx = _subtask(
            _turn(),
            conductor=ConductorState(ledger=[{"agent": "a", "status": "done"}], tally=tally),
            procedure=ProcedureInvocation("i", "p", "v"),
        )
        outcome = outcome_of(ctx, 3)
        assert outcome.index == 3
        assert outcome.conductor.tally is tally
        assert outcome.procedure is not None and outcome.procedure.subtask == 3
        assert outcome.conductor.ledger == ctx.conductor.ledger
        assert outcome.conductor.ledger is not ctx.conductor.ledger

    def test_no_procedure_means_none(self) -> None:
        assert outcome_of(_subtask(_turn()), 0).procedure is None
