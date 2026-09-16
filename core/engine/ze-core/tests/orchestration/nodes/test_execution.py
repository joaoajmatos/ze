import asyncio
from unittest.mock import AsyncMock

import pytest

from ze_agents.types import GateDecision
from ze_agents.errors import AgentTimeoutError
from ze_memory.types import MemoryContext
from ze_agents.registry import agent, clear_registry, register_instance
from ze_core.orchestration.nodes.execution import (
    await_confirmation,
    await_subtask_confirmation,
    capability_check,
    draft_response,
    execute_tool,
)
from ze_agents.types import AgentContext, AgentResult
from ze_core.routing.types import RoutingEnvelope, SubTask


@pytest.fixture(autouse=True)
def clean_registry():
    clear_registry()
    yield
    clear_registry()


def _make_agent_class(name: str, response: str = "ok", timeout: int = 30):
    class _A:
        async def run(self, ctx: AgentContext) -> AgentResult:
            return AgentResult(agent=name, response=response)

    _A.__name__ = f"Agent_{name}"
    _A.name = name
    _A.description = f"Agent {name}"
    _A.enabled = True
    _A.timeout = timeout
    return _A


def _register_and_wire(name: str, response: str = "ok", timeout: int = 30):
    cls = _make_agent_class(name, response, timeout)
    agent(cls)
    instance = object.__new__(cls)
    instance.run = cls.run.__get__(instance, cls)
    instance.stream = AsyncMock(side_effect=NotImplementedError)
    register_instance(name, instance)
    return instance


def _envelope(
    agent_name: str,
    intent: str = "read",
    is_compound: bool = False,
    is_sequential: bool = False,
    subtasks: list | None = None,
) -> RoutingEnvelope:
    if subtasks is None:
        subtasks = [SubTask(agent=agent_name, intent=intent, prompt="do it")]
    return RoutingEnvelope(
        primary_agent=agent_name,
        confidence=0.9,
        score_gap=0.3,
        routing_method="embedding",
        is_compound=is_compound,
        subtasks=subtasks,
        requires_synthesis=is_compound and not is_sequential,
        is_sequential=is_sequential,
    )


def _ctx(agent_name: str = "a", intent: str = "read") -> AgentContext:
    return AgentContext(
        session_id="s1",
        prompt="do it",
        intent=intent,
        memory=MemoryContext(),
        messages=[],
    )


def _config(gate=None) -> dict:
    return {
        "configurable": {
            "capability_gate": gate,
            "thread_id": "s1",
        }
    }


# ── capability_check ──────────────────────────────────────────────────────────


