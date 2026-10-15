from __future__ import annotations

import pytest

from ze_proactive.errors import PushPolicyError
from ze_proactive.push_kinds import QUIET_HOURS_SUMMARY, registered_push_kinds
from ze_proactive.types import PushKind


def test_identical_reregistration_is_noop():
    a = PushKind("t_same", "discretionary", "low", "tests")
    b = PushKind("t_same", "discretionary", "low", "tests")
    assert a == b
    assert registered_push_kinds()["t_same"] == a


@pytest.mark.parametrize(
    "push_class,urgency,source",
    [
        ("accountability", "low", "tests"),
        ("discretionary", "high", "tests"),
        ("discretionary", "low", "other"),
    ],
)
def test_conflicting_reregistration_raises(push_class, urgency, source):
    PushKind("t_conflict", "discretionary", "low", "tests")
    with pytest.raises(PushPolicyError):
        PushKind("t_conflict", push_class, urgency, source)


def test_registered_push_kinds_returns_copy():
    snapshot = registered_push_kinds()
    snapshot["bogus"] = QUIET_HOURS_SUMMARY
    assert "bogus" not in registered_push_kinds()


def test_quiet_hours_summary_declared():
    assert QUIET_HOURS_SUMMARY.push_class == "accountability"
    assert registered_push_kinds()["quiet_hours_summary"] == QUIET_HOURS_SUMMARY
