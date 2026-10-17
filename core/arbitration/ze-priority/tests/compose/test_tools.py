from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
import ze_priority
from ze_agents.tool import get_tool
from ze_components import context as ctx
from ze_priority.compose import Composition
from ze_priority.compose.tools import show_decisions, show_slipping, show_topic


def _composition(tag: str) -> Composition:
    return Composition(
        headline=tag.upper(),
        components=[
            {"type": "headline", "text": tag.upper()},
            {"type": "claim_card", "title": f"{tag} card"},
        ],
        summary=f"{tag} summary",
        sources_failed=["goals"],
    )


def _composer():
    composer = AsyncMock()
    composer.compose_slipping = AsyncMock(return_value=_composition("slipping"))
    composer.compose_decisions = AsyncMock(return_value=_composition("decisions"))
    composer.compose_topic = AsyncMock(return_value=_composition("topic"))
    return composer


async def _run(tool, **kwargs):
    token = ctx.begin_collection()
    try:
        result = await tool(**kwargs)
    finally:
        appended = ctx.collect_and_reset(token)
    return result, appended


async def test_each_tool_appends_the_composition_in_order_and_returns_the_summary():
    composer = _composer()
    for tool, kwargs, tag in (
        (show_slipping, {}, "slipping"),
        (show_decisions, {}, "decisions"),
        (show_topic, {"topic": "LedgerLite"}, "topic"),
    ):
        result, appended = await _run(
            tool, world_composer=composer, preset=None, **kwargs
        )
        assert result == {"summary": f"{tag} summary", "sources_failed": ["goals"]}
        assert [c["type"] for c in appended] == ["headline", "claim_card"]


@pytest.mark.parametrize(
    ("tool", "kwargs", "own_key"),
    [
        (show_slipping, {}, "slipping"),
        (show_decisions, {}, "decisions"),
        (show_topic, {"topic": "  LedgerLite   Launch "}, "topic:ledgerlite launch"),
    ],
)
async def test_the_tool_whose_preset_is_active_only_returns_the_summary(
    tool, kwargs, own_key
):
    result, appended = await _run(
        tool, world_composer=_composer(), preset=own_key, **kwargs
    )
    assert appended == []
    assert result["summary"].endswith("summary")


async def test_another_preset_or_none_still_appends():
    composer = _composer()
    for preset in (None, "decisions", "topic:ledgerlite"):
        _, appended = await _run(show_slipping, world_composer=composer, preset=preset)
        assert appended
    _, appended = await _run(
        show_topic, world_composer=composer, preset="topic:ledgerlite", topic="billing"
    )
    assert appended


async def test_show_topic_passes_the_topic_to_the_composer():
    composer = _composer()
    await _run(show_topic, world_composer=composer, preset=None, topic="LedgerLite")
    composer.compose_topic.assert_awaited_once_with("LedgerLite")


def test_tools_are_registered_as_read_tools_with_hidden_dependencies():
    ze_priority.import_agent_modules()
    for name in ("show_slipping", "show_decisions", "show_topic"):
        spec = get_tool(name)
        assert spec.access.value == "read"
        props = spec.llm_schema()["function"]["parameters"]["properties"]
        assert "world_composer" not in props and "preset" not in props
    topic_props = get_tool("show_topic").llm_schema()["function"]["parameters"][
        "properties"
    ]
    assert list(topic_props) == ["topic"]


def test_agent_module_paths_register_compose_tools_before_the_agent():
    paths = ze_priority.agent_module_paths()
    assert paths.index("ze_priority.compose.tools") < paths.index("ze_priority.agent")
