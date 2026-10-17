"""The finance agent renders metrics and charts (render follow-ups)."""

from ze_finance.agents.finance.agent import _AGENT_INSTRUCTIONS, FinanceAgent


def test_finance_lists_metric_and_chart_beside_confirm_and_list():
    assert {
        "render_metric",
        "render_chart",
        "render_confirm",
        "render_list",
    } <= set(FinanceAgent.tools)


def test_prompt_never_invents_figures():
    assert "render_metric" in _AGENT_INSTRUCTIONS
    assert "never invent" in _AGENT_INSTRUCTIONS
