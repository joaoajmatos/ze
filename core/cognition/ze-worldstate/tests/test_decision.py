import dataclasses

import pytest

from ze_worldstate.decision import CommitDecision, CommitResult


def test_decision_defaults():
    decision = CommitDecision("create_suspected", "implied")
    assert decision.consumed == frozenset()
    assert decision.title is None
    assert decision.window_days is None


def test_decision_is_frozen():
    decision = CommitDecision("hold", "trivial")
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.kind = "resolve"  # type: ignore[misc]


def test_result_defaults_to_no_loops():
    result = CommitResult("held", "trivial")
    assert result.loops == ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        result.outcome = "created"  # type: ignore[misc]
