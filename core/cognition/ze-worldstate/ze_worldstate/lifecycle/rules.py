"""Which moves an open loop may make, and the declared stamp. Pure: no I/O.

`EVENT_RULES` is the one table. `LoopLifecycle` builds its SQL guards from
`allowed_from`; the table test walks every (event, state) pair.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

from ze_worldstate.types import LoopState


class LoopEvent(StrEnum):
    CREATE_SUSPECTED = "create_suspected"
    CREATE_DECLARED = "create_declared"
    CONFIRM = "confirm"
    TRACK = "track"
    NOTE_EVIDENCE = "note_evidence"
    CORROBORATE = "corroborate"
    PROMOTE = "promote"
    RESOLVE = "resolve"
    CLOSE = "close"
    DROP = "drop"
    EXPIRE = "expire"
    LINK = "link"
    DECAY = "decay"
    DRIFT = "drift"


class Verdict(StrEnum):
    """What an event does from one starting state."""

    MOVE = "move"  # to EventRule.to_state
    STAY = "stay"  # writes, state unchanged
    NO_CHANGE = "no_change"  # returns without writing or raising
    REFUSED = "refused"  # raises InvalidLoopTransitionError


@dataclass(frozen=True)
class EventRule:
    event: LoopEvent
    verdicts: Mapping[LoopState, Verdict]  # empty for the create events
    to_state: LoopState | None


S, A, D, C, X = (
    LoopState.SUSPECTED,
    LoopState.ACTIVE,
    LoopState.DRIFTING,
    LoopState.CLOSED,
    LoopState.DROPPED,
)
_MOVE, _STAY, _NONE, _NO = (
    Verdict.MOVE,
    Verdict.STAY,
    Verdict.NO_CHANGE,
    Verdict.REFUSED,
)


def _rule(
    event: LoopEvent,
    to_state: LoopState | None,
    s: Verdict,
    a: Verdict,
    d: Verdict,
    c: Verdict,
    x: Verdict,
) -> EventRule:
    return EventRule(event, {S: s, A: a, D: d, C: c, X: x}, to_state)


EVENT_RULES: Mapping[LoopEvent, EventRule] = {
    LoopEvent.CREATE_SUSPECTED: EventRule(LoopEvent.CREATE_SUSPECTED, {}, S),
    LoopEvent.CREATE_DECLARED: EventRule(LoopEvent.CREATE_DECLARED, {}, A),
    LoopEvent.CONFIRM: _rule(LoopEvent.CONFIRM, A, _MOVE, _NO, _NO, _NO, _NO),
    # A is a reinforce (state kept); D is a revive, the only edge into active from drifting.
    LoopEvent.TRACK: _rule(LoopEvent.TRACK, A, _MOVE, _STAY, _MOVE, _NO, _NO),
    LoopEvent.NOTE_EVIDENCE: _rule(
        LoopEvent.NOTE_EVIDENCE, None, _STAY, _STAY, _STAY, _NO, _NO
    ),
    LoopEvent.CORROBORATE: _rule(LoopEvent.CORROBORATE, None, _STAY, _NO, _NO, _NO, _NO),
    # A and D mean another inflow promoted first: the source row is kept, nothing else is written.
    LoopEvent.PROMOTE: _rule(LoopEvent.PROMOTE, A, _MOVE, _NONE, _NONE, _NO, _NO),
    LoopEvent.RESOLVE: _rule(LoopEvent.RESOLVE, C, _MOVE, _MOVE, _MOVE, _NONE, _NONE),
    LoopEvent.CLOSE: _rule(LoopEvent.CLOSE, C, _NO, _MOVE, _MOVE, _NO, _NO),
    LoopEvent.DROP: _rule(LoopEvent.DROP, X, _MOVE, _MOVE, _MOVE, _NO, _NO),
    LoopEvent.EXPIRE: _rule(LoopEvent.EXPIRE, X, _MOVE, _NONE, _NONE, _NONE, _NONE),
    LoopEvent.LINK: _rule(LoopEvent.LINK, None, _STAY, _STAY, _STAY, _NONE, _NONE),
    # Only an active loop changes state; every other state takes the confidence alone.
    LoopEvent.DECAY: _rule(LoopEvent.DECAY, D, _STAY, _MOVE, _STAY, _STAY, _STAY),
    LoopEvent.DRIFT: _rule(LoopEvent.DRIFT, D, _NONE, _MOVE, _NONE, _NONE, _NONE),
}


def verdict(event: LoopEvent, state: LoopState) -> Verdict:
    return EVENT_RULES[event].verdicts[state]


def allowed_from(event: LoopEvent) -> tuple[LoopState, ...]:
    """States an event writes from (MOVE or STAY): the SQL guard's `state = ANY(...)`."""
    return tuple(
        state
        for state, v in EVENT_RULES[event].verdicts.items()
        if v in (Verdict.MOVE, Verdict.STAY)
    )


# Postgres evaluates every SET expression against the old row, so the prior
# reads the value before this write. Only a real change stamps.
CONFIDENCE_STAMP: Final = (
    "confidence_prior = CASE WHEN confidence IS DISTINCT FROM {new} "
    "THEN confidence ELSE confidence_prior END, "
    "confidence_changed_at = CASE WHEN confidence IS DISTINCT FROM {new} "
    "THEN now() ELSE confidence_changed_at END, "
    "confidence = {new}"
)

SUSPECTED_CONFIDENCE: Final = 0.3


class DeclaredStamp:
    """What a user-stated loop is stamped with, defined once (FR-004)."""

    CONFIDENCE: Final = 0.9
    DEFAULT_WINDOW_DAYS: Final = 7

    @staticmethod
    def sql(confidence_expr: str, window_param: str) -> str:
        """SET fragment: confidence (with its prior), confirmed_at, deadline, no rationale.

        Promote passes `GREATEST(confidence, $c)` as its own confidence rule.
        The caller sets `updated_at`; `LoopLifecycle._write` does for every event.
        """
        return (
            CONFIDENCE_STAMP.format(new=confidence_expr)
            + ", confirmed_at = now()"
            + f", drift_deadline = now() + make_interval(days => {window_param})"
            + ", drift_rationale = NULL"
        )
