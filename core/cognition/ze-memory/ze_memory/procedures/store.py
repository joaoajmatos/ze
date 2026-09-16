from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Protocol
from uuid import UUID, uuid4

from ze_agents.claims import Provenance
from ze_plugin.contribution import EvidenceRef

from ze_memory.procedures.types import (
    CandidateStatus,
    CapabilityDecision,
    IdentityStatus,
    InvocationState,
    LearningRef,
    LifecycleEventKind,
    ProcedureAdmission,
    ProcedureActionLink,
    ProcedureActionOutcome,
    ProcedureCandidate,
    ProcedureFeedback,
    ProcedureIdentity,
    ProcedureInvocation,
    ProcedureInvocationOrigin,
    ProcedureLifecycleEvent,
    ProcedureOutcome,
    ProcedureOutcomeFeedback,
    ProcedureSourceKind,
    ProcedureVersion,
    ProvisionalProcedure,
    ProvisionalStatus,
    VersionStatus,
)

UTC = timezone.utc


class ProcedureStore(Protocol):
    async def save_candidate(
        self, candidate: ProcedureCandidate
    ) -> ProcedureCandidate: ...

    async def get_candidate(self, candidate_id: UUID) -> ProcedureCandidate | None: ...

    async def save_identity(self, identity: ProcedureIdentity) -> ProcedureIdentity: ...

    async def get_identity(self, identity_id: UUID) -> ProcedureIdentity | None: ...

    async def find_identity_by_name(
        self, canonical_name: str
    ) -> ProcedureIdentity | None: ...

    async def save_admission(
        self, admission: ProcedureAdmission
    ) -> ProcedureAdmission: ...

    async def save_version(self, version: ProcedureVersion) -> ProcedureVersion: ...

    async def get_version(self, version_id: UUID) -> ProcedureVersion | None: ...

    async def list_versions(self, procedure_id: UUID) -> list[ProcedureVersion]: ...

    async def list_active_versions(self) -> list[ProcedureVersion]: ...

    async def list_all_versions(self) -> list[ProcedureVersion]: ...

    async def save_feedback(self, feedback: ProcedureFeedback) -> ProcedureFeedback: ...

    async def list_feedback(self, version_id: UUID) -> list[ProcedureFeedback]: ...

    async def save_event(
        self, event: ProcedureLifecycleEvent
    ) -> ProcedureLifecycleEvent: ...

    async def save_provisional(
        self, provisional: ProvisionalProcedure
    ) -> ProvisionalProcedure: ...

    async def list_open_provisionals(
        self, goal_id: UUID
    ) -> list[ProvisionalProcedure]: ...

    async def list_candidates(
        self, statuses: list[CandidateStatus] | None = None
    ) -> list[ProcedureCandidate]: ...

    async def list_events(
        self,
        *,
        identity_id: UUID | None = None,
        candidate_id: UUID | None = None,
    ) -> list[ProcedureLifecycleEvent]: ...

    async def save_invocation(
        self, invocation: ProcedureInvocation
    ) -> ProcedureInvocation: ...

    async def get_invocation(
        self, invocation_id: UUID
    ) -> ProcedureInvocation | None: ...

    async def save_action_link(
        self, link: ProcedureActionLink
    ) -> ProcedureActionLink: ...

    async def list_action_links(
        self, invocation_id: UUID
    ) -> list[ProcedureActionLink]: ...

    async def save_activation_feedback(
        self, feedback: ProcedureOutcomeFeedback
    ) -> ProcedureOutcomeFeedback: ...

    async def get_activation_feedback(
        self, invocation_id: UUID
    ) -> ProcedureOutcomeFeedback | None: ...

    async def action_record_exists(self, action_record_id: UUID) -> bool: ...


