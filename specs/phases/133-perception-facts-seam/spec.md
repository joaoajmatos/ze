# Feature Specification: Perception Facts onto the Contribution Seam

**Feature Branch**: `133-perception-facts-seam`

**Created**: 2026-09-15

**Status**: Implemented

**Input**: User description: "Governed by specs/arch/contribution-seam.md rollout step 5: route perception-shaped propose_facts callers through the contribution seam (domain Fact + Contribution envelope + submit_and_detect_collisions with write= callback), matching ingest_signal. Include conversation write_memory (LLM-extracted vs explicit memory_proposals stamped per fact), MemorySink ingestion facts with ingestion_id as evidence/source_refs, messenger inbound extraction, onboarding memory_fact seeds, and goal-learning promotion as synthesized perception facts with the goal as evidence. Do not hard-cut Fact/memory_facts schema or delete propose_facts from the Protocol (phase 134). Do not change PriorityView, surface_loops, resume recap, rank_subset, push budget, or contribution arbitration."

**Governed by**: [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md) (phased-rollout **step 5** — perception facts on the seam), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md) (call-site cut this phase; schema/API hard-cut is the next phase, not a wrap lasting until v1), and [`specs/arch/claim-topology.md`](../../arch/claim-topology.md) leftover (shared `ClaimKind` / `Provenance` / `Confidence` on the **row** is **not** this phase). Follow-up: **Phase 134** (sibling spec — hard-cut `memory_facts` onto the shared vocabulary and retire public ungated `propose_facts`). Depends on Phase 124 (`Contribution` + validated write path), Phase 126 (`submit_and_detect_collisions` — detect, do not arbitrate), and the existing `ingest_signal` pattern. Phase 132 (Priority Turn Surfacing) is a **read-side** consumer of `PriorityView` and MUST remain untouched.

---

## Overview

Perception already lands **signals** and **open-loop candidates** through the contribution seam. Conversation-extracted facts, ingested-document facts, inbound-message facts, and onboarding-stated facts still walk around that door: they call `propose_facts` as a public write. Memory is supposed to be the **target** of contributions, not a second ungated writer.

This phase closes that hole for every perception-shaped fact producer that currently uses that door, using the same envelope already proven on `ingest_signal`: a domain `Fact`, a `Contribution` with `source_function=PERCEPTION` and `claim_kind=FACT`, and `submit_and_detect_collisions(write=callback)` where the callback is the existing store persist. Provenance is stamped **per fact**, not once for a mixed batch. Ingestion finally carries `ingestion_id` as evidence (Phase 69 promised this and never landed). Goal-learning promotion — today an ACTION-adjacent caller of the same ungated door — is included so Phase 134 can delete the public door without leaving a second writer.

Nothing about what the user sees in a turn (inline mentions, resume recap, ranking, push budget) changes. Collision **detection** already runs on the seam; this phase does not add cross-function **arbitration**. Plugin extractors (finance and similar) keep writing their own tables and keep returning string facts; only the memory sink that receives those strings changes.

---

## Goal-learning pin *(resolved — not a clarification)*

`ze_automation/goals/executor.py` `_promote_learnings` currently calls `propose_facts`. `SourceFunction.ACTION` is licensed for **nothing**; `REFLECTION` cannot submit `FACT`.

**Decision:** Treat goal-learning promotion as **synthesized perception facts** with the **goal as evidence**. They are extracted generalizable **user** facts (durable preferences, decisions, patterns), not action result records and not a new claim kind. Route them through **this phase's** seam so Phase 134 can delete the ungated public door. Do **not** invent a new claim kind. Do **not** start contribution arbitration. Do **not** stamp `source_function=ACTION` or `source_function=REFLECTION`.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conversation facts enter memory only through the seam (Priority: P1)

After a turn, facts Ze extracted from the conversation, and facts an agent explicitly proposed, both land in memory only after they pass the same contribution gate signals already use. Extracted facts are tagged as synthesized perception; explicit proposals are tagged as prompt-supplied perception. If a batch contains both, each fact keeps its own tag — a mixed batch does not get one stamp for everyone.

**Why this priority**: This is the highest-volume perception-fact writer and the shape every other caller copies.

**Independent Test**: Drive `write_memory` with LLM-extracted facts only, explicit `memory_proposals` only, and a mixed batch. Assert each write goes through the seam (not ungated `propose_facts` from the node), `source_function=PERCEPTION`, `claim_kind=FACT`, and per-fact provenance (`SYNTHESIZED` vs `PROMPT_SUPPLIED`). Assert a license-mismatched contribution is rejected before persist.

