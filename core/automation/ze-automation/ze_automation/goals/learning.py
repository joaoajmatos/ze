from __future__ import annotations

from dataclasses import asdict, replace
from typing import Any
from uuid import UUID

from ze_agents.claims import ClaimKind, Provenance
from ze_agents.errors import (
    GoalLearningEvidenceError,
    GoalLearningError,
    GoalLearningPromotionError,
)
from ze_memory.action_records.store import ActionRecordStore
from ze_memory.action_records.types import ActionRecord
from ze_memory.contribution import PerceptionFactSubmit, submit_perception_facts
from ze_memory.defaults import NLI_CONTRADICTION_THRESHOLD
from ze_memory.types import Fact
from ze_plugin.contribution import EvidenceRef, TargetFace

from ze_automation.goals.types import (
    EligibleLearning,
    GoalLearning,
    LearningEvidence,
    LearningEvidenceDraft,
    LearningEvidenceKind,
    LearningEvidenceRole,
    LearningPromotion,
    LearningPromotionState,
    LearningStatus,
    PromotionEligibility,
)


def execution_context_key(record: ActionRecord) -> str:
    ctx = record.context
    if ctx.milestone_id is not None:
        return f"milestone:{ctx.milestone_id}"
    if ctx.goal_id is not None:
        return f"goal:{ctx.goal_id}"
    if ctx.workflow_run_id is not None:
        return f"workflow_run:{ctx.workflow_run_id}"
    return f"action:{record.id}"


def validate_learning_draft(
    learning: GoalLearning,
    evidence: list[LearningEvidenceDraft],
    *,
    allow_imported: bool = False,
) -> None:
    if not learning.content.strip():
        raise GoalLearningError("learning content must be nonempty")
    if not 0.0 <= learning.confidence <= 1.0:
        raise GoalLearningError("learning confidence must be within [0, 1]")
    if learning.status is LearningStatus.RETRACTED and learning.retracted_at is None:
        raise GoalLearningError("retracted learnings require retracted_at")
    if (
        learning.status is LearningStatus.SUPERSEDED
        and learning.superseded_by_id is None
    ):
        raise GoalLearningError("superseded learnings require superseded_by_id")
    if learning.claim_kind is ClaimKind.ACTION_RECORD:
        raise GoalLearningError("a learning must not be typed as an action record")

    for item in evidence:
        sources = [item.action_record_id is not None, item.review_id is not None]
        if sum(sources) != 1:
            raise GoalLearningEvidenceError(
                "each evidence row must cite exactly one source"
            )
        if item.evidence_kind is LearningEvidenceKind.ACTION_RECORD:
            if item.action_record_id is None:
                raise GoalLearningEvidenceError("action evidence requires action_record_id")
        elif item.review_id is None:
            raise GoalLearningEvidenceError("user evidence requires review_id")

    action_support = [
        e
        for e in evidence
        if e.evidence_kind is LearningEvidenceKind.ACTION_RECORD
        and e.role is LearningEvidenceRole.SUPPORTS
    ]
    user_confirm = [
        e
        for e in evidence
        if e.evidence_kind is LearningEvidenceKind.USER_CONFIRMATION
        and e.role is LearningEvidenceRole.SUPPORTS
    ]
    automated = learning.provenance is Provenance.SYNTHESIZED
    if (
        automated
        and not allow_imported
        and learning.status
        in {LearningStatus.ACTIVE, LearningStatus.PENDING_REVIEW}
        and not action_support
        and not user_confirm
    ):
        raise GoalLearningEvidenceError(
            "automated learnings require ActionRecord or user-confirmation evidence"
        )


