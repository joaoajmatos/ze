# Feature Specification: Evidence-Backed Goal Learning

**Feature Branch**: `137-evidence-backed-learning`  
**Created**: 2026-09-15  
**Status**: Implemented  
**Input**: User description: "Create roadmap Phase 137: replace dual goal-learning persistence (`goal_learnings` rows plus `goals.learnings` blob) with one authoritative evidence-bearing learning model. Depend uniformly on Phase 136 ActionRecords. Preserve Phase 133 doctrine: learnings are not Action records; verified outcomes are ActionRecords, generalizations remain INFERENCE until corroborated or confirmed by the user, and FACT is used only when the source supports it. Include promotion, review, retraction, contradiction, evidence-diversity gates, and retrieval/priority consumer behavior. Do not rewire `signal_sources()` or introduce generic contribution arbitration. Pre-v1 hard cut; no shims or dual writes."

**Governed by**: [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), [`specs/arch/claim-topology.md`](../../arch/claim-topology.md), [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md), and [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md). **Depends on** Phase 133 (`perception-facts-seam`) for claim/provenance doctrine, Phase 134 (`memory-facts-hard-cut`) for doctrine-shaped facts and no public ungated fact writer, and **Phase 136** for uniformly shaped, evidence-addressable `ActionRecord`s. Phase 136 is a required implementation prerequisite; this specification does not duplicate or redesign it.

---

## Overview

Goal execution currently records learning twice: append-only-looking `goal_learnings` rows and a lossy newline blob in `goals.learnings`. Neither representation says what happened, what supports a claimed pattern, whether it was reviewed, or whether later evidence withdrew it. The completion promoter then asks an LLM to turn that material into user facts. That shortcut can promote a plausible inference as if it were established fact.

Phase 137 replaces both stores with one authoritative, evidence-bearing `GoalLearning` model. It links every learning to one or more Phase 136 `ActionRecord`s or explicitly recorded user confirmation/review. The raw verified outcome remains an `ActionRecord`; it is never copied into or relabelled as a learning. A generalization derived from outcomes is an `INFERENCE` with honest provenance and remains non-factual until independent corroboration or explicit user confirmation justifies promotion. A `FACT` is only permitted when the underlying source itself supports a factual claim under the shared doctrine.

The feature also defines how a learning is reviewed, promoted, contradicted, retracted, retrieved, and considered by priority consumers. It deliberately leaves source polling and generic contribution arbitration untouched.

---

## Doctrine pin *(resolved — not a clarification)*

1. **Action is evidence, not learning.** Phase 136 `ActionRecord` is the normalized record of a verified outcome. A goal learning references it; it does not become one, duplicate it, or add a second action-result table.
2. **Generalization is inference first.** A statement such as "the user works best with short feedback loops" inferred from successful goal outcomes is `ClaimKind.INFERENCE`, even when a model extracted it cleanly.
3. **FACT requires source support.** A learning may be a `FACT` only when cited evidence directly establishes the statement, or the user explicitly confirms it. Several similar model-generated interpretations alone do not turn an inference into a fact.
4. **Evidence diversity matters.** Repeated records from one action, one milestone, or one homogeneous execution path increase detail but do not corroborate a generalization. Automatic promotion requires independent evidence from at least two distinct Phase 136 action records in distinct execution contexts, unless the user confirms it.
5. **Retraction is durable history.** Contradicted or superseded learnings are retained with their lifecycle and evidence history; they are excluded from normal retrieval and priority input. No destructive overwrite hides why Ze stopped relying on them.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Goal outcomes become evidence-backed learnings (Priority: P1)

When an executor records a verified outcome, it creates or references the Phase 136 `ActionRecord`. If Ze extracts a reusable lesson, that lesson is stored once as a learning with direct links to the relevant action records and honest epistemic metadata. The same update never appends a competing text blob to the goal.

**Why this priority**: This is the authoritative write path and removes the current double persistence.

**Independent Test**: Complete a milestone with a mock Phase 136 action record and extract a learning. Assert exactly one learning record references that action record; no `goals.learnings` write or `goal_learnings` legacy insert occurs. Assert a learning cannot be stored with missing evidence.

