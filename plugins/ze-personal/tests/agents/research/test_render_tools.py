"""The research agent renders tables and charts when the data is tabular (render follow-ups)."""

from ze_personal.agents.research.agent import _AGENT_INSTRUCTIONS, ResearchAgent


def test_research_lists_table_and_chart_next_to_web_search():
    assert {"openrouter:web_search", "render_table", "render_chart"} <= set(
        ResearchAgent.tools
    )


def test_prompt_keeps_prose_the_default():
    assert "Prose is the default" in _AGENT_INSTRUCTIONS
    assert "render_table" in _AGENT_INSTRUCTIONS


def test_prompt_asks_for_a_takeaway_line_after_a_render():
    assert "write one short line" in _AGENT_INSTRUCTIONS
    assert "using only the" in _AGENT_INSTRUCTIONS
