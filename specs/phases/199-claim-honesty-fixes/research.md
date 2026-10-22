# Research: Claim Honesty Fixes (199)

Every decision below was checked against the code on branch `199-claim-honesty-fixes` (base `c8dc97da`) and the local `ze` database on 2026-10-22. The ADR decisions (D1–D4) and the user's answers to Q1–Q3 are fixed inputs.

## R1 — How decay and expiry recognise a dream insight

- **Decision**: Add `AND dream_run_id IS NOT NULL` to the decay `SELECT` and the expiry `UPDATE` in `ze_memory/dream/promoter.py` (`_run_confidence_decay`, `_expire_stale_synthetic_facts`). Keep the existing `provenance = 'synthesized'` condition. The promoter's `_insert_fact` stops naming `creation_method`.
- **Rationale**: User answer Q1 A. `_insert_fact` is the only writer that sets `dream_run_id` on `memory_facts` (verified by grep: `dream_run_id` only appears in `promoter.py`, `zm009` and readers). It is the "dream wrote this" marker that already exists. Two conditions mean a wrong provenance alone cannot bring the bug back (ADR intent).
- **Alternatives**: a `creation_method` column (Q1 B, rejected: stores the same fact twice); `agent = 'dream'` (rejected: `agent` is free text that any writer sets).
- **Side fix**: `_insert_fact` today inserts into `creation_method`, which `memory_facts` lacks (`\d memory_facts` on the dev DB). Any promotion raises inside `run_morning_integration`, so decay and expiry, which run after the promotion loop, are skipped that night (`job.py:117-128` logs `dream_integration_failed`). Removing the column from the insert fixes both.

## R2 — Which perception writers change

- **Decision**: Three call sites change `Provenance.SYNTHESIZED` to `Provenance.PROMPT_SUPPLIED`:
  - `ze_core/orchestration/nodes/memory.py:217` (conversation facts from the commitment intake or the Haiku fallback);
  - `ze_ingestion/sink.py:53` (ingested documents);
  - `ze_messenger/inbound/processor.py:207` (inbound messages).
- **Unchanged writers** (already right): `remember_fact` and onboarding (`PROMPT_SUPPLIED`, `reviewed=True`), goal learning promotion (`learning.py:269`, `PROMPT_SUPPLIED`). `submit_perception_facts` already forces `claim_kind = FACT`.
- **Out of scope by the ADR's own line**: loop contributions (`ze_worldstate/contribution.py`, Executive judgments), social-cognition identity edges (`graph/memory_hooks.py:166`), procedure candidates, correlation hypotheses, action records.
- **Seeds**: `ze_seed/narrative/persona.yaml:127` and `:490` seed two `synthesized` facts with no dream run. Under FR-002 they would be invalid rows. They become `prompt_supplied` (both are companion-extracted narrative facts), and `ze-seed/tests/test_loader.py:69-72` changes its count to 0. `ze_seed/domains/memory.py:94` keeps its rule (it is correct for a synthesized seed if one is ever added).

## R2a — Consolidation's merged fact (added 2026-10-23, facts-lane review finding 1)

- **Decision** (option a): a merged fact carries its inputs' claim.
  - `PostgresConsolidationStore.fetch_active_facts` also selects `provenance`, `claim_kind` and `dream_run_id`.
  - In `MemoryConsolidator.dedup_facts`, the model-merge branch (NLI entailment) runs only when both rows have `dream_run_id` NULL and the same `provenance` and `claim_kind`. Otherwise it skips the pair: no model call, no contradiction, no insert. The silent-threshold branch and the NLI-contradiction branch do not change.
  - `insert_merged_fact(predicate, value, confidence, embedding, provenance, claim_kind)` writes the values it is given. `agent` stays `'consolidation'`, and `dream_run_id` stays NULL.
- **Rationale**: merging two user statements is not reflection, so the result keeps the label its inputs had. If the merge always stamped `prompt_supplied`, a dream inference merged with a user fact would turn into "the user said". Copying a dream insight's claim through a merge would make consolidation a second reflection writer, with a new row, a new `created_at` and a lost `valid_until`. Skipping that pair is honest: the insight keeps its own lifecycle.
- **Rejected** (option b): license consolidation as a second `synthesized` writer and add `agent <> 'consolidation'` to zm026. That widens FR-002 and the dream-only decay rule, and still labels two merged user statements as Ze's conclusion.
- **zm026 is unchanged.** Rows consolidation wrote before this phase that are `synthesized` with no dream run are merges of perception facts, so re-stamping them `prompt_supplied` is right. Local `ze` DB: the 7 `agent='consolidation'` rows are already `prompt_supplied`, and there are no dream facts.

## R3 — The fact re-stamp (zm026)

