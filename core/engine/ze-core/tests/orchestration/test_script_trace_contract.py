"""Every outcome and limit a script step can produce survives the REST trace schema (197)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.registry import clear_registry
from ze_agents.script_step import run_script_step
from ze_agents.scripts import (
    DispatchReply,
    ScriptLimits,
    ScriptOutcome,
    ScriptRequest,
)
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext, AgentResult
from ze_core.orchestration.nodes.trace import record_trace

router = pytest.importorskip("ze_api.api.v0.messages.router")
from ze_api.api.v0.messages.schemas import ScriptTraceResponse  # noqa: E402

_STATUSES = [
    "ok",
    "exception",
    "timeout",
    "killed",
    "bad_request",
    "busy",
    "unavailable",
    "resource_limit",
]


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()

    @tool(access=ToolAccess.READ, description="rows")
    async def get_rows() -> str:
        return '{"n": 1}'

    yield
    clear_registry()
    clear_tool_registry()


class _Agent(BaseAgent):
    name = "finance"
    description = "t"
    tools = ["get_rows"]

    async def run(self, ctx: AgentContext) -> AgentResult:
        return AgentResult(agent=self.name, response="ok")


class _Runner:
    def __init__(self, outcome: ScriptOutcome, requests: int = 1, limits=None):
        self.outcome = outcome
        self.requests = requests
        self.limits = limits

    async def run(self, *, dispatch, **_):
        for i in range(self.requests):
            reply: DispatchReply = await dispatch(
                ScriptRequest(seq=i, tool="get_rows", args={})
            )
            if reply.stop:
                break
        return self.outcome


async def _response(runner: _Runner, args: dict | None = None, ctx=None):
    ctx = ctx or AgentContext(session_id="s", prompt="p", script_runner=runner)
    step = (
        await run_script_step(
            _Agent(),
            args if args is not None else {"source": "x = 1"},
            ctx,
            "c1",
            {},
            ["get_rows"],
        )
    ).tool_call
    state = {
        "envelope": SimpleNamespace(
            primary_agent="finance",
            routing_method="embedding",
            confidence=0.9,
            score_gap=0.1,
            is_compound=False,
            subtasks=[],
        ),
        "agent_result": AgentResult(agent="finance", response="ok", tool_calls=[step]),
        "agent_context": AgentContext(session_id="s", prompt="p"),
    }
    trace = (await record_trace(state, {"configurable": {}}))["message_trace"]
    return router._trace_to_response(trace).tool_calls[0]


@pytest.mark.parametrize("status", _STATUSES)
async def test_every_runner_status_validates(status: str) -> None:
    row = await _response(_Runner(ScriptOutcome(status=status)))  # type: ignore[arg-type]
    assert row.access == "script"
    assert row.script.outcome == status
    assert row.script.limit in (None, "wall_time")


@pytest.mark.parametrize(
    ("runner", "limit"),
    [
        (
            _Runner(ScriptOutcome(status="killed"), 25),
            "inner_calls",
        ),
        (_Runner(ScriptOutcome(status="timeout"), 0), "wall_time"),
        (
            _Runner(ScriptOutcome(status="ok", value={"t": "z" * 6000}), 0),
            "result_size",
        ),
    ],
)
async def test_every_limit_validates(runner: _Runner, limit: str) -> None:
    row = await _response(runner)
    assert row.script.limit == limit


async def test_spend_limit_validates() -> None:
    from ze_agents.scripts import charge_script

    @tool(access=ToolAccess.READ, description="costly")
    async def get_costly() -> str:
        charge_script(1.0)
        return "{}"

    class _CostlyRunner(_Runner):
        async def run(self, *, dispatch, **_):
            for i, name in enumerate(["get_costly", "get_rows"]):
                reply = await dispatch(ScriptRequest(seq=i, tool=name, args={}))
                if reply.stop:
                    break
            return self.outcome

    agent = _Agent()
    agent.tools = ["get_rows", "get_costly"]
    runner = _CostlyRunner(
        ScriptOutcome(status="killed"), limits=ScriptLimits(max_spend_usd=0.01)
    )
    ctx = AgentContext(session_id="s", prompt="p", script_runner=runner)
    step = (
        await run_script_step(
            agent, {"source": "x"}, ctx, "c1", {}, ["get_rows", "get_costly"]
        )
    ).tool_call
    assert step.script["limit"] == "spend"
    assert (
        ScriptTraceResponse(
            **{
                k: step.script[k]
                for k in (
                    "source",
                    "source_cut",
                    "outcome",
                    "limit",
                    "source_hash",
                    "procedure_id",
                )
            }
        ).limit
        == "spend"
    )


@pytest.mark.parametrize(
    "args", [{"source": "x = 1\n" * 2000}, {"procedure_id": "nope"}, {}]
)
async def test_refusals_without_a_run_validate(args: dict) -> None:
    row = await _response(_Runner(ScriptOutcome(status="ok")), args)
    assert row.script.limit is None
    assert row.script.outcome in (
        "source_too_long",
        "procedure_not_script",
        "bad_request",
    )