**Acceptance Scenarios**:

1. **Given** a completed turn that yields only LLM-extracted facts, **When** memory is written, **Then** each fact is submitted as a perception `FACT` contribution with `Provenance.SYNTHESIZED` and persists only via the seam's `write=` callback.
2. **Given** a completed turn that yields only explicit `AgentResult.memory_proposals`, **When** memory is written, **Then** each fact is submitted as a perception `FACT` contribution with `Provenance.PROMPT_SUPPLIED`.
3. **Given** a mixed batch (extracted + explicit, including an explicit fact overriding an extracted fact on the same predicate), **When** memory is written, **Then** provenance is stamped per surviving fact, not once for the whole batch.
4. **Given** a contribution that is not a perception `FACT` (wrong `source_function` or `claim_kind`), **When** submitted on this path, **Then** the write is rejected before persist, with the existing seam warning + typed error behavior.

---

### User Story 2 - Ingested document facts cite the ingestion and use the seam (Priority: P1)

When the user ingests a document, string facts from extraction become memory facts through the seam, synthesized, with the ingestion's id attached as evidence / source refs so the archive can be cited. Plugin extractors still return strings and still write their own domain tables; they do not grow a `Contribution` type. Open-loop extraction already on the seam is left alone.

**Why this priority**: This is the other call site named in contribution-seam step 5, plus the Phase 69 citation gap.

**Independent Test**: Push a non-empty fact list through `MemorySink` with a known `ingestion_id`. Assert seam submission, `SYNTHESIZED`, and `ingestion_id` on evidence and on the stored fact's `source_refs`. Assert empty lists still no-op. Assert finance (or equivalent) extractors are unchanged.

**Acceptance Scenarios**:

1. **Given** an ingestion with a non-empty `ExtractionResult.facts` list and an `ingestion_id`, **When** `MemorySink.push` runs, **Then** each string becomes a `Fact` submitted as a perception `FACT` / `SYNTHESIZED` contribution whose evidence (and `source_refs`) cite that `ingestion_id`, and persist only via the seam callback.
2. **Given** an empty fact list, **When** `push` runs, **Then** no seam write and no store write occur.
3. **Given** a plugin extractor that returns `facts: list[str]` and writes its own tables, **When** this phase ships, **Then** that extractor is unmodified; only the memory sink that consumes the strings changes.
4. **Given** ingestion open-loop extraction already on the seam, **When** this phase ships, **Then** that path is unchanged.

---

### User Story 3 - Inbound messages and onboarding seeds use the same door (Priority: P2)

Facts extracted from inbound messages use the same conversation-extraction stamps as a turn (perception, `FACT`, synthesized). Facts the user stated during onboarding (already reviewed) also go through the seam (perception, `FACT`, prompt-supplied) so there is not a second user-fact door.

**Why this priority**: Closes remaining perception-shaped writers so the public door can die in Phase 134 without leftovers.

**Independent Test**: Run inbound fact extraction with a mocked extractor; run onboarding `memory_fact` seed apply. Assert seam + stamps. Assert `reviewed=True` still holds for onboarding facts.

**Acceptance Scenarios**:

1. **Given** an inbound message that yields extracted facts, **When** the messenger inbound processor extracts them, **Then** they submit as conversation-extraction stamps (`PERCEPTION` + `FACT` + `SYNTHESIZED`) through the seam.
2. **Given** an onboarding `memory_fact` seed, **When** it is applied, **Then** it submits as `PERCEPTION` + `FACT` + `PROMPT_SUPPLIED` through the seam, still `reviewed=True`.
3. **Given** onboarding `profile_facet` or `plugin_setting` seeds, **When** applied, **Then** those paths are unchanged (not fact-seam work).

---

### User Story 4 - Goal-learning promotion uses the same seam without a new kind (Priority: P1)

When a goal completes and generalizable learnings are promoted into user memory, those facts go through this same perception-fact seam, synthesized, with the goal cited as evidence. They are not action records, not reflection facts, and not a new claim kind.

**Why this priority**: Without this pin, Phase 134 cannot delete the ungated door; ACTION cannot legally submit FACT.

**Independent Test**: Run `_promote_learnings` with mocked planner output. Assert seam path, `PERCEPTION` + `FACT` + `SYNTHESIZED`, goal id in evidence. Assert no `ACTION`/`REFLECTION` source function. Assert existing swallow-on-failure behavior remains.

**Acceptance Scenarios**:

