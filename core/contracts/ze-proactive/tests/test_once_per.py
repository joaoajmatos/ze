from __future__ import annotations

from datetime import timedelta

import pytest

from ze_proactive.errors import PushPolicyError
from ze_proactive.types import OncePer, is_sent


def test_empty_key_is_refused():
    with pytest.raises(PushPolicyError):
        OncePer("")


@pytest.mark.parametrize("within", [timedelta(0), timedelta(hours=-1)])
def test_non_positive_window_is_refused(within):
    with pytest.raises(PushPolicyError):
        OncePer("k", within=within)


def test_no_window_means_once_ever():
    assert OncePer("k").within is None


def test_window_is_kept():
    assert OncePer("k", within=timedelta(days=7)).within == timedelta(days=7)


@pytest.mark.parametrize(
    "outcome,expected",
    [
        ("delivered", True),
        ("held", True),
        ("suppressed_budget", False),
        ("deduped", False),
        ("failed", False),
        (None, False),
    ],
)
def test_is_sent_only_for_delivered_and_held(outcome, expected):
    assert is_sent(outcome) is expected
