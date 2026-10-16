"""Every commitment label has a reader in `decide()` (phase 173, FR-016)."""

from __future__ import annotations

import pytest
from ze_agents.nested_tools import TurnCreation
from ze_memory.types import CommitmentChoice

from tests.commitment_fixtures import _CAL, make
from ze_worldstate.commitment_judge import decide

_ABOVE_EVERY_BAR = dict(
    conf=0.99, family_conf=0.99, bio=0.99, concern=0.99, explicit=0.99, resolves=0.0
)
_EXPECTED = {
    CommitmentChoice.REMINDER: ("hold", "reminder_not_created"),
    CommitmentChoice.LOOP: ("create_loop_declared", "explicit"),
    CommitmentChoice.GOAL: ("hold", "goal_not_created"),
    CommitmentChoice.WAITING_ON: ("hold", "waiting_on"),
    CommitmentChoice.FACT: ("persist_fact", "persist"),
    CommitmentChoice.FORGET: ("hold", "forget"),
    CommitmentChoice.INGEST: ("hold", "ingest"),
    CommitmentChoice.CLARIFY: ("hold", "clarify"),
    CommitmentChoice.NONE: ("hold", "none"),
}


def _decide(choice: CommitmentChoice):
    return decide(make(choice.value, **_ABOVE_EVERY_BAR), _CAL, TurnCreation(), False)


def test_expectations_cover_every_label():
    assert set(_EXPECTED) == set(CommitmentChoice)


@pytest.mark.parametrize("choice", list(CommitmentChoice), ids=lambda c: c.value)
def test_every_label_gets_its_own_outcome(choice):
    out = _decide(choice)
    assert (out.kind, out.reason) == _EXPECTED[choice]


def test_no_two_labels_share_an_outcome_or_a_hold_reason():
    outcomes = {c: _decide(c) for c in CommitmentChoice}
    pairs = [(o.kind, o.reason) for o in outcomes.values()]
    assert len(set(pairs)) == len(pairs)
    holds = [o.reason for o in outcomes.values() if o.kind == "hold"]
    assert len(set(holds)) == len(holds)
    assert all(o.kind != "fallback" for o in outcomes.values())