**Acceptance Scenarios**:
1. **Given** a verified milestone outcome represented by an `ActionRecord`, **When** a candidate learning is extracted, **Then** it persists once with the action record as evidence and its claim kind/provenance/confidence.
2. **Given** a failed or unverified operation, **When** the executor considers extracting a learning, **Then** it may record a bounded observation only if the corresponding action record reports that outcome; it MUST NOT claim a successful strategy from that failure.
3. **Given** a caller attempts to create a learning with no action-record evidence and no user confirmation, **When** it writes, **Then** the typed validation rejects it before persistence.
4. **Given** the same goal update, **When** persistence is inspected, **Then** neither the legacy `goals.learnings` blob nor the legacy `goal_learnings` table receives a write.

---

### User Story 2 — A generalization is promoted only when warranted (Priority: P1)

At goal completion or review, Ze can propose a generalization from evidence-backed learnings. It stays an `INFERENCE` until independent evidence diversity and consistency meet the automatic-promotion gate, or the user explicitly confirms it. Promotion writes a doctrine-shaped memory claim through the existing licensed memory contribution path; it does not bypass it.

**Why this priority**: It preserves the boundary between observed outcomes and durable beliefs about the user.

**Independent Test**: Submit two learning candidates with equivalent wording but evidence from one action record: assert no automatic promotion. Submit corroborating evidence from two independent action records with distinct milestone or goal contexts: assert a promotion candidate is eligible but persists as `INFERENCE` unless the rule permits factual source support. Confirming it as user input promotes under `PROMPT_SUPPLIED` provenance.

**Acceptance Scenarios**:
1. **Given** a single action outcome supports a broad claim, **When** promotion is evaluated, **Then** the claim remains an unpromoted or review-pending `INFERENCE`.
2. **Given** corroborating outcomes from two independent action records in distinct contexts, **When** their claims are consistent, **Then** the system may create an eligible promotion candidate with all evidence preserved.
3. **Given** an eligible inferred pattern, **When** it is made available to planners and memory
   retrieval, **Then** it remains a `SYNTHESIZED` `INFERENCE` in the learning model; it is not
   written to `memory_facts` or silently upgraded to `FACT`.
4. **Given** the user confirms a proposed generalization, **When** the confirmation is persisted, **Then** the promoted claim has user-confirmation evidence and may be a `FACT` only if that confirmation directly supports the asserted statement.

---

### User Story 3 — Users and later evidence can review, contradict, and retract learning (Priority: P1)

The user can approve, reject, or correct a learning proposal. Later evidence that materially conflicts with an active learning creates a contradiction relationship and queues review; it does not silently overwrite either claim. A rejected, disproven, or superseded learning is retracted with reason and provenance, and downstream consumers stop treating it as active.

**Why this priority**: Long-lived learning without a correction path is unsafe.

**Independent Test**: Create an active inferred learning, submit contrary evidence, and assert it becomes review-required rather than deleted. Reject the learning and assert its lifecycle becomes retracted, its prior evidence remains queryable, and retrieval/priority inputs omit it.

**Acceptance Scenarios**:
1. **Given** a pending learning, **When** the user approves it, **Then** the review decision, actor, timestamp, and optional user wording become evidence-bearing history.
2. **Given** an active learning, **When** a later action record contradicts its claim, **Then** the system records the contradiction link, lowers eligibility for automated use, and requests review rather than choosing a winner through generic arbitration.
3. **Given** a user rejects or corrects a learning, **When** the decision is saved, **Then** the original learning is retracted or superseded, not overwritten or deleted.
4. **Given** a retracted learning, **When** an operator views its history, **Then** the original content, supporting evidence, contradictory evidence, and reason remain available.

---

### User Story 4 — Retrieval and priority use only epistemically eligible learning (Priority: P2)

Future goal planning, goal execution context, and priority ranking can consume active evidence-backed learnings. They must show claim kind, confidence, provenance, and compact evidence rationale. Pending, contradicted, and retracted learnings do not steer plans or priority automatically. Inferences remain usable as explicitly marked, lower-authority context where their confidence and relevance pass the existing consumer’s threshold.

**Why this priority**: The model is valuable only if downstream reasoning can distinguish established context from tentative patterns.