class InMemoryProcedureStore:
    def __init__(self, *, known_action_records: set[UUID] | None = None) -> None:
        self.candidates: dict[UUID, ProcedureCandidate] = {}
        self.identities: dict[UUID, ProcedureIdentity] = {}
        self.admissions: dict[UUID, ProcedureAdmission] = {}
        self.versions: dict[UUID, ProcedureVersion] = {}
        self.feedback: list[ProcedureFeedback] = []
        self.events: list[ProcedureLifecycleEvent] = []
        self.provisionals: dict[UUID, ProvisionalProcedure] = {}
        self.invocations: dict[UUID, ProcedureInvocation] = {}
        self.action_links: list[ProcedureActionLink] = []
        self.activation_feedback: dict[UUID, ProcedureOutcomeFeedback] = {}
        self.known_action_records = known_action_records or set()

    async def save_candidate(self, candidate: ProcedureCandidate) -> ProcedureCandidate:
        if candidate.id is None:
            candidate.id = uuid4()
        if candidate.submitted_at is None:
            candidate.submitted_at = datetime.now(UTC)
        self.candidates[candidate.id] = candidate
        return candidate

    async def get_candidate(self, candidate_id: UUID) -> ProcedureCandidate | None:
        return self.candidates.get(candidate_id)

    async def save_identity(self, identity: ProcedureIdentity) -> ProcedureIdentity:
        if identity.id is None:
            identity.id = uuid4()
        now = datetime.now(UTC)
        if identity.created_at is None:
            identity.created_at = now
        identity.updated_at = now
        self.identities[identity.id] = identity
        return identity

    async def get_identity(self, identity_id: UUID) -> ProcedureIdentity | None:
        return self.identities.get(identity_id)

    async def find_identity_by_name(
        self, canonical_name: str
    ) -> ProcedureIdentity | None:
        key = canonical_name.strip().lower()
        for identity in self.identities.values():
            if identity.canonical_name.strip().lower() == key:
                return identity
        return None

    async def save_admission(self, admission: ProcedureAdmission) -> ProcedureAdmission:
        if admission.id is None:
            admission.id = uuid4()
        if admission.created_at is None:
            admission.created_at = datetime.now(UTC)
        self.admissions[admission.id] = admission
        return admission

    async def save_version(self, version: ProcedureVersion) -> ProcedureVersion:
        if version.id is None:
            version.id = uuid4()
        if version.created_at is None:
            version.created_at = datetime.now(UTC)
        self.versions[version.id] = version
        return version

    async def get_version(self, version_id: UUID) -> ProcedureVersion | None:
        return self.versions.get(version_id)

    async def list_versions(self, procedure_id: UUID) -> list[ProcedureVersion]:
        rows = [v for v in self.versions.values() if v.procedure_id == procedure_id]
        return sorted(rows, key=lambda v: v.version_number)

    async def list_active_versions(self) -> list[ProcedureVersion]:
        return [v for v in self.versions.values() if v.status is VersionStatus.ACTIVE]

    async def list_all_versions(self) -> list[ProcedureVersion]:
        return list(self.versions.values())

    async def save_feedback(self, feedback: ProcedureFeedback) -> ProcedureFeedback:
        if feedback.id is None:
            feedback.id = uuid4()
        if feedback.created_at is None:
            feedback.created_at = datetime.now(UTC)
        self.feedback.append(feedback)
        return feedback

    async def list_feedback(self, version_id: UUID) -> list[ProcedureFeedback]:
        return [f for f in self.feedback if f.procedure_version_id == version_id]

    async def save_event(
        self, event: ProcedureLifecycleEvent
    ) -> ProcedureLifecycleEvent:
        if event.id is None:
            event.id = uuid4()
        if event.created_at is None:
            event.created_at = datetime.now(UTC)
        self.events.append(event)
        return event

    async def save_provisional(
        self, provisional: ProvisionalProcedure
    ) -> ProvisionalProcedure:
        if provisional.id is None:
            provisional.id = uuid4()
        self.provisionals[provisional.id] = provisional
        return provisional

    async def list_open_provisionals(self, goal_id: UUID) -> list[ProvisionalProcedure]:
        return [
            p
            for p in self.provisionals.values()
            if p.goal_id == goal_id and p.status is ProvisionalStatus.OPEN
        ]

    async def list_candidates(
        self, statuses: list[CandidateStatus] | None = None
    ) -> list[ProcedureCandidate]:
        rows = list(self.candidates.values())
        if statuses is not None:
            allowed = set(statuses)
            rows = [c for c in rows if c.status in allowed]
        return sorted(
            rows,
            key=lambda c: c.submitted_at or datetime.min.replace(tzinfo=UTC),
            reverse=True,
        )

    async def list_events(
        self,
        *,
        identity_id: UUID | None = None,
        candidate_id: UUID | None = None,
    ) -> list[ProcedureLifecycleEvent]:
        rows = list(self.events)
        if identity_id is not None:
            rows = [e for e in rows if e.identity_id == identity_id]
        if candidate_id is not None:
            rows = [e for e in rows if e.candidate_id == candidate_id]
        return rows

    async def save_invocation(
        self, invocation: ProcedureInvocation
    ) -> ProcedureInvocation:
        if invocation.id is None:
            invocation.id = uuid4()
        if invocation.started_at is None:
            invocation.started_at = datetime.now(UTC)
        self.invocations[invocation.id] = invocation
        return invocation

    async def get_invocation(
        self, invocation_id: UUID
    ) -> ProcedureInvocation | None:
        return self.invocations.get(invocation_id)

    async def save_action_link(self, link: ProcedureActionLink) -> ProcedureActionLink:
        if link.id is None:
            link.id = uuid4()
        if link.created_at is None:
            link.created_at = datetime.now(UTC)
        self.action_links.append(link)
        return link

    async def list_action_links(self, invocation_id: UUID) -> list[ProcedureActionLink]:
        return [link for link in self.action_links if link.invocation_id == invocation_id]

    async def save_activation_feedback(
        self, feedback: ProcedureOutcomeFeedback
    ) -> ProcedureOutcomeFeedback:
        if feedback.id is None:
            feedback.id = uuid4()
        if feedback.submitted_at is None:
            feedback.submitted_at = datetime.now(UTC)
        self.activation_feedback[feedback.invocation_id] = feedback
        return feedback

    async def get_activation_feedback(
        self, invocation_id: UUID
    ) -> ProcedureOutcomeFeedback | None:
        return self.activation_feedback.get(invocation_id)

    async def action_record_exists(self, action_record_id: UUID) -> bool:
        return action_record_id in self.known_action_records


