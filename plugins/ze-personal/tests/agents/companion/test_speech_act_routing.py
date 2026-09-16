from ze_personal.agents.companion.agent import CompanionAgent, _AGENT_INSTRUCTIONS

# 153 conductor embedding — companion description must mention coordination.
_COMPANION_DESCRIPTION_SNAPSHOT = """
      Chat, conversation, reasoning, and coordinating specialists in one reply.
      Use for: greetings, emotional check-ins, brainstorming, writing help,
      "explain X", "help me think through X", "what can you do", biography
      questions, and work that needs more than one specialist in sequence
      (calendar then email, research then a message). You speak; specialists do not.
      Scale effort: one specialist for a single-domain ask — not a four-step plan
      for "what's on Tuesday". Not for web search, calendar, email, reminders, or
      news as your own tools — delegate those. Timed "remember to / remind me" is
      a reminder. Multi-week outcomes go to goals. Lingering concerns without a
      fire time are open loops.
    """


def test_companion_keeps_remember_forget_and_delegate():
    assert "remember_fact" in CompanionAgent.tools
    assert "forget_fact" in CompanionAgent.tools
    assert "delegate_to_agent" in CompanionAgent.tools
    assert "set_reminder" not in CompanionAgent.tools


def test_companion_description_mentions_coordination():
    assert CompanionAgent.description == _COMPANION_DESCRIPTION_SNAPSHOT
    assert "coordinating" in CompanionAgent.description.lower()
    assert "sequence" in CompanionAgent.description.lower()


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


def test_instructions_use_objective_not_task_context():
    text = _AGENT_INSTRUCTIONS.lower()
    assert "objective" in text
    assert "prior_outputs" in text
    assert "do not pass task or context" in text


def test_instructions_route_cancel_speech_away_from_forget_fact():
    text = _AGENT_INSTRUCTIONS.lower()
    assert "forget the dentist" in text
    assert "delegate_to_agent" in text
    assert "objective" in text
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


def test_conductor_instructions_scale_and_no_auto_workflow():
    text = _AGENT_INSTRUCTIONS.lower()
    assert "you own the user-facing reply" in text
    assert "not a plan you must execute as a dag" in text
    assert "scale effort" in text
    assert "durable workflow" in text
    assert "ze_calendar" not in text
    assert "from ze_calendar" not in CompanionAgent.__module__
