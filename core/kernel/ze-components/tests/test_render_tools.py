"""Render tools for the 191a primitives and their typed-action boundary."""

from __future__ import annotations

import pytest

import ze_components.tools  # noqa: F401 — registers the render tools
from ze_agents.errors import InvalidComponentError
from ze_agents.tool import ToolAccess, get_tool
from ze_components import context as ctx


def _props(name: str) -> dict:
    return get_tool(name).llm_schema()["function"]["parameters"]["properties"]


async def _render(name: str, **kwargs) -> dict:
    token = ctx.begin_collection()
    await get_tool(name).func(**kwargs)
    (component,) = ctx.collect_and_reset(token)
    return component


@pytest.mark.parametrize(
    "name", ["render_stat_row", "render_keyed_table", "render_sparkline"]
)
def test_new_render_tools_are_read_tools_without_claim_or_actions(name) -> None:
    spec = get_tool(name)
    assert spec.access is ToolAccess.READ
    schema = str(spec.llm_schema())
    assert "claim" not in _props(name)
    assert "row_actions" not in schema
    for kind in ("'tool'", "'navigate'", "'compose'"):
        assert kind not in schema


async def test_stat_row_builds_items() -> None:
    node = await _render(
        "render_stat_row",
        items=[{"label": "Spend", "value": "$4", "delta": "+1", "direction": "up"}],
    )
    assert node["type"] == "stat_row"
    assert node["items"][0]["direction"] == "up"


async def test_stat_row_over_six_items_raises() -> None:
    items = [{"label": str(i), "value": "1"} for i in range(7)]
    with pytest.raises(InvalidComponentError):
        await get_tool("render_stat_row").func(items=items)


async def test_keyed_table_keeps_keys() -> None:
    node = await _render(
        "render_keyed_table",
        headers=["Name"],
        rows=[["a"], ["b"]],
        keys=["k1", "k2"],
    )
    assert node["type"] == "table" and node["keys"] == ["k1", "k2"]


async def test_keyed_table_with_mismatched_keys_raises() -> None:
    with pytest.raises(InvalidComponentError):
        await get_tool("render_keyed_table").func(
            headers=["Name"], rows=[["a"], ["b"]], keys=["k1"]
        )


async def test_sparkline_over_sixty_points_keeps_the_latest_sixty() -> None:
    node = await _render("render_sparkline", label="Spend", points=list(range(75)))
    assert node["type"] == "sparkline"
    assert len(node["points"]) == 60
    assert node["points"][-1] == 74


def _ask_values(node: object) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        action = node.get("action")
        if isinstance(action, dict) and action.get("kind") == "ask":
            found.append(action["text"])
        for value in node.values():
            found.extend(_ask_values(value))
    elif isinstance(node, list):
        for item in node:
            found.extend(_ask_values(item))
    return found


async def test_confirm_keeps_label_value_style_and_builds_ask_actions() -> None:
    props = _props("render_confirm")["actions"]
    assert "value" in str(props) and "label" in str(props)
    node = await _render(
        "render_confirm",
        prompt="Send it?",
        actions=[
            {"label": "Yes", "value": "yes, send", "style": "primary"},
            {"label": "No", "value": "no"},
        ],
    )
    assert _ask_values(node) == ["yes, send", "no"]


async def test_choice_group_options_become_ask_actions() -> None:
    node = await _render(
        "render_choice_group",
        id="g",
        title="Pick",
        options=[{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
    )
    assert _ask_values(node) == ["a", "b"]


@pytest.mark.parametrize("value", ["", "x" * 501])
async def test_confirm_with_a_bad_value_is_a_tool_error(value) -> None:
    with pytest.raises(InvalidComponentError):
        await get_tool("render_confirm").func(
            prompt="p", actions=[{"label": "Go", "value": value}]
        )


@pytest.mark.parametrize("value", ["", "x" * 501])
async def test_choice_group_with_a_bad_id_is_a_tool_error(value) -> None:
    with pytest.raises(InvalidComponentError):
        await get_tool("render_choice_group").func(
            id="g", title="t", options=[{"id": value, "label": "A"}]
        )
