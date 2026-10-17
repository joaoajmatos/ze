"""The companion can show structured results with the render_* tools (CF-02 U-01)."""

import ze_components.tools  # noqa: F401 — registers the render_* tools

from ze_agents.tool import ToolAccess, get_tool
from ze_personal.agents.companion.agent import _AGENT_INSTRUCTIONS, CompanionAgent

RENDER_TOOLS = (
    "render_table",
    "render_chart",
    "render_metric",
    "render_timeline",
    "render_form",
    "render_choice_group",
    "render_consent",
    "render_connect_account",
    "render_review",
    "render_connections",
)


def test_companion_lists_the_ten_render_tools():
    assert set(RENDER_TOOLS) <= set(CompanionAgent.tools)


def test_companion_keeps_its_memory_and_delegate_tools():
    assert {"remember_fact", "forget_fact", "delegate_to_agent"} <= set(
        CompanionAgent.tools
    )


def test_every_render_tool_is_registered_and_read_only():
    # READ keeps Retry eligibility (165/180) and the 181 write gate unchanged.
    for name in RENDER_TOOLS:
        spec = get_tool(name)
        assert spec.access is ToolAccess.READ, name
        assert spec.llm_schema()["function"]["name"] == name


def test_prompt_says_when_to_render_and_keeps_prose_the_default():
    text = _AGENT_INSTRUCTIONS
    assert "render_chart" in text and "render_table" in text
    assert "Prose is the default" in text
    assert "never narrate" in text.lower()


def test_prompt_sends_consent_requests_to_render_consent():
    text = _AGENT_INSTRUCTIONS
    assert "call render_consent with one scope per permission" in text
    assert "render_connect_account for the account" in text
