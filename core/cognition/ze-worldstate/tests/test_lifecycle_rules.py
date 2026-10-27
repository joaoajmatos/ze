"""Every (event, starting state) pair of the lifecycle table (data-model.md, SC-004)."""

from __future__ import annotations

import pytest

from ze_worldstate.lifecycle.rules import (
    CONFIDENCE_STAMP,
    EVENT_RULES,
    DeclaredStamp,
    LoopEvent,
    Verdict,
    allowed_from,
    verdict,
)
from ze_worldstate.types import LoopState

S, A, D, C, X = (
    LoopState.SUSPECTED,
    LoopState.ACTIVE,
    LoopState.DRIFTING,
    LoopState.CLOSED,
    LoopState.DROPPED,
)
MOVE, STAY, NONE, NO = (
    Verdict.MOVE,
    Verdict.STAY,
    Verdict.NO_CHANGE,
    Verdict.REFUSED,
)

# event: (to_state, verdicts in S, A, D, C, X order) — data-model.md "Events and rules"
TABLE: dict[LoopEvent, tuple[LoopState | None, tuple[Verdict, ...]]] = {
    LoopEvent.CONFIRM: (A, (MOVE, NO, NO, NO, NO)),
    LoopEvent.TRACK: (A, (MOVE, STAY, MOVE, NO, NO)),
    LoopEvent.NOTE_EVIDENCE: (None, (STAY, STAY, STAY, NO, NO)),
    LoopEvent.CORROBORATE: (None, (STAY, NO, NO, NO, NO)),
    LoopEvent.PROMOTE: (A, (MOVE, NONE, NONE, NO, NO)),
    LoopEvent.RESOLVE: (C, (MOVE, MOVE, MOVE, NONE, NONE)),
    LoopEvent.CLOSE: (C, (NO, MOVE, MOVE, NO, NO)),
    LoopEvent.DROP: (X, (MOVE, MOVE, MOVE, NO, NO)),
    LoopEvent.EXPIRE: (X, (MOVE, NONE, NONE, NONE, NONE)),
    LoopEvent.LINK: (None, (STAY, STAY, STAY, NONE, NONE)),
    LoopEvent.DECAY: (D, (STAY, MOVE, STAY, STAY, STAY)),
    LoopEvent.DRIFT: (D, (NONE, MOVE, NONE, NONE, NONE)),
}
STATES = (S, A, D, C, X)

ROWS = [
    (event, state, v)
    for event, (_, verdicts) in TABLE.items()
    for state, v in zip(STATES, verdicts, strict=True)
]


def test_every_event_has_a_rule():
    assert set(EVENT_RULES) == set(LoopEvent)
    assert len(ROWS) == 60


@pytest.mark.parametrize(
    "event,state,expected", ROWS, ids=lambda x: getattr(x, "value", x)
)
def test_verdict(event: LoopEvent, state: LoopState, expected: Verdict):
    assert verdict(event, state) is expected


@pytest.mark.parametrize("event", list(TABLE), ids=lambda e: e.value)
def test_to_state(event: LoopEvent):
    assert EVENT_RULES[event].to_state is TABLE[event][0]


def test_create_events_have_no_starting_state():
    suspected = EVENT_RULES[LoopEvent.CREATE_SUSPECTED]
    declared = EVENT_RULES[LoopEvent.CREATE_DECLARED]
    assert suspected.verdicts == {} and suspected.to_state is S
    assert declared.verdicts == {} and declared.to_state is A


def test_allowed_from_is_the_states_an_event_writes_from():
    assert allowed_from(LoopEvent.CONFIRM) == (S,)
    assert allowed_from(LoopEvent.TRACK) == (S, A, D)
    assert allowed_from(LoopEvent.PROMOTE) == (S,)
    assert allowed_from(LoopEvent.DRIFT) == (A,)
    assert allowed_from(LoopEvent.LINK) == (S, A, D)
    assert allowed_from(LoopEvent.CREATE_SUSPECTED) == ()


def _moves(from_state: LoopState, to_state: LoopState) -> set[LoopEvent]:
    return {
        event
        for event, rule in EVENT_RULES.items()
        if rule.verdicts.get(from_state) is Verdict.MOVE and rule.to_state is to_state
    }


def test_only_drift_and_decay_move_active_to_drifting():
    assert _moves(A, D) == {LoopEvent.DECAY, LoopEvent.DRIFT}


def test_only_track_revives_a_drifting_loop():
    assert _moves(D, A) == {LoopEvent.TRACK}


def test_only_resolve_moves_suspected_to_closed():
    assert _moves(S, C) == {LoopEvent.RESOLVE}


def test_only_confirm_track_and_promote_move_suspected_to_active():
    assert _moves(S, A) == {LoopEvent.CONFIRM, LoopEvent.TRACK, LoopEvent.PROMOTE}


def test_terminal_states_are_never_left():
    for state in (C, X):
        for rule in EVENT_RULES.values():
            assert rule.verdicts.get(state) is not Verdict.MOVE


def test_declared_stamp_constants():
    assert DeclaredStamp.CONFIDENCE == 0.9
    assert DeclaredStamp.DEFAULT_WINDOW_DAYS == 7


def test_declared_stamp_sql_stamps_all_four_fields():
    sql = DeclaredStamp.sql("$2", "$3")
    assert CONFIDENCE_STAMP.format(new="$2") in sql
    assert "confirmed_at = now()" in sql
    assert "drift_deadline = now() + make_interval(days => $3)" in sql
    assert "drift_rationale = NULL" in sql


def test_promote_keeps_its_own_confidence_rule():
    sql = DeclaredStamp.sql("GREATEST(confidence, $2)", "$3")
    assert "confidence = GREATEST(confidence, $2)" in sql