class TestCapabilityCheck:
    async def test_execute_decision(self):
        from ze_agents.types import Intent, Mode
        from ze_core.capability import CapabilityGate

        cls = _make_agent_class("alpha")
        cls.intents = {"read": Intent(Mode.AUTONOMOUS)}
        agent(cls)
        register_instance("alpha", object.__new__(cls))
        gate = CapabilityGate()
        state = {"envelope": _envelope("alpha"), "session_overrides": {}}
        result = await capability_check(state, _config(gate))
        assert result["gate_decision"] == GateDecision.EXECUTE

    async def test_no_envelope_returns_blocked(self):
        from ze_core.capability import CapabilityGate

        gate = CapabilityGate()
        state = {"envelope": None, "session_overrides": {}}
        result = await capability_check(state, _config(gate))
        assert result["gate_decision"] == GateDecision.BLOCKED

    async def test_budget_exceeded_downgrades_execute_to_await_confirmation(self):
        from ze_agents.types import Intent, Mode
        from ze_core.capability import CapabilityGate
        from ze_core.telemetry.budget import BudgetStatus

        cls = _make_agent_class("alpha")
        cls.intents = {"read": Intent(Mode.AUTONOMOUS)}
        agent(cls)
        register_instance("alpha", object.__new__(cls))
        gate = CapabilityGate()

        budget_checker = AsyncMock()
        budget_checker.check = AsyncMock(
            return_value=BudgetStatus(
                within_budget=False,
                scope="session",
                current_spend_usd=5.0,
                limit_usd=2.0,
            )
        )

        config = _config(gate)
        config["configurable"]["budget_checker"] = budget_checker
        state = {
            "envelope": _envelope("alpha"),
            "session_overrides": {},
            "session_id": "s1",
        }

        result = await capability_check(state, config)

        assert result["gate_decision"] == GateDecision.AWAIT_CONFIRMATION
        assert result["budget_status"].scope == "session"
        budget_checker.check.assert_awaited_once_with(session_id="s1")

    async def test_no_budget_checker_is_a_regression_noop(self):
        """budget_checker absent from configurable behaves exactly as before (FR-007)."""
        from ze_agents.types import Intent, Mode
        from ze_core.capability import CapabilityGate

        cls = _make_agent_class("alpha")
        cls.intents = {"read": Intent(Mode.AUTONOMOUS)}
        agent(cls)
        register_instance("alpha", object.__new__(cls))
        gate = CapabilityGate()

        state = {
            "envelope": _envelope("alpha"),
            "session_overrides": {},
            "session_id": "s1",
        }
        result = await capability_check(state, _config(gate))

        assert result["gate_decision"] == GateDecision.EXECUTE
        assert "budget_status" not in result

    async def test_compound_mixed_read_write_execute_sibling_not_held(self):
        from ze_agents.types import Intent, Mode
        from ze_core.capability import CapabilityGate

        read_cls = _make_agent_class("calendar")
        read_cls.intents = {"read": Intent(Mode.AUTONOMOUS)}
        write_cls = _make_agent_class("messenger")
        write_cls.intents = {"create": Intent(Mode.CONFIRM)}
        agent(read_cls)
        agent(write_cls)
        register_instance("calendar", object.__new__(read_cls))
        register_instance("messenger", object.__new__(write_cls))
        gate = CapabilityGate()
        env = _envelope(
            "calendar",
            is_compound=True,
            subtasks=[
                SubTask(agent="calendar", intent="read", prompt="tue"),
                SubTask(agent="messenger", intent="create", prompt="mail"),
            ],
        )
        state = {"envelope": env, "session_overrides": {}}
        result = await capability_check(state, _config(gate))
        by_agent = {
            row["agent"]: row["decision"] for row in result["subtask_gate_decisions"]
        }
        assert by_agent["calendar"] == GateDecision.EXECUTE
        assert by_agent["messenger"] == GateDecision.AWAIT_CONFIRMATION
        assert result["gate_decision"] != GateDecision.AWAIT_CONFIRMATION

    async def test_compound_all_execute_independent_reads(self):
        from ze_agents.types import Intent, Mode
        from ze_core.capability import CapabilityGate

        news_cls = _make_agent_class("news")
        news_cls.intents = {"read": Intent(Mode.AUTONOMOUS)}
        research_cls = _make_agent_class("research")
        research_cls.intents = {"read": Intent(Mode.AUTONOMOUS)}
        agent(news_cls)
        agent(research_cls)
        register_instance("news", object.__new__(news_cls))
        register_instance("research", object.__new__(research_cls))
        gate = CapabilityGate()
        env = _envelope(
            "news",
            is_compound=True,
            subtasks=[
                SubTask(agent="news", intent="read", prompt="headlines"),
                SubTask(agent="research", intent="read", prompt="notes"),
            ],
        )
        result = await capability_check(
            {"envelope": env, "session_overrides": {}}, _config(gate)
        )
        decisions = [row["decision"] for row in result["subtask_gate_decisions"]]
        assert decisions == [GateDecision.EXECUTE, GateDecision.EXECUTE]
        assert result["gate_decision"] != GateDecision.BLOCKED

    async def test_compound_all_blocked_still_blocks(self):
        from ze_agents.types import Intent, Mode
        from ze_core.capability import CapabilityGate

        alpha_cls = _make_agent_class("alpha")
        alpha_cls.intents = {"read": Intent(Mode.DISABLED)}
        beta_cls = _make_agent_class("beta")
        beta_cls.intents = {"read": Intent(Mode.DISABLED)}
        agent(alpha_cls)
        agent(beta_cls)
        register_instance("alpha", object.__new__(alpha_cls))
        register_instance("beta", object.__new__(beta_cls))
        gate = CapabilityGate()
        env = _envelope(
            "alpha",
            is_compound=True,
            subtasks=[
                SubTask(agent="alpha", intent="read", prompt="p1"),
                SubTask(agent="beta", intent="read", prompt="p2"),
            ],
        )
        result = await capability_check(
            {"envelope": env, "session_overrides": {}}, _config(gate)
        )
        assert result["gate_decision"] == GateDecision.BLOCKED
        assert all(
            row["decision"] == GateDecision.BLOCKED
            for row in result["subtask_gate_decisions"]
        )

    async def test_bind_delegate_evaluator_budget_holds_execute(self):
        from ze_agents.types import Intent, Mode
        from ze_core.capability import CapabilityGate
        from ze_core.orchestration.nodes.execution import bind_delegate_evaluator
        from ze_core.telemetry.budget import BudgetStatus

        cls = _make_agent_class("calendar")
        cls.intents = {"read": Intent(Mode.AUTONOMOUS)}
        agent(cls)
        register_instance("calendar", object.__new__(cls))
        gate = CapabilityGate()
        budget_checker = AsyncMock()
        budget_checker.check = AsyncMock(
            return_value=BudgetStatus(
                within_budget=False,
                scope="session",
                current_spend_usd=5.0,
                limit_usd=2.0,
            )
        )
        ctx = _ctx("calendar")
        config = _config(gate)
        config["configurable"]["budget_checker"] = budget_checker
        bind_delegate_evaluator(
            ctx, config, {"session_id": "s1", "session_overrides": {}}
        )
        decision = await ctx.evaluate_delegate("calendar", "read")
        assert decision == GateDecision.AWAIT_CONFIRMATION

    async def test_compound_budget_overage_composes_per_subtask(self):
        from ze_agents.types import Intent, Mode
        from ze_core.capability import CapabilityGate
        from ze_core.telemetry.budget import BudgetStatus

        read_cls = _make_agent_class("calendar")
        read_cls.intents = {"read": Intent(Mode.AUTONOMOUS)}
        draft_cls = _make_agent_class("messenger")
        draft_cls.intents = {"create": Intent(Mode.DRAFT_ONLY)}
        agent(read_cls)
        agent(draft_cls)
        register_instance("calendar", object.__new__(read_cls))
        register_instance("messenger", object.__new__(draft_cls))
        gate = CapabilityGate()
        budget_checker = AsyncMock()
        budget_checker.check = AsyncMock(
            return_value=BudgetStatus(
                within_budget=False,
                scope="session",
                current_spend_usd=5.0,
                limit_usd=2.0,
            )
        )
        config = _config(gate)
        config["configurable"]["budget_checker"] = budget_checker
        env = _envelope(
            "calendar",
            is_compound=True,
            subtasks=[
                SubTask(agent="calendar", intent="read", prompt="tue"),
                SubTask(agent="messenger", intent="create", prompt="mail"),
            ],
        )
        result = await capability_check(
            {"envelope": env, "session_overrides": {}, "session_id": "s1"},
            config,
        )
        by_agent = {
            row["agent"]: row["decision"] for row in result["subtask_gate_decisions"]
        }
        assert by_agent["calendar"] == GateDecision.AWAIT_CONFIRMATION
        assert by_agent["messenger"] == GateDecision.DRAFT
        assert result["gate_decision"] == GateDecision.EXECUTE


