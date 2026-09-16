# Contract: Procedure Admission Lifecycle

Internal typed contract. This is the only procedure write boundary; it introduces no generic
contribution arbitration and no skill-execution capability.

## Submission

```python
async def submit_procedure_candidate(
    candidate: ProcedureCandidate,
) -> ProcedureCandidate:
    ...
```

Callers may submit only one of these `source_kind` values:

```text
goal | workflow | workspace_run | action_pattern |
user_instruction | reflection | skill
```

The candidate must include Phase 137 evidence references and shared provenance. A
`workspace_run` candidate is rejected before review unless its evidence confirms existing
approval. Reflection candidates require an already reviewed dream/reflection artifact.

Submission stores a pending candidate; it does not make the procedure retrievable or execute it.

## Review and admission

```python
async def review_procedure_candidate(
    candidate_id: UUID,
    decision: ProcedureAdmissionDecision,
    *,
    reason: str,
    review_evidence: Sequence[EvidenceRef],
    review_learnings: Sequence[LearningRef],
) -> ProcedureAdmissionResult:
    ...
```

```text
ProcedureAdmissionDecision = approve | reject | needs_review | withdraw
```

On `approve`, the operation atomically:

1. validates operational completeness and source eligibility;
2. resolves or creates a canonical ProcedureIdentity;
3. creates an immutable ProcedureVersion;
4. supersedes the existing active version only when the candidate replaces it;
5. records ProcedureAdmission and lifecycle events; and
6. exposes the new active version to default retrieval.

`reject`, `needs_review`, and `withdraw` create a decision record but never create an active
version. A reviewer may only approve a candidate whose evidence meets Phase 137 validation.

## Feedback

```python
async def record_procedure_feedback(
    procedure_version_id: UUID,
    *,
    action_record_id: UUID,
    outcome: ProcedureOutcome,
    summary: str,
    evidence: Sequence[EvidenceRef],
    learnings: Sequence[LearningRef],
) -> ProcedureFeedback:
    ...
```

```text
ProcedureOutcome = succeeded | failed | partial | abandoned
```

The action record must already exist. This operation appends feedback and may enqueue/return a
review indication. It MUST NOT alter ProcedureVersion content or run a skill/workspace action.

## Rollback

```python
async def rollback_procedure(
    procedure_id: UUID,
    *,
    target_version_id: UUID | None,
    reason: str,
    evidence: Sequence[EvidenceRef],
    learnings: Sequence[LearningRef],
) -> ProcedureRollbackResult:
    ...
```

The active version is marked `rolled_back`. If `target_version_id` is omitted, the service
chooses the latest eligible non-retired predecessor. If no eligible target exists, it retires
the ProcedureIdentity. Rollback retains all prior versions and emits lifecycle events.

## Retrieval

```python
async def retrieve_procedures(
    request: RetrievalRequest,
    *,
    include_history: bool = False,
) -> list[ProcedureVersion]:
    ...
```

Default retrieval returns active admitted versions only. `include_history=True` is for an
authorized audit/review surface and includes superseded, rolled-back, and retired versions with
their decisions and lineage.

## Hard-cut requirements

- `MemoryStore.propose_procedure` is absent from the public contract.
- No source calls a direct `memory_procedures` persistence function.
- Dream/reflection promotion calls `submit_procedure_candidate` after its existing review.
- Goal and workflow extraction call `submit_procedure_candidate`.
- Provisional goal material calls the submission contract on completion or records a discard
  lifecycle event on every other terminal path.

## Error behavior

Use typed domain errors for incomplete candidates, invalid Phase 137 evidence, unapproved
workspace evidence, invalid lifecycle transition, unknown version, and missing action record.
No caller may catch an admission failure and fall back to a direct procedure write.
