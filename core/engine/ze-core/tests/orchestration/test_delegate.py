"""Tests for delegate_to_agent built-in harness tool."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from ze_agents.types import GateDecision
from ze_agents.errors import AgentAbortedError
from ze_agents.registry import agent, clear_registry, register_instance
from ze_agents.base_agent import BaseAgent
from ze_agents.delegate import (
    DELEGATE_TOOL_NAME,
    DELEGATE_TOOL_SCHEMA,
    _DELEGATE_MAX_DEPTH,
    run_delegate,
)
from ze_agents.interrupt import tool_interrupt_fn
from ze_agents.tool import clear_tool_registry
from ze_agents.types import AbortToken, AgentContext, AgentResult, ToolCall

_CALLER = "companion"


async def _eval_execute(_agent: str, _intent: str) -> GateDecision:
    return GateDecision.EXECUTE


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    yield
    clear_registry()
    clear_tool_registry()


def _ctx(
    depth: int = 0,
    gate_decision: GateDecision = GateDecision.EXECUTE,
    abort_token: AbortToken | None = None,
    intent: str = "reason",
    evaluate_delegate=None,
) -> AgentContext:
    extensions = {"_delegate_depth": depth} if depth else {}
    return AgentContext(
        session_id="s1",
        prompt="hello",
        intent=intent,
        gate_decision=gate_decision,
        extensions=extensions,
        abort_token=abort_token,
        evaluate_delegate=evaluate_delegate or _eval_execute,
    )


async def _run(arguments: dict, ctx: AgentContext | None = None, caller: str = _CALLER):
    return await run_delegate(arguments, ctx or _ctx(), iteration=0, caller_name=caller)


def _make_agent(agent_name: str, response: str = "agent response") -> BaseAgent:
    async def _run_impl(self, ctx: AgentContext) -> AgentResult:
        return AgentResult(agent=agent_name, response=response)

    cls = type(
        f"_Agent_{agent_name}",
        (BaseAgent,),
        {
            "name": agent_name,
            "description": f"{agent_name} agent",
            "tools": [],
            "run": _run_impl,
        },
    )
    agent(cls)
    instance = cls()
    register_instance(agent_name, instance)
    return instance


# ── DELEGATE_TOOL_SCHEMA ─────────────────────────────────────────────────────


class TestDelegateToolSchema:
    def test_schema_has_correct_name(self):
        assert DELEGATE_TOOL_SCHEMA["function"]["name"] == DELEGATE_TOOL_NAME

    def test_schema_requires_agent_name_and_objective(self):
        required = DELEGATE_TOOL_SCHEMA["function"]["parameters"]["required"]
        assert required == ["agent_name", "objective"]

    def test_schema_omits_task_and_context(self):
        props = DELEGATE_TOOL_SCHEMA["function"]["parameters"]["properties"]
        assert "task" not in props
        assert "context" not in props

    def test_schema_optional_fat_fields(self):
        props = DELEGATE_TOOL_SCHEMA["function"]["parameters"]["properties"]
        required = DELEGATE_TOOL_SCHEMA["function"]["parameters"]["required"]
        for name in (
            "prior_outputs",
            "inputs",
            "output_shape",
            "stop_condition",
            "intent",
        ):
            assert name in props
            assert name not in required

    def test_schema_has_description(self):
        assert len(DELEGATE_TOOL_SCHEMA["function"]["description"]) > 10

    def test_max_depth_is_one(self):
        assert _DELEGATE_MAX_DEPTH == 1


# ── run_delegate ──────────────────────────────────────────────────────────────


class TestRunDelegate:
    async def test_delegates_to_named_agent(self):
        _make_agent("calendar", response="you have 3 events")

        tc = await _run({"agent_name": "calendar", "objective": "list my events"})

        assert tc.success is True
        assert tc.result == {
            "response": "you have 3 events",
            "tool_calls": [],
        }
        assert tc.tool_name == DELEGATE_TOOL_NAME

    async def test_emits_conductor_progress_calendar_then_mail(self):
        _make_agent("calendar", response="tue")
        _make_agent("messenger", response="drafted")
        reporter = AsyncMock()
        ctx = _ctx()
        ctx.reporter = reporter
        await _run({"agent_name": "calendar", "objective": "list tuesday"}, ctx)
        await _run({"agent_name": "messenger", "objective": "draft mail"}, ctx)
        keys = [c.args[0] for c in reporter.emit.await_args_list]
        assert keys == ["conductor.checking_calendar", "conductor.drafting_mail"]

    async def test_ledger_marks_done_on_success(self):
        _make_agent("calendar", response="ok")
        ctx = _ctx()
        ctx.conductor_ledger = [{"agent": "calendar", "status": "planned"}]
        await _run({"agent_name": "calendar", "objective": "list"}, ctx)
        assert ctx.conductor_ledger[-1]["status"] == "done"
        assert ctx.conductor_ledger[-1]["agent"] == "calendar"

    async def test_nested_cancel_payload_is_visible(self):
        @agent
        class _R(BaseAgent):
            name = "reminders"
            description = "reminders"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                nested = ToolCall(
                    tool_name="cancel_reminder",
                    args={"reminder_id": "r1"},
                    result={"cancelled": "Call the dentist"},
                    duration_ms=1,
                    success=True,
                )
                return AgentResult(
                    agent="reminders",
                    response="Cancelled the dentist reminder.",
                    tool_calls=[nested],
                )

        register_instance("reminders", _R())
        tc = await _run({"agent_name": "reminders", "objective": "forget the dentist"})
        assert tc.success is True
        assert isinstance(tc.result, dict)
        assert tc.result["response"] == "Cancelled the dentist reminder."
        assert tc.result["tool_calls"][0]["tool_name"] == "cancel_reminder"
        assert tc.result["tool_calls"][0]["result"]["cancelled"] == "Call the dentist"

    async def test_fat_fields_appear_in_worker_prompt(self):
        received = {}

        @agent
        class _E(BaseAgent):
            name = "echo_agent"
            description = "echo"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                received["prompt"] = ctx.prompt
                received["messages"] = ctx.messages
                return AgentResult(agent="echo_agent", response="ok")

        register_instance("echo_agent", _E())

        await _run(
            {
                "agent_name": "echo_agent",
                "objective": "do X",
                "prior_outputs": "event-42",
                "inputs": "recipient bob@example.com",
                "output_shape": "one sentence",
                "stop_condition": "do not send",
            }
        )

        prompt = received["prompt"]
        assert "Objective: do X" in prompt
        assert "Prior outputs: event-42" in prompt
        assert "Inputs: recipient bob@example.com" in prompt
        assert "Output shape: one sentence" in prompt
        assert "Stop: do not send" in prompt
        assert received["messages"] == [{"role": "user", "content": prompt}]

    async def test_omitted_optionals_do_not_appear_in_prompt(self):
        received = {}

        @agent
        class _B(BaseAgent):
            name = "bare_agent"
            description = "bare"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                received["prompt"] = ctx.prompt
                return AgentResult(agent="bare_agent", response="ok")

        register_instance("bare_agent", _B())

        await _run({"agent_name": "bare_agent", "objective": "just this"})

        assert received["prompt"] == "Objective: just this"
        assert "Prior outputs:" not in received["prompt"]
        assert "Inputs:" not in received["prompt"]
        assert "Output shape:" not in received["prompt"]
        assert "Stop:" not in received["prompt"]

    async def test_worker_messages_stay_off_parent_context(self):
        parent = _ctx()
        parent.messages = [{"role": "user", "content": "parent turn"}]
        _make_agent("iso_agent", response="ok")
        await _run({"agent_name": "iso_agent", "objective": "work"}, parent)
        assert parent.messages == [{"role": "user", "content": "parent turn"}]

    async def test_empty_objective_fails_without_run(self):
        ran = {"n": 0}

        @agent
        class _E(BaseAgent):
            name = "empty_obj"
            description = "empty"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                ran["n"] += 1
                return AgentResult(agent="empty_obj", response="ok")

        register_instance("empty_obj", _E())
        tc = await _run({"agent_name": "empty_obj", "objective": "  "})
        assert tc.success is False
        assert ran["n"] == 0

    async def test_evaluator_sets_gate_not_parent_copy(self):
        received = {}

        async def _eval(_agent: str, _intent: str) -> GateDecision:
            return GateDecision.DRAFT

        @agent
        class _G(BaseAgent):
            name = "gate_agent"
            description = "gate"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                received["gate"] = ctx.gate_decision
                return AgentResult(agent="gate_agent", response="ok")

        register_instance("gate_agent", _G())

        await _run(
            {"agent_name": "gate_agent", "objective": "t"},
            _ctx(gate_decision=GateDecision.EXECUTE, evaluate_delegate=_eval),
        )

        assert received["gate"] == GateDecision.DRAFT

    async def test_inherits_abort_token(self):
        received = {}
        token = AbortToken()

        @agent
        class _T(BaseAgent):
            name = "token_agent"
            description = "token"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                received["token"] = ctx.abort_token
                return AgentResult(agent="token_agent", response="ok")

        register_instance("token_agent", _T())

        await _run(
            {"agent_name": "token_agent", "objective": "t"},
            _ctx(abort_token=token),
        )

        assert received["token"] is token

    async def test_depth_incremented_in_sub_ctx(self):
        received = {}

        @agent
        class _D(BaseAgent):
            name = "depth_agent"
            description = "depth"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                received["depth"] = ctx.extensions.get("_delegate_depth", 0)
                return AgentResult(agent="depth_agent", response="ok")

        register_instance("depth_agent", _D())

        await _run({"agent_name": "depth_agent", "objective": "t"}, _ctx(depth=0))

        assert received["depth"] == 1

    async def test_depth_limit_returns_error_toolcall(self):
        ran = {"n": 0}

        @agent
        class _Deep(BaseAgent):
            name = "deep_agent"
            description = "deep"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                ran["n"] += 1
                return AgentResult(agent="deep_agent", response="ok")

        register_instance("deep_agent", _Deep())

        tc = await _run(
            {"agent_name": "deep_agent", "objective": "t"},
            _ctx(depth=_DELEGATE_MAX_DEPTH),
        )

        assert tc.success is False
        assert "depth" in tc.error
        assert ran["n"] == 0

    async def test_non_companion_caller_fails_without_run(self):
        ran = {"n": 0}

        @agent
        class _C(BaseAgent):
            name = "calendar"
            description = "cal"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                ran["n"] += 1
                return AgentResult(agent="calendar", response="ok")

        register_instance("calendar", _C())
        tc = await _run(
            {"agent_name": "calendar", "objective": "list events"},
            caller="research",
        )
        assert tc.success is False
        assert ran["n"] == 0

    async def test_target_companion_fails_without_run(self):
        ran = {"n": 0}

        @agent
        class _Comp(BaseAgent):
            name = "companion"
            description = "companion"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                ran["n"] += 1
                return AgentResult(agent="companion", response="ok")

        register_instance("companion", _Comp())
        tc = await _run({"agent_name": "companion", "objective": "talk"})
        assert tc.success is False
        assert ran["n"] == 0

    async def test_unknown_agent_returns_error_toolcall(self):
        tc = await _run({"agent_name": "nonexistent", "objective": "t"})

        assert tc.success is False
        assert tc.error is not None

    async def test_agent_exception_returns_error_toolcall(self):
        @agent
        class _C(BaseAgent):
            name = "crash_agent"
            description = "crash"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                raise RuntimeError("agent exploded")

        register_instance("crash_agent", _C())

        tc = await _run({"agent_name": "crash_agent", "objective": "t"})

        assert tc.success is False
        assert "agent exploded" in tc.error

    async def test_agent_aborted_error_propagates(self):
        @agent
        class _A(BaseAgent):
            name = "aborting_agent"
            description = "aborts"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                raise AgentAbortedError("sub aborted")

        register_instance("aborting_agent", _A())

        with pytest.raises(AgentAbortedError, match="sub aborted"):
            await _run({"agent_name": "aborting_agent", "objective": "t"})

    async def test_shared_abort_token_propagates_through_loop(self):
        token = AbortToken()

        @agent
        class _Sub(BaseAgent):
            name = "token_aborting_agent"
            description = "aborts via token"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                raise AgentAbortedError("token fired")

        register_instance("token_aborting_agent", _Sub())

        @agent
        class _Parent(BaseAgent):
            name = "companion"
            description = "delegates"
            tools = [DELEGATE_TOOL_NAME]

            async def run(self, ctx: AgentContext) -> AgentResult:
                return AgentResult(agent="companion", response="ok")

        register_instance("companion", _Parent())

        client = MagicMock()
        client.complete_with_tools = AsyncMock(
            side_effect=[
                (
                    None,
                    [
                        {
                            "id": "d1",
                            "name": DELEGATE_TOOL_NAME,
                            "arguments": {
                                "agent_name": "token_aborting_agent",
                                "objective": "t",
                            },
                        }
                    ],
                ),
            ]
        )
        client.complete = AsyncMock(return_value="fallback")

        parent = _Parent()
        ctx = AgentContext(
            session_id="s1",
            prompt="q",
            intent="reason",
            abort_token=token,
            evaluate_delegate=_eval_execute,
        )

        with pytest.raises(AgentAbortedError):
            await parent.agentic_loop(
                ctx, client, [{"role": "user", "content": "q"}], system="s"
            )


# ── delegate in agentic_loop ─────────────────────────────────────────────────


class TestDelegateInAgenticLoop:
    def _client(self, responses):
        client = MagicMock()
        client.complete_with_tools = AsyncMock(side_effect=responses)
        client.complete = AsyncMock(return_value="fallback")
        return client

    def _loop_agent(self, agent_name: str = "companion") -> BaseAgent:
        async def _run(self, ctx: AgentContext) -> AgentResult:
            return AgentResult(agent=agent_name, response="ok")

        cls = type(
            f"_Loop_{agent_name}",
            (BaseAgent,),
            {
                "name": agent_name,
                "description": "loop",
                "tools": [DELEGATE_TOOL_NAME],
                "run": _run,
            },
        )
        agent(cls)
        instance = cls()
        register_instance(agent_name, instance)
        return instance

    async def test_delegate_schema_included_when_tool_listed(self):
        a = self._loop_agent()
        captured_schemas = []

        async def _capture(messages, model, tools, system, max_tokens):
            captured_schemas.extend(tools)
            return ("done", None)

        client = MagicMock()
        client.complete_with_tools = AsyncMock(side_effect=_capture)
        messages = [{"role": "user", "content": "q"}]
        ctx = AgentContext(session_id="s1", prompt="q", intent="reason")

        await a.agentic_loop(ctx, client, messages, system="s")

        names = [s["function"]["name"] for s in captured_schemas]
        assert DELEGATE_TOOL_NAME in names

    async def test_loop_calls_delegate_when_llm_requests(self):
        _make_agent("target_agent", response="target result")
        a = self._loop_agent()

        client = self._client(
            [
                (
                    None,
                    [
                        {
                            "id": "d1",
                            "name": DELEGATE_TOOL_NAME,
                            "arguments": {
                                "agent_name": "target_agent",
                                "objective": "sub task",
                            },
                        }
                    ],
                ),
                ("final answer", None),
            ]
        )
        ctx = AgentContext(
            session_id="s1",
            prompt="q",
            intent="reason",
            evaluate_delegate=_eval_execute,
        )
        messages = [{"role": "user", "content": "q"}]

        text, calls = await a.agentic_loop(ctx, client, messages, system="s")

        assert text == "final answer"
        assert len(calls) == 1
        assert calls[0].tool_name == DELEGATE_TOOL_NAME
        assert calls[0].success is True
        assert calls[0].result == {"response": "target result", "tool_calls": []}

    async def test_non_companion_loop_delegate_fails_closed(self):
        ran = {"n": 0}

        @agent
        class _T(BaseAgent):
            name = "target_agent"
            description = "target"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                ran["n"] += 1
                return AgentResult(agent="target_agent", response="nope")

        register_instance("target_agent", _T())
        a = self._loop_agent(agent_name="research")

        client = self._client(
            [
                (
                    None,
                    [
                        {
                            "id": "d1",
                            "name": DELEGATE_TOOL_NAME,
                            "arguments": {
                                "agent_name": "target_agent",
                                "objective": "sub task",
                            },
                        }
                    ],
                ),
                ("I cannot delegate.", None),
            ]
        )
        ctx = AgentContext(session_id="s1", prompt="q", intent="read")
        text, calls = await a.agentic_loop(
            ctx, client, [{"role": "user", "content": "q"}], system="s"
        )

        assert text == "I cannot delegate."
        assert calls[0].success is False
        assert ran["n"] == 0


class TestPerDelegateGate:
    async def test_lookup_runs_write_does_not_until_confirm(self):
        order: list[str] = []

        @agent
        class _Cal(BaseAgent):
            name = "calendar"
            description = "calendar"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                order.append("calendar")
                return AgentResult(agent="calendar", response="tue 3pm")

        @agent
        class _Mail(BaseAgent):
            name = "messenger"
            description = "mail"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                order.append("messenger")
                return AgentResult(agent="messenger", response="sent")

        register_instance("calendar", _Cal())
        register_instance("messenger", _Mail())

        async def _eval(agent: str, intent: str) -> GateDecision:
            if agent == "calendar":
                return GateDecision.EXECUTE
            return GateDecision.AWAIT_CONFIRMATION

        ctx = _ctx(evaluate_delegate=_eval)
        cal = await _run({"agent_name": "calendar", "objective": "what's Tuesday"}, ctx)
        assert cal.success is True
        assert order == ["calendar"]

        mail = await _run({"agent_name": "messenger", "objective": "email Bob"}, ctx)
        assert mail.success is False
        assert "interrupt" in (mail.error or "")
        assert order == ["calendar"]

    async def test_await_runs_once_after_approve(self):
        ran = {"n": 0}

        @agent
        class _W(BaseAgent):
            name = "calendar"
            description = "cal"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                ran["n"] += 1
                assert ctx.gate_decision == GateDecision.EXECUTE
                return AgentResult(agent="calendar", response="created")

        register_instance("calendar", _W())

        async def _eval(_a: str, _i: str) -> GateDecision:
            return GateDecision.AWAIT_CONFIRMATION

        seen = {}

        def _interrupt(payload: dict) -> dict:
            seen["payload"] = payload
            assert ran["n"] == 0
            return {"choice": "approve"}

        token = tool_interrupt_fn.set(_interrupt)
        try:
            tc = await _run(
                {"agent_name": "calendar", "objective": "create event"},
                _ctx(evaluate_delegate=_eval),
            )
        finally:
            tool_interrupt_fn.reset(token)

        assert tc.success is True
        assert ran["n"] == 1
        assert seen["payload"]["kind"] == "delegate"
        assert seen["payload"]["request_id"]

    async def test_deny_does_not_run_worker(self):
        ran = {"n": 0}

        @agent
        class _W(BaseAgent):
            name = "calendar"
            description = "cal"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                ran["n"] += 1
                return AgentResult(agent="calendar", response="created")

        register_instance("calendar", _W())

        async def _eval(_a: str, _i: str) -> GateDecision:
            return GateDecision.AWAIT_CONFIRMATION

        token = tool_interrupt_fn.set(lambda _p: {"choice": "deny"})
        try:
            tc = await _run(
                {"agent_name": "calendar", "objective": "create event"},
                _ctx(evaluate_delegate=_eval),
            )
        finally:
            tool_interrupt_fn.reset(token)

        assert tc.success is False
        assert "denied" in (tc.error or "")
        assert ran["n"] == 0

    async def test_blocked_fails_without_run(self):
        ran = {"n": 0}

        @agent
        class _W(BaseAgent):
            name = "calendar"
            description = "cal"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                ran["n"] += 1
                return AgentResult(agent="calendar", response="nope")

        register_instance("calendar", _W())

        async def _eval(_a: str, _i: str) -> GateDecision:
            return GateDecision.BLOCKED

        tc = await _run(
            {"agent_name": "calendar", "objective": "x"},
            _ctx(evaluate_delegate=_eval),
        )
        assert tc.success is False
        assert ran["n"] == 0

    async def test_declared_intent_is_passed_to_evaluator(self):
        seen = {}

        async def _eval(agent: str, intent: str) -> GateDecision:
            seen["agent"] = agent
            seen["intent"] = intent
            if intent == "create":
                return GateDecision.DRAFT
            return GateDecision.EXECUTE

        received = {}

        @agent
        class _C(BaseAgent):
            name = "calendar"
            description = "cal"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                received["gate"] = ctx.gate_decision
                return AgentResult(agent="calendar", response="ok")

        register_instance("calendar", _C())

        await _run(
            {"agent_name": "calendar", "objective": "look", "intent": "read"},
            _ctx(evaluate_delegate=_eval),
        )
        assert seen["intent"] == "read"
        assert received["gate"] == GateDecision.EXECUTE

        await _run(
            {"agent_name": "calendar", "objective": "make", "intent": "create"},
            _ctx(evaluate_delegate=_eval),
        )
        assert seen["intent"] == "create"
        assert received["gate"] == GateDecision.DRAFT

    async def test_omitted_intent_still_runs(self):
        seen = {}

        async def _eval(agent: str, intent: str) -> GateDecision:
            seen["intent"] = intent
            return GateDecision.EXECUTE

        _make_agent("reminders", response="set")
        tc = await _run(
            {"agent_name": "reminders", "objective": "remind me at 3"},
            _ctx(evaluate_delegate=_eval),
        )
        assert tc.success is True
        assert seen["intent"] == ""

    async def test_missing_evaluator_fails_without_run(self):
        ran = {"n": 0}

        @agent
        class _C(BaseAgent):
            name = "calendar"
            description = "cal"
            tools = []

            async def run(self, ctx: AgentContext) -> AgentResult:
                ran["n"] += 1
                return AgentResult(agent="calendar", response="ok")

        register_instance("calendar", _C())
        ctx = AgentContext(
            session_id="s1",
            prompt="h",
            intent="reason",
            evaluate_delegate=None,
        )
        tc = await _run({"agent_name": "calendar", "objective": "x"}, ctx)
        assert tc.success is False
        assert ran["n"] == 0