**Independent Test**: Seed active FACT, active INFERENCE, pending review, contradicted, and retracted learnings. Assert retrieval returns only active eligible records with metadata; assert priority input excludes non-active records and does not treat an inference as a fact.

**Acceptance Scenarios**:
1. **Given** a planning or execution query relevant to an active learning, **When** learning context is returned, **Then** it includes the statement, claim kind, provenance, confidence, and evidence summary sufficient to label uncertainty.
2. **Given** a pending, contradicted, or retracted learning, **When** normal retrieval or priority ranking runs, **Then** it is excluded from automated context and ranking signals.
3. **Given** an active `INFERENCE`, **When** it meets relevance and confidence thresholds, **Then** it may be returned as tentative context and MUST be labeled as such to the consuming prompt or view.
4. **Given** active evidence-backed learnings, **When** priority ranks work, **Then** it may use their relevance as a bounded input but MUST NOT create a priority override, push notification, or cross-function arbitration decision.

---

### Edge Cases

- **Legacy rows disagree with blob text**: migration preserves each unique legacy row as historical evidence-marked imported learning where it can be represented honestly. The `goals.learnings` blob is not treated as independent corroboration and is deleted after migration; duplicate text is not double-counted.
- **No Phase 136 action record**: implementation is blocked for new automated learning writes. It MUST NOT recreate an ad hoc outcome string or a compatibility learning record. Explicit user review/confirmation may be represented with user evidence, but not presented as an action-derived outcome.
- **Repeated retries of the same action**: retries sharing an action lineage or milestone do not satisfy diversity by themselves.
- **LLM contradiction uncertainty**: a possible contradiction creates a review-needed link only when existing NLI/claim checks meet their configured threshold. It does not automatically retract a learning.
- **A directly observed fact is also useful as a generalization**: retain the supported factual observation as a fact-shaped claim only if direct evidence supports it; create a separate inferred generalization with explicit derivation links rather than widening the fact’s wording.
- **User correction conflicts with prior confirmation**: the newer explicit correction supersedes the previous user-confirmed claim, preserving both decisions and their times.
- **Goal completion promotion fails**: retain the source learnings and record no partially promoted memory claim; retry/review can happen later.
- **ActionRecord deletion or redaction**: action evidence must remain addressable by stable id and a redaction-safe summary. A learning whose only evidence becomes unavailable is moved to review-needed and excluded from automated use.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST replace `goal_learnings` rows and `goals.learnings` with one authoritative persisted evidence-bearing goal-learning model; after cutover there MUST be no dual write, dual read, compatibility view, or fallback to either legacy representation.
- **FR-002**: Every automated goal learning MUST cite one or more Phase 136 `ActionRecord` identifiers as evidence. A raw verified outcome remains solely an `ActionRecord`; a learning MUST NOT be typed as or substitute for an action record.
- **FR-003**: A goal learning MUST persist shared `ClaimKind`, `Provenance`, confidence, lifecycle status, source text, and immutable evidence links. Generalizations derived from outcomes MUST start as `ClaimKind.INFERENCE` with honest provenance.
- **FR-004**: A learning MUST be eligible for automatic promotion only when its evidence is consistent and diverse: at least two distinct Phase 136 action records from distinct execution contexts, or explicit user confirmation. Multiple records from the same action lineage or one milestone MUST NOT satisfy the diversity gate.
- **FR-005**: Active eligible learnings MUST be available through a labeled learning-retrieval
  projection without writing inferred content to `memory_facts`. Only a learning whose exact
  assertion is explicitly user-confirmed or directly established as a FACT MAY be published as a
  Fact through Phase 133's licensed perception-fact path, preserving all supported citations.
