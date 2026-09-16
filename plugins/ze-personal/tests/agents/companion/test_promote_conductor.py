from ze_core.orchestration.promote import classify_promote_kind, should_offer_promote
from ze_personal.agents.companion.agent import CompanionAgent, _AGENT_INSTRUCTIONS


def test_companion_does_not_list_create_goal_or_workflow():
    assert "create_goal" not in CompanionAgent.tools
    assert "create_workflow" not in CompanionAgent.tools
    assert "delegate_to_agent" in CompanionAgent.tools


def test_promote_instructions_keep_going_uses_delegate_and_152():
    text = _AGENT_INSTRUCTIONS.lower()
    assert "keep going" in text
    assert "delegate_to_agent" in text
    assert "create_goal" in text
    assert "create_workflow" in text
    assert "prior_outputs" in text
    assert "never both" in text
    assert "memory_procedures" in text
    assert "capability confirmation still applies" in text


def test_successful_all_done_conductor_does_not_offer():
    ledger = [
        {"agent": "research", "status": "done"},
        {"agent": "messenger", "status": "done"},
    ]
    assert should_offer_promote(ledger) is False
    text = _AGENT_INSTRUCTIONS.lower()
    assert "do not auto-offer promote when every ledger step is done" in text


def test_decline_means_instructions_forbid_insert_until_accept():
    text = _AGENT_INSTRUCTIONS.lower()
    assert "do not create either until the user accepts" in text


def test_goal_vs_workflow_ambiguous_asks_once():
    assert classify_promote_kind("keep going on this") == "ask"
    assert classify_promote_kind("keep going on this as a goal") == "goal"
    assert classify_promote_kind("keep going on this as a workflow") == "workflow"
    assert (
        classify_promote_kind(
            "keep going on this as a goal and keep going on this as a workflow"
        )
        == "ask"
    )
