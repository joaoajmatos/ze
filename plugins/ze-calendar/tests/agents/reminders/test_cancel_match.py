from uuid import uuid4

from ze_agents.label_match import Ambiguous, Miss, Unique, precise_label_match
from ze_calendar.agents.reminders.agent import _AGENT_INSTRUCTIONS


def test_instructions_require_unique_label_cancel():
    text = _AGENT_INSTRUCTIONS.lower()
    assert "list_reminders" in text
    assert "unique" in text
    assert "at most" in text
    assert "never batch" in text


def test_two_dentist_labels_are_not_both_unique():
    result = precise_label_match(
        "forget the dentist",
        [(uuid4(), "Call the dentist"), (uuid4(), "Dentist bill")],
    )
    assert isinstance(result, (Ambiguous, Miss))


def test_single_dentist_label_is_unique():
    dentist = uuid4()
    result = precise_label_match(
        "forget the dentist",
        [(dentist, "Call the dentist"), (uuid4(), "buy milk")],
    )
    assert isinstance(result, Unique)
    assert result.item_id == dentist