def _json(value: object) -> str:
    return json.dumps(value)


def _load(raw: object) -> object:
    if raw is None:
        return None
    if isinstance(raw, str):
        return json.loads(raw)
    return raw


def _str_list(raw: object) -> list[str]:
    data = _load(raw)
    if not isinstance(data, list):
        return []
    return [str(item) for item in data]


def _evidence(raw: object) -> list[EvidenceRef]:
    data = _load(raw)
    if not isinstance(data, list):
        return []
    refs: list[EvidenceRef] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        refs.append(EvidenceRef(kind=item["kind"], id=UUID(str(item["id"]))))
    return refs


def _learnings(raw: object) -> list[LearningRef]:
    data = _load(raw)
    if not isinstance(data, list):
        return []
    refs: list[LearningRef] = []
    for item in data:
        if isinstance(item, dict):
            refs.append(LearningRef(learning_id=UUID(str(item["learning_id"]))))
        else:
            refs.append(LearningRef(learning_id=UUID(str(item))))
    return refs


def _dump_evidence(refs: list[EvidenceRef]) -> str:
    return _json([{"kind": ref.kind, "id": str(ref.id)} for ref in refs])


def _dump_learnings(refs: list[LearningRef]) -> str:
    return _json([{"learning_id": str(ref.learning_id)} for ref in refs])


def _parse_uuid(value: object) -> UUID | None:
    if value is None:
        return None
    return value if isinstance(value, UUID) else UUID(str(value))


