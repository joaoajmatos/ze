from __future__ import annotations

from datetime import datetime, timezone
from collections.abc import Sequence
from uuid import UUID

from ze_agents.claims import Provenance
from ze_plugin.contribution import EvidenceRef

from ze_memory.procedures.errors import (
    InvalidProcedureTransitionError,
    MissingActionRecordError,
    UnavailableRollbackTargetError,
)
from ze_memory.procedures.store import ProcedureStore
from ze_memory.procedures.types import (
    CandidateStatus,
    IdentityStatus,
    LearningRef,
    LifecycleEventKind,
    ProcedureAdmission,
    ProcedureAdmissionDecision,
    ProcedureAdmissionResult,
    ProcedureCandidate,
    ProcedureFeedback,
    ProcedureIdentity,
    ProcedureLifecycleEvent,
    ProcedureOutcome,
    ProcedureOutcomeFeedback,
    ProcedureRollbackResult,
    ProcedureSourceKind,
    ProcedureVersion,
    ProvisionalProcedure,
    ProvisionalStatus,
    VersionStatus,
)
from ze_memory.procedures.validate import validate_candidate
from ze_memory.types import Procedure

UTC = timezone.utc


class ProcedureAdmissionService:
    def __init__(self, store: ProcedureStore) -> None:
        self._store = store

    async def submit_procedure_candidate(
        self, candidate: ProcedureCandidate
    ) -> ProcedureCandidate:
        validate_candidate(candidate)
        candidate.status = CandidateStatus.PENDING
        saved = await self._store.save_candidate(candidate)
        await self._store.save_event(
            ProcedureLifecycleEvent(
                kind=LifecycleEventKind.SUBMITTED,
                reason="candidate submitted",
                candidate_id=saved.id,
                evidence_refs=list(saved.evidence_refs),
                learning_refs=list(saved.learning_refs),
            )
        )
        return saved

    async def review_procedure_candidate(
        self,
        candidate_id: UUID,
        decision: ProcedureAdmissionDecision,
        *,
        reason: str,
        review_evidence: Sequence[EvidenceRef] = (),
        review_learnings: Sequence[LearningRef] = (),
        reviewer: str = "user",
    ) -> ProcedureAdmissionResult:
        candidate = await self._store.get_candidate(candidate_id)
        if candidate is None:
            raise InvalidProcedureTransitionError("candidate not found")
        if candidate.status in {
            CandidateStatus.APPROVED,
            CandidateStatus.REJECTED,
            CandidateStatus.WITHDRAWN,
        }:
            raise InvalidProcedureTransitionError(
                f"candidate already {candidate.status.value}"
            )
        admission = await self._store.save_admission(
            ProcedureAdmission(
                candidate_id=candidate_id,
                decision=decision,
                reason=reason,
                reviewer=reviewer,
                review_evidence_refs=list(review_evidence),
                review_learning_refs=list(review_learnings),
            )
        )
        await self._store.save_event(
            ProcedureLifecycleEvent(
                kind=LifecycleEventKind.REVIEWED,
                reason=reason,
                candidate_id=candidate_id,
                evidence_refs=list(review_evidence),
                learning_refs=list(review_learnings),
            )
        )
        if decision is ProcedureAdmissionDecision.APPROVE:
            return await self._admit(candidate, admission)
        if decision is ProcedureAdmissionDecision.NEEDS_REVIEW:
            candidate.status = CandidateStatus.NEEDS_REVIEW
        elif decision is ProcedureAdmissionDecision.REJECT:
            candidate.status = CandidateStatus.REJECTED
            candidate.resolved_at = datetime.now(UTC)
        else:
            candidate.status = CandidateStatus.WITHDRAWN
            candidate.resolved_at = datetime.now(UTC)
        await self._store.save_candidate(candidate)
        return ProcedureAdmissionResult(candidate=candidate, admission=admission)

    async def record_procedure_feedback(
        self,
        procedure_version_id: UUID,
        *,
        action_record_id: UUID,
        outcome: ProcedureOutcome,
        summary: str,
        evidence: Sequence[EvidenceRef] = (),
        learnings: Sequence[LearningRef] = (),
    ) -> ProcedureFeedback:
        version = await self._store.get_version(procedure_version_id)
        if version is None:
            raise InvalidProcedureTransitionError("procedure version not found")
        if not await self._store.action_record_exists(action_record_id):
            raise MissingActionRecordError(
                f"ActionRecord {action_record_id} does not exist"
            )
        feedback = await self._store.save_feedback(
            ProcedureFeedback(
                procedure_version_id=procedure_version_id,
                action_record_id=action_record_id,
                outcome=outcome,
                summary=summary,
                evidence_refs=list(evidence),
                learning_refs=list(learnings),
            )
        )
        await self._store.save_event(
            ProcedureLifecycleEvent(
                kind=LifecycleEventKind.FEEDBACK_RECORDED,
                reason=summary,
                version_id=procedure_version_id,
                identity_id=version.procedure_id,
                evidence_refs=list(evidence),
                learning_refs=list(learnings),
            )
        )
        if outcome is ProcedureOutcome.FAILED:
            identity = await self._store.get_identity(version.procedure_id)
            if identity is not None:
                await self._store.save_event(
                    ProcedureLifecycleEvent(
                        kind=LifecycleEventKind.REVIEWED,
                        reason="failure feedback requires review",
                        identity_id=identity.id,
                        version_id=procedure_version_id,
                    )
                )
        return feedback

    async def rollback_procedure(
        self,
        procedure_id: UUID,
        *,
        target_version_id: UUID | None,
        reason: str,
        evidence: Sequence[EvidenceRef] = (),
        learnings: Sequence[LearningRef] = (),
    ) -> ProcedureRollbackResult:
        identity = await self._store.get_identity(procedure_id)
        if identity is None:
            raise InvalidProcedureTransitionError("procedure identity not found")
        current = (
            await self._store.get_version(identity.active_version_id)
            if identity.active_version_id
            else None
        )
        versions = await self._store.list_versions(procedure_id)
        target = None
        if target_version_id is not None:
            target = await self._store.get_version(target_version_id)
            if target is None or target.procedure_id != procedure_id:
                raise UnavailableRollbackTargetError("rollback target not found")
        else:
            eligible = [
                v
                for v in reversed(versions)
                if v.status is not VersionStatus.RETIRED
                and (current is None or v.id != current.id)
            ]
            target = eligible[0] if eligible else None
        if current is not None:
            current.status = VersionStatus.ROLLED_BACK
            current.ended_at = datetime.now(UTC)
            await self._store.save_version(current)
        if target is None:
            identity.status = IdentityStatus.RETIRED
            identity.active_version_id = None
            await self._store.save_identity(identity)
            await self._store.save_event(
                ProcedureLifecycleEvent(
                    kind=LifecycleEventKind.RETIRED,
                    reason=reason,
                    identity_id=identity.id,
                    evidence_refs=list(evidence),
                    learning_refs=list(learnings),
                )
            )
            return ProcedureRollbackResult(
                identity=identity, restored_version=None, retired=True
            )
        target.status = VersionStatus.ACTIVE
        target.ended_at = None
        await self._store.save_version(target)
        identity.active_version_id = target.id
        identity.status = IdentityStatus.ACTIVE
        await self._store.save_identity(identity)
        await self._store.save_event(
            ProcedureLifecycleEvent(
                kind=LifecycleEventKind.ROLLED_BACK,
                reason=reason,
                identity_id=identity.id,
                version_id=target.id,
                evidence_refs=list(evidence),
                learning_refs=list(learnings),
            )
        )
        await self._store.save_event(
            ProcedureLifecycleEvent(
                kind=LifecycleEventKind.RESTORED,
                reason=reason,
                identity_id=identity.id,
                version_id=target.id,
            )
        )
        return ProcedureRollbackResult(
            identity=identity, restored_version=target, retired=False
        )

    async def retrieve_procedures(
        self, *, include_history: bool = False
    ) -> list[ProcedureVersion]:
        if include_history:
            return await self._store.list_all_versions()
        return await self._store.list_active_versions()

    async def list_procedure_candidates(
        self, statuses: Sequence[CandidateStatus] | None = None
    ) -> list[ProcedureCandidate]:
        return await self._store.list_candidates(
            list(statuses) if statuses is not None else None
        )

    async def list_procedure_versions(
        self, procedure_id: UUID
    ) -> list[ProcedureVersion]:
        return await self._store.list_versions(procedure_id)

    async def lifecycle_history(self, procedure_id: UUID) -> dict:
        identity = await self._store.get_identity(procedure_id)
        versions = await self._store.list_versions(procedure_id)
        events = await self._store.list_events(identity_id=procedure_id)
        return {"identity": identity, "versions": versions, "events": events}

    async def list_procedure_summaries(self) -> list[tuple[ProcedureIdentity, ProcedureVersion]]:
        latest: dict[UUID, ProcedureVersion] = {}
        for version in await self._store.list_all_versions():
            current = latest.get(version.procedure_id)
            if current is None or version.version_number > current.version_number:
                latest[version.procedure_id] = version
        rows: list[tuple[ProcedureIdentity, ProcedureVersion]] = []
        for procedure_id, version in latest.items():
            identity = await self._store.get_identity(procedure_id)
            if identity is not None:
                rows.append((identity, version))
        return rows

    async def edit_procedure(
        self,
        procedure_id: UUID,
        *,
        name: str,
        trigger: str,
        preconditions: Sequence[str],
        steps: Sequence[str],
        success_criteria: Sequence[str],
        limits: Sequence[str],
        reason: str,
    ) -> ProcedureAdmissionResult:
        identity = await self._store.get_identity(procedure_id)
        if identity is None:
            raise InvalidProcedureTransitionError("procedure identity not found")
        submitted = await self.submit_procedure_candidate(
            ProcedureCandidate(
                source_kind=ProcedureSourceKind.USER_INSTRUCTION,
                provenance=Provenance.PROMPT_SUPPLIED,
                name=name,
                trigger=trigger,
                preconditions=list(preconditions),
                steps=list(steps),
                success_criteria=list(success_criteria),
                limits=list(limits),
                proposed_identity_id=procedure_id,
            )
        )
        return await self.review_procedure_candidate(
            submitted.id,
            ProcedureAdmissionDecision.APPROVE,
            reason=reason,
        )

    async def list_version_feedback(self, version_id: UUID):
        return await self._store.list_feedback(version_id)

    async def remember_provisional(self, provisional: ProvisionalProcedure) -> None:
        await self._store.save_provisional(provisional)

    async def resolve_provisional(
        self,
        goal_id: UUID,
        *,
        discard: bool,
        reason: str,
    ) -> None:
        open_rows = await self._store.list_open_provisionals(goal_id)
        for row in open_rows:
            if discard:
                row.status = ProvisionalStatus.DISCARDED
                row.resolution_reason = reason
                await self._store.save_provisional(row)
                await self._store.save_event(
                    ProcedureLifecycleEvent(
                        kind=LifecycleEventKind.DISCARDED_PROVISIONAL,
                        reason=reason,
                        candidate_id=row.candidate.id,
                    )
                )
            else:
                submitted = await self.submit_procedure_candidate(row.candidate)
                row.status = ProvisionalStatus.SUBMITTED
                row.resolution_reason = reason
                row.candidate = submitted
                await self._store.save_provisional(row)

    async def _admit(
        self, candidate: ProcedureCandidate, admission: ProcedureAdmission
    ) -> ProcedureAdmissionResult:
        validate_candidate(candidate)
        identity = None
        if candidate.proposed_identity_id is not None:
            identity = await self._store.get_identity(candidate.proposed_identity_id)
        if identity is None:
            identity = await self._store.find_identity_by_name(candidate.name)
        if identity is None:
            identity = await self._store.save_identity(
                ProcedureIdentity(canonical_name=candidate.name)
            )
        prior = None
        versions = await self._store.list_versions(identity.id)  # type: ignore[arg-type]
        next_number = max((v.version_number for v in versions), default=0) + 1
        if identity.active_version_id is not None:
            prior = await self._store.get_version(identity.active_version_id)
            if prior is not None:
                prior.status = VersionStatus.SUPERSEDED
                prior.ended_at = datetime.now(UTC)
                await self._store.save_version(prior)
        version = await self._store.save_version(
            ProcedureVersion(
                procedure_id=identity.id,  # type: ignore[arg-type]
                version_number=next_number,
                name=candidate.name,
                trigger=candidate.trigger,
                preconditions=list(candidate.preconditions),
                steps=list(candidate.steps),
                success_criteria=list(candidate.success_criteria),
                limits=list(candidate.limits),
                provenance=candidate.provenance,
                evidence_refs=list(candidate.evidence_refs),
                learning_refs=list(candidate.learning_refs),
                admission_id=admission.id,
                supersedes_version_id=prior.id if prior else None,
            )
        )
        if prior is not None:
            prior.superseded_by_version_id = version.id
            await self._store.save_version(prior)
            await self._store.save_event(
                ProcedureLifecycleEvent(
                    kind=LifecycleEventKind.SUPERSEDED,
                    reason="replaced by admitted version",
                    identity_id=identity.id,
                    version_id=prior.id,
                    candidate_id=candidate.id,
                )
            )
        identity.active_version_id = version.id
        identity.status = IdentityStatus.ACTIVE
        await self._store.save_identity(identity)
        candidate.status = CandidateStatus.APPROVED
        candidate.resolved_at = datetime.now(UTC)
        candidate.proposed_identity_id = identity.id
        await self._store.save_candidate(candidate)
        await self._store.save_event(
            ProcedureLifecycleEvent(
                kind=LifecycleEventKind.ADMITTED,
                reason=admission.reason,
                identity_id=identity.id,
                candidate_id=candidate.id,
                version_id=version.id,
                evidence_refs=list(candidate.evidence_refs),
                learning_refs=list(candidate.learning_refs),
            )
        )
        return ProcedureAdmissionResult(
            candidate=candidate,
            admission=admission,
            version=version,
            identity=identity,
        )

    async def disable_procedure(self, procedure_id: UUID, *, reason: str) -> ProcedureIdentity:
        identity = await self._store.get_identity(procedure_id)
        if identity is None:
            raise InvalidProcedureTransitionError("procedure identity not found")
        if identity.active_version_id is not None:
            current = await self._store.get_version(identity.active_version_id)
            if current is not None and current.status is VersionStatus.ACTIVE:
                current.status = VersionStatus.RETIRED
                current.ended_at = datetime.now(UTC)
                await self._store.save_version(current)
        identity.status = IdentityStatus.RETIRED
        identity.active_version_id = None
        await self._store.save_identity(identity)
        await self._store.save_event(
            ProcedureLifecycleEvent(
                kind=LifecycleEventKind.RETIRED,
                reason=reason,
                identity_id=identity.id,
            )
        )
        return identity

    async def ingest_activation_feedback(
        self, feedback: ProcedureOutcomeFeedback
    ) -> None:
        await self._store.save_event(
            ProcedureLifecycleEvent(
                kind=LifecycleEventKind.FEEDBACK_RECORDED,
                reason=feedback.summary,
                identity_id=feedback.procedure_id,
                version_id=feedback.version_id,
            )
        )
        if feedback.outcome is ProcedureOutcome.FAILED:
            await self._store.save_event(
                ProcedureLifecycleEvent(
                    kind=LifecycleEventKind.REVIEWED,
                    reason="activation failure requires review",
                    identity_id=feedback.procedure_id,
                    version_id=feedback.version_id,
                )
            )


def version_to_procedure(version: ProcedureVersion) -> Procedure:
    return Procedure(
        id=version.id,
        name=version.name,
        trigger=version.trigger,
        preconditions=list(version.preconditions),
        steps=list(version.steps),
        success_criteria=list(version.success_criteria),
        version=version.version_number,
        source_refs=[ref.learning_id for ref in version.learning_refs],
    )
