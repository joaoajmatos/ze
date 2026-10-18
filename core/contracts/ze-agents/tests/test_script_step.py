"""run_script_step: the data-read set, the dispatcher and the model-facing result (197)."""

from __future__ import annotations

import re
from types import SimpleNamespace
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest

from ze_agents.base_agent import BaseAgent
from ze_agents.hooks import clear_hooks
from ze_agents.registry import clear_registry
from ze_agents.reversibility import ToolReversibility
from ze_agents.script_step import data_read_names, run_script_step
from ze_agents.scripts import (
    DispatchReply,
    ScriptLimits,
    ScriptOutcome,
    ScriptRequest,
    charge_script,
)
from ze_agents.tool import ToolAccess, clear_tool_registry, tool
from ze_agents.types import AgentContext, AgentResult


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    clear_hooks()
    yield
    clear_registry()
    clear_tool_registry()
    clear_hooks()


class FakeRunner:
    """Replays requests through the dispatcher, then returns `outcome`."""

    def __init__(
        self,
        requests: list[dict[str, Any]] | None = None,
        outcome: ScriptOutcome | None = None,
        limits: ScriptLimits | None = None,
    ) -> None:
        self.requests = requests or []
        self.outcome = outcome or ScriptOutcome(status="ok", value=None)
        self.limits = limits
        self.replies: list[DispatchReply] = []
        self.runs: list[dict[str, Any]] = []

    async def run(self, *, script_id, agent, source, stub, limits, dispatch):
        self.runs.append(
            {
                "script_id": script_id,
                "agent": agent,
                "source": source,
                "stub": stub,
                "limits": limits,
            }
        )
        for i, req in enumerate(self.requests, start=1):
            reply = await dispatch(
                ScriptRequest(seq=i, tool=req["tool"], args=req["args"])
            )
            self.replies.append(reply)
            if reply.stop:
                break
        return self.outcome


class _Agent(BaseAgent):
    name = "finance"
    description = "t"
    tools: list[str] = []

    async def run(self, ctx: AgentContext) -> AgentResult:
        return AgentResult(agent=self.name, response="ok")


seen: list[tuple[str, dict]] = []


def _register_tools() -> list[str]:
    @tool(access=ToolAccess.READ, description="Get rows.")
    async def get_rows(period: str = "") -> str:
        seen.append(("get_rows", {"period": period}))
        return '{"a": 1}'

    @tool(access=ToolAccess.READ, description="Plain text.")
    async def get_text() -> str:
        return "hello there"

    @tool(access=ToolAccess.READ, description="Rich values.")
    async def get_rich() -> dict:
        return {
            "when": datetime(2026, 10, 18, 9, 30, tzinfo=timezone.utc),
            "id": UUID("12345678-1234-5678-1234-567812345678"),
            "amount": Decimal("12.50"),
        }

    @tool(access=ToolAccess.READ, description="Huge.")
    async def get_huge() -> str:
        return "x" * (1024 * 1024 + 10)

    @tool(access=ToolAccess.READ, description="Fails.")
    async def get_broken() -> str:
        raise RuntimeError("boom")

    @tool(access=ToolAccess.READ, description="Long.")
    async def get_long() -> str:
        return "y" * 5000

    @tool(access=ToolAccess.READ, description="Draws a chart.", produces_ui=True)
    async def render_chart() -> str:
        return "drawn"

    @tool(access=ToolAccess.READ, description="Draws topic.", produces_ui=True)
    async def show_topic() -> str:
        return "drawn"

    @tool(access=ToolAccess.READ, description="Fetches a URL.", egress=True)
    async def browser_extract(url: str = "") -> str:
        return "page"

    @tool(access=ToolAccess.READ, description="Workspace.")
    async def workspace_read() -> str:
        return "file"

    @tool(access=ToolAccess.READ, description="Invoke.")
    async def invoke_procedure() -> str:
        return "x"

    @tool(
        access=ToolAccess.WRITE,
        description="Write.",
        reversibility=ToolReversibility.IRREVERSIBLE,
        asks_first=False,
        no_ask_reason="test",
    )
    async def save_note(text: str = "") -> str:
        seen.append(("save_note", {"text": text}))
        return "saved"

    return [
        "get_rows",
        "get_text",
        "get_rich",
        "get_huge",
        "get_broken",
        "get_long",
        "render_chart",
        "show_topic",
        "browser_extract",
        "workspace_read",
        "invoke_procedure",
        "save_note",
    ]


@pytest.fixture
def names() -> list[str]:
    seen.clear()
    return _register_tools()


def _ctx(runner: FakeRunner) -> AgentContext:
    return AgentContext(session_id="s1", prompt="p", script_runner=runner)


