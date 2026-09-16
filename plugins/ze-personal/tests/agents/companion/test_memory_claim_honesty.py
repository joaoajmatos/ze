from ze_agents.types import ToolCall
from ze_personal.agents.companion.honesty import (
    COULD_NOT_APPLY_CONSTRAINT,
    COULD_NOT_CANCEL,
    COULD_NOT_FORGET,
    COULD_NOT_STORE,
    COULD_NOT_STORE_OR_FORGET,
    enforce_memory_confirmations,
)


def _call(
    name: str,
    result: object,
    *,
    success: bool = True,
) -> ToolCall:
    return ToolCall(
        tool_name=name,
        args={},
        result=result,
        duration_ms=1,
        success=success,
    )


def test_unearned_remember_claim_is_stripped():
    gated = enforce_memory_confirmations("I'll remember that.", [])
    assert "remember" not in gated.lower()
    assert gated == COULD_NOT_STORE


def test_got_it_without_memory_claim_remains():
    gated = enforce_memory_confirmations("Got it.", [])
    assert gated == "Got it."


def test_ok_false_is_not_earned_even_if_toolcall_success():
    gated = enforce_memory_confirmations(
        "I'll remember that.",
        [_call("remember_fact", {"ok": False, "error": "nli blocked"}, success=True)],
    )
    assert "I'll remember" not in gated
    assert gated == COULD_NOT_STORE


def test_earned_ok_true_may_keep_remember_confirmation():
    text = "I'll remember that."
    gated = enforce_memory_confirmations(
        text,
        [_call("remember_fact", {"ok": True, "id": "abc"})],
    )
    assert gated == text


def test_json_string_ok_true_is_earned():
    gated = enforce_memory_confirmations(
        "I'll remember that.",
        [_call("remember_fact", '{"ok": true, "id": "abc"}')],
    )
    assert "I'll remember that." in gated


def test_unearned_forget_claim_is_stripped():
    gated = enforce_memory_confirmations("I've forgotten that.", [])
    assert "forgotten" not in gated.lower()
    assert "forgot" not in gated.lower()
    assert gated == COULD_NOT_FORGET


def test_ok_false_forget_is_not_earned():
    gated = enforce_memory_confirmations(
        "I forgot that.",
        [_call("forget_fact", {"ok": False, "error": "no matching fact"}, success=True)],
    )
    assert gated == COULD_NOT_FORGET


def test_earned_forget_may_keep_confirmation():
    text = "I've forgotten that."
    gated = enforce_memory_confirmations(
        text,
        [_call("forget_fact", {"ok": True, "ids": ["abc"]})],
    )
    assert gated == text


def test_mixed_sentence_with_extra_invented_memory_is_dropped():
    gated = enforce_memory_confirmations(
        "I'll remember the dark mode preference, and I also remembered you hate coffee.",
        [_call("remember_fact", {"ok": True, "id": "abc"})],
    )
    assert "hate coffee" not in gated
    assert "I'll remember" not in gated


def test_unearned_remember_and_forget_use_combined_fallback():
    gated = enforce_memory_confirmations(
        "I'll remember that. I forgot the old one.",
        [],
    )
    assert gated == COULD_NOT_STORE_OR_FORGET


def test_keeps_non_claim_sentences_around_stripped_claim():
    gated = enforce_memory_confirmations(
        "Got it. I'll remember that.",
        [],
    )
    assert gated == "Got it."
    assert "remember" not in gated.lower()


def test_unearned_veto_claim_is_stripped():
    gated = enforce_memory_confirmations(
        "I won't send that because of your constraint.",
        [],
    )
    assert gated == COULD_NOT_APPLY_CONSTRAINT
    assert "won't send" not in gated.lower()


def test_earned_veto_may_keep_claim():
    text = "I won't send that because of your constraint."
    gated = enforce_memory_confirmations(
        text,
        [
            _call(
                "send_email",
                {
                    "ok": False,
                    "veto": True,
                    "constraint_ids": ["c1"],
                    "error": "blocked",
                },
                success=False,
            )
        ],
    )
    assert gated == text


def test_got_it_without_veto_claim_remains():
    gated = enforce_memory_confirmations("Got it.", [])
    assert gated == "Got it."


def test_unsolicited_recitation_is_stripped():
    gated = enforce_memory_confirmations(
        "I remember that you like aisle seats. Want coffee?",
        [],
        user_text="How's the weather?",
    )
    assert "i remember that you" not in gated.lower()
    assert "aisle seats" not in gated.lower()
    assert "coffee" in gated.lower()


