# Contract: Social Cognition Co-Occurrence

No new REST route and no new UI (FR-011) — this phase's "interfaces" are the
`ze_sdk` surface a plugin consumes, the two `Contribution` shapes the
contribution seam gates, and the two conversational tools an agent can call.
`/brain/graph` and existing REST already expose the resulting graph edges
unchanged from Phase 128.

## `ze_sdk.correlation` (NEW re-export module)

```python
from ze_sdk.correlation import Hypothesis, EvidenceRef, HypothesisStore

# HypothesisStore is the Protocol ze_personal.social code depends on —
# satisfied by the existing ze_correlation.store.PostgresHypothesisStore,
# wired at apps/ze-api/ze_api/container.py, same DI shape as every other
# store Protocol in this codebase.
class HypothesisStore(Protocol):
    async def save(self, hypothesis: Hypothesis) -> UUID: ...
    async def get(self, id: UUID) -> Hypothesis | None: ...
    async def list_by_entities(self, entity_ids: list[UUID]) -> list[Hypothesis]: ...  # NEW method
    async def confirm(self, id: UUID) -> Hypothesis: ...       # NEW method
    async def mark_promoted(self, id: UUID) -> Hypothesis: ...  # NEW method
```

## Contribution shape 1 — hypothesis formation (submitted by `SocialCooccurrenceJob`)

```python
Contribution(
    claim_kind=ClaimKind.INFERENCE,
    provenance=Provenance.SYNTHESIZED,
    confidence=Confidence(value=<weighted_score>, decay_profile=DecayProfile.TIME_LINEAR),
    target_face=TargetFace.SELF,
    source_function=SourceFunction.REFLECTION,   # licensed for INFERENCE — see research.md Decision 1
    evidence=[EvidenceRef(kind="signal", id=<event_id>), ...],
    entity_ids=[person_id, project_id],  # or [person_a_id, person_b_id]
)
```

Write callback: `hypothesis_store.save(hypothesis)` (create) or an
update-in-place path that re-saves the same `id` with refreshed `evidence`/
`confidence` (exact method name is a task-level detail — either `save()` is
idempotent on `id` or a dedicated `update()` is added; `tasks.md` decides,
`data-model.md`'s `existing_hypothesis_id` field is what the job checks first).

## Contribution shape 2 — promotion (submitted by `SocialCooccurrenceJob` or the confirm tool)

```python
Contribution(
    claim_kind=ClaimKind.IDENTITY,
    provenance=Provenance.SYNTHESIZED,
    confidence=Confidence(value=<hypothesis.confidence>, decay_profile=DecayProfile.TIME_LINEAR),
    target_face=TargetFace.USER,
    source_function=SourceFunction.SOCIAL_COGNITION,   # licensed for IDENTITY only
    evidence=[EvidenceRef(kind="signal", id=<event_id>), ...],  # carried over from the hypothesis
    entity_ids=[person_id, project_id],
)
```

Write callback: `_write_relationship_edge_via_seam()`
(`ze_personal/graph/memory_hooks.py`) — upserts both entities, then
`graph_store.upsert_relationship(Relationship(predicate=WORKS_ON or
COLLABORATES_WITH, confidence=..., last_contact=...))`. Submitted via
`ze_sdk.contribution.submit_and_detect_collisions(contribution, write=..., collision_store=..., nli_client=...)`
— collision detection (Phase 126) applies automatically, no new arbitration
logic (spec Assumptions).

## Tool: `who_is_on_project`

```python
@tool
async def who_is_on_project(project_name: str) -> WhoIsOnProjectResult:
    """Answer "who is on project X" with confirmed edges and hedged inferences kept separate."""
```

```python
@dataclass
class WhoIsOnProjectResult:
    project_name: str
    confirmed_members: list[str]           # from GraphStore, current-membership view (30-day window)
    hedged_candidates: list[HedgedCandidate]  # from unconfirmed, unpromoted hypotheses only
```

```python
@dataclass
class HedgedCandidate:
    person_name: str
    evidence_summaries: list[str]  # human-readable, e.g. "3 email replies in the last 2 weeks"
```

Never merges the two lists into one undifferentiated "members" answer — the
agent's response template must render `hedged_candidates` with hedging
language (e.g. "seems to be," "based on recent messages") and
`confirmed_members` without it, satisfying FR-005/User Story 1 Acceptance
Scenario 2 by construction rather than by prompt instruction alone.

## Tool: `confirm_project_membership`

```python
@tool
async def confirm_project_membership(hypothesis_id: UUID) -> ConfirmationResult:
    """User says 'yes, Alice is on Launch' — sets confirmed=true and promotes immediately."""
```

Calls `hypothesis_store.confirm(hypothesis_id)` then, if not already
`promoted_at`-set, runs the same promotion write as the job's corroboration
path (shared helper, not duplicated logic) — mirroring
`PersonStore.confirm()`'s "flip the flag, then write the entity" shape
(research.md, "pending-contact confirm flow" precedent).
