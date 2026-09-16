# Data Model: Governed Procedure Lifecycle

Phase 137 owns the underlying `Evidence` and `Learning` vocabulary. The types below retain
references to those canonical records and must not duplicate their payload or lifecycle fields.

## ProcedureIdentity

The stable identity for one operational purpose.

| Field | Meaning |
|---|---|
| `id` | Stable identifier |
| `canonical_name` | Normalized human-readable purpose |
| `status` | `active`, `retired` |
| `active_version_id` | The sole retrievable version, or null |
| `created_at`, `updated_at` | Lifecycle timestamps |

Invariant: an identity has zero or one active version.

## ProcedureCandidate

An untrusted proposal submitted by any supported source.

| Field | Meaning |
|---|---|
| `id` | Candidate identifier |
| `proposed_identity_id` | Existing identity when revision is intended; otherwise null |
| `source_kind` | `goal`, `workflow`, `workspace_run`, `action_pattern`, `user_instruction`, `reflection`, `skill` |
| `provenance` | Shared honest provenance |
| `name`, `trigger`, `preconditions`, `steps`, `success_criteria`, `limits` | Proposed playbook content |
| `evidence_refs` | Phase 137 evidence references |
| `learning_refs` | Phase 137 learning references |
| `status` | `pending`, `needs_review`, `approved`, `rejected`, `withdrawn` |
| `submitted_at`, `resolved_at` | Candidate timestamps |

Validation: non-empty trigger and ordered steps; success criteria required; evidence references
must be valid under Phase 137; only `workspace_run` evidence already marked approved is eligible.

## ProcedureAdmission

The immutable decision over a candidate.

| Field | Meaning |
|---|---|
| `id`, `candidate_id` | Decision identity |
| `decision` | `approve`, `reject`, `needs_review`, `withdraw` |
| `reason` | Human-readable decision rationale |
| `review_evidence_refs`, `review_learning_refs` | Phase 137 reasoning inputs |
| `reviewer` | User or system reviewer identity/context |
| `created_at` | Decision time |

An approval creates one ProcedureVersion atomically with its decision. A candidate may have
multiple review attempts, but only one terminal approval/rejection/withdrawal.

## ProcedureVersion

Immutable admitted playbook content.

| Field | Meaning |
|---|---|
| `id`, `procedure_id`, `version_number` | Identity and ordered lineage |
| `name`, `trigger`, `preconditions`, `steps`, `success_criteria`, `limits` | Snapshot content |
| `provenance`, `evidence_refs`, `learning_refs` | Attributable basis |
| `status` | `active`, `superseded`, `rolled_back`, `retired` |
| `supersedes_version_id` | Prior version when replacing one |
| `superseded_by_version_id` | Successor link |
| `admission_id` | Approving decision |
| `created_at`, `ended_at` | Validity interval |

Invariant: version content does not mutate after admission. A material change creates a new
candidate and version.

## ProcedureFeedback

Append-only outcome evidence about a specific version.

| Field | Meaning |
|---|---|
| `id`, `procedure_version_id` | Feedback target |
| `action_record_id` | Existing action/execution record; not copied action data |
| `outcome` | `succeeded`, `failed`, `partial`, `abandoned` |
| `summary` | Outcome explanation |
| `evidence_refs`, `learning_refs` | Phase 137 feedback basis |
| `created_at` | Recorded time |

Feedback cannot modify ProcedureVersion fields. It may create a candidate or review request.

## ProcedureLifecycleEvent

Append-only audit record for `submitted`, `reviewed`, `admitted`, `superseded`, `rolled_back`,
`restored`, `retired`, `feedback_recorded`, and `discarded_provisional`.

Every event references the affected candidate/version/identity where applicable and includes the
Phase 137 evidence/learning references that justified it.

## ProvisionalProcedure

Temporary goal-execution material, scoped to an owning goal and execution attempt.

| Field | Meaning |
|---|---|
| `goal_id`, `execution_id` | Ownership and recovery scope |
| `candidate_payload` | Proposed playbook content and Phase 137 references |
| `status` | `open`, `submitted`, `discarded` |
| `resolution_reason` | Completion/admission handoff or intentional discard |

Invariant: no `open` provisional procedure survives a goal terminal state or recovered executor
startup. `submitted` is not an active procedure; it means a candidate now owns the material.

## Relationships

```text
Phase 137 Evidence/Learning ──▶ ProcedureCandidate ──▶ ProcedureAdmission
                                                    └─▶ ProcedureVersion ──▶ ProcedureFeedback
Goal execution ──▶ ProvisionalProcedure ──▶ ProcedureCandidate | discarded event
```

The relationship is evidence attribution, not ownership: deleting or unavailable source records
must preserve the historical reference and mark it unavailable.
