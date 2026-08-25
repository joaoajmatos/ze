from uuid import uuid4

import pytest
from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_agents.errors import (
    DanglingEvidenceError,
    MissingEvidenceError,
    UnlicensedClaimKindError,
)
from ze_plugin.contribution import (
    Contribution,
    EvidenceRef,
    SourceFunction,
    TargetFace,
    validate_and_submit,
)


def _confidence(value: float = 0.5) -> Confidence:
    return Confidence(value=value, decay_profile=DecayProfile.TIME_LINEAR)


async def _write() -> str:
    return "written"


@pytest.mark.parametrize(
    ("source_function", "claim_kind"),
    [
        (SourceFunction.PERCEPTION, ClaimKind.FACT),
        (SourceFunction.REFLECTION, ClaimKind.INFERENCE),
        (SourceFunction.REFLECTION, ClaimKind.SUSPICION),
        (SourceFunction.EXECUTIVE, ClaimKind.PRIORITY),
    ],
)
async def test_licensed_claim_kind_is_accepted(source_function, claim_kind) -> None:
    evidence = (
        [EvidenceRef(kind="fact", id=uuid4())]
        if claim_kind in {ClaimKind.INFERENCE, ClaimKind.SUSPICION}
        else []
    )
    contribution = Contribution(
        claim_kind=claim_kind,
        provenance=Provenance.SYNTHESIZED,
        confidence=_confidence(),
        target_face=TargetFace.SELF,
        source_function=source_function,
        evidence=evidence,
    )

    async def check_fact_exists(_id):
        return True

    result = await validate_and_submit(
        contribution, _write, check_fact_exists=check_fact_exists
    )
    assert result == "written"


@pytest.mark.parametrize(
    ("source_function", "claim_kind"),
    [
        (SourceFunction.PERCEPTION, ClaimKind.INFERENCE),
        (SourceFunction.PERCEPTION, ClaimKind.SUSPICION),
        (SourceFunction.REFLECTION, ClaimKind.FACT),
        (SourceFunction.REFLECTION, ClaimKind.PRIORITY),
    ],
)
async def test_unlicensed_claim_kind_is_rejected(source_function, claim_kind) -> None:
    contribution = Contribution(
        claim_kind=claim_kind,
        provenance=Provenance.SYNTHESIZED,
        confidence=_confidence(),
        target_face=TargetFace.SELF,
        source_function=source_function,
        evidence=[EvidenceRef(kind="fact", id=uuid4())],
    )

    with pytest.raises(UnlicensedClaimKindError):
        await validate_and_submit(contribution, _write)


async def test_missing_evidence_is_rejected() -> None:
    contribution = Contribution(
        claim_kind=ClaimKind.INFERENCE,
        provenance=Provenance.SYNTHESIZED,
        confidence=_confidence(),
        target_face=TargetFace.SELF,
        source_function=SourceFunction.REFLECTION,
        evidence=[],
    )

    with pytest.raises(MissingEvidenceError):
        await validate_and_submit(contribution, _write)


async def test_dangling_evidence_is_rejected() -> None:
    contribution = Contribution(
        claim_kind=ClaimKind.SUSPICION,
        provenance=Provenance.SYNTHESIZED,
        confidence=_confidence(),
        target_face=TargetFace.SELF,
        source_function=SourceFunction.REFLECTION,
        evidence=[EvidenceRef(kind="fact", id=uuid4())],
    )

    async def check_fact_exists(_id):
        return False

    with pytest.raises(DanglingEvidenceError):
        await validate_and_submit(
            contribution, _write, check_fact_exists=check_fact_exists
        )


async def test_rejection_emits_warning_log() -> None:
    import structlog.testing

    contribution = Contribution(
        claim_kind=ClaimKind.FACT,
        provenance=Provenance.SYNTHESIZED,
        confidence=_confidence(),
        target_face=TargetFace.SELF,
        source_function=SourceFunction.REFLECTION,
        evidence=[],
    )

    with structlog.testing.capture_logs() as logs:
        with pytest.raises(UnlicensedClaimKindError):
            await validate_and_submit(contribution, _write)

    assert any(e.get("event") == "contribution_rejected" for e in logs)
