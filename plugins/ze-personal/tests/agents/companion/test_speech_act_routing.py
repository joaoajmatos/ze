from ze_personal.agents.companion.agent import CompanionAgent, _AGENT_INSTRUCTIONS


def test_companion_keeps_remember_forget_and_delegate():
    assert "remember_fact" in CompanionAgent.tools
    assert "forget_fact" in CompanionAgent.tools
    assert "delegate_to_agent" in CompanionAgent.tools
    assert "set_reminder" not in CompanionAgent.tools


def test_instructions_route_timed_remember_to_reminders_not_facts():
    text = _AGENT_INSTRUCTIONS.lower()
    assert "time beats biography" in text
    assert "reminders" in text
    assert "remember_fact" in text
    assert "forget_fact" in text
    assert "goals" in text
    assert "open loop" in text
    assert "ingest" in text
    assert "later phase" in text


def test_instructions_do_not_tell_companion_to_own_mail_veto():
    assert "do not block mail/calendar" in _AGENT_INSTRUCTIONS.lower()
