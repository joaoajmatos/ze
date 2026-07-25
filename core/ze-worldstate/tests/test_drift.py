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


def test_is_drift_eligible_when_elapsed_and_no_fresh_evidence():
    confirmed_at = datetime.now(timezone.utc) - timedelta(days=10)
    loop = _loop(
        confirmed_at=confirmed_at,
        updated_at=confirmed_at,
        drift_deadline=confirmed_at + timedelta(days=7),
    )
    assert is_drift_eligible(loop) is True


def test_not_eligible_when_evidence_is_fresh():
    confirmed_at = datetime.now(timezone.utc) - timedelta(days=10)
    loop = _loop(
        confirmed_at=confirmed_at,
        updated_at=datetime.now(timezone.utc),
        drift_deadline=confirmed_at + timedelta(days=7),
    )
    assert is_drift_eligible(loop) is False


def test_not_eligible_when_window_not_elapsed():
    confirmed_at = datetime.now(timezone.utc)
    loop = _loop(
        confirmed_at=confirmed_at,
        updated_at=confirmed_at,
        drift_deadline=confirmed_at + timedelta(days=7),
    )
    assert is_drift_eligible(loop) is False


def test_not_eligible_when_not_active():
    confirmed_at = datetime.now(timezone.utc) - timedelta(days=10)
    loop = _loop(
        state=LoopState.SUSPECTED,
        confirmed_at=confirmed_at,
        updated_at=confirmed_at,
        drift_deadline=confirmed_at + timedelta(days=7),
    )
    assert is_drift_eligible(loop) is False


def test_compose_absence_rationale_cites_dates():
    confirmed_at = datetime(2026, 7, 10, tzinfo=timezone.utc)
    loop = _loop(confirmed_at=confirmed_at, drift_deadline=confirmed_at + timedelta(days=7))
    rationale = compose_absence_rationale(loop)
    assert "2026-07-10" in rationale
    assert "2026-07-17" in rationale
    assert "No corroborating evidence" in rationale


def test_compose_contradiction_rationale_cites_evidence():
    evidence_id = uuid4()
    rationale = compose_contradiction_rationale("fact", evidence_id)
    assert str(evidence_id) in rationale
    assert "fact" in rationale