# ── execute_tool ──────────────────────────────────────────────────────────────


class TestExecuteTool:
    async def test_single_agent_result(self):
        _register_and_wire("a", response="hello")
        state = {
            "envelope": _envelope("a"),
            "agent_context": _ctx("a"),
            "gate_decision": GateDecision.EXECUTE,
            "image_data": None,
        }
        result = await execute_tool(state, {"configurable": {}})
        assert result["agent_result"].response == "hello"
        assert result["subtask_results"] == []

    async def test_missing_context_returns_error(self):
        state = {
            "envelope": None,
            "agent_context": None,
            "gate_decision": GateDecision.EXECUTE,
        }
        result = await execute_tool(state, {"configurable": {}})
        assert "error" in result

    async def test_compound_parallel(self):
        _register_and_wire("alpha", response="r1")
        _register_and_wire("beta", response="r2")
        subtasks = [
            SubTask(agent="alpha", intent="read", prompt="p1"),
            SubTask(agent="beta", intent="read", prompt="p2"),
        ]
        env = _envelope("alpha", is_compound=True, subtasks=subtasks)
        state = {
            "envelope": env,
            "agent_context": _ctx("alpha"),
            "gate_decision": GateDecision.EXECUTE,
            "subtask_gate_decisions": [
                {
                    "agent": "alpha",
                    "intent": "read",
                    "decision": GateDecision.EXECUTE,
                },
                {
                    "agent": "beta",
                    "intent": "read",
                    "decision": GateDecision.EXECUTE,
                },
            ],
            "image_data": None,
        }
        result = await execute_tool(state, {"configurable": {}})
        assert result["agent_result"] is None
        assert len(result["subtask_results"]) == 2
        responses = {r.response for r in result["subtask_results"]}
        assert responses == {"r1", "r2"}
        assert not result.get("pending_subtask_awaits")

    async def test_compound_mixed_execute_runs_while_sibling_awaits(self):
        calendar = _register_and_wire("calendar", response="tue free")
        messenger = _register_and_wire("messenger", response="sent")
        calendar_runs = {"n": 0}
        messenger_runs = {"n": 0}
        orig_cal = calendar.run
        orig_msg = messenger.run

        async def cal_run(ctx):
            calendar_runs["n"] += 1
            return await orig_cal(ctx)

        async def msg_run(ctx):
            messenger_runs["n"] += 1
            return await orig_msg(ctx)

        calendar.run = cal_run
        messenger.run = msg_run
        subtasks = [
            SubTask(agent="calendar", intent="read", prompt="tue"),
            SubTask(agent="messenger", intent="create", prompt="mail"),
        ]
        env = _envelope("calendar", is_compound=True, subtasks=subtasks)
        state = {
            "envelope": env,
            "agent_context": _ctx("calendar"),
            "gate_decision": GateDecision.EXECUTE,
            "subtask_gate_decisions": [
                {
                    "agent": "calendar",
                    "intent": "read",
                    "decision": GateDecision.EXECUTE,
                },
                {
                    "agent": "messenger",
                    "intent": "create",
                    "decision": GateDecision.AWAIT_CONFIRMATION,
                },
            ],
            "image_data": None,
        }
        result = await execute_tool(state, {"configurable": {}})
        assert calendar_runs["n"] == 1
        assert messenger_runs["n"] == 0
        assert [r.agent for r in result["subtask_results"]] == ["calendar"]
        pending = result["pending_subtask_awaits"]
        assert len(pending) == 1
        assert pending[0]["agent"] == "messenger"
        assert pending[0]["request_id"]

    async def test_compound_approve_runs_only_that_subtask(self):
        calendar = _register_and_wire("calendar", response="tue free")
        messenger = _register_and_wire("messenger", response="sent")
        calendar_runs = {"n": 0}
        messenger_runs = {"n": 0}
        orig_cal = calendar.run
        orig_msg = messenger.run

        async def cal_run(ctx):
            calendar_runs["n"] += 1
            return await orig_cal(ctx)

        async def msg_run(ctx):
            messenger_runs["n"] += 1
            return await orig_msg(ctx)

        calendar.run = cal_run
        messenger.run = msg_run
        subtasks = [
            SubTask(agent="calendar", intent="read", prompt="tue"),
            SubTask(agent="messenger", intent="create", prompt="mail"),
        ]
        env = _envelope("calendar", is_compound=True, subtasks=subtasks)
        prior = AgentResult(agent="calendar", response="tue free")
        state = {
            "envelope": env,
            "agent_context": _ctx("calendar"),
            "gate_decision": GateDecision.EXECUTE,
            "subtask_gate_decisions": [
                {
                    "agent": "calendar",
                    "intent": "read",
                    "decision": GateDecision.EXECUTE,
                },
                {
                    "agent": "messenger",
                    "intent": "create",
                    "decision": GateDecision.AWAIT_CONFIRMATION,
                },
            ],
            "completed_subtask_indexes": [0],
            "subtask_results": [prior],
            "approved_subtask_indexes": [1],
            "pending_subtask_awaits": [],
            "image_data": None,
        }
        result = await execute_tool(state, {"configurable": {}})
        assert calendar_runs["n"] == 0
        assert messenger_runs["n"] == 1
        assert [r.agent for r in result["subtask_results"]] == ["calendar", "messenger"]
        assert result["pending_subtask_awaits"] == []

    async def test_compound_deny_skips_write(self):
        calendar = _register_and_wire("calendar", response="tue free")
        messenger = _register_and_wire("messenger", response="sent")
        calendar_runs = {"n": 0}
        messenger_runs = {"n": 0}
        orig_cal = calendar.run
        orig_msg = messenger.run

        async def cal_run(ctx):
            calendar_runs["n"] += 1
            return await orig_cal(ctx)

        async def msg_run(ctx):
            messenger_runs["n"] += 1
            return await orig_msg(ctx)

        calendar.run = cal_run
        messenger.run = msg_run
        subtasks = [
            SubTask(agent="calendar", intent="read", prompt="tue"),
            SubTask(agent="messenger", intent="create", prompt="mail"),
        ]
        env = _envelope("calendar", is_compound=True, subtasks=subtasks)
        prior = AgentResult(agent="calendar", response="tue free")
        state = {
            "envelope": env,
            "agent_context": _ctx("calendar"),
            "gate_decision": GateDecision.EXECUTE,
            "subtask_gate_decisions": [
                {
                    "agent": "calendar",
                    "intent": "read",
                    "decision": GateDecision.EXECUTE,
                },
                {
                    "agent": "messenger",
                    "intent": "create",
                    "decision": GateDecision.AWAIT_CONFIRMATION,
                },
            ],
            "completed_subtask_indexes": [0],
            "subtask_results": [prior],
            "denied_subtask_indexes": [1],
            "pending_subtask_awaits": [],
            "image_data": None,
        }
        result = await execute_tool(state, {"configurable": {}})
        assert calendar_runs["n"] == 0
        assert messenger_runs["n"] == 0
        assert [r.agent for r in result["subtask_results"]] == ["calendar"]
        assert result["pending_subtask_awaits"] == []

    async def test_compound_two_await_neither_runs_until_confirm(self):
        calendar = _register_and_wire("calendar", response="created")
        messenger = _register_and_wire("messenger", response="sent")
        calendar_runs = {"n": 0}
        messenger_runs = {"n": 0}
        orig_cal = calendar.run
        orig_msg = messenger.run

        async def cal_run(ctx):
            calendar_runs["n"] += 1
            return await orig_cal(ctx)

        async def msg_run(ctx):
            messenger_runs["n"] += 1
            return await orig_msg(ctx)

        calendar.run = cal_run
        messenger.run = msg_run
        subtasks = [
            SubTask(agent="calendar", intent="create", prompt="event"),
            SubTask(agent="messenger", intent="create", prompt="mail"),
        ]
        env = _envelope("calendar", is_compound=True, subtasks=subtasks)
        state = {
            "envelope": env,
            "agent_context": _ctx("calendar"),
            "gate_decision": GateDecision.EXECUTE,
            "subtask_gate_decisions": [
                {
                    "agent": "calendar",
                    "intent": "create",
                    "decision": GateDecision.AWAIT_CONFIRMATION,
                },
                {
                    "agent": "messenger",
                    "intent": "create",
                    "decision": GateDecision.AWAIT_CONFIRMATION,
                },
            ],
            "image_data": None,
        }
        result = await execute_tool(state, {"configurable": {}})
        assert calendar_runs["n"] == 0
        assert messenger_runs["n"] == 0
        assert result["subtask_results"] == []
        pending = result["pending_subtask_awaits"]
        assert [p["agent"] for p in pending] == ["calendar", "messenger"]
        assert pending[0]["request_id"] != pending[1]["request_id"]

    async def test_compound_execute_and_draft_per_specialist(self):
        received: dict[str, GateDecision] = {}

        class _Capture:
            name = "alpha"
            description = "alpha"
            enabled = True
            timeout = 30

            async def run(self, ctx: AgentContext) -> AgentResult:
                received[ctx.intent] = ctx.gate_decision
                return AgentResult(agent="alpha", response=ctx.intent)

        class _CaptureBeta(_Capture):
            name = "beta"

            async def run(self, ctx: AgentContext) -> AgentResult:
                received[ctx.intent] = ctx.gate_decision
                return AgentResult(agent="beta", response=ctx.intent)

        agent(_Capture)
        agent(_CaptureBeta)
        register_instance("alpha", _Capture())
        register_instance("beta", _CaptureBeta())
        subtasks = [
            SubTask(agent="alpha", intent="read", prompt="lookup"),
            SubTask(agent="beta", intent="create", prompt="draft it"),
        ]
        env = _envelope("alpha", is_compound=True, subtasks=subtasks)
        state = {
            "envelope": env,
            "agent_context": _ctx("alpha"),
            "gate_decision": GateDecision.EXECUTE,
            "subtask_gate_decisions": [
                {
                    "agent": "alpha",
                    "intent": "read",
                    "decision": GateDecision.EXECUTE,
                },
                {
                    "agent": "beta",
                    "intent": "create",
                    "decision": GateDecision.DRAFT,
                },
            ],
            "image_data": None,
        }
        result = await execute_tool(state, {"configurable": {}})
        assert received["read"] == GateDecision.EXECUTE
        assert received["create"] == GateDecision.DRAFT
        assert {r.agent for r in result["subtask_results"]} == {"alpha", "beta"}

    async def test_compound_blocked_sibling_does_not_run(self):
        alpha = _register_and_wire("alpha", response="ok")
        beta = _register_and_wire("beta", response="nope")
        alpha_runs = {"n": 0}
        beta_runs = {"n": 0}
        orig_a = alpha.run
        orig_b = beta.run

        async def a_run(ctx):
            alpha_runs["n"] += 1
            return await orig_a(ctx)

        async def b_run(ctx):
            beta_runs["n"] += 1
            return await orig_b(ctx)

        alpha.run = a_run
        beta.run = b_run
        subtasks = [
            SubTask(agent="alpha", intent="read", prompt="p1"),
            SubTask(agent="beta", intent="read", prompt="p2"),
        ]
        env = _envelope("alpha", is_compound=True, subtasks=subtasks)
        state = {
            "envelope": env,
            "agent_context": _ctx("alpha"),
            "gate_decision": GateDecision.EXECUTE,
            "subtask_gate_decisions": [
                {
                    "agent": "alpha",
                    "intent": "read",
                    "decision": GateDecision.EXECUTE,
                },
                {
                    "agent": "beta",
                    "intent": "read",
                    "decision": GateDecision.BLOCKED,
                },
            ],
            "image_data": None,
        }
        result = await execute_tool(state, {"configurable": {}})
        assert alpha_runs["n"] == 1
        assert beta_runs["n"] == 0
        assert [r.agent for r in result["subtask_results"]] == ["alpha"]

    async def test_await_subtask_approve_isolates_request_id(self, monkeypatch):
        monkeypatch.setattr(
            "ze_core.orchestration.nodes.execution.interrupt",
            lambda payload: {"choice": "approve"},
        )
        second = {
            "index": 1,
            "agent": "messenger",
            "intent": "create",
            "prompt": "mail",
            "request_id": "req-b",
        }
        result = await await_subtask_confirmation(
            {
                "pending_subtask_awaits": [
                    {
                        "index": 0,
                        "agent": "calendar",
                        "intent": "create",
                        "prompt": "event",
                        "request_id": "req-a",
                    },
                    second,
                ]
            },
            {"configurable": {}},
        )
        assert result["approved_subtask_indexes"] == [0]
        assert result["pending_subtask_awaits"] == [second]

    async def test_await_subtask_deny_skips_that_index(self, monkeypatch):
        monkeypatch.setattr(
            "ze_core.orchestration.nodes.execution.interrupt",
            lambda payload: {"choice": "deny"},
        )
        result = await await_subtask_confirmation(
            {
                "pending_subtask_awaits": [
                    {
                        "index": 1,
                        "agent": "messenger",
                        "intent": "create",
                        "prompt": "mail",
                        "request_id": "req-m",
                    }
                ]
            },
            {"configurable": {}},
        )
        assert result["denied_subtask_indexes"] == [1]
        assert result["pending_subtask_awaits"] == []

    async def test_compound_single_subtask_uses_agent_result(self):
        _register_and_wire("news", response="headlines")
        subtasks = [SubTask(agent="news", intent="read", prompt="search trump health")]
        env = _envelope("news", is_compound=True, subtasks=subtasks)
        state = {
            "envelope": env,
            "agent_context": _ctx("news"),
            "gate_decision": GateDecision.EXECUTE,
            "image_data": None,
        }
        result = await execute_tool(state, {"configurable": {}})
        assert result["agent_result"].response == "headlines"
        assert result["subtask_results"] == []

    async def test_compound_sequential_flag_still_fans_out(self):
        """Sequential execute loop is gone; compound still gathers in parallel."""
        _register_and_wire("alpha", response="r1")
        _register_and_wire("beta", response="r2")
        subtasks = [
            SubTask(agent="alpha", intent="read", prompt="p1"),
            SubTask(agent="beta", intent="read", prompt="p2"),
        ]
        env = _envelope(
            "alpha", is_compound=True, is_sequential=True, subtasks=subtasks
        )
        state = {
            "envelope": env,
            "agent_context": _ctx("alpha"),
            "gate_decision": GateDecision.EXECUTE,
            "image_data": None,
        }
        result = await execute_tool(state, {"configurable": {}})
        assert result["agent_result"] is None
        assert len(result["subtask_results"]) == 2

    async def test_timeout_raises(self):
        cls = _make_agent_class("slow", timeout=0)

        async def slow_run(self, ctx):
            await asyncio.sleep(10)
            return AgentResult(agent="slow", response="late")

        cls.run = slow_run
        agent(cls)
        instance = object.__new__(cls)
        instance.run = slow_run.__get__(instance, cls)
        register_instance("slow", instance)

        state = {
            "envelope": _envelope("slow"),
            "agent_context": _ctx("slow"),
            "gate_decision": GateDecision.EXECUTE,
            "image_data": None,
        }
        with pytest.raises(AgentTimeoutError):
            await execute_tool(state, {"configurable": {}})