def _candidate_from_row(row: Any) -> ProcedureCandidate:
    return ProcedureCandidate(
        source_kind=ProcedureSourceKind(row["source_kind"]),
        provenance=Provenance(row["provenance"]),
        name=row["name"],
        trigger=row["trigger"],
        preconditions=_str_list(row["preconditions"]),
        steps=_str_list(row["steps"]),
        success_criteria=_str_list(row["success_criteria"]),
        limits=_str_list(row["limits"]),
        evidence_refs=_evidence(row["evidence_refs"]),
        learning_refs=_learnings(row["learning_refs"]),
        proposed_identity_id=_parse_uuid(row["proposed_identity_id"]),
        workspace_run_approved=bool(row["workspace_run_approved"]),
        status=CandidateStatus(row["status"]),
        id=row["id"],
        submitted_at=row["submitted_at"],
        resolved_at=row["resolved_at"],
    )


def _identity_from_row(row: Any) -> ProcedureIdentity:
    return ProcedureIdentity(
        canonical_name=row["canonical_name"],
        status=IdentityStatus(row["status"]),
        id=row["id"],
        active_version_id=_parse_uuid(row["active_version_id"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _version_from_row(row: Any) -> ProcedureVersion:
    return ProcedureVersion(
        procedure_id=row["procedure_id"],
        version_number=row["version_number"],
        name=row["name"],
        trigger=row["trigger"],
        preconditions=_str_list(row["preconditions"]),
        steps=_str_list(row["steps"]),
        success_criteria=_str_list(row["success_criteria"]),
        provenance=Provenance(row["provenance"]),
        status=VersionStatus(row["status"]),
        limits=_str_list(row["limits"]),
        evidence_refs=_evidence(row["evidence_refs"]),
        learning_refs=_learnings(row["learning_refs"]),
        supersedes_version_id=_parse_uuid(row["supersedes_version_id"]),
        superseded_by_version_id=_parse_uuid(row["superseded_by_version_id"]),
        admission_id=_parse_uuid(row["admission_id"]),
        id=row["id"],
        created_at=row["created_at"],
        ended_at=row["ended_at"],
    )


def _dump_candidate(candidate: ProcedureCandidate) -> str:
    return _json(
        {
            "source_kind": candidate.source_kind.value,
            "provenance": candidate.provenance.value,
            "name": candidate.name,
            "trigger": candidate.trigger,
            "preconditions": candidate.preconditions,
            "steps": candidate.steps,
            "success_criteria": candidate.success_criteria,
            "limits": candidate.limits,
            "evidence_refs": [
                {"kind": ref.kind, "id": str(ref.id)} for ref in candidate.evidence_refs
            ],
            "learning_refs": [
                {"learning_id": str(ref.learning_id)} for ref in candidate.learning_refs
            ],
            "proposed_identity_id": (
                str(candidate.proposed_identity_id)
                if candidate.proposed_identity_id
                else None
            ),
            "workspace_run_approved": candidate.workspace_run_approved,
            "status": candidate.status.value,
            "id": str(candidate.id) if candidate.id else None,
            "submitted_at": (
                candidate.submitted_at.isoformat() if candidate.submitted_at else None
            ),
            "resolved_at": (
                candidate.resolved_at.isoformat() if candidate.resolved_at else None
            ),
        }
    )


def _candidate_from_dict(data: object) -> ProcedureCandidate:
    payload = _load(data)
    if not isinstance(payload, dict):
        payload = {}
    submitted = payload.get("submitted_at")
    resolved = payload.get("resolved_at")
    return ProcedureCandidate(
        source_kind=ProcedureSourceKind(payload["source_kind"]),
        provenance=Provenance(payload["provenance"]),
        name=payload["name"],
        trigger=payload["trigger"],
        preconditions=list(payload.get("preconditions") or []),
        steps=list(payload.get("steps") or []),
        success_criteria=list(payload.get("success_criteria") or []),
        limits=list(payload.get("limits") or []),
        evidence_refs=_evidence(payload.get("evidence_refs") or []),
        learning_refs=_learnings(payload.get("learning_refs") or []),
        proposed_identity_id=_parse_uuid(payload.get("proposed_identity_id")),
        workspace_run_approved=bool(payload.get("workspace_run_approved")),
        status=CandidateStatus(payload.get("status", "pending")),
        id=_parse_uuid(payload.get("id")),
        submitted_at=datetime.fromisoformat(submitted) if submitted else None,
        resolved_at=datetime.fromisoformat(resolved) if resolved else None,
    )


class PostgresProcedureStore:
    def __init__(self, pool: Any, *, embedder: Any | None = None) -> None:
        self._pool = pool
        self._embedder = embedder

    async def save_candidate(self, candidate: ProcedureCandidate) -> ProcedureCandidate:
        if candidate.id is None:
            candidate.id = uuid4()
        if candidate.submitted_at is None:
            candidate.submitted_at = datetime.now(UTC)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO procedure_candidates (
                    id, proposed_identity_id, source_kind, provenance, name, trigger,
                    preconditions, steps, success_criteria, limits, evidence_refs,
                    learning_refs, workspace_run_approved, status, submitted_at, resolved_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9::jsonb, $10::jsonb,
                    $11::jsonb, $12::jsonb, $13, $14, $15, $16
                )
                ON CONFLICT (id) DO UPDATE SET
                    proposed_identity_id = EXCLUDED.proposed_identity_id,
                    source_kind = EXCLUDED.source_kind,
                    provenance = EXCLUDED.provenance,
                    name = EXCLUDED.name,
                    trigger = EXCLUDED.trigger,
                    preconditions = EXCLUDED.preconditions,
                    steps = EXCLUDED.steps,
                    success_criteria = EXCLUDED.success_criteria,
                    limits = EXCLUDED.limits,
                    evidence_refs = EXCLUDED.evidence_refs,
                    learning_refs = EXCLUDED.learning_refs,
                    workspace_run_approved = EXCLUDED.workspace_run_approved,
                    status = EXCLUDED.status,
                    resolved_at = EXCLUDED.resolved_at
                """,
                candidate.id,
                candidate.proposed_identity_id,
                candidate.source_kind.value,
                candidate.provenance.value,
                candidate.name,
                candidate.trigger,
                _json(candidate.preconditions),
                _json(candidate.steps),
                _json(candidate.success_criteria),
                _json(candidate.limits),
                _dump_evidence(candidate.evidence_refs),
                _dump_learnings(candidate.learning_refs),
                candidate.workspace_run_approved,
                candidate.status.value,
                candidate.submitted_at,
                candidate.resolved_at,
            )
        return candidate

    async def get_candidate(self, candidate_id: UUID) -> ProcedureCandidate | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM procedure_candidates WHERE id = $1", candidate_id
            )
        return _candidate_from_row(row) if row else None

    async def save_identity(self, identity: ProcedureIdentity) -> ProcedureIdentity:
        if identity.id is None:
            identity.id = uuid4()
        now = datetime.now(UTC)
        if identity.created_at is None:
            identity.created_at = now
        identity.updated_at = now
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO procedure_identities (
                    id, canonical_name, status, active_version_id, created_at, updated_at
                ) VALUES ($1, $2, $3, $4, $5, $6)
                ON CONFLICT (id) DO UPDATE SET
                    canonical_name = EXCLUDED.canonical_name,
                    status = EXCLUDED.status,
                    active_version_id = EXCLUDED.active_version_id,
                    updated_at = EXCLUDED.updated_at
                """,
                identity.id,
                identity.canonical_name,
                identity.status.value,
                identity.active_version_id,
                identity.created_at,
                identity.updated_at,
            )
        return identity

    async def get_identity(self, identity_id: UUID) -> ProcedureIdentity | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM procedure_identities WHERE id = $1", identity_id
            )
        return _identity_from_row(row) if row else None

    async def find_identity_by_name(
        self, canonical_name: str
    ) -> ProcedureIdentity | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM procedure_identities
                WHERE lower(canonical_name) = lower($1)
                """,
                canonical_name,
            )
        return _identity_from_row(row) if row else None

    async def save_admission(self, admission: ProcedureAdmission) -> ProcedureAdmission:
        if admission.id is None:
            admission.id = uuid4()
        if admission.created_at is None:
            admission.created_at = datetime.now(UTC)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO procedure_admissions (
                    id, candidate_id, decision, reason, reviewer,
                    review_evidence_refs, review_learning_refs, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8)
                ON CONFLICT (id) DO NOTHING
                """,
                admission.id,
                admission.candidate_id,
                admission.decision.value,
                admission.reason,
                admission.reviewer,
                _dump_evidence(admission.review_evidence_refs),
                _dump_learnings(admission.review_learning_refs),
                admission.created_at,
            )
        return admission

    def _embedding(self, version: ProcedureVersion) -> list[float] | None:
        if self._embedder is None:
            return None
        try:
            return list(self._embedder.encode(f"{version.trigger} {version.name}"))
        except Exception:
            return None

    async def save_version(self, version: ProcedureVersion) -> ProcedureVersion:
        if version.id is None:
            version.id = uuid4()
        if version.created_at is None:
            version.created_at = datetime.now(UTC)
        embedding = self._embedding(version)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO procedure_versions (
                    id, procedure_id, version_number, name, trigger, preconditions,
                    steps, success_criteria, limits, provenance, evidence_refs,
                    learning_refs, status, supersedes_version_id,
                    superseded_by_version_id, admission_id, embedding, created_at, ended_at
                ) VALUES (
                    $1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8::jsonb, $9::jsonb,
                    $10, $11::jsonb, $12::jsonb, $13, $14, $15, $16, $17::vector, $18, $19
                )
                ON CONFLICT (id) DO UPDATE SET
                    status = EXCLUDED.status,
                    superseded_by_version_id = EXCLUDED.superseded_by_version_id,
                    ended_at = EXCLUDED.ended_at
                """,
                version.id,
                version.procedure_id,
                version.version_number,
                version.name,
                version.trigger,
                _json(version.preconditions),
                _json(version.steps),
                _json(version.success_criteria),
                _json(version.limits),
                version.provenance.value,
                _dump_evidence(version.evidence_refs),
                _dump_learnings(version.learning_refs),
                version.status.value,
                version.supersedes_version_id,
                version.superseded_by_version_id,
                version.admission_id,
                embedding,
                version.created_at,
                version.ended_at,
            )
        return version

    async def get_version(self, version_id: UUID) -> ProcedureVersion | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM procedure_versions WHERE id = $1", version_id
            )
        return _version_from_row(row) if row else None

    async def list_versions(self, procedure_id: UUID) -> list[ProcedureVersion]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM procedure_versions
                WHERE procedure_id = $1
                ORDER BY version_number
                """,
                procedure_id,
            )
        return [_version_from_row(row) for row in rows]

    async def list_active_versions(self) -> list[ProcedureVersion]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM procedure_versions WHERE status = 'active'"
            )
        return [_version_from_row(row) for row in rows]

    async def list_all_versions(self) -> list[ProcedureVersion]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT * FROM procedure_versions ORDER BY created_at"
            )
        return [_version_from_row(row) for row in rows]

    async def save_feedback(self, feedback: ProcedureFeedback) -> ProcedureFeedback:
        if feedback.id is None:
            feedback.id = uuid4()
        if feedback.created_at is None:
            feedback.created_at = datetime.now(UTC)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO procedure_feedback (
                    id, procedure_version_id, action_record_id, outcome, summary,
                    evidence_refs, learning_refs, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7::jsonb, $8)
                """,
                feedback.id,
                feedback.procedure_version_id,
                feedback.action_record_id,
                feedback.outcome.value,
                feedback.summary,
                _dump_evidence(feedback.evidence_refs),
                _dump_learnings(feedback.learning_refs),
                feedback.created_at,
            )
        return feedback

    async def list_feedback(self, version_id: UUID) -> list[ProcedureFeedback]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM procedure_feedback
                WHERE procedure_version_id = $1
                ORDER BY created_at
                """,
                version_id,
            )
        return [
            ProcedureFeedback(
                procedure_version_id=row["procedure_version_id"],
                action_record_id=row["action_record_id"],
                outcome=ProcedureOutcome(row["outcome"]),
                summary=row["summary"],
                evidence_refs=_evidence(row["evidence_refs"]),
                learning_refs=_learnings(row["learning_refs"]),
                id=row["id"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def save_event(
        self, event: ProcedureLifecycleEvent
    ) -> ProcedureLifecycleEvent:
        if event.id is None:
            event.id = uuid4()
        if event.created_at is None:
            event.created_at = datetime.now(UTC)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO procedure_lifecycle_events (
                    id, kind, reason, identity_id, candidate_id, version_id,
                    evidence_refs, learning_refs, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8::jsonb, $9)
                """,
                event.id,
                event.kind.value,
                event.reason,
                event.identity_id,
                event.candidate_id,
                event.version_id,
                _dump_evidence(event.evidence_refs),
                _dump_learnings(event.learning_refs),
                event.created_at,
            )
        return event

    async def save_provisional(
        self, provisional: ProvisionalProcedure
    ) -> ProvisionalProcedure:
        if provisional.id is None:
            provisional.id = uuid4()
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO procedure_provisionals (
                    id, goal_id, execution_id, candidate, status, resolution_reason
                ) VALUES ($1, $2, $3, $4::jsonb, $5, $6)
                ON CONFLICT (id) DO UPDATE SET
                    candidate = EXCLUDED.candidate,
                    status = EXCLUDED.status,
                    resolution_reason = EXCLUDED.resolution_reason
                """,
                provisional.id,
                provisional.goal_id,
                provisional.execution_id,
                _dump_candidate(provisional.candidate),
                provisional.status.value,
                provisional.resolution_reason,
            )
        return provisional

    async def list_open_provisionals(self, goal_id: UUID) -> list[ProvisionalProcedure]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM procedure_provisionals
                WHERE goal_id = $1 AND status = 'open'
                """,
                goal_id,
            )
        return [
            ProvisionalProcedure(
                goal_id=row["goal_id"],
                candidate=_candidate_from_dict(row["candidate"]),
                execution_id=_parse_uuid(row["execution_id"]),
                status=ProvisionalStatus(row["status"]),
                resolution_reason=row["resolution_reason"],
                id=row["id"],
            )
            for row in rows
        ]

    async def list_candidates(
        self, statuses: list[CandidateStatus] | None = None
    ) -> list[ProcedureCandidate]:
        async with self._pool.acquire() as conn:
            if statuses is None:
                rows = await conn.fetch(
                    "SELECT * FROM procedure_candidates ORDER BY submitted_at DESC"
                )
            else:
                rows = await conn.fetch(
                    """
                    SELECT * FROM procedure_candidates
                    WHERE status = ANY($1::text[])
                    ORDER BY submitted_at DESC
                    """,
                    [status.value for status in statuses],
                )
        return [_candidate_from_row(row) for row in rows]

    async def list_events(
        self,
        *,
        identity_id: UUID | None = None,
        candidate_id: UUID | None = None,
    ) -> list[ProcedureLifecycleEvent]:
        clauses = []
        args: list[object] = []
        if identity_id is not None:
            args.append(identity_id)
            clauses.append(f"identity_id = ${len(args)}")
        if candidate_id is not None:
            args.append(candidate_id)
            clauses.append(f"candidate_id = ${len(args)}")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                f"""
                SELECT * FROM procedure_lifecycle_events
                {where}
                ORDER BY created_at
                """,
                *args,
            )
        return [
            ProcedureLifecycleEvent(
                kind=LifecycleEventKind(row["kind"]),
                reason=row["reason"],
                identity_id=_parse_uuid(row["identity_id"]),
                candidate_id=_parse_uuid(row["candidate_id"]),
                version_id=_parse_uuid(row["version_id"]),
                evidence_refs=_evidence(row["evidence_refs"]),
                learning_refs=_learnings(row["learning_refs"]),
                id=row["id"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def save_invocation(
        self, invocation: ProcedureInvocation
    ) -> ProcedureInvocation:
        if invocation.id is None:
            invocation.id = uuid4()
        if invocation.started_at is None:
            invocation.started_at = datetime.now(UTC)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO procedure_invocations (
                    id, procedure_id, version_id, origin, caller, task_context_ref,
                    state, outcome_id, started_at, finished_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
                ON CONFLICT (id) DO UPDATE SET
                    state = EXCLUDED.state,
                    outcome_id = EXCLUDED.outcome_id,
                    finished_at = EXCLUDED.finished_at
                """,
                invocation.id,
                invocation.procedure_id,
                invocation.version_id,
                invocation.origin.value,
                invocation.caller,
                invocation.task_context_ref,
                invocation.state.value,
                invocation.outcome_id,
                invocation.started_at,
                invocation.finished_at,
            )
        return invocation

    async def get_invocation(
        self, invocation_id: UUID
    ) -> ProcedureInvocation | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM procedure_invocations WHERE id = $1", invocation_id
            )
        if row is None:
            return None
        return ProcedureInvocation(
            procedure_id=row["procedure_id"],
            version_id=row["version_id"],
            origin=ProcedureInvocationOrigin(row["origin"]),
            caller=row["caller"],
            state=InvocationState(row["state"]),
            task_context_ref=row["task_context_ref"],
            outcome_id=_parse_uuid(row["outcome_id"]),
            id=row["id"],
            started_at=row["started_at"],
            finished_at=row["finished_at"],
        )

    async def save_action_link(self, link: ProcedureActionLink) -> ProcedureActionLink:
        if link.id is None:
            link.id = uuid4()
        if link.created_at is None:
            link.created_at = datetime.now(UTC)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO procedure_action_links (
                    id, invocation_id, procedure_id, version_id, step_ref,
                    action_trace_ref, capability_decision, outcome, created_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                """,
                link.id,
                link.invocation_id,
                link.procedure_id,
                link.version_id,
                link.step_ref,
                link.action_trace_ref,
                link.capability_decision.value,
                link.outcome.value,
                link.created_at,
            )
        return link

    async def list_action_links(self, invocation_id: UUID) -> list[ProcedureActionLink]:
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT * FROM procedure_action_links
                WHERE invocation_id = $1 ORDER BY created_at
                """,
                invocation_id,
            )
        return [
            ProcedureActionLink(
                invocation_id=row["invocation_id"],
                procedure_id=row["procedure_id"],
                version_id=row["version_id"],
                step_ref=row["step_ref"],
                capability_decision=CapabilityDecision(row["capability_decision"]),
                outcome=ProcedureActionOutcome(row["outcome"]),
                action_trace_ref=row["action_trace_ref"],
                id=row["id"],
                created_at=row["created_at"],
            )
            for row in rows
        ]

    async def save_activation_feedback(
        self, feedback: ProcedureOutcomeFeedback
    ) -> ProcedureOutcomeFeedback:
        if feedback.id is None:
            feedback.id = uuid4()
        if feedback.submitted_at is None:
            feedback.submitted_at = datetime.now(UTC)
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO procedure_activation_feedback (
                    id, invocation_id, procedure_id, version_id, outcome,
                    summary, action_link_ids, submitted_at
                ) VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8)
                ON CONFLICT (invocation_id) DO NOTHING
                """,
                feedback.id,
                feedback.invocation_id,
                feedback.procedure_id,
                feedback.version_id,
                feedback.outcome.value,
                feedback.summary,
                _json([str(item) for item in feedback.action_link_ids]),
                feedback.submitted_at,
            )
        existing = await self.get_activation_feedback(feedback.invocation_id)
        return existing or feedback

    async def get_activation_feedback(
        self, invocation_id: UUID
    ) -> ProcedureOutcomeFeedback | None:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM procedure_activation_feedback
                WHERE invocation_id = $1
                """,
                invocation_id,
            )
        if row is None:
            return None
        return ProcedureOutcomeFeedback(
            invocation_id=row["invocation_id"],
            procedure_id=row["procedure_id"],
            version_id=row["version_id"],
            outcome=ProcedureOutcome(row["outcome"]),
            summary=row["summary"],
            action_link_ids=[UUID(str(item)) for item in (_load(row["action_link_ids"]) or [])],
            id=row["id"],
            submitted_at=row["submitted_at"],
        )

    async def action_record_exists(self, action_record_id: UUID) -> bool:
        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT 1 FROM action_records WHERE id = $1", action_record_id
            )
        return row is not None
