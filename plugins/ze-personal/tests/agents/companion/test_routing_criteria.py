"""Companion and research declare disjoint routing lanes (phase 167)."""

from ze_personal.agents.companion.agent import CompanionAgent
from ze_personal.agents.research.agent import ResearchAgent


def test_companion_description_no_longer_claims_explanations():
    assert "explain" not in CompanionAgent.description.lower()


def test_companion_criteria_sends_factual_work_to_the_web_agent():
    text = CompanionAgent.routing_criteria
    assert "Not for" in text and "web" in text


def test_research_declares_routing_criteria_and_keeps_description():
    assert ResearchAgent.routing_criteria.strip()
    assert "explain X" in ResearchAgent.description