def evaluate_eligibility(
    learning: GoalLearning,
    evidence: list[LearningEvidence] | list[LearningEvidenceDraft],
    *,
    user_confirmed: bool = False,
) -> PromotionEligibility:
    supporting = [
        e
        for e in evidence
        if e.role is LearningEvidenceRole.SUPPORTS
        and getattr(e, "evidence_kind", None) is LearningEvidenceKind.ACTION_RECORD
        and getattr(e, "action_record_id", None) is not None
    ]
    contradicting = [
        e for e in evidence if e.role is LearningEvidenceRole.CONTRADICTS
    ]
    action_ids = tuple(
        dict.fromkeys(e.action_record_id for e in supporting if e.action_record_id)
    )
    contexts = {
        getattr(e, "execution_context_key", None) or f"action:{e.action_record_id}"
        for e in supporting
    }
    independent = len(contexts)
    unresolved = bool(contradicting) and learning.status in {
        LearningStatus.REVIEW_NEEDED,
        LearningStatus.PENDING_REVIEW,
    }
    if learning.status not in {LearningStatus.ACTIVE, LearningStatus.PENDING_REVIEW}:
        return PromotionEligibility(
            eligible=False,
            reason="learning is not in an eligible lifecycle",
            supporting_action_record_ids=action_ids,
            independent_context_count=independent,
            user_confirmed=user_confirmed,
            unresolved_contradiction=unresolved,
            permitted_claim_kind=ClaimKind.INFERENCE,
        )
    if unresolved:
        return PromotionEligibility(
            eligible=False,
            reason="unresolved contradiction",
            supporting_action_record_ids=action_ids,
            independent_context_count=independent,
            user_confirmed=user_confirmed,
            unresolved_contradiction=True,
            permitted_claim_kind=ClaimKind.INFERENCE,
        )
    diverse = independent >= 2 and len(action_ids) >= 2
    eligible = user_confirmed or diverse
    permitted = ClaimKind.FACT if user_confirmed else ClaimKind.INFERENCE
    return PromotionEligibility(
        eligible=eligible,
        reason=(
            "user confirmation"
            if user_confirmed
            else "independent action contexts"
            if diverse
            else "insufficient independent evidence"
        ),
        supporting_action_record_ids=action_ids,
        independent_context_count=independent,
        user_confirmed=user_confirmed,
        unresolved_contradiction=False,
        permitted_claim_kind=permitted,
    )


async def resolve_action_records(
    store: ActionRecordStore | None,
    evidence: list[LearningEvidenceDraft],
) -> tuple[list[LearningEvidenceDraft], dict[UUID, ActionRecord]]:
    found: dict[UUID, ActionRecord] = {}
    resolved: list[LearningEvidenceDraft] = []
    if store is None:
        return evidence, found
    for item in evidence:
        if item.action_record_id is None:
            resolved.append(item)
            continue
        record = await store.get(item.action_record_id)
        if record is None:
            raise GoalLearningEvidenceError(
                f"ActionRecord {item.action_record_id} does not exist"
            )
        found[item.action_record_id] = record
        if item.execution_context_key:
            resolved.append(item)
        else:
            resolved.append(
                replace(item, execution_context_key=execution_context_key(record))
            )
    return resolved, found


def eligibility_snapshot(eligibility: PromotionEligibility) -> dict:
    data = asdict(eligibility)
    data["permitted_claim_kind"] = eligibility.permitted_claim_kind.value
    data["supporting_action_record_ids"] = [
        str(item) for item in eligibility.supporting_action_record_ids
    ]
    return data


def has_user_confirmation(learning: GoalLearning) -> bool:
    return any(
        e.evidence_kind is LearningEvidenceKind.USER_CONFIRMATION
        and e.role is LearningEvidenceRole.SUPPORTS
        for e in learning.evidence
    )