- **Decision**: `zm026_perception_fact_provenance.py` on the `zm` chain (down revision `zm025`). It exposes:
  - `COUNT_SQL`: counts rows that will change, and how many of them carry the decay signature (`contradicted AND confidence < 0.25 AND NOT corroborated`).
  - `REPAIR_SQL`: `UPDATE memory_facts SET provenance = 'prompt_supplied', claim_kind = 'fact' WHERE provenance = 'synthesized' AND dream_run_id IS NULL`.
  - `upgrade()` runs `COUNT_SQL`, logs both counts with `get_logger` (`zm026_restamped`, `decay_damaged`), then runs `REPAIR_SQL`. `downgrade()` is a no-op with a comment (the old label was wrong; pre-v1).
- **Rationale**: User answer Q2 B, re-stamp only. The pattern follows `zm025` (SQL constant, test-pg test runs it). It is idempotent by construction: a second run matches no rows.
- **Measured**: local `ze` DB re-stamps 2 rows; 0 carry the decay signature.
- **`updated_at`**: not touched, so consolidation's age-based rules see the same ages as before.

## R4 — Deriving a loop's claim kind

- **Decision**: In `ze_worldstate/types.py`, add `loop_claim_kind(state: LoopState) -> ClaimKind | None` (suspected → SUSPICION; active, drifting, closed → PRIORITY; dropped → None). `OpenLoop.claim_kind` stops being a dataclass field and becomes a read-only `@property` returning `loop_claim_kind(self.state)`. Every `OpenLoop(..., claim_kind=...)` constructor loses the argument (hard cut).
- **Store**: `_loop_from_row` stops reading `claim_kind`; `create` stops inserting it. `zw006_drop_loop_claim_kind.py` drops `open_loops.claim_kind`. Its `downgrade` re-adds the column, filled from `state` by the same table.
- **Readers**: `ze_priority/scoring.py:51` and `compose/rules.py:77` only see open states (`view.py` `_OPEN_LOOP_STATES`, `composer.py` `_OPEN_STATES`, `turn.py` suspected only), so they get a non-null kind and need no code change. `screen_resolvers.py:55` already accepts `ClaimKind | None` (`ScreenPosture.kind`). `rest.py:34` changes to `loop.claim_kind.value if loop.claim_kind else None`. `contribution.py:25` is only called on create (suspected or active), so FR-012 holds by construction. A test asserts it.
- **REST**: `LoopListItem.claim_kind: str | None` (`apps/ze-api/ze_api/api/v0/loops/schemas.py:19`). `make codegen` regenerates `@myguyze/ze-client`. Web readers: `concerns.ts:73` (`claimKind` is already nullable at `:29`), `LoopsRail.tsx:44`, `DoingGoalPage.tsx:165` (guard `CLAIM[...]`/`humanizeStatus` against null).
- **Alternatives**: rewriting a stored kind on confirm and promote (ADR option 2, rejected by D3).

## R5 — The resolve event

- **Decision**: Add `LoopStore.resolve(loop_id: UUID, evidence: Sequence[EvidenceRef]) -> OpenLoop | None` to the Protocol and `PostgresLoopStore`. In one transaction:
  1. `UPDATE open_loops SET state = 'closed', closed_at = now(), updated_at = now() WHERE id = $1 AND state IN ('suspected', 'active', 'drifting') RETURNING *`;
  2. one `derived_from` `memory_relationships` row per evidence ref, the same SQL `link_evidence` uses (`ON CONFLICT DO NOTHING`).

  It returns `None` when no row moved (already closed or dropped, or a concurrent resolve won). It never writes `dismissed_evidence_fingerprint`. It logs `open_loop_transitioned` with `via="resolve"` (structlog reserves `event`).
- `_close_matching_loop` (`extraction.py:380-400`) gains `evidence_refs` and calls `loop_store.resolve(existing.id, evidence_refs)` instead of `transition(CLOSED)`. Both callers already hold `evidence_refs` (`_commit_admitted`, `extraction.py:511-514`; the 109 fallback, `:637-641`).
- `_ALLOWED_TRANSITIONS` and `transition()` do not change, so the REST close route, `close_loop`, `review.close_loop`, decay and the drift sweep still refuse `suspected → closed` (FR-017).
- **Evidence per inflow**: conversation passes the turn episode (`_commit_with_episode` in `nodes/memory.py`); email passes the message reference; ingestion passes the ingestion id; calendar passes none (`calendar_reminder.py`). This is unchanged from create.
- **Fakes**: in-memory `LoopStore` fakes in ze-worldstate tests gain `resolve`.
- **Alternatives**: a `transition(..., event="resolve")` flag (rejected: a boolean that unlocks edges is the pattern 203 removes); drop instead of close (ADR option 2, rejected by D1).
- **203**: later moves `resolve` into the lifecycle module. Keeping it as one store method makes that move a rename.

## R6 — The Executive licence

- **Decision**: `ze_plugin/contribution.py:54-62` becomes `SourceFunction.EXECUTIVE: frozenset({ClaimKind.PRIORITY, ClaimKind.SUSPICION})`.
- **Verified producers**: `ze_worldstate/contribution.py` (suspicion or priority, from R4) and `ze_priority/contribution.py:24,42` (priority). No other `SourceFunction.EXECUTIVE` in the tree (grep).
- `specs/arch/contribution-seam.md:99` already attributes candidate loops to Executive. FR-015 is a check only.

