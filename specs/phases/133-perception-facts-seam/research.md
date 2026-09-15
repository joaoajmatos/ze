# Research: Perception Facts onto the Contribution Seam

## R1. Envelope pattern

**Decision:** Copy `ingest_signal`: `fact_to_contribution(...)` then `submit_and_detect_collisions(contribution, write, result_id=..., producer_kind="fact", collision_store=..., nli_client=...)`. `write` persists one `Fact` via existing `_write_fact_with_contradiction_check` (returns `UUID`) so Phase 126 `result_id` is satisfied.

**Rationale:** Spec requires the same shape as signals. `propose_facts` today returns `None` and swallows per-fact errors; the gated path should submit **per fact** so a license rejection is attributable and `result_id` is a real row id. Batch `propose_facts` remains for tests and as a possible inner persist of already-gated facts, but listed call sites must not use it as the front door.

**Alternatives considered:** Making `propose_facts` internally wrap the seam (call sites unchanged) — fails FR-011 (“stop using it as the ungated front door”) and would silently gate test doubles. A new persisted contribution queue — rejected in Phase 124 assumptions; not this phase.

## R2. Do not copy Contribution provenance onto `Fact.provenance` str

**Decision:** Leave `Fact.provenance` default `"raw"` (unless a caller already set the string). Stamp **only** `Contribution.provenance` (`SYNTHESIZED` vs `PROMPT_SUPPLIED`). Phase 134 owns mapping the row onto shared `Provenance` / `ClaimKind`.

**Rationale:** `_write_fact_with_contradiction_check` inserts `claim_kind=INFERENCE` when `fact.provenance == "synthesized"`. That dialect is dream/reflection bookkeeping. Perception facts today insert as `FACT` because they use `"raw"`. Copying `Provenance.SYNTHESIZED` onto the string would mis-tag conversation facts as inferences and contaminate dream source pools.

**Alternatives considered:** Set `Fact.provenance = "synthesized"` for LLM extracts to “match” the envelope — rejected (wrong `claim_kind` on the row). Dual-write envelope + string this phase — wrap-then-replace smell; Phase 134 is the cut.

## R3. Per-fact provenance after merge

**Decision:** Keep `merge_fact_proposals` (explicit predicate wins). After merge, `PROMPT_SUPPLIED` iff the surviving predicate was in the explicit `memory_proposals` set; otherwise `SYNTHESIZED`. Messenger inbound and ingestion have no explicit set → all `SYNTHESIZED`. Onboarding seeds → `PROMPT_SUPPLIED`. Goal-learning → `SYNTHESIZED`.

**Rationale:** Spec forbids one stamp for a mixed batch. Origin is recoverable from the explicit predicate set without a new `Fact` field.

**Alternatives considered:** New `Fact.contribution_provenance` field this phase — unnecessary; Phase 134 will replace the string dialect anyway.

## R4. `ingestion_id` / goal id as evidence without dangling false positives

**Decision:** Extend `EvidenceRef.kind` with `"ingestion"` and `"goal"` (`id: UUID`). Dangling validation: for `"fact"` / `"episode"` / `"signal"`, keep today’s checker behavior; for `"ingestion"` / `"goal"`, **skip** existence checks unless a checker is passed (optional). Always copy parseable UUIDs onto `Fact.source_refs`. Non-UUID `ingestion_id` strings: still log/carry on contribution `content` or skip `EvidenceRef` and store nothing in `source_refs` rather than crashing; prefer UUID (pipeline already uses `uuid.uuid4()`).

**Rationale:** Current `EvidenceRef` only allows `fact|episode|signal`. Missing checker today ⇒ `exists=False` ⇒ `DanglingEvidenceError`. Ingestion/goal rows are not in those stores. FACT does not require evidence, but the spec requires citations to travel as evidence **and** `source_refs`.

**Alternatives considered:** Citations only on `source_refs` (empty `evidence`) — fails FR-005’s evidence requirement. Passing fake `check_fact_exists` that returns True — lies. Rewiring validate to skip all missing checkers — would weaken INFERENCE/SUSPICION evidence checks if a caller forgets checkers.

## R5. Goal-learning pin (implementation)

**Decision:** `_promote_learnings` calls the perception-fact submit helper with `Provenance.SYNTHESIZED`, `SourceFunction.PERCEPTION`, `claim_kind=FACT`, `EvidenceRef(kind="goal", id=goal.id)` and `source_refs=[goal.id]`. Keep swallow-and-log failure policy.

**Rationale:** Spec pin. ACTION license is empty; REFLECTION cannot submit FACT. These are generalizable user facts extracted from goal work, not action result records (rollout step 7).

**Alternatives considered:** Leave promotion on ungated `propose_facts` until Phase 134 — leaves a public door. New claim kind — forbidden. `SourceFunction.EXECUTIVE` — these are not open-loop/priority writes; executive FACT is licensed but would confuse collision pairing and doctrine tables.

## R6. Plugin extractors / loops / Protocol

**Decision:** Change `MemorySink` only. `loop_extractor` hook unchanged. `MemoryStore.propose_facts` stays on the Protocol. Re-export `submit_perception_facts` (name may be `submit_perception_fact` singular in a loop) from `ze_sdk.memory` for messenger/onboarding/automation. `ze-core` `write_memory` calls the same helper (store-bound method or module function taking the store).

**Rationale:** Spec FR-006/007/011.

**Alternatives considered:** Give Finance a `Contribution` type — out of scope.

## R7. Collision wiring

**Decision:** Pass `collision_store` / `nli_client` from the memory store when already present (same `getattr` pattern as `ingest_signal`). Absence ⇒ validate-only, same as today for unwired sites.

**Rationale:** Detection already shipped; this phase does not add arbitration.

## R8. Target face

**Decision:** `TargetFace.USER` for onboarding seeds and goal-learning (facts about the user). `TargetFace.WORLD` for ingestion document facts. Conversation/inbound extracts: `USER` when the fact is about the user (current extractor is user-memory); default `USER` to match persona memory, not `WORLD`.

**Rationale:** Conversation facts are user memory (`user_facts` heritage). Ingestion is world/document. Collision matching uses `target_face`; mixing all onto WORLD would collide document facts with user facts noisily.

**Alternatives considered:** All WORLD like signals — rejected for user-stated onboarding facts.