def test_asked_recall_may_state_facts():
    text = "I remember that you like aisle seats."
    gated = enforce_memory_confirmations(
        text,
        [],
        user_text="What do you know about my seating preference?",
    )
    assert gated == text


def test_earned_remember_confirmation_is_not_recitation():
    text = "I'll remember that."
    gated = enforce_memory_confirmations(
        text,
        [_call("remember_fact", {"ok": True, "id": "abc"})],
        user_text="Remember that I prefer aisle seats.",
    )
    assert gated == text


def test_earned_forget_confirmation_is_not_recitation():
    text = "I've forgotten that."
    gated = enforce_memory_confirmations(
        text,
        [_call("forget_fact", {"ok": True, "ids": ["abc"]})],
        user_text="Forget the aisle seat thing.",
    )
    assert gated == text


def test_open_item_paraphrase_is_not_stripped():
    text = "You still have an open loop about the job switch."
    gated = enforce_memory_confirmations(
        text,
        [],
        user_text="What's next today?",
    )
    assert gated == text


def test_task_paraphrase_is_not_stripped():
    text = "I remember that you asked me to send this email."
    gated = enforce_memory_confirmations(
        text,
        [],
        user_text="Send the email we drafted.",
    )
    assert gated == text


def test_in_turn_quote_is_not_stripped():
    text = "I remember that you like aisle seats."
    gated = enforce_memory_confirmations(
        text,
        [],
        user_text="As I told you, I like aisle seats — book the flight.",
    )
    assert "aisle seats" in gated.lower()


def test_recitation_only_fallback_is_not_could_not_store():
    gated = enforce_memory_confirmations(
        "I remember that you like aisle seats.",
        [],
        user_text="How's the weather?",
    )
    assert gated != COULD_NOT_STORE
    assert gated != COULD_NOT_FORGET
    assert "i remember that you" not in gated.lower()


def test_ingest_language_is_allowed():
    text = "Ingested the PDF and extracted 3 facts."
    gated = enforce_memory_confirmations(text, [], user_text="Ingest this PDF.")
    assert gated == text


def test_ingest_remember_claim_without_ok_is_stripped():
    gated = enforce_memory_confirmations(
        "I'll remember this PDF.",
        [],
        user_text="Ingest this PDF.",
    )
    assert "remember" not in gated.lower()
    assert gated == COULD_NOT_STORE


def test_mixed_ingest_and_earned_preference_does_not_confirm_the_file():
    gated = enforce_memory_confirmations(
        "I'll remember the aisle seats. I'll remember this PDF.",
        [_call("remember_fact", {"ok": True, "id": "abc"})],
        user_text="Ingest this PDF and remember that I prefer aisle seats.",
    )
    assert "aisle" in gated.lower()
    assert "pdf" not in gated.lower()


def test_nested_cancel_does_not_earn_forgotten_fact():
    gated = enforce_memory_confirmations(
        "I've forgotten that. Cancelled the dentist reminder.",
        [
            _call(
                "delegate_to_agent",
                {
                    "response": "Cancelled.",
                    "tool_calls": [
                        {
                            "tool_name": "cancel_reminder",
                            "args": {},
                            "result": {"cancelled": "Call the dentist"},
                            "duration_ms": 1,
                            "success": True,
                            "error": None,
                        }
                    ],
                },
            )
        ],
    )
    assert "forgotten" not in gated.lower()
    assert "forgot" not in gated.lower()
    assert "cancelled" in gated.lower()


def test_unearned_cancelled_claim_is_stripped():
    gated = enforce_memory_confirmations("I've cancelled your reminder.", [])
    assert gated == COULD_NOT_CANCEL


def test_forget_fact_ok_false_still_no_forgotten_claim():
    gated = enforce_memory_confirmations(
        "I've forgotten that.",
        [_call("forget_fact", {"ok": False, "error": "miss"}, success=True)],
    )
    assert gated == COULD_NOT_FORGET


def test_mixed_cancel_and_invented_forget_is_dropped():
    gated = enforce_memory_confirmations(
        "I've cancelled your reminder and I've forgotten that.",
        [
            _call(
                "delegate_to_agent",
                {
                    "response": "ok",
                    "tool_calls": [
                        {
                            "tool_name": "cancel_reminder",
                            "args": {},
                            "result": {"cancelled": "Call the dentist"},
                            "duration_ms": 1,
                            "success": True,
                            "error": None,
                        }
                    ],
                },
            )
        ],
    )
    assert "forgotten" not in gated.lower()
    assert "cancelled" not in gated.lower()
    assert gated == COULD_NOT_FORGET