## R7 — Contact provenance (Q3 A)

- **Decision**:
  - `ze_personal/contacts/types.py`: `_SOURCE_TYPE_TO_PROVENANCE` becomes `{manual, conversation, email, calendar} → PROMPT_SUPPLIED, research → LIVE_SEARCH`, exported as `source_provenance(source_type) -> Provenance`. An unknown source type raises `ContactSourceTypeError(ZeCoreError)`, defined in a new `ze_personal/contacts/errors.py` (imports `ZeCoreError` from `ze_sdk.errors`).
  - `PersonSource.provenance` stops being a constructor field and becomes a property derived from `source_type`.
  - `ContactProposal.provenance` is deleted (it never reached storage; hard cut), along with its uses in `extractors.py`.
- **Write paths** that create a `Person` pass `provenance=source.provenance`: `consolidator.py:259`, `graph/memory_hooks.py:240`, `ze_prospecting/agents/tools.py:66`.
- **Readers**: `contacts/store.py:54-60` stops passing `provenance=` to `PersonSource`, and `add_source` writes `source.provenance`. `person_source_to_contribution` is unchanged.
- **Co-occurrence**: `jobs/social_cooccurrence.py:53` origin becomes `PROMPT_SUPPLIED` for email and calendar (was `LIVE_SEARCH`). Conversation keeps `SYNTHESIZED`; the user's answer to Q3 named email and calendar only. The `_evidence_ref` docstring invariant stays.
- **Re-stamp**: `zc041_contact_source_provenance.py` in `plugins/ze-personal/ze_personal/migrations/versions/` (down revision `zc040`; floor 198 adds no migration). It exposes `REPAIR_SQL` (`contact_sources` by `source_type`; then each `contacts` row from its earliest source; contacts without sources untouched) and logs counts. Downgrade is a no-op.
- **Measured**: local DB has 4 contacts (no sources, so untouched) and 0 sources.
- **Boundary**: ze-prospecting imports `PersonSource` and `Person` from `ze_personal`, which is allowed (`ze-prospecting → ze-personal`).

## R8 — Test strategy (FR-020)

- Each story's first task is a failing test through the real interface:
  - B7: the `write_memory` node with a mocked memory store asserts the submitted provenance; the sink and the inbound processor likewise. The decay and expiry behaviour and the zm026 SQL run on test-pg (`apps/ze-api/tests/pg/test_dream_decay_pg.py`, `test_zm026_pg.py`), with `DreamPromoter` built on the real pool and a stub dream store.
  - B12: test-pg (`test_loop_claim_kind_pg.py`) through `PostgresLoopStore`, `review.confirm_loop`, corroboration `promote`, `PriorityView` and the loops REST route.
  - B3: test-pg (`test_loop_resolve_pg.py`) through `LoopInflow.commit_for` with a resolve admission, for each inflow, plus refusal of `transition(CLOSED)` from suspected.
  - B8: a unit test through `validate_and_submit` (no SQL).
  - Contacts: test-pg (`test_contact_provenance_pg.py`) through the consolidator and the zc041 SQL; unit tests for prospecting and co-occurrence.
- Mock-only tests are updated, not trusted as proof.

## R9 — Cross-floor coordination (198)

- 198 adds no migration (198 FR-026). `zm026`, `zw006` and `zc041` are free.
- `nodes/memory.py`: 199 edits only the provenance line (~217); 198's engine lane owns lines 252-342.
- 198's attention lane owns `ze_priority/` and its tests, plus `ze-worldstate/tests/test_surfacing.py`. 199 changes no `ze_priority` source. It deletes `claim_kind=` from the `OpenLoop` constructors in `ze-priority/tests/factories.py`, `tests/test_turn.py`, `tests/compose/test_rules_topic.py`, `tests/compose/test_rules_slipping.py` and `ze-worldstate/tests/test_surfacing.py`. Each is a one-line deletion that merges trivially whichever floor lands first.
- 198 also regenerates `@myguyze/ze-client` (`PriorityItem` computed rank). The second floor to land re-runs `make codegen` after the merge instead of hand-merging generated files.
- `ze-worldstate/README.md`, `docs/goals.md`, `docs/cognitive-architecture.md`: both floors' docs lanes may touch them. They are different paragraphs, so the second floor rebases.

## R10 — Docs touched

`docs/dreaming.md` (decay and expiry apply to dream insights, selected by `dream_run_id`), `docs/architecture.md:574,605-606`, `docs/memory.md` (fact provenance table or paragraph), `docs/goals.md:162` (stale: promotion is `prompt_supplied`), `docs/features.md:43` (state machine: resolve closes suspected loops, which may need a diagram update), `core/cognition/ze-worldstate/README.md` (transition table, claim kind derived, resolve), `core/cognition/ze-memory/README.md` (decay scope), `plugins/ze-personal/README.md` if it states contact provenance, `AGENTS.md` (phase row; migration rows `zm`, `zw`, `zc`), and `specs/README.md` (199 Status cell). The task ends with `git diff main...HEAD --stat` against this list.
