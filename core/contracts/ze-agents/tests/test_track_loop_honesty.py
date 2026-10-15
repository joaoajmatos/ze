from __future__ import annotations

import json

import pytest

from ze_agents.nested_tools import (
    COULD_NOT_ABANDON,
    COULD_NOT_CANCEL,
    COULD_NOT_CLOSE,
    COULD_NOT_TRACK,
    enforce_domain_cancel_confirmations,
    tracking_earned,
)
from ze_agents.types import ToolCall

_OK = {
    "ok": True,
    "outcome": "created",
    "id": "loop-1",
    "title": "Porto",
    "state": "active",
}
_FAIL = {"ok": False, "error": "db down"}


def _call(name: str, result) -> ToolCall:
    return ToolCall(tool_name=name, args={}, result=result, duration_ms=1, success=True)


def _nested(calls: list) -> ToolCall:
    return _call("delegate_to_agent", {"tool_calls": calls})


def _nested_item(result) -> dict:
    return {
        "tool_name": "track_loop",
        "args": {},
        "result": result,
        "duration_ms": 1,
        "success": True,
    }


def test_tracking_earned_top_level():
    assert tracking_earned([_call("track_loop", _OK)]) is True


def test_tracking_earned_nested_dict():
    delegate = _nested([_nested_item(_OK)])
    assert tracking_earned([delegate]) is True


def test_tracking_earned_nested_json_string():
    delegate = _call(
        "delegate_to_agent",
        json.dumps({"tool_calls": [_nested_item(json.dumps(_OK))]}),
    )
    assert tracking_earned([delegate]) is True


def test_tracking_earned_counts_confirm_loop():
    ok = {"ok": True, "id": "loop-1", "title": "Bank", "state": "active"}
    assert tracking_earned([_call("confirm_loop", ok)]) is True
    delegate = _nested([{**_nested_item(ok), "tool_name": "confirm_loop"}])
    assert tracking_earned([delegate]) is True
    assert tracking_earned([_call("confirm_loop", _FAIL)]) is False


@pytest.mark.parametrize(
    "sentence", ["I'll keep track of the bank switch.", "Vou acompanhar isso."]
)
def test_confirm_loop_earns_tracking_claims(sentence):
    ok = {"ok": True, "id": "loop-1", "title": "Bank", "state": "active"}
    assert (
        enforce_domain_cancel_confirmations(
            sentence, [_call("confirm_loop", ok)], strip_track_claims=True
        )
        == sentence
    )
    assert (
        enforce_domain_cancel_confirmations(
            sentence, [_call("confirm_loop", _FAIL)], strip_track_claims=True
        )
        == COULD_NOT_TRACK
    )


def test_tracking_earned_false_for_failure_missing_and_other_tools():
    assert tracking_earned([_call("track_loop", _FAIL)]) is False
    assert tracking_earned([]) is False
    assert tracking_earned([_call("close_loop", _OK)]) is False


_STRIP = [
    "I'll keep that on my radar.",
    "I'm keeping an eye on it.",
    "It's on your radar now.",
    "I've started tracking the Porto move.",
    "I'll keep track of it.",
    "I'll keep that on your radar.",
    "Fico atento a isso.",
    "Já está no meu radar.",
    "Vou acompanhar isso.",
    "Fica no teu radar.",
    "Estou a acompanhar o assunto.",
    "Vou acompanhar o assunto.",
]

_KEEP = [
    "Want me to keep this on your radar?",
    "You have 3 open loops: Renew passport.",
    "I could not track that.",
    "Tracking requires a clear title.",
    "Queres que fique atento?",
]


@pytest.mark.parametrize("sentence", _STRIP)
def test_unearned_track_claim_is_stripped(sentence):
    assert (
        enforce_domain_cancel_confirmations(sentence, [], strip_track_claims=True)
        == COULD_NOT_TRACK
    )


@pytest.mark.parametrize("sentence", _KEEP)
def test_offers_and_lists_are_not_claims(sentence):
    assert (
        enforce_domain_cancel_confirmations(sentence, [], strip_track_claims=True)
        == sentence
    )


@pytest.mark.parametrize("sentence", _STRIP)
def test_earned_track_claim_survives(sentence):
    earned = [_call("track_loop", _OK)]
    assert (
        enforce_domain_cancel_confirmations(sentence, earned, strip_track_claims=True)
        == sentence
    )


@pytest.mark.parametrize("sentence", _STRIP)
def test_default_does_not_strip_track_claims(sentence):
    assert enforce_domain_cancel_confirmations(sentence, []) == sentence


def test_mixed_close_and_unearned_track_strips_only_track():
    reply = "I closed the loop. I'll keep that on my radar."
    out = enforce_domain_cancel_confirmations(
        reply,
        [_call("close_loop", {"state": "closed"})],
        strip_track_claims=True,
    )
    assert out == "I closed the loop."


def test_existing_cancel_close_abandon_still_enforced():
    assert enforce_domain_cancel_confirmations("I've cancelled your reminder.", []) == (
        COULD_NOT_CANCEL
    )
    assert enforce_domain_cancel_confirmations("I dropped the concern.", []) == (
        COULD_NOT_CLOSE
    )
    assert enforce_domain_cancel_confirmations("I've abandoned the goal.", []) == (
        COULD_NOT_ABANDON
    )


def test_existing_earned_close_still_survives():
    assert (
        enforce_domain_cancel_confirmations(
            "I dropped the concern.", [_call("drop_loop", {"state": "dropped"})]
        )
        == "I dropped the concern."
    )
