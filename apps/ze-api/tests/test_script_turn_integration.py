"""A scripted read turn reaches the trace; only agents with a data read get scripts (197)."""

from __future__ import annotations

from importlib.metadata import entry_points
from unittest.mock import AsyncMock, MagicMock

from ze_agents.base_agent import BaseAgent
from ze_agents.bootstrap import reload_agent_modules
from ze_agents.registry import get_registered_agents
from ze_agents.script_step import data_read_names
from ze_agents.scripts import ScriptOutcome, ScriptRequest
from ze_agents.tool import ToolAccess, tool
from ze_agents.types import AgentContext, AgentResult
from ze_core.orchestration.nodes.trace import _extract_tool_calls

from tests.support.agent_modules import ALL_AGENT_MODULE_PATHS

EXTRA = [
    "ze_calendar.agents.calendar.tools",
    "ze_calendar.agents.reminders.tools",
    "ze_finance.agents.finance.tools",
    "ze_workspace.tools",
    "ze_ingestion.agent",
    "ze_worldstate.agents.tools",
]


def _load_everything() -> None:
    paths = set(ALL_AGENT_MODULE_PATHS) | set(EXTRA)
    for ep in entry_points(group="ze.plugins"):
        plugin = object.__new__(ep.load())
        plugin._enabled = True
        paths.update(plugin.agent_module_paths())
    reload_agent_modules(sorted(paths))


def _ctx() -> AgentContext:
    return AgentContext(session_id="s", prompt="what did I spend")


def test_agents_get_scripts_exactly_when_they_have_a_data_read() -> None:
    _load_everything()
    ctx = _ctx()
    offered = {}
    for name, cls in get_registered_agents().items():
        agent = object.__new__(cls)
        offered[name] = bool(data_read_names(agent, ctx, list(cls.tools or [])))
    for name in ("finance", "calendar", "messenger", "companion", "goals", "workflow"):
        assert offered[name], name
    for name in ("research", "priority", "ingestion", "prospecting"):
        assert not offered[name], name


async def test_a_finance_turn_that_scripts_two_reads_leaves_step_and_inner_calls() -> (
    None
):
    @tool(access=ToolAccess.READ, description="accounts")
    async def list_accounts_it() -> str:
        return '[{"id": "a"}]'

    @tool(access=ToolAccess.READ, description="transactions")
    async def get_transactions_it(account: str) -> str:
        return '[{"merchant": "m", "amount": 3}]'

    class _Finance(BaseAgent):
        name = "finance_it"
        description = "t"
        tools = ["list_accounts_it", "get_transactions_it"]

        async def run(self, ctx):
            return AgentResult(agent=self.name, response="")

    class _Runner:
        async def run(
            self, *, script_id, agent, source, stub, limits, dispatch, procedure_id=None
        ):
            await dispatch(ScriptRequest(1, "list_accounts_it", {}))
            await dispatch(ScriptRequest(2, "get_transactions_it", {"account": "a"}))
            return ScriptOutcome(status="ok", value={"top": [["m", 3]]})

    agent = _Finance.__new__(_Finance)
    ctx = _ctx()
    ctx.script_runner = _Runner()
    client = MagicMock()
    client.complete_with_tools = AsyncMock(
        side_effect=[
            (
                None,
                [{"id": "c1", "name": "run_tool_script", "arguments": {"source": "x"}}],
            ),
            ("You spent 3 at m.", None),
        ]
    )
    client.complete = AsyncMock(return_value="x")

    text, calls = await agent.agentic_loop(ctx, client, [], system="s")

    assert text == "You spent 3 at m."
    assert client.complete_with_tools.call_count == 2
    rows = _extract_tool_calls(
        AgentResult(agent="finance_it", response=text, tool_calls=calls)
    )
    assert [(r.name, r.access) for r in rows] == [
        ("run_tool_script", "script"),
        ("list_accounts_it", "read"),
        ("get_transactions_it", "read"),
    ]
    step = rows[0]
    assert rows[1].parent_call_id == step.call_id == rows[2].parent_call_id
    assert step.script is not None and step.script.outcome == "ok"