async def promote_eligible_learning(
    store: Any,
    learning: GoalLearning,
    *,
    memory_store: Any | None = None,
    user_confirmed: bool | None = None,
) -> LearningPromotion:
    if learning.id is None:
        raise GoalLearningPromotionError("learning must be persisted before promotion")
    confirmed = (
        has_user_confirmation(learning) if user_confirmed is None else user_confirmed
    )
    eligibility = evaluate_eligibility(
        learning, learning.evidence, user_confirmed=confirmed
    )
    snapshot = eligibility_snapshot(eligibility)
    latest = await store.get_latest_promotion(learning.id)
    if (
        latest is not None
        and latest.state is LearningPromotionState.PROMOTED
        and latest.memory_fact_id is not None
    ):
        return latest
    if (
        not eligibility.eligible
        or eligibility.permitted_claim_kind is not ClaimKind.FACT
    ):
        return await store.record_promotion(
            learning.id,
            state=LearningPromotionState.BLOCKED,
            snapshot=snapshot,
            failure_reason=eligibility.reason,
        )
    if memory_store is None:
        return await store.record_promotion(
            learning.id,
            state=LearningPromotionState.FAILED,
            snapshot=snapshot,
            failure_reason="memory store unavailable",
        )
    fact = Fact(
        predicate="goal_learning",
        value=learning.content,
        confidence=learning.confidence,
        agent="goal_learning",
        source_refs=[learning.id, *eligibility.supporting_action_record_ids],
        reviewed=True,
    )
    evidence = [EvidenceRef(kind="goal", id=learning.goal_id)]
    try:
        await submit_perception_facts(
            memory_store,
            [
                PerceptionFactSubmit(
                    fact=fact,
                    provenance=Provenance.PROMPT_SUPPLIED,
                    target_face=TargetFace.USER,
                    evidence=evidence,
                )
            ],
        )
    except Exception as exc:
        return await store.record_promotion(
            learning.id,
            state=LearningPromotionState.FAILED,
            snapshot=snapshot,
            failure_reason=str(exc),
        )
    if fact.id is None:
        return await store.record_promotion(
            learning.id,
            state=LearningPromotionState.FAILED,
            snapshot=snapshot,
            failure_reason="perception-fact path returned no id",
        )
    return await store.record_promotion(
        learning.id,
        state=LearningPromotionState.PROMOTED,
        snapshot=snapshot,
        memory_fact_id=fact.id,
    )


async def apply_nli_contradictions(
    store: Any,
    nli: Any | None,
    learning: GoalLearning,
    *,
    threshold: float = NLI_CONTRADICTION_THRESHOLD,
) -> None:
    if nli is None or learning.id is None:
        return
    peers = await store.list_goal_learnings(learning.goal_id, include_history=False)
    action_id = next(
        (e.action_record_id for e in learning.evidence if e.action_record_id),
        None,
    )
    if action_id is None:
        return
    pairs: list[tuple[str, str]] = []
    targets: list[UUID] = []
    for peer in peers:
        if peer.id == learning.id:
            continue
        if peer.status is LearningStatus.RETRACTED or peer.status is LearningStatus.SUPERSEDED:
            continue
        pairs.append((peer.content, learning.content))
        targets.append(peer.id)
    if not pairs:
        return
    scores = await nli.scores(pairs)
    for peer_id, score in zip(targets, scores, strict=False):
        if not score or float(score.get("contradiction", 0.0)) < threshold:
            continue
        await store.record_contradiction(
            peer_id,
            LearningEvidenceDraft(
                evidence_kind=LearningEvidenceKind.ACTION_RECORD,
                role=LearningEvidenceRole.CONTRADICTS,
                excerpt=learning.content[:500],
                action_record_id=action_id,
                execution_context_key=f"learning:{learning.id}",
            ),
            rationale="nli contradiction",
        )


def format_eligible(learning: GoalLearning, relevance: float = 1.0) -> EligibleLearning:
    excerpts = "; ".join(e.excerpt for e in learning.evidence[:3]) or "no evidence summary"
    return EligibleLearning(
        id=learning.id,  # type: ignore[arg-type]
        content=learning.content,
        claim_kind=learning.claim_kind,
        provenance=learning.provenance,
        confidence=learning.confidence,
        evidence_summary=excerpts,
        relevance=relevance,
    )
