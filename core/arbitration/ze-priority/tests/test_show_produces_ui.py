from __future__ import annotations

import pytest

from ze_agents.tool import get_tool

import ze_priority.compose.tools  # noqa: F401 — registers the show_* tools


@pytest.mark.parametrize("name", ["show_slipping", "show_decisions", "show_topic"])
def test_show_tools_produce_ui(name: str):
    assert get_tool(name).produces_ui is True
