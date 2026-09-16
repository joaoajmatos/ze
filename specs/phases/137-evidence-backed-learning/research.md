# Research: Evidence-Backed Goal Learning

## R1. One learning model, not a repaired dual write

**Decision:** Replace both `goal_learnings` and `goals.learnings` with a new authoritative `goal_learning_claims` aggregate plus normalized evidence, review, relationship, and promotion tables.

**Rationale:** The row table holds fragments while the blob serves an accumulated prompt summary. Neither can reliably express epistemic status or correction history. Making one feed the other would preserve two authorities. A query-built prompt summary from authoritative learning rows is sufficient.

**Rejected:** Retain `goals.learnings` as a materialized cache; retain `goal_learnings` as an audit shadow; write both during migration. All violate the required hard cut.

## R2. ActionRecords are evidence, never claim identity

**Decision:** Each automated learning references Phase 136 `ActionRecord.id`; the action record remains separately retrievable outcome evidence. `GoalLearning` never subclasses, embeds, or mirrors the action record.

**Rationale:** A verified result answers “what happened.” A learning answers “what may be reusable or true beyond that event.” They have different kinds, lifecycles, and confidence.

**Rejected:** Add learning fields to ActionRecord; use a generic event table; copy action result text into a learning without an id.

## R3. Generalization starts as INFERENCE

**Decision:** Generated reusable lessons are `ClaimKind.INFERENCE`, normally
`Provenance.SYNTHESIZED`, and are exposed through the learning-retrieval projection rather than
persisted to `memory_facts`. Only direct supporting evidence or explicit user confirmation can
justify publishing the exact assertion as a FACT through the perception-fact path.

**Rationale:** Generalization necessarily goes beyond any one observed outcome. Multiple LLM renderings are not independent evidence.

**Rejected:** Promote all completion learnings as FACT, or regard two generated summaries as corroboration.

## R4. Evidence diversity is semantic, not a count alone

**Decision:** Automatic eligibility requires: (a) at least two supporting action-record ids, (b) distinct execution contexts, defined initially as different goal ids or different milestone ids with different action lineage, (c) no unresolved material contradiction, and (d) a configured consistency threshold. Explicit user confirmation bypasses the numeric diversity threshold but is recorded as evidence.

**Rationale:** Retries, tool steps, and summaries generated from one milestone are correlated. Distinct context bounds false corroboration while remaining implementable from Phase 136 fields.

**Rejected:** “Two evidence rows” regardless of origin; requiring two separate goals only; using generic collision arbitration to decide truth.

## R5. Contradiction queues review; it does not adjudicate

**Decision:** Use the existing NLI/claim comparison capability to identify material conflicts. Store a `contradicts` relationship with evidence and transition the affected active claim to `REVIEW_NEEDED`. Only an explicit user/system review may retract, supersede, or keep it.

**Rationale:** Contradiction detection is evidence, not authority. This preserves the contribution-seam distinction between collision detection and arbitration.

**Rejected:** Automatically retract based on NLI; add generic cross-function contribution arbitration.

## R6. Retraction is lifecycle plus append-only history

**Decision:** Claims have an active lifecycle (`PENDING_REVIEW`, `ACTIVE`, `REVIEW_NEEDED`, `RETRACTED`, `SUPERSEDED`). Review decisions and claim relationships are append-only. Retraction freezes the claim’s historical relevance but leaves its evidence queryable.

**Rationale:** The user and operators must be able to inspect why a claim once influenced reasoning. Deletion hides error provenance.

**Rejected:** Hard delete; mutate claim text in place on correction; a boolean `reviewed`.

## R7. Promotion records state independently from learning lifecycle

**Decision:** A `LearningPromotion` records only each attempt to publish a FACT-eligible learning
through the perception-fact path, its eligibility basis, resulting fact id, and failure reason.
It is idempotent per learning + authoritative claim revision. The underlying learning can stay
active as an INFERENCE even when no FACT publication is requested or succeeds.

**Rationale:** Promotion is an external side effect, not evidence itself. Separating it prevents retry ambiguity and allows review before publication.

**Rejected:** A `promoted` boolean; promote during extraction before diversity/review.

## R8. Retrieval separates raw outcomes from lessons

**Decision:** Add `list_eligible_learnings()` to GoalStore for planner/executor context and an equivalent bounded read for priority. It filters active claims, excludes unresolved contradictions and retractions, applies relevance/confidence limits, and returns doctrine labels plus evidence summaries. Existing action-record consumers continue to retrieve raw outcomes through Phase 136 APIs.

**Rationale:** A prompt must not receive tentative learning as unqualified truth, and a new model should not erase access to raw outcomes.

**Rejected:** Reuse `list_learnings()` without lifecycle/evidence metadata; feed all historical rows to prompts; merge ActionRecord and learning retrieval.

## R9. Legacy migration preserves history without inventing proof

**Decision:** Migrate each legacy `goal_learnings` row to an imported historical claim with explicit `Provenance.SYNTHESIZED` only if its source says automated extraction; otherwise use a migration-owned imported historical marker represented in metadata/audit, not a new doctrine provenance. Attach available goal/milestone/action references deterministically. The blob is only used to recover unique text absent from rows, tagged `REVIEW_NEEDED` with no automatic eligibility. Drop both legacy stores after validation.

**Rationale:** Old strings lack enough provenance and evidence to claim corroboration. Keeping them visible for review is honest; treating their duplication as evidence is not.

**Rejected:** Map every old entry to FACT; silently discard unmatched blob text; retain blob as fallback.

## R10. No source or priority system redesign

**Decision:** This phase supplies a filtered, labeled learning read model to existing consumers. It does not alter `signal_sources()`, source polling, priority override persistence, push budgets, notification policy, loop surfacing, or contribution arbitration.

**Rationale:** The requested change is goal-learning truth maintenance, not an inflow or attention-arbitration redesign.