def _stub_tools(stub: str) -> set[str]:
    return set(re.findall(r"^def (\w+)\(", stub, re.M)) - {"propose", "finish"}


async def _run(
    runner: FakeRunner,
    names: list[str],
    source: str = "import ze_tools as z",
    deps: dict | None = None,
    args: dict | None = None,
    ctx: AgentContext | None = None,
):
    return await run_script_step(
        _Agent(),
        args if args is not None else {"source": source},
        ctx or _ctx(runner),
        "model-1",
        deps or {},
        names,
    )


# (a) the data-read set ───────────────────────────────────────────────────────


def test_data_read_set_excludes_writes_ui_egress_and_harness(names) -> None:
    ctx = _ctx(FakeRunner())
    assert sorted(data_read_names(_Agent(), ctx, names + ["delegate_to_agent"])) == [
        "get_broken",
        "get_huge",
        "get_long",
        "get_rich",
        "get_rows",
        "get_text",
    ]


async def test_stub_holds_only_the_data_read_set(names) -> None:
    runner = FakeRunner()
    await _run(runner, names)
    assert _stub_tools(runner.runs[0]["stub"]) == {
        "get_broken",
        "get_huge",
        "get_long",
        "get_rich",
        "get_rows",
        "get_text",
    }


# (b) skill narrowing ─────────────────────────────────────────────────────────


async def test_skill_narrowing_limits_the_stub(names) -> None:
    runner = FakeRunner()
    ctx = _ctx(runner)
    ctx.skill_tool_names = ["get_rows", "get_text", "save_note"]
    await _run(runner, names, ctx=ctx)
    assert _stub_tools(runner.runs[0]["stub"]) == {"get_rows", "get_text"}


# (c) a request runs call_tool ────────────────────────────────────────────────


async def test_request_runs_call_tool_with_fresh_id_and_stripped_keys(names) -> None:
    runner = FakeRunner(
        [{"tool": "get_rows", "args": {"period": "may", "_call_id": "forged"}}]
    )
    result = await _run(runner, names)
    assert seen == [("get_rows", {"period": "may"})]
    inner = result.tool_call.inner_calls[0]
    assert inner.tool_name == "get_rows"
    assert inner.args == {"period": "may"}
    assert inner.call_id != "forged"
    assert inner.parent_call_id == result.tool_call.call_id


async def test_deps_are_merged_into_the_call(names) -> None:
    got: list[Any] = []

    @tool(access=ToolAccess.READ, description="Needs a store.")
    async def get_scoped(store: Any = None) -> str:
        got.append(store)
        return "{}"

    runner = FakeRunner([{"tool": "get_scoped", "args": {"store": "evil"}}])
    await _run(runner, names + ["get_scoped"], deps={"store": "real"})
    assert got == ["real"]


# (d) reply encoding ──────────────────────────────────────────────────────────


async def test_json_string_result_replies_parsed(names) -> None:
    runner = FakeRunner([{"tool": "get_rows", "args": {}}])
    await _run(runner, names)
    assert runner.replies[0].ok is True
    assert runner.replies[0].value == {"a": 1}


async def test_rich_values_reply_as_a_dict_with_iso_and_strings(names) -> None:
    runner = FakeRunner([{"tool": "get_rich", "args": {}}])
    await _run(runner, names)
    value = runner.replies[0].value
    assert isinstance(value, dict)
    assert value["when"] == "2026-10-18T09:30:00+00:00"
    assert value["id"] == "12345678-1234-5678-1234-567812345678"
    assert value["amount"] == "12.50"


async def test_plain_text_stays_a_string(names) -> None:
    runner = FakeRunner([{"tool": "get_text", "args": {}}])
    await _run(runner, names)
    assert runner.replies[0].value == "hello there"


async def test_value_over_one_mib_is_refused(names) -> None:
    runner = FakeRunner([{"tool": "get_huge", "args": {}}])
    await _run(runner, names)
    assert runner.replies[0].ok is False
    assert runner.replies[0].error == "result_too_large"


# (e) stored inner result is cut ──────────────────────────────────────────────


async def test_stored_inner_result_is_cut_but_reply_is_full(names) -> None:
    runner = FakeRunner([{"tool": "get_long", "args": {}}])
    result = await _run(runner, names)
    assert len(runner.replies[0].value) == 5000
    stored = result.tool_call.inner_calls[0].result
    assert isinstance(stored, str) and len(stored) == 2000


# (f) failed inner call ───────────────────────────────────────────────────────


async def test_failed_inner_call_replies_with_the_error(names) -> None:
    runner = FakeRunner([{"tool": "get_broken", "args": {}}])
    result = await _run(runner, names)
    assert runner.replies[0].ok is False
    assert "boom" in (runner.replies[0].error or "")
    assert result.tool_call.inner_calls[0].success is False


