"""effect_imperative and ensure_declined_lines (Phase 181)."""

from __future__ import annotations

import pytest

from ze_agents.effects import effect_imperative, ensure_declined_lines


@pytest.mark.parametrize(
    ("past", "imperative"),
    [
        ("deleted a calendar event", "delete a calendar event"),
        ("sent an email", "send an email"),
        ("ran a workspace command", "run a workspace command"),
        ("forgot a memory", "forget a memory"),
        ("ingested a web page", "ingest a web page"),
        ("set a reminder", "set a reminder"),
        (
            "changed what Ze treats as most urgent",
            "change what Ze treats as most urgent",
        ),
    ],
)
def test_known_phrases(past: str, imperative: str) -> None:
    assert effect_imperative(past) == imperative


def test_unknown_regular_verbs_use_the_rule() -> None:
    assert effect_imperative("renamed a file") == "rename a file"
    assert effect_imperative("copied a file") == "copy a file"
    assert effect_imperative("stopped a job") == "stop a job"


def _row(outcome: str, effect: str = "delete a calendar event") -> dict:
    return {"outcome": outcome, "effect": effect}


def test_adds_one_line_per_declined_item() -> None:
    reply = ensure_declined_lines(
        "Anything else?",
        [_row("denied"), _row("timed_out", "send an email"), _row("approved", "x y")],
    )
    assert reply.count("Okay, I didn't") == 2
    assert "Okay, I didn't delete a calendar event." in reply
    assert "Okay, I didn't send an email." in reply


def test_no_line_when_the_reply_already_says_it() -> None:
    reply = "Okay, I didn't delete a calendar event."
    assert ensure_declined_lines(reply, [_row("denied")]) == reply
    reply = "I will not Delete a Calendar Event for you."
    assert ensure_declined_lines(reply, [_row("denied")]) == reply


def test_no_line_for_approved_items() -> None:
    assert ensure_declined_lines("Done.", [_row("approved"), _row("edited")]) == "Done."


def test_duplicate_effects_collapse() -> None:
    reply = ensure_declined_lines("", [_row("denied"), _row("superseded")])
    assert reply == "Okay, I didn't delete a calendar event."