1. **Given** a goal with generalizable learnings and a memory store, **When** promotion runs, **Then** each fact is a perception `FACT` contribution with `Provenance.SYNTHESIZED` and evidence citing the goal, persisted only via the seam callback.
2. **Given** the same promotion, **When** inspected, **Then** `source_function` is not `ACTION` and not `REFLECTION`, and `claim_kind` is not a new value.
3. **Given** no memory store, no learnings, or a planner/write failure, **When** promotion runs, **Then** behavior matches today (skip or swallow + log), with no ungated `propose_facts` from this caller.

---

### Edge Cases

- What happens if extracted and explicit facts share a predicate? Existing merge (explicit wins) still applies **before** seam submit; the surviving fact carries **explicit** provenance (`PROMPT_SUPPLIED`).
- What happens if `ingestion_id` is not a UUID-shaped string? The contribution MUST still carry the id as evidence; persist MUST not drop the citation. Prefer putting a UUID into `source_refs` when parseable; otherwise keep the id on contribution evidence (and any existing citation field that can hold a string) rather than silently omitting it.
- What happens if the seam rejects a fact (license, dangling evidence)? Persist MUST not run for that fact; existing caller failure policy stands (conversation/ingestion/inbound/onboarding/promotion keep their current log/swallow vs raise behavior except the write is no longer ungated).
- What happens to tests that mock `MemoryStore.propose_facts` as the front door? They MUST be updated to the seam entry (or to asserting the `write=` callback). `propose_facts` MAY remain on the Protocol for tests and as the callback body.
- What happens if a caller still invokes ungated `propose_facts` after this phase? That is a defect in this phase for the listed call sites. Other writers (`propose_events`, facets, episodes) are out of scope and MAY still call their own store methods.
- What happens to PriorityView / `surface_loops` / resume recap / `rank_subset` / push budget? **Nothing** — this phase MUST NOT change them.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST route `write_memory` fact persistence (LLM-extracted facts from the fact extractor) through the contribution seam using `source_function=PERCEPTION`, `claim_kind=FACT`, and `Provenance.SYNTHESIZED`, with store persist only as the seam `write=` callback — the same pattern as `ingest_signal`.
- **FR-002**: System MUST route `AgentResult.memory_proposals` through the same seam with `source_function=PERCEPTION`, `claim_kind=FACT`, and `Provenance.PROMPT_SUPPLIED`.
- **FR-003**: System MUST stamp provenance **per fact**. When extracted and explicit proposals are merged, the batch MUST NOT receive a single provenance for all members.
- **FR-004**: System MUST route `MemorySink.push` so each `ExtractionResult.facts` string becomes a `Fact` submitted through the seam as `PERCEPTION` + `FACT` + `SYNTHESIZED`.
- **FR-005**: System MUST attach the ingestion's `ingestion_id` to each sunk fact as contribution **evidence** and as the fact's **source_refs** (UUID when parseable) so Phase 69's citation promise is met without a schema migration.
- **FR-006**: Plugin extractors that return `facts: list[str]` (finance and similar) MUST NOT gain a `Contribution` type; this phase changes the memory sink, not those extractors.
- **FR-007**: Ingestion open-loop extraction already on the seam MUST remain unchanged.
- **FR-008**: Messenger inbound `_extract_facts` MUST use the same conversation-extraction stamps as FR-001 (`PERCEPTION` + `FACT` + `SYNTHESIZED`) and the same seam.
- **FR-009**: Onboarding `memory_fact` seeds MUST go through the seam as `PERCEPTION` + `FACT` + `PROMPT_SUPPLIED`, remaining `reviewed=True`, so there is not a second user-fact door. Non-fact seed kinds stay as they are.
- **FR-010**: Goal-learning promotion (`_promote_learnings`) MUST go through this same seam as synthesized perception facts (`PERCEPTION` + `FACT` + `SYNTHESIZED`) with the **goal** as evidence. MUST NOT use `SourceFunction.ACTION` or `REFLECTION`, MUST NOT invent a new claim kind, MUST NOT add contribution arbitration.
- **FR-011**: `propose_facts` MUST remain the store's internal persist used as the seam `write=` callback and MAY remain on `MemoryStore` for tests. Listed call sites MUST stop using it as the ungated front door. This phase MUST NOT delete `propose_facts` from the public Protocol and MUST NOT hard-cut `Fact.provenance` string dialect (`"raw"` / `"synthesized"`) — those are Phase 134.
- **FR-012**: This phase MUST NOT change `surface_loops`, resume recap, `rank_subset`, the shared push budget, PriorityView ranking, or contribution **arbitration** (Phase 126 detection may run as it already does on the seam).
- **FR-013**: This phase MUST NOT rewire `signal_sources()` polling, MUST NOT migrate `propose_events` / `upsert_entity` / `write_episode` / profile facets onto the seam, and MUST NOT introduce action result records as a new producer theory beyond FR-010.
- **FR-014**: License violations on these paths MUST be rejected before persist, with the existing seam structured warning + typed error (Phase 124), not a new audit table.

