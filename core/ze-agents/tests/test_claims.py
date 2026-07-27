import pytest

from ze_agents.claims import CONFIDENCE_FLOOR, DecayProfile, decay
from ze_agents.errors import MissingDecayParameterError


def test_evidence_weighted_floors_at_total_evidence_le_1():
    assert decay(0.8, DecayProfile.EVIDENCE_WEIGHTED, remaining_evidence=0, total_evidence=1) == (
        CONFIDENCE_FLOOR
    )
    assert decay(0.8, DecayProfile.EVIDENCE_WEIGHTED, remaining_evidence=0, total_evidence=0) == (
        CONFIDENCE_FLOOR
    )


def test_evidence_weighted_recomputes_from_remaining_evidence():
    result = decay(
        0.9, DecayProfile.EVIDENCE_WEIGHTED, remaining_evidence=2, total_evidence=3
    )
    assert result == pytest.approx(0.9 * 2 / 3)


def test_time_linear_decays_by_rate_per_30_day_period():
    result = decay(0.8, DecayProfile.TIME_LINEAR, elapsed_days=30)
    assert result == pytest.approx(0.77)


def test_time_linear_never_goes_below_zero():
    result = decay(0.01, DecayProfile.TIME_LINEAR, elapsed_days=3000)
    assert result == 0.0


def test_evidence_weighted_missing_params_raises_typed_error():
    with pytest.raises(MissingDecayParameterError):
        decay(0.8, DecayProfile.EVIDENCE_WEIGHTED)


def test_time_linear_missing_params_raises_typed_error():
    with pytest.raises(MissingDecayParameterError):
        decay(0.8, DecayProfile.TIME_LINEAR)
