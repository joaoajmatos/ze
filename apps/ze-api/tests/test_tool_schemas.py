"""Model-visible tool schemas: typed optionals and lists show, injected params never do."""

from __future__ import annotations

from importlib.metadata import entry_points

import pytest

from ze_agents.bootstrap import reload_agent_modules
from ze_agents.tool import get_tool, registered_tools

from tests.support.agent_modules import ALL_AGENT_MODULE_PATHS

_CORE_TOOL_MODULES = [
    "ze_calendar.agents.calendar.tools",
    "ze_calendar.agents.reminders.tools",
    "ze_calendar.timezone.tools",
    "ze_finance.agents.finance.tools",
    "ze_workspace.tools",
    "ze_ingestion.agent",
    "ze_worldstate.agents.tools",
    "ze_browser.tool",
    "ze_news.agents.tools",
]

_STR = {"type": "string"}
_STR_LIST = {"type": "array", "items": {"type": "string"}}

VISIBLE = [
    (
        "update_event",
        {"summary": _STR, "start": _STR, "end": _STR, "description": _STR},
    ),
    ("send_email", {"thread_id": _STR}),
    ("world_time", {"locations": _STR_LIST}),
    ("get_positions", {"account_id": _STR}),
    ("get_spending_summary", {"account_id": _STR, "since": _STR, "until": _STR}),
    ("get_transactions", {"account_id": _STR, "since": _STR, "until": _STR}),
    ("get_recurring_expenses", {"status": _STR}),
    ("search_news", {"tags": _STR_LIST}),
    ("get_headlines", {"tags": _STR_LIST}),
    ("add_prospect", {"company": _STR, "role": _STR}),
]

HIDDEN = [
    (
        "browser_extract",
        {"browser_client", "browser_delay_ms", "browser_max_text_chars"},
    ),
    ("draft_outreach", {"campaign_id", "model", "client", "person_store"}),
    ("add_prospect", {"campaign_id", "person_store", "campaign_store"}),
    (
        "get_headlines",
        {"news_store", "_personalization_ctx", "_diagnostic_query", "_min_preferences"},
    ),
    ("create_workflow", {"store", "session_id", "user_message_id"}),
    ("edit_workflow_steps", {"store", "session_id", "user_message_id"}),
    ("forget_fact", {"memory_store", "restore_fact_ids"}),
    ("restore_priority_override", {"override_store", "prior_override_id"}),
    ("update_event", {"credentials"}),
    ("send_email", {"channel_registry", "thread_channel_map", "user_channel_store"}),
]


@pytest.fixture(scope="module", autouse=True)
def _all_tools() -> None:
    paths = set(ALL_AGENT_MODULE_PATHS) | set(_CORE_TOOL_MODULES)
    for ep in entry_points(group="ze.plugins"):
        plugin_cls = ep.load()
        plugin = object.__new__(plugin_cls)
        plugin._enabled = True  # NewsPlugin gates its module list on config
        paths.update(plugin.agent_module_paths())
    reload_agent_modules(sorted(paths))


def _params(name: str) -> dict:
    return get_tool(name).llm_schema()["function"]["parameters"]


@pytest.mark.parametrize(("name", "expected"), VISIBLE)
def test_param_is_visible_and_typed(name: str, expected: dict) -> None:
    props = _params(name)["properties"]
    for param, schema in expected.items():
        assert props.get(param) == schema, f"{name}.{param}"


@pytest.mark.parametrize(("name", "hidden"), HIDDEN)
def test_injected_and_dependency_params_are_hidden(name: str, hidden: set) -> None:
    props = _params(name)["properties"]
    assert hidden.isdisjoint(props), f"{name} exposes {hidden & set(props)}"
    assert hidden <= get_tool(name).hidden_params()


def test_world_time_requires_locations() -> None:
    assert _params("world_time")["required"] == ["locations"]


def test_no_tool_exposes_a_session_or_message_id() -> None:
    internal = {"session_id", "user_message_id", "ctx"}
    leaks = sorted(
        name
        for name, spec in registered_tools().items()
        if internal & set(spec.llm_schema()["function"]["parameters"]["properties"])
    )
    assert leaks == []
