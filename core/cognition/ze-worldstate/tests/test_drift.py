from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from ze_worldstate.drift import (
    DEFAULT_DRIFT_WINDOW_DAYS,
    compose_absence_rationale,
    compose_contradiction_rationale,
    compute_drift_deadline,
    is_drift_eligible,
)
from ze_worldstate.types import LoopClaimKind, LoopProvenance, LoopState, OpenLoop


def _loop(**overrides) -> OpenLoop:
    defaults = dict(
        id=uuid4(),
        title="Send Maria the contract",
        claim_kind=LoopClaimKind.PRIORITY,
        provenance=LoopProvenance.USER_DECLARED,
        confidence=0.9,
        state=LoopState.ACTIVE,
    )
    defaults.update(overrides)
    return OpenLoop(**defaults)


def test_compute_drift_deadline_uses_default_window():
    confirmed_at = datetime(2026, 7, 10, tzinfo=timezone.utc)
    deadline = compute_drift_deadline(confirmed_at)
    assert deadline == confirmed_at + timedelta(days=DEFAULT_DRIFT_WINDOW_DAYS)


def test_compute_drift_deadline_uses_implied_window():
    confirmed_at = datetime(2026, 7, 10, tzinfo=timezone.utc)
    deadline = compute_drift_deadline(confirmed_at, implied_window_days=2)
    assert deadline == confirmed_at + timedelta(days=2)


def test_eligible_when_active_and_deadline_passed():
    now = datetime.now(timezone.utc)
    loop = _loop(drift_deadline=now - timedelta(seconds=1))
    assert is_drift_eligible(loop, now) is True


def test_eligible_at_the_deadline_instant():
    now = datetime.now(timezone.utc)
    assert is_drift_eligible(_loop(drift_deadline=now), now) is True


def test_not_eligible_before_the_deadline():
    now = datetime.now(timezone.utc)
    assert is_drift_eligible(_loop(drift_deadline=now + timedelta(days=1)), now) is False


def test_naive_deadline_is_treated_as_utc():
    now = datetime.now(timezone.utc)
    naive_past = (now - timedelta(days=1)).replace(tzinfo=None)
    assert is_drift_eligible(_loop(drift_deadline=naive_past), now) is True


def test_updated_at_and_confirmed_at_are_ignored():
    now = datetime.now(timezone.utc)
    loop = _loop(
        drift_deadline=now - timedelta(days=1),
        confirmed_at=now - timedelta(days=10),
        updated_at=now,
    )
    assert is_drift_eligible(loop, now) is True


def test_not_eligible_when_not_active():
    now = datetime.now(timezone.utc)
    for state in (LoopState.SUSPECTED, LoopState.DRIFTING, LoopState.CLOSED, LoopState.DROPPED):
        assert is_drift_eligible(_loop(state=state, drift_deadline=now - timedelta(days=1)), now) is False


def test_not_eligible_without_a_deadline():
    assert is_drift_eligible(_loop(drift_deadline=None)) is False


def test_compose_absence_rationale_cites_the_deadline():
    loop = _loop(drift_deadline=datetime(2026, 7, 17, tzinfo=timezone.utc))
    rationale = compose_absence_rationale(loop)
    assert "2026-07-17" in rationale
    assert "No corroborating evidence" in rationale
    assert "before the implied window elapsed" in rationale
    assert "confirmation" not in rationale


def test_compose_absence_rationale_without_a_deadline():
    assert "unknown" in compose_absence_rationale(_loop(drift_deadline=None))


def test_compose_contradiction_rationale_cites_evidence():
    evidence_id = uuid4()
    rationale = compose_contradiction_rationale("fact", evidence_id)
    assert str(evidence_id) in rationale
    assert "fact" in rationale