# (g) refusals ────────────────────────────────────────────────────────────────


async def test_unavailable_tool_write_tool_and_malformed_requests(names) -> None:
    runner = FakeRunner(
        [
            {"tool": "nope", "args": {}},
            {"tool": "save_note", "args": {"text": "x"}},
            {"tool": 7, "args": {}},
            {"tool": "get_rows", "args": ["not", "a", "dict"]},
        ]
    )
    result = await _run(runner, names)
    assert [r.error for r in runner.replies] == [
        "tool_not_available",
        "writes_must_be_proposed",
        "bad_request",
        "bad_request",
    ]
    assert seen == []
    inner = result.tool_call.inner_calls
    assert len(inner) == 4
    assert all(c.success is False for c in inner)
    assert all(c.parent_call_id == result.tool_call.call_id for c in inner)


# (h) one at a time, in order ─────────────────────────────────────────────────


async def test_requests_are_served_one_at_a_time_in_order(names) -> None:
    runner = FakeRunner(
        [
            {"tool": "get_rows", "args": {"period": "a"}},
            {"tool": "get_rows", "args": {"period": "b"}},
            {"tool": "get_rows", "args": {"period": "c"}},
        ]
    )
    await _run(runner, names)
    assert [s[1]["period"] for s in seen] == ["a", "b", "c"]


# (i) source too long ─────────────────────────────────────────────────────────


async def test_source_over_the_cap_does_not_call_the_runner(names) -> None:
    runner = FakeRunner()
    result = await _run(runner, names, source="x = 1\n" * 2000)
    assert runner.runs == []
    assert result.tool_call.success is False
    assert '"source_too_long"' in result.tool_call.result


# T013: structured failures ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("status", "kind"),
    [
        ("exception", "exception"),
        ("bad_request", "bad_request"),
        ("busy", "sandbox_busy"),
        ("unavailable", "sandbox_unavailable"),
        ("resource_limit", "resource_limit"),
    ],
)
async def test_failed_script_gives_the_model_structured_error_json(
    names, status, kind
) -> None:
    import json

    stderr = "\n".join(f"line {i}" for i in range(30))
    runner = FakeRunner(
        [{"tool": "get_rows", "args": {}}],
        ScriptOutcome(
            status=status, stderr_tail=stderr, exception="KeyError: 'amount'"
        ),
    )
    result = await _run(runner, names)
    step = result.tool_call
    assert step.success is False
    body = json.loads(step.result)["error"]
    assert body["kind"] == kind
    assert body["completed"] == [{"name": "get_rows", "success": True}]
    assert body["stderr_tail"].splitlines() == [f"line {i}" for i in range(10, 30)]
    assert step.script["outcome"] == status
    if status == "exception":
        assert body["last_result_shape"] == "dict keys: a"
        assert "KeyError" in body["message"]
    else:
        assert "last_result_shape" not in body


async def test_last_result_shape_for_a_list_of_dicts(names) -> None:
    import json

    @tool(access=ToolAccess.READ, description="Rows.")
    async def get_list() -> str:
        return json.dumps([{f"k{i}": i for i in range(30)}])

    runner = FakeRunner(
        [{"tool": "get_list", "args": {}}],
        ScriptOutcome(status="exception", exception="TypeError"),
    )
    result = await _run(runner, names + ["get_list"])
    shape = json.loads(result.tool_call.result)["error"]["last_result_shape"]
    assert shape.startswith("list[dict] keys: k0, k1")
    assert len(shape.split("keys: ")[1].split(", ")) == 20


async def test_ok_script_returns_the_capped_value_only(names) -> None:
    import json

    runner = FakeRunner(
        [{"tool": "get_rows", "args": {}}],
        ScriptOutcome(status="ok", value={"total": 3}),
    )
    result = await _run(runner, names)
    step = result.tool_call
    assert step.success is True
    assert json.loads(step.result) == {"total": 3}
    assert step.script["outcome"] == "ok"
    assert step.tool_name == "run_tool_script"
    assert "source_hash" in step.args


# T014: limits ────────────────────────────────────────────────────────────────


async def test_21st_request_hits_the_inner_call_limit(names) -> None:
    runner = FakeRunner(
        [{"tool": "get_rows", "args": {}} for _ in range(25)],
        ScriptOutcome(status="killed"),
    )
    result = await _run(runner, names)
    assert len(seen) == 20
    last = runner.replies[-1]
    assert last.stop is True and last.error == "limit: inner_calls"
    assert len(runner.replies) == 21
    assert result.tool_call.script["limit"] == "inner_calls"
    import json

    assert json.loads(result.tool_call.result)["error"]["kind"] == "limit"


