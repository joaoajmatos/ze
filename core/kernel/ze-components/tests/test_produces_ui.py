from __future__ import annotations

from ze_agents.tool import ToolAccess, _tools, get_tool, registered_tools, tool

import ze_components.tools  # noqa: F401 — ensures render tools are registered


def test_every_render_tool_produces_ui():
    renders = {
        name: spec
        for name, spec in registered_tools().items()
        if name.startswith("render_")
    }
    assert renders, "render tools did not register"
    missing = sorted(
        name for name, spec in renders.items() if spec.produces_ui is not True
    )
    assert missing == []


def test_plain_read_tool_does_not_produce_ui():
    @tool(access=ToolAccess.READ, description="Look up a value.")
    async def _flags_probe_plain_read(query: str) -> dict:
        return {"query": query}

    try:
        assert get_tool("_flags_probe_plain_read").produces_ui is False
    finally:
        _tools.pop("_flags_probe_plain_read", None)