# ── draft_response ────────────────────────────────────────────────────────────


class TestDraftResponse:
    async def test_sets_pending_confirmation(self):
        _register_and_wire("a", response="draft text")
        state = {
            "envelope": _envelope("a"),
            "agent_context": _ctx("a"),
            "image_data": None,
        }
        result = await draft_response(state, {"configurable": {}})
        assert result["pending_confirmation"] is True
        assert result["agent_result"].response == "draft text"

    async def test_agent_receives_draft_gate_decision(self):
        received_decision = {}

        class _DraftCapture:
            name = "capture"
            description = "capture"
            enabled = True
            timeout = 30

            async def run(self, ctx: AgentContext) -> AgentResult:
                received_decision["decision"] = ctx.gate_decision
                return AgentResult(agent="capture", response="ok")

        agent(_DraftCapture)
        instance = _DraftCapture()
        register_instance("capture", instance)

        state = {
            "envelope": _envelope("capture"),
            "agent_context": _ctx("capture"),
            "image_data": None,
        }
        await draft_response(state, {"configurable": {}})
        assert received_decision["decision"] == GateDecision.DRAFT

    async def test_budget_status_appends_spend_and_limit_to_draft_text(self):
        from ze_core.telemetry.budget import BudgetStatus

        _register_and_wire("a", response="draft text")
        state = {
            "envelope": _envelope("a"),
            "agent_context": _ctx("a"),
            "image_data": None,
            "budget_status": BudgetStatus(
                within_budget=False,
                scope="daily",
                current_spend_usd=12.34,
                limit_usd=10.0,
            ),
        }
        result = await draft_response(state, {"configurable": {}})
        response = result["agent_result"].response
        assert "draft text" in response
        assert "12.34" in response
        assert "10.00" in response
        assert "daily" in response


# ── await_confirmation ────────────────────────────────────────────────────────


class TestAwaitConfirmation:
    async def test_resets_pending_and_sets_execute(self):
        state = {
            "session_id": "s1",
            "envelope": _envelope("a"),
            "pending_confirmation": True,
        }
        result = await await_confirmation(state, {"configurable": {}})
        assert result["pending_confirmation"] is False
        assert result["gate_decision"] == GateDecision.EXECUTE
