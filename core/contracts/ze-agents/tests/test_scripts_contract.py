"""Programmatic tool use contract (Phase 197): limits, schema, budget, flags."""

from __future__ import annotations

import pytest

from ze_agents.errors import ZeError
from ze_agents.registry import clear_registry
from ze_agents.scripts import (
    SCRIPT_TOOL_NAME,
    SCRIPT_TOOL_SCHEMA,
    ScriptBudget,
    ScriptError,
    ScriptLimits,
    charge_script,
    current_script_budget,
    in_script_call,
)
from ze_agents.tool import ToolAccess, clear_tool_registry, get_tool, tool


@pytest.fixture(autouse=True)
def clean():
    clear_registry()
    clear_tool_registry()
    yield
    clear_registry()
    clear_tool_registry()


def test_limit_defaults() -> None:
    limits = ScriptLimits()
    assert limits.wall_seconds == 30
    assert limits.max_inner_calls == 20
    assert limits.max_proposed_writes == 10
    assert limits.max_spend_usd == 0.05
    assert limits.max_result_chars == 4000
    assert limits.max_source_chars == 8000
    assert limits.max_request_bytes == 262144
    assert limits.max_reply_bytes == 1048576
    assert limits.inner_result_store_chars == 2000


def test_from_config_reads_workspace_scripts() -> None:
    config = {"workspace": {"scripts": {"wall_seconds": 10, "max_spend_usd": 0.5}}}
    limits = ScriptLimits.from_config(config)
    assert limits.wall_seconds == 10
    assert limits.max_spend_usd == 0.5
    assert limits.max_inner_calls == 20


@pytest.mark.parametrize("bad", ["x", 0, -3, None, True])
def test_from_config_falls_back_per_field(bad) -> None:
    config = {"workspace": {"scripts": {"wall_seconds": bad, "max_inner_calls": 7}}}
    limits = ScriptLimits.from_config(config)
    assert limits.wall_seconds == 30
    assert limits.max_inner_calls == 7


@pytest.mark.parametrize(
    "config", [None, {}, {"workspace": None}, {"workspace": {"scripts": "x"}}]
)
def test_from_config_tolerates_missing_blocks(config) -> None:
    assert ScriptLimits.from_config(config) == ScriptLimits()


def test_tool_schema_names_the_tool_with_optional_source_and_procedure() -> None:
    fn = SCRIPT_TOOL_SCHEMA["function"]
    assert SCRIPT_TOOL_NAME == "run_tool_script" == fn["name"]
    assert set(fn["parameters"]["properties"]) == {"source", "procedure_id"}
    assert not fn["parameters"].get("required")


def test_charge_without_budget_is_a_no_op() -> None:
    assert current_script_budget.get() is None
    charge_script(0.01)


def test_charge_inside_a_budget_adds_and_is_shared() -> None:
    budget = ScriptBudget(limit_usd=0.05)
    token = current_script_budget.set(budget)
    try:
        charge_script(0.01)
        charge_script(0.02)
    finally:
        current_script_budget.reset(token)
    assert budget.spent_usd == pytest.approx(0.03)
    assert not budget.exhausted
    budget.spent_usd = 0.05
    assert budget.exhausted


def test_in_script_call_defaults_false() -> None:
    assert in_script_call.get() is False


def test_script_error_is_a_ze_error_with_kind() -> None:
    err = ScriptError("limit", "limit: inner_calls (20)")
    assert isinstance(err, ZeError)
    assert err.kind == "limit"


def test_tool_flags_default_off_and_can_be_set() -> None:
    @tool(access=ToolAccess.READ, description="d")
    async def plain(x: str) -> str:
        return x

    @tool(access=ToolAccess.READ, description="d", produces_ui=True)
    async def drawer(x: str) -> str:
        return x

    @tool(access=ToolAccess.READ, description="d", egress=True)
    async def fetcher(url: str) -> str:
        return url

    assert (get_tool("plain").produces_ui, get_tool("plain").egress) == (False, False)
    assert get_tool("drawer").produces_ui is True
    assert get_tool("fetcher").egress is True
