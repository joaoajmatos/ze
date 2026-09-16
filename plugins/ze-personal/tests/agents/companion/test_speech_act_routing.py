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
    assert "loops" in text
    assert "ingest" in text
    assert "reviewed constraints" in text
    assert "file as a whole" in text
    assert "extraction" in text or "extracted" in text


def test_instructions_do_not_defer_mail_veto():
    text = _AGENT_INSTRUCTIONS.lower()
    assert "do not block mail/calendar" not in text
    assert "later phase" not in text
    assert "veto" in text


def test_instructions_route_cancel_speech_away_from_forget_fact():
    text = _AGENT_INSTRUCTIONS.lower()
    assert "forget the dentist" in text
    assert "delegate_to_agent" in text
    assert "loops" in text
    assert "do not call forget_fact" in text
    assert "two named targets" in text
    assert "never dual-write" in text


def test_biography_forget_stays_forget_fact():
    text = _AGENT_INSTRUCTIONS.lower()
    assert "aisle seats" in text
    assert "forget_fact" in text
    assert "biography" in text


def test_vague_dentist_cancel_is_not_batch_forget():
    text = _AGENT_INSTRUCTIONS.lower()
    assert "never one batch retract" in text
    assert "forget_fact" in CompanionAgent.tools
    assert "cancel_reminder" not in CompanionAgent.tools
    assert "set_reminder" not in CompanionAgent.tools
