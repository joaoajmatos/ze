from ze_core.orchestration.promote import (
    classify_promote_kind,
    confirmation_timeout_message,
    ledger_is_unfinished,
    should_offer_promote,
)


def test_unfinished_ledger_should_offer_and_does_not_need_a_store():
    ledger = [
        {"agent": "research", "status": "done"},
        {"agent": "messenger", "status": "planned"},
    ]
    assert ledger_is_unfinished(ledger) is True
    assert should_offer_promote(ledger) is True


def test_all_done_ledger_does_not_offer():
    ledger = [
        {"agent": "research", "status": "done"},
        {"agent": "messenger", "status": "done"},
    ]
    assert ledger_is_unfinished(ledger) is False
    assert should_offer_promote(ledger) is False


def test_empty_ledger_does_not_offer():
    assert should_offer_promote([]) is False
    assert should_offer_promote(None) is False


def test_ask_user_same_reply_does_not_stack_promote():
    ledger = [{"agent": "research", "status": "ask_user"}]
    assert should_offer_promote(ledger) is False
    assert should_offer_promote(ledger, timeout_or_abort=True) is True


def test_skipped_and_denied_are_terminal():
    ledger = [
        {"agent": "calendar", "status": "skipped"},
        {"agent": "messenger", "status": "denied"},
    ]
    assert ledger_is_unfinished(ledger) is False
    assert should_offer_promote(ledger) is False


def test_timeout_message_offers_when_unfinished_without_creating():
    ledger = [{"agent": "calendar", "status": "awaiting_confirmation"}]
    text = confirmation_timeout_message(ledger)
    assert "elapsed" in text
    assert "goal" in text
    assert "workflow" in text
    assert "not until you accept" in text


def test_timeout_message_stays_generic_when_finished():
    ledger = [{"agent": "calendar", "status": "done"}]
    text = confirmation_timeout_message(ledger)
    assert text.endswith("try again.")
    assert "workflow" not in text


def test_classify_promote_kind_never_both():
    assert classify_promote_kind("keep going on this as a goal") == "goal"
    assert classify_promote_kind("run this unattended every week") == "workflow"
    assert (
        classify_promote_kind("keep going on this as a goal and also as a workflow")
        == "ask"
    )
    assert classify_promote_kind("keep going on this") == "ask"
