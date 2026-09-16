from uuid import uuid4

import pytest
from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_agents.errors import (
    ActionRecordPayloadError,
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
        (SourceFunction.SOCIAL_COGNITION, ClaimKind.IDENTITY),
        (SourceFunction.ACTION, ClaimKind.ACTION_RECORD),
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
        action_record=object() if claim_kind is ClaimKind.ACTION_RECORD else None,
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
        (SourceFunction.SOCIAL_COGNITION, ClaimKind.FACT),
        (SourceFunction.SOCIAL_COGNITION, ClaimKind.INFERENCE),
        (SourceFunction.SOCIAL_COGNITION, ClaimKind.SUSPICION),
        (SourceFunction.SOCIAL_COGNITION, ClaimKind.PRIORITY),
        (SourceFunction.ACTION, ClaimKind.FACT),
        (SourceFunction.ACTION, ClaimKind.INFERENCE),
        (SourceFunction.PERCEPTION, ClaimKind.ACTION_RECORD),
        (SourceFunction.MEMORY, ClaimKind.ACTION_RECORD),
        (SourceFunction.EXECUTIVE, ClaimKind.ACTION_RECORD),
        (SourceFunction.SOCIAL_COGNITION, ClaimKind.ACTION_RECORD),
        (SourceFunction.REFLECTION, ClaimKind.ACTION_RECORD),
        (SourceFunction.GOVERNANCE, ClaimKind.ACTION_RECORD),
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


def test_content_and_entity_ids_default_to_empty() -> None:
    contribution = Contribution(
        claim_kind=ClaimKind.FACT,
        provenance=Provenance.SYNTHESIZED,
        confidence=_confidence(),
        target_face=TargetFace.WORLD,
        source_function=SourceFunction.PERCEPTION,
    )

    assert contribution.content is None
    assert contribution.entity_ids == []


async def test_ingestion_evidence_without_checker_is_accepted() -> None:
    contribution = Contribution(
        claim_kind=ClaimKind.FACT,
        provenance=Provenance.SYNTHESIZED,
        confidence=_confidence(),
        target_face=TargetFace.WORLD,
        source_function=SourceFunction.PERCEPTION,
        evidence=[EvidenceRef(kind="ingestion", id=uuid4())],
    )
    result = await validate_and_submit(contribution, _write)
    assert result == "written"


async def test_goal_evidence_without_checker_is_accepted() -> None:
    contribution = Contribution(
        claim_kind=ClaimKind.FACT,
        provenance=Provenance.SYNTHESIZED,
        confidence=_confidence(),
        target_face=TargetFace.USER,
        source_function=SourceFunction.PERCEPTION,
        evidence=[EvidenceRef(kind="goal", id=uuid4())],
    )
    result = await validate_and_submit(contribution, _write)
    assert result == "written"


async def test_fact_evidence_without_checker_is_still_dangling() -> None:
    contribution = Contribution(
        claim_kind=ClaimKind.FACT,
        provenance=Provenance.SYNTHESIZED,
        confidence=_confidence(),
        target_face=TargetFace.USER,
        source_function=SourceFunction.PERCEPTION,
        evidence=[EvidenceRef(kind="fact", id=uuid4())],
    )
    with pytest.raises(DanglingEvidenceError):
        await validate_and_submit(contribution, _write)


async def test_validate_and_submit_ignores_content_and_entity_ids() -> None:
    entity_id = uuid4()
    contribution = Contribution(
        claim_kind=ClaimKind.FACT,
        provenance=Provenance.SYNTHESIZED,
        confidence=_confidence(),
        target_face=TargetFace.WORLD,
        source_function=SourceFunction.PERCEPTION,
        content="X moved to Berlin",
        entity_ids=[entity_id],
    )

    result = await validate_and_submit(contribution, _write)
    assert result == "written"


async def test_action_record_without_payload_is_rejected() -> None:
    contribution = Contribution(
        claim_kind=ClaimKind.ACTION_RECORD,
        provenance=Provenance.PROMPT_SUPPLIED,
        confidence=_confidence(1.0),
        target_face=TargetFace.WORLD,
        source_function=SourceFunction.ACTION,
        action_record=None,
    )
    with pytest.raises(ActionRecordPayloadError):
        await validate_and_submit(contribution, _write)


async def test_non_action_kind_rejects_action_payload() -> None:
    contribution = Contribution(
        claim_kind=ClaimKind.FACT,
        provenance=Provenance.PROMPT_SUPPLIED,
        confidence=_confidence(1.0),
        target_face=TargetFace.WORLD,
        source_function=SourceFunction.PERCEPTION,
        action_record=object(),
    )
    with pytest.raises(ActionRecordPayloadError):
        await validate_and_submit(contribution, _write)


async def test_action_record_evidence_without_checker_is_dangling() -> None:
    contribution = Contribution(
        claim_kind=ClaimKind.ACTION_RECORD,
        provenance=Provenance.PROMPT_SUPPLIED,
        confidence=_confidence(1.0),
        target_face=TargetFace.WORLD,
        source_function=SourceFunction.ACTION,
        action_record=object(),
        evidence=[EvidenceRef(kind="action_record", id=uuid4())],
    )
    with pytest.raises(DanglingEvidenceError):
        await validate_and_submit(contribution, _write)


async def test_action_record_evidence_with_checker_is_accepted() -> None:
    contribution = Contribution(
        claim_kind=ClaimKind.ACTION_RECORD,
        provenance=Provenance.PROMPT_SUPPLIED,
        confidence=_confidence(1.0),
        target_face=TargetFace.WORLD,
        source_function=SourceFunction.ACTION,
        action_record=object(),
        evidence=[EvidenceRef(kind="action_record", id=uuid4())],
    )

    async def check_action_record_exists(_id):
        return True

    result = await validate_and_submit(
        contribution, _write, check_action_record_exists=check_action_record_exists
    )
    assert result == "written"