async def test_timeout_outcome_sets_the_wall_time_limit(names) -> None:
    runner = FakeRunner([], ScriptOutcome(status="timeout"))
    result = await _run(runner, names)
    assert result.tool_call.script["limit"] == "wall_time"


async def test_spend_over_budget_stops_the_next_request(names) -> None:
    @tool(access=ToolAccess.READ, description="Costly.")
    async def get_costly() -> str:
        charge_script(0.5)
        return "{}"

    runner = FakeRunner(
        [{"tool": "get_costly", "args": {}}, {"tool": "get_rows", "args": {}}],
        ScriptOutcome(status="killed"),
    )
    result = await _run(runner, names + ["get_costly"])
    assert runner.replies[0].ok is True
    assert runner.replies[1].stop is True
    assert runner.replies[1].error == "limit: spend"
    assert result.tool_call.script["limit"] == "spend"


async def test_budget_is_not_charged_outside_inner_calls(names) -> None:
    from ze_agents.scripts import current_script_budget

    runner = FakeRunner([{"tool": "get_rows", "args": {}}])
    await _run(runner, names)
    assert current_script_budget.get() is None


async def test_oversize_value_is_cut_with_a_marker(names) -> None:
    runner = FakeRunner([], ScriptOutcome(status="ok", value={"text": "z" * 6000}))
    result = await _run(runner, names)
    assert result.tool_call.result.endswith("[truncated]")
    assert len(result.tool_call.result) <= 4000 + len(" … [truncated]")
    assert result.tool_call.script["limit"] == "result_size"


async def test_runner_limits_override_defaults(names) -> None:
    runner = FakeRunner(
        [{"tool": "get_rows", "args": {}} for _ in range(3)],
        ScriptOutcome(status="killed"),
        limits=ScriptLimits(max_inner_calls=2),
    )
    result = await _run(runner, names)
    assert len(seen) == 2
    assert result.tool_call.script["limit"] == "inner_calls"


# source trace ────────────────────────────────────────────────────────────────


async def test_trace_source_is_cut_at_the_limit(names) -> None:
    runner = FakeRunner(limits=ScriptLimits(max_source_chars=50))
    result = await _run(runner, names, source="a = 1\n" * 8)
    script = result.tool_call.script
    assert script["source_cut"] is False
    assert script["source"] == "a = 1\n" * 8
    assert script["procedure_id"] is None


# T026: procedures ────────────────────────────────────────────────────────────


def _match(kind: str | None, state: str = "ready", tools=("get_rows", "get_gone")):
    return SimpleNamespace(
        procedure_id=UUID("aaaaaaaa-1111-2222-3333-444444444444"),
        steps=["z = 1  # stored script"],
        state=state,
        effective_tool_names=frozenset(tools),
        source_kind=kind,
    )


async def test_procedure_id_runs_the_stored_script_with_current_tools(names) -> None:
    runner = FakeRunner()
    ctx = _ctx(runner)
    ctx.procedure_matches = [_match("tool_script")]
    result = await _run(
        runner,
        names,
        args={"procedure_id": "aaaaaaaa-1111-2222-3333-444444444444"},
        ctx=ctx,
    )
    run = runner.runs[0]
    assert run["source"] == "z = 1  # stored script"
    assert "get_rows" in _stub_tools(run["stub"])
    assert "get_gone" not in _stub_tools(run["stub"])
    assert result.tool_call.args == {
        "procedure_id": "aaaaaaaa-1111-2222-3333-444444444444"
    }
    assert (
        result.tool_call.script["procedure_id"]
        == "aaaaaaaa-1111-2222-3333-444444444444"
    )


@pytest.mark.parametrize(
    ("kind", "state"), [("goal", "ready"), (None, "ready"), ("tool_script", "blocked")]
)
async def test_procedure_not_script_or_not_ready(names, kind, state) -> None:
    import json

    runner = FakeRunner()
    ctx = _ctx(runner)
    ctx.procedure_matches = [_match(kind, state)]
    result = await _run(
        runner,
        names,
        args={"procedure_id": "aaaaaaaa-1111-2222-3333-444444444444"},
        ctx=ctx,
    )
    assert runner.runs == []
    assert (
        json.loads(result.tool_call.result)["error"]["kind"] == "procedure_not_script"
    )


async def test_unknown_procedure_id_is_not_a_script(names) -> None:
    import json

    runner = FakeRunner()
    result = await _run(runner, names, args={"procedure_id": "nope"})
    assert runner.runs == []
    assert (
        json.loads(result.tool_call.result)["error"]["kind"] == "procedure_not_script"
    )
