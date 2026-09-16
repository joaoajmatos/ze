from ze_agents.claims import ClaimKind, DecayProfile, Provenance, decay
from ze_agents.errors import MissingDecayParameterError


def test_claim_kind_is_closed_and_includes_action_record() -> None:
    assert set(ClaimKind) == {
        ClaimKind.IDENTITY,
        ClaimKind.FACT,
        ClaimKind.INFERENCE,
        ClaimKind.SUSPICION,
        ClaimKind.PRIORITY,
        ClaimKind.ACTION_RECORD,
    }
    assert ClaimKind.ACTION_RECORD.value == "action_record"


def test_unknown_decay_profile_raises() -> None:
    try:
        decay(0.5, "not-a-profile")  # type: ignore[arg-type]
    except MissingDecayParameterError as exc:
        assert "unknown decay_profile" in str(exc)
        return
    raise AssertionError("expected MissingDecayParameterError")


def test_provenance_remains_closed() -> None:
    assert set(Provenance) == {
        Provenance.GRAPH_RECALL,
        Provenance.LIVE_SEARCH,
        Provenance.PROMPT_SUPPLIED,
        Provenance.SYNTHESIZED,
    }


def test_decay_profiles_remain_closed() -> None:
    assert set(DecayProfile) == {
        DecayProfile.EVIDENCE_WEIGHTED,
        DecayProfile.TIME_LINEAR,
    }
