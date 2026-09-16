# Data Model: Evidence-Backed Goal Learning

All tables below belong to `ze-automation` and are created in one `zc` migration. Names are design-level until Phase 136’s contract is verified.

## `GoalLearning`

Authoritative claim derived from goal work. It is not an ActionRecord.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `goal_id` | UUID | Goal that first produced the claim |
| `content` | text | Atomic, reviewable statement |
| `claim_kind` | shared `ClaimKind` | Normally `INFERENCE`; FACT only under doctrine gate |
| `provenance` | shared `Provenance` | Honest source origin |
| `confidence` | float | 0–1, bounded |
| `status` | `LearningStatus` | Lifecycle below |
| `created_at`, `updated_at` | timestamp | Audit timestamps |
| `activated_at`, `retracted_at` | timestamp nullable | Lifecycle timestamps |
| `superseded_by_id` | UUID nullable | Newer corrected claim |

`LearningStatus`: `pending_review`, `active`, `review_needed`, `retracted`, `superseded`.

Constraints:

- `confidence` is within `[0, 1]`.
- `content` is nonempty.
- `retracted_at` is required for `retracted`.
- a `superseded` claim has `superseded_by_id`.
- an automated claim has at least one action-record evidence link before it can become active or eligible.

## `LearningEvidence`

Immutable support or challenge link.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `learning_id` | UUID | Authoritative learning |
| `evidence_kind` | `action_record` \| `user_confirmation` \| `user_correction` | No generic inferred evidence |
| `action_record_id` | UUID nullable | Phase 136 id for action evidence |
| `review_id` | UUID nullable | User evidence from review |
| `role` | `supports` \| `contradicts` \| `derives` | Relationship to learning |
| `execution_context_key` | text nullable | Phase 136 lineage/milestone/goal-derived key |
| `excerpt` | text | Redaction-safe rationale; not raw payload |
| `created_at` | timestamp | Immutable |

Exactly one source reference applies. Unique `(learning_id, evidence_kind, action_record_id, role)` prevents duplicate support from one action.

## `LearningReview`

Append-only human or system-reviewed decision.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `learning_id` | UUID | Reviewed claim |
| `decision` | `approve` \| `reject` \| `correct` \| `defer` \| `retain` | Explicit outcome |
| `actor_kind` | `user` \| `system` | System cannot fabricate user confirmation |
| `rationale` | text nullable | Decision reason |
| `corrected_content` | text nullable | Required for `correct` |
| `created_at` | timestamp | Immutable |

`approve` from `user` supplies user-confirmation evidence. `correct` creates a new claim and a `supersedes` relationship; it never modifies original text.

## `LearningRelationship`

Typed, append-only relationship between claims.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `from_learning_id` | UUID | Source claim |
| `to_learning_id` | UUID | Target claim |
| `relationship` | `corroborates` \| `contradicts` \| `supersedes` | No winner selection |
| `basis` | text | Redaction-safe explanation |
| `created_at` | timestamp | Immutable |

## `LearningPromotion`

Audit/idempotency record for the exceptional publication of a FACT-eligible learning through the
licensed perception-fact path. Active inferred learnings are instead exposed by the
learning-retrieval projection and have no `memory_facts` row.

| Field | Type | Notes |
|---|---|---|
| `id` | UUID | Primary key |
| `learning_id` | UUID | Source learning |
| `state` | `pending` \| `promoted` \| `failed` \| `blocked` | Side-effect state |
| `memory_fact_id` | UUID nullable | Resulting Fact only when the exact learning is FACT-eligible |
| `eligibility_snapshot` | JSONB | Evidence ids, diversity decision, claim metadata |
| `failure_reason` | text nullable | Typed failure projection |
| `created_at`, `updated_at` | timestamp | Audit/idempotency |

Unique active promotion per learning/revision prevents duplicate Fact writes. An INFERENCE cannot
create a promoted row solely because it met the diversity gate.

## Derived views and indexes

- `goal_learning_claims(goal_id, status, created_at DESC)` for goal detail.
- `learning_evidence(learning_id, role)` and `(action_record_id)` for support/contradiction checks.
- context-key index for diversity evaluation.
- active/retrieval index over `(status, claim_kind, confidence)`.
- Goal detail returns a bounded summary and evidence counts; evidence detail is fetched only on demand.

## Legacy cutover

1. Read legacy `goal_learnings` and `goals.learnings` inside the migration.
2. Create imported historical claims without counting them as independently corroborated evidence.
3. Recover exact duplicate blob/row text once; unpaired blob material becomes `review_needed`.
4. Validate expected migrated counts and report/fail on unrepresentable records.
5. Remove `goals.learnings` and drop `goal_learnings`.

There is no legacy shadow column, view, dual-read query, or dual-write path after the migration.