### Key Entities

- **Perception-fact contribution**: A `Contribution` wrapping one domain `Fact`: `source_function=PERCEPTION`, `claim_kind=FACT`, shared `Confidence`, honest `Provenance` (`SYNTHESIZED` or `PROMPT_SUPPLIED`), optional evidence (ingestion id, goal id), content from the fact.
- **Domain Fact**: Existing memory fact; this phase does not replace its stored provenance string dialect.
- **Ingestion citation**: The `ingestion_id` of an ingest run, carried as evidence / `source_refs`.
- **Goal citation**: The originating goal id attached as evidence on promoted learnings.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of the listed perception-fact writers (conversation extract, explicit proposals, ingestion sink, inbound extract, onboarding memory_fact seeds, goal-learning promotion) persist facts only after a seam submit in dedicated tests — zero remaining ungated `propose_facts` calls from those sites.
- **SC-002**: A mixed conversation batch is 100% correctly provenance-stamped per fact in tests (extracted vs explicit), including after predicate merge.
- **SC-003**: Every ingested fact in tests carries the originating `ingestion_id` on evidence/`source_refs`; none persist without it when an id was provided.
- **SC-004**: Priority-turn, loop-surfacing, resume-recap, ranking, and push-budget existing tests remain green without production-code edits in those areas.
- **SC-005**: A reflection- or action-tagged `FACT` submitted on these new wrappers is rejected 100% of the time before persist (license check), matching the existing seam.

## Assumptions

- "Through the seam" means: build `Contribution`, call `submit_and_detect_collisions` (or the same validated wrapper `ingest_signal` uses), persist only in `write=`. No new persisted contribution queue, no new table, no Alembic migration this phase.
- A shared helper (Fact → Contribution, analogous to `signal_to_contribution`) is in scope as design, not a second product surface.
- Collision **logging** from Phase 126 may fire on these writes; that is detection, not arbitration.
- Phase 134 (sibling) owns: `Fact` / `memory_facts` onto `ClaimKind` / `Provenance` / `Confidence`, dropping the string provenance dialect, and removing `propose_facts` from the public Protocol.
- Code implementation of this spec waits until Phase 132's product work is sequenced first if both are in flight; **speccing** this phase is allowed now. Phase 132 is already Done in the index.
- Inflow channel (`conversation`, `ingestion`, plugin key) remains plugin-domain vocabulary, not a `Provenance` member (`contribution-seam.md` resolved provenance).
- Goal-learning facts may keep today's `agent` / reviewed flags on the domain `Fact`; only the envelope and door change.

## Verbatim Constraints

- `source_function=PERCEPTION`
- `claim_kind=FACT`
- `Provenance.SYNTHESIZED` (LLM-extracted conversation facts, ingestion strings, inbound extraction, goal-learning promotion)
- `Provenance.PROMPT_SUPPLIED` (explicit `memory_proposals`, onboarding `memory_fact` seeds)
- `submit_and_detect_collisions(write=callback)`
- `ingestion_id` as evidence / `source_refs`
- Call sites: `ze_core/orchestration/nodes/memory.py` `write_memory`; `ze_ingestion/sink.py` `MemorySink.push`; messenger inbound `_extract_facts`; `ze_onboarding/persistence.py` onboarding memory_fact seeds; `ze_automation/goals/executor.py` `_promote_learnings`
- MUST NOT: `surface_loops`, resume recap, `rank_subset`, push budget, contribution arbitration
- Follow-up phase: hard-cut `memory_facts` / delete public `propose_facts` (Phase 134)

## Out of Scope

- Hard-cut `Fact` / `memory_facts` onto `ClaimKind` / `Provenance` / `Confidence` (Phase 134)
- Deleting `MemoryStore.propose_facts` from the public Protocol (Phase 134)
- `propose_events`, `upsert_entity`, `write_episode`, profile facets
- PriorityView / inline mentions / resume recap / `surface_loops` / `rank_subset` / push budget
- Real cross-function arbitration (contribution-seam step 8)
- Action result records as a new producer theory (step 7) beyond the goal-learning pin
- Rewiring `signal_sources()` polling
- Changing FinanceIngestionExtractor (or similar) internals
