# Contract: Evidence-Backed Learning and Promotion

Internal Python and REST contract. Exact module names may vary, but behavior and doctrine are pinned.

## Domain interfaces

```python
class GoalLearningStore(Protocol):
    async def create_learning(
        self,
        learning: GoalLearning,
        evidence: list[LearningEvidenceDraft],
    ) -> GoalLearning: ...

    async def get_learning(self, learning_id: UUID) -> GoalLearning | None: ...

    async def list_goal_learnings(
        self,
        goal_id: UUID,
        *,
        include_history: bool = False,
    ) -> list[GoalLearningSummary]: ...

    async def list_eligible_learnings(
        self,
        query: str,
        *,
        goal_id: UUID | None = None,
        limit: int = 10,
    ) -> list[EligibleLearning]: ...

    async def review_learning(
        self,
        learning_id: UUID,
        decision: LearningReviewDecision,
        *,
        rationale: str | None = None,
        corrected_content: str | None = None,
    ) -> GoalLearning: ...

    async def record_contradiction(
        self,
        learning_id: UUID,
        evidence: LearningEvidenceDraft,
        *,
        rationale: str,
    ) -> GoalLearning: ...

    async def promote_learning(self, learning_id: UUID) -> LearningPromotion: ...
```

`create_learning` validates every automated evidence reference against Phase 136 ActionRecord identity and outcome status before persistence.

## Eligibility gate

```python
@dataclass(frozen=True)
class PromotionEligibility:
    eligible: bool
    reason: str
    supporting_action_record_ids: tuple[UUID, ...]
    independent_context_count: int
    user_confirmed: bool
    unresolved_contradiction: bool
    permitted_claim_kind: ClaimKind
```

Rules:

1. Generalizations have `ClaimKind.INFERENCE` initially.
2. Automatic eligibility requires two or more supporting Phase 136 action records in distinct execution contexts, consistency above the existing configured threshold, and no unresolved contradiction.
3. User confirmation may satisfy the diversity requirement, but is stored as explicit evidence.
4. `permitted_claim_kind=FACT` only when direct evidence or user confirmation supports the exact assertion. Repeated synthesized claims do not qualify.
5. An ineligible claim creates no memory write.

## Promotion semantics

```python
async def promote_eligible_learning(
    learning: GoalLearning,
    eligibility: PromotionEligibility,
    *,
    memory_contributor: MemoryContributor,
) -> LearningPromotion:
    ...
```

- An active eligible INFERENCE is exposed by `list_eligible_learnings()` and does not create a
  `memory_facts` write or `LearningPromotion` record.
- Persist a `LearningPromotion` attempt before/with the exceptional FACT publication to provide
  idempotency.
- Submit a FACT only through the existing licensed perception-fact contribution path, at the
  explicit user-confirmation or directly observed-fact boundary.
- Preserve the learning id and all action/user evidence as citations or source references
  supported by that path.
- Never coerce an outcome-derived INFERENCE to FACT. On publication failure, record `failed`,
  preserve the learning, and do not synthesize missing evidence.

## Review and contradiction semantics

| Event | Required state result |
|---|---|
| User approves a pending inference | `active`; user review retained |
| User rejects | `retracted`; review + reason retained |
| User corrects | original `superseded`; new claim created and linked |
| Material contrary evidence | `review_needed`; `contradicts` evidence/relationship retained |
| Reviewer retains after contradiction | `active` only with decision rationale |
| Retracted/superseded claim | excluded from default retrieval/priority |

No event calls generic contribution arbitration or silently chooses a contradiction winner.

## REST surface

Goal detail evolves its existing response:

```text
GET /api/v0/goals/{goal_id}
```

It returns active learning summaries by default: `id`, `content`, `claim_kind`, `provenance`,
`confidence`, `status`, `evidence_count`, `promotion_state`, and `review_needed`.

Focused review endpoints:

```text
GET  /api/v0/goals/{goal_id}/learnings?include_history=true
GET  /api/v0/goals/{goal_id}/learnings/{learning_id}
POST /api/v0/goals/{goal_id}/learnings/{learning_id}/review
POST /api/v0/goals/{goal_id}/learnings/{learning_id}/promote
```

The review request accepts exactly `approve`, `reject`, `correct`, or `defer`, with optional
rationale and required corrected content for `correct`. Responses never expose raw/redacted
ActionRecord payloads; they expose allowed evidence summaries and ids.

## Consumer contract

`EligibleLearning` returned to planner, executor, and priority consumers includes:

```python
@dataclass(frozen=True)
class EligibleLearning:
    id: UUID
    content: str
    claim_kind: ClaimKind
    provenance: Provenance
    confidence: float
    evidence_summary: str
    relevance: float
```

Consumers must:

- use only active, non-contradicted, non-retracted eligible records;
- label `INFERENCE` as tentative in prompts/UI;
- treat FACT and INFERENCE differently;
- avoid priority overrides, notifications, push-budget behavior, and generic arbitration.
