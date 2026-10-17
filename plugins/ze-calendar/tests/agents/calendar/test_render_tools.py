"""The calendar agent renders timelines and forms (render follow-ups)."""

from ze_calendar.agents.calendar.agent import _AGENT_INSTRUCTIONS, CalendarAgent


def test_calendar_lists_timeline_and_form():
    assert {"render_timeline", "render_form"} <= set(CalendarAgent.tools)


def test_prompt_renders_only_for_dated_runs_and_forms():
    assert "render_timeline" in _AGENT_INSTRUCTIONS
    assert "render_form" in _AGENT_INSTRUCTIONS
    assert "stays prose" in _AGENT_INSTRUCTIONS


def test_prompt_asks_for_a_takeaway_line_after_a_render():
    assert "always write one short line of takeaway" in _AGENT_INSTRUCTIONS