- **FR-006**: The system MUST support review states and decisions for approve, reject, correct, and defer. A decision MUST record actor, timestamp, rationale or correction text when supplied, and supporting user evidence where applicable.
- **FR-007**: The system MUST detect material contradiction between active learning and newly linked evidence or a proposed learning, record an evidence relationship, and move affected learning to review-needed. This feature MUST NOT add generic contribution arbitration or silently select a winner.
- **FR-008**: The system MUST support durable retraction and supersession. Retraction MUST preserve original claim, evidence, decision history, and reason; retracted/superseded learning MUST be excluded from ordinary automated consumers.
- **FR-009**: Goal detail and learning-review contracts MUST expose active and historical learning with claim metadata, confidence, lifecycle, promotion status, evidence summaries, and contradiction/retraction rationale without exposing redacted action payloads.
- **FR-010**: Goal planner/executor retrieval MUST consume only active, eligible learnings and MUST preserve the distinction between `FACT` and `INFERENCE` in injected context. Existing raw ActionRecord retrieval remains separate.
- **FR-011**: Priority consumers MAY use active eligible learning as relevance-scored, uncertainty-labeled context; they MUST exclude pending, contradicted, retracted, and superseded learning and MUST NOT create overrides, notifications, push-budget changes, or generic arbitration behavior.
- **FR-012**: The migration MUST hard-cut existing data: migrate representable legacy `goal_learnings` once with explicit imported provenance/history, remove the `goals.learnings` blob and legacy table, and fail loudly on unrepresentable data rather than retaining a shadow fallback.
- **FR-013**: This phase MUST NOT alter `signal_sources()` wiring, inbound polling, generic contribution arbitration, collision policy, ActionRecord schema/producer semantics, priority override storage, push budget, or loop surfacing.
- **FR-014**: All new domain write failures MUST use typed `ZeError` subclasses; ordinary automated extraction/promotion failures may log and leave a retriable pending state but MUST NOT fabricate missing evidence.

### Key Entities

- **ActionRecord (Phase 136)**: the uniform, addressable verified outcome evidence. It is not a learning.
- **GoalLearning**: one durable claim or bounded observation derived from goal work, with doctrine metadata, lifecycle, and evidence links.
- **LearningEvidence**: an immutable link from a learning to an ActionRecord or explicit user decision, including role and redaction-safe supporting excerpt.
- **LearningReview**: append-only approval, rejection, correction, or defer decision.
- **LearningRelationship**: a typed relation such as `supports`, `contradicts`, `supersedes`, or `derived_from`; not generic arbitration.
- **Promotion**: a recorded, optional attempt to publish a FACT-eligible learning through the
  perception-fact path, including outcome and resulting fact reference when successful.

## Success Criteria *(mandatory)*

- **SC-001**: After migration, 100% of production goal-learning reads and writes use the authoritative model; 0 production reads/writes target `goal_learnings` or `goals.learnings`.
- **SC-002**: 100% of newly automated goal learnings in tests cite at least one Phase 136 ActionRecord; zero can persist with a missing action-evidence link.
- **SC-003**: Tests show a single-action or single-context pattern never passes the automatic evidence-diversity gate, while two independent consistent contexts do.
- **SC-004**: Tests show automatic outcome-derived promotion never upgrades an inference to FACT solely because multiple model outputs agree.
- **SC-005**: 100% of reviewed retractions and contradictions remain historically inspectable while contributing 0 records to default planning, execution, and priority inputs.
- **SC-006**: Goal detail/review clients can distinguish FACT, INFERENCE, pending review, contradicted, retracted, and promoted states without reading raw ActionRecord payloads.

## Assumptions

- Phase 136 exposes stable action record ids, verification/outcome state, action lineage or equivalent execution-context fields, timestamps, and redaction-safe summaries required for references and diversity checks.
- The shared `ClaimKind`, `Provenance`, confidence, and NLI vocabulary from prior phases remain the canonical doctrine; Phase 137 adds no private parallel vocabulary.
- Goal-history migration is acceptable pre-v1 and local/dev databases may remigrate. Imported legacy learnings are historical claims, not proof of new corroboration.
- The web client already has a goal-detail surface; this phase may evolve that contract and add a focused learning review surface, with generated client types updated as part of the hard cut.

## Out of Scope

- Implementing or changing Phase 136 ActionRecord producers, fields, validation, or verification behavior
- Raw ActionRecord storage, generic event sourcing, or a new universal evidence ledger
- `signal_sources()` rewiring, source polling, ingestion flow changes, or generic contribution arbitration
- Priority override behavior, push budget, notifications, loop surfacing, resume recap, and ranking redesign
- Reinterpreting all existing memory facts or migrating non-goal memory sources
