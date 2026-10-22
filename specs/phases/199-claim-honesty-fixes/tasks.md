---

description: "Tasks for phase 199 Claim Honesty Fixes"
---

# Tasks: Claim Honesty Fixes

**Input**: Design documents from `specs/phases/199-claim-honesty-fixes/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required (spec FR-020). Each story begins with a test that fails on today's code, through the real interface. Any SQL-backed behaviour has a test-pg test in `apps/ze-api/tests/pg/` (`pytestmark = pytest.mark.pg`, `pg_pool` fixture, run with `make test-pg`).

**Organization**: Tasks are grouped by user story (spec.md US1–US6).

## Format: `[ID] [P?] [Lane] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Lane]**: The crew lane from plan.md's Lane Plan that owns this task: `[L:lead]`, `[L:facts]`, `[L:loops]`, `[L:contacts]`, `[L:jr1]`, `[L:docs]`. A task touches only files its lane owns.
- **[Story]**: The user story (US1–US6)
- **Tags**: [BE] backend, [WEB] web app, [PLATFORM] migrations, codegen and gates, [DOCS] documentation

**Crew**: the Maestro staffs one agent per lane: Sonnet for `lead` and the ENG lanes (`facts`, `loops`, `contacts`), and Haiku for `jr1` and `docs`. The contract step (`[L:lead]`) lands first. The other lanes then run in parallel in their own worktrees, and each is reviewed as it finishes.

**Rules for every lane**: tick a task's checkbox in the same commit that finishes it. Run `graphify affected "<Symbol>" --depth 2` before you change a public symbol, and update every caller it lists in the same change. Never edit `nodes/memory.py` outside the provenance hunk at about line 217 (floor 198 owns lines 252-342).

---

## Phase 1: Setup (contract step)

**Purpose**: Reserve migration revisions and confirm the cross-floor boundaries before any lane starts.

- [x] T001 [L:lead] [PLATFORM] Confirm the next free revisions are `zm026` (after `zm025` in `core/cognition/ze-memory/ze_memory/migrations/versions/`), `zw006` (after `zw005` in `core/cognition/ze-worldstate/ze_worldstate/migrations/versions/`) and `zc041` (after `zc040` in `plugins/ze-personal/ze_personal/migrations/versions/`). Ask floor 198 (Fathom) through the Maestro to confirm it still adds no migration (198 FR-026). Record the three revisions and file names (`zm026_perception_fact_provenance.py`, `zw006_drop_loop_claim_kind.py`, `zc041_contact_source_provenance.py`) in the "199 Claim Honesty Fixes Handoffs" note.

---

## Phase 2: Foundational

None. The lanes touch disjoint packages and need no shared stub. The only cross-lane edge is the nullable REST field (T026 → T040).

---

## Phase 3: User Story 1 - What the user says stays believed (Priority: P1) 🎯 MVP

**Goal**: Perception facts are stored `prompt_supplied`. Dream decay and expiry touch only dream insights (`dream_run_id IS NOT NULL`). Dream promotion stores insights again.

**Independent Test**: `make test-core test-ingestion test-messenger test-memory test-seed` and `make test-pg -k dream_decay`.

- [ ] T002 [P] [L:facts] [US1] [BE] Write a failing test in `core/engine/ze-core/tests/orchestration/nodes/test_memory.py`: run `write_memory` with a fact admission that persists one fact (reuse the existing persist-fact fixtures in that file and patch `submit_perception_facts` the way the file already does), and assert that every `PerceptionFactSubmit.provenance` is `Provenance.PROMPT_SUPPLIED`. It fails today (`SYNTHESIZED`).
- [ ] T003 [L:facts] [US1] [BE] In `core/engine/ze-core/ze_core/orchestration/nodes/memory.py` (the `PerceptionFactSubmit(...)` block at about line 214-221 only), change `provenance=Provenance.SYNTHESIZED` to `Provenance.PROMPT_SUPPLIED`. T002 passes. `make test-core`.
- [ ] T004 [P] [L:facts] [US1] [BE] Write a failing test in `core/ops/ze-ingestion/tests/test_sink.py`: `MemorySink.push(ingestion_id, ["fact"])` submits facts whose provenance is `PROMPT_SUPPLIED`.
- [ ] T005 [L:facts] [US1] [BE] In `core/ops/ze-ingestion/ze_ingestion/sink.py:53`, stamp `Provenance.PROMPT_SUPPLIED`. T004 passes. `make test-ingestion`.
- [ ] T006 [P] [L:facts] [US1] [BE] Write a failing test in `plugins/ze-messenger/tests/test_inbound_processor.py`: `_extract_facts` (mock `extract_facts` returning one fact) submits it with provenance `PROMPT_SUPPLIED`.
- [ ] T007 [L:facts] [US1] [BE] In `plugins/ze-messenger/ze_messenger/inbound/processor.py:207`, stamp `Provenance.PROMPT_SUPPLIED`. T006 passes. `make test-messenger`.
- [ ] T008 [L:facts] [US1] [BE] Write failing test-pg tests in a new `apps/ze-api/tests/pg/test_dream_decay_pg.py`. Build `DreamPromoter(pool, dream_store=stub)` from `ze_memory.dream.promoter`, where the stub's `get_pending_artifacts_for_run` returns a list you control and its other methods are `AsyncMock`. Insert rows into `memory_facts` with raw SQL, setting `created_at = now() - interval '60 days'`. Cover four cases:
  (a) A `synthesized` fact with `dream_run_id` NULL, confidence 0.8, `reviewed` true, uncorroborated: after 10 calls of `run_morning_integration(uuid4())`, confidence, `reviewed` and `contradicted` are unchanged. This fails today.
  (b) A `synthesized` fact with `dream_run_id` set, confidence 0.8: after 1 call, confidence is 0.77.
  (c) A `synthesized` fact with `dream_run_id` NULL and `valid_until` in the past: after 1 call, it is not contradicted. This fails today. The same row with `dream_run_id` set is contradicted.
  (d) The stub returns one artifact (`artifact_type='synthesized_insight'`, `status='pending'`, `critic_a_verdict='PASS'`, `critic_b_verdict='PASS'`, support and spread fields above the defaults in `promoter.py`): the call does not raise, a new `memory_facts` row exists with `agent='dream'` and `dream_run_id` set, and a pre-aged dream insight inserted beforehand was decayed in the same call. This fails today with `UndefinedColumnError: creation_method`.
- [ ] T009 [L:facts] [US1] [BE] In `core/cognition/ze-memory/ze_memory/dream/promoter.py`:
  - add `AND dream_run_id IS NOT NULL` to the `SELECT` in `_run_confidence_decay` and to the `UPDATE` in `_expire_stale_synthetic_facts`;
  - remove `creation_method` and its `'synthesized'` value from the `INSERT` in `_insert_fact`;
  - update both docstrings to say "dream insights".

  Update `core/cognition/ze-memory/tests/dream/test_promoter.py` for any SQL-text assertions. T008 passes (`make test-pg`), and so does `make test-memory`.
- [ ] T010 [P] [L:facts] [US1] [BE] In `core/ops/ze-seed/ze_seed/narrative/persona.yaml`, change the two seed facts with `provenance: synthesized` (ids `00000006-0001-4000-8000-000000000010` and `...00000000003d`) to `provenance: prompt_supplied`. In `core/ops/ze-seed/tests/test_loader.py:69-72`, assert that no seed fact is `synthesized`. `make test-seed`.

**Checkpoint**: New conversation, ingestion and inbound facts are `prompt_supplied`, and decay touches dream insights only.

---

## Phase 4: User Story 2 - Existing facts are re-stamped once (Priority: P1)

**Goal**: The one-time `zm026` re-stamp, re-stamp only (Clarification Q2).

**Independent Test**: `make test-pg -k zm026`.

- [ ] T011 [L:facts] [US2] [PLATFORM] Write a failing test-pg test in a new `apps/ze-api/tests/pg/test_zm026_pg.py`, following `test_zm025_pg.py`. Import `ze_memory.migrations.versions.zm026_perception_fact_provenance as zm026`. Seed `memory_facts` with five rows:
  - A: `synthesized`, `dream_run_id` NULL, claim kind `inference`, confidence 0.2, contradicted;
  - B: `synthesized`, `dream_run_id` NULL, claim kind `fact`, confidence 0.8;
  - C: `synthesized`, `dream_run_id` set, claim kind `inference`;
  - D: `prompt_supplied`;
  - E: `live_search`.

  Run `zm026.COUNT_SQL` and assert `restamped = 2` and `decay_damaged = 1`. Run `zm026.REPAIR_SQL` and assert:
  - A and B are `prompt_supplied` with claim kind `fact`;
  - A keeps confidence 0.2 and `contradicted = true`;
  - C, D and E are unchanged;
  - `updated_at` is unchanged on every row.

  Run both again and assert `restamped = 0` the second time.
- [ ] T012 [L:facts] [US2] [PLATFORM] Create `core/cognition/ze-memory/ze_memory/migrations/versions/zm026_perception_fact_provenance.py` (`revision = "zm026"`, `down_revision = "zm025"`), per research R3 and `contracts/migrations.md`:
  - `COUNT_SQL` returns one row with the columns `restamped` and `decay_damaged`;
  - `REPAIR_SQL` is the `UPDATE`;
  - `upgrade()` runs `COUNT_SQL` through `op.get_bind()`, logs `zm026_restamped` with both counts through `get_logger(__name__)`, then runs `REPAIR_SQL`;
  - `downgrade()` is a no-op with a one-line comment (pre-v1; the old label was wrong).

  T011 passes.
- [ ] T013 [L:facts] [US2] [PLATFORM] Measure without writing: run `zm026.COUNT_SQL` read-only against the local `ze` database (`docker exec ze-postgres-1 psql -U ze -d ze -c "<COUNT_SQL>"`), and record `restamped` and `decay_damaged` in the Handoffs note. Expected on 2026-10-22: 2 and 0.

**Checkpoint**: `make test-pg -k "zm026 or dream_decay"` is green, and the `facts` lane is ready for review.

---

## Phase 5: User Story 3 - A loop's standing follows its state (Priority: P1)

**Goal**: `OpenLoop.claim_kind` is derived from state; `open_loops.claim_kind` is dropped; REST `claim_kind` is nullable.

**Independent Test**: `make test-worldstate test-priority test` and `make test-pg -k loop_claim_kind`.

- [ ] T014 [L:loops] [US3] [BE] Write failing test-pg tests in a new `apps/ze-api/tests/pg/test_loop_claim_kind_pg.py`, using `PostgresLoopStore`:
  - create a suspected loop through `store.create` and assert `claim_kind is ClaimKind.SUSPICION`;
  - confirm it with `ze_worldstate.review.confirm_loop`, re-read it, and assert `PRIORITY`. This fails today;
  - create another suspected loop, run `store.promote(id, confidence=0.7, window_days=7)`, and assert `PRIORITY`. This fails today;
  - move an active loop to drifting and then closed with `transition`, and assert `PRIORITY` each time;
  - drop a suspected loop and assert `claim_kind is None`;
  - `ze_worldstate.rest.list_loops(store, ["dropped"])` returns `"claim_kind": None` for it;
  - `information_schema.columns` has no `open_loops.claim_kind`;
  - `PriorityView` (built as in `apps/ze-api/tests/pg/test_acceptance.py`) returns the confirmed loop with `claim_kind is ClaimKind.PRIORITY`.
- [ ] T015 [P] [L:loops] [US3] [BE] Write a failing unit test in a new `core/cognition/ze-worldstate/tests/test_claim_kind.py` covering the full table: `loop_claim_kind(LoopState.X)` for all five states, and that `OpenLoop(title=..., provenance=..., confidence=..., state=...)` exposes the matching `.claim_kind`.
- [ ] T016 [L:loops] [US3] [BE] In `core/cognition/ze-worldstate/ze_worldstate/types.py`:
  - add `def loop_claim_kind(state: LoopState) -> ClaimKind | None` (table in `data-model.md`);
  - remove the `claim_kind` dataclass field from `OpenLoop`;
  - add a read-only `@property claim_kind` returning `loop_claim_kind(self.state)`.

  Run `graphify affected "OpenLoop" --depth 2` first and keep its output for T018–T020. T015 passes.
- [ ] T017 [L:loops] [US3] [BE] In `core/cognition/ze-worldstate/ze_worldstate/store.py`, drop `claim_kind` from `_loop_from_row` and from the `INSERT` column list and values in `create`.
- [ ] T018 [L:loops] [US3] [BE] Remove the `claim_kind=` argument from the `OpenLoop(...)` constructors in `core/cognition/ze-worldstate/ze_worldstate/extraction.py` (about lines 354 and 462) and `ze_worldstate/tracking.py` (about line 130). In `ze_worldstate/rest.py:34`, emit `loop.claim_kind.value if loop.claim_kind is not None else None`. `contribution.py` stays as it is (it reads the property).
- [ ] T019 [L:loops] [US3] [PLATFORM] Create `core/cognition/ze-worldstate/ze_worldstate/migrations/versions/zw006_drop_loop_claim_kind.py` (`revision = "zw006"`, `down_revision = "zw005"`).
  - `upgrade`: `ALTER TABLE open_loops DROP COLUMN claim_kind`.
  - `downgrade`: re-add it as `TEXT`, fill it with `CASE state WHEN 'suspected' THEN 'suspicion' WHEN 'dropped' THEN 'suspicion' ELSE 'priority' END`, then set it `NOT NULL`. The old column was not nullable; the comment says dropped maps to suspicion only for the restore.
- [ ] T020 [L:loops] [US3] [BE] Remove `claim_kind=` from every `OpenLoop(...)` call in the test files, deleting only those lines and changing nothing else:
  - `core/cognition/ze-worldstate/tests/` (`test_track_loop_tool.py`, `test_loop_agent_cancel.py`, `test_extraction.py`, `test_track_loop_undo_payload.py`, `test_rest.py`, `test_admission.py`, `test_contribution.py`, `test_corroboration_flow.py`, `test_intake.py`, `test_store.py`, `test_tracking.py`, `test_surfacing.py`, `test_confirm_loop_tool.py`, `test_decay.py`, `test_matching.py`, `jobs/test_stale_suspicion.py`, `jobs/test_drift_sweep.py`, `test_loop_screen_resolver.py`, `test_drift.py`, `test_corroboration.py`, `test_loop_evidence_plumbing.py`, `test_review.py`);
  - `core/arbitration/ze-priority/tests/factories.py`, `tests/test_turn.py`, `tests/compose/test_rules_topic.py`, `tests/compose/test_rules_slipping.py`;
  - `apps/ze-api/tests/pg/_builders.py`.

  Where a test sets a kind that disagrees with its state, set the state instead. Rewrite `test_contribution.py::test_extraction_write_path_rejects_malformed_claim_kind_before_create`: a malformed stored kind is no longer possible, so replace it with a test that the contribution built for a new suspected loop declares `SUSPICION`, and for a declared active loop `PRIORITY` (FR-012).
- [ ] T021 [L:loops] [US3] [BE] In `apps/ze-api/ze_api/api/v0/loops/schemas.py:19`, make `LoopListItem.claim_kind` `str | None`. Update the route's `description` to say it is null for dropped loops. In `apps/ze-api/tests/api/test_loops_route.py`, add a case for a dropped loop returning `claim_kind: null`, and remove its `claim_kind=` constructor arguments.
- [ ] T022 [L:loops] [US3] [BE] Run `make test-worldstate test-priority test` and `make test-pg -k loop_claim_kind`. All green; T014 passes.

**Checkpoint**: A confirmed or promoted loop reads `priority` everywhere, and the column is gone.

---

## Phase 6: User Story 4 - "That's done" closes a loop nobody confirmed (Priority: P1)

**Goal**: A resolve closes a suspected, active or drifting loop, links the resolving evidence, and never writes a fingerprint. Generic transitions still refuse `suspected → closed`.

**Independent Test**: `make test-worldstate` and `make test-pg -k loop_resolve`.

- [ ] T023 [L:loops] [US4] [BE] Write failing test-pg tests in a new `apps/ze-api/tests/pg/test_loop_resolve_pg.py`, reusing the `_TitleEmbedder`, `_graph()` and `_propose(...)` pattern from `apps/ze-api/tests/pg/test_loop_evidence.py`. Use an `_Llm` that returns `{"is_loop": false, "resolves_existing": true, "title": "Renew passport"}`. Cover:
  (a) A suspected loop titled "Renew passport", created through `_propose` with an email ref. A second `_propose` with a resolve reply and a new episode ref closes it: `state is CLOSED`, `closed_at` is set, `list_evidence` contains the new ref, and `dismissed_evidence_fingerprint` is NULL. This fails today.
  (b) The same, run through the System One admission path: `_commit_admitted` with a `LoopGateDecision("resolve", ...)`, called as `propose_loop_candidates(..., admission=LoopAdmission(...))` the way `ze_worldstate/admission.py` does. Repeat for the provenances `conversation`, `email` and `ingestion` (each with one evidence ref, linked after the resolve) and `calendar` (no refs: it closes with nothing linked).
  (c) Active and drifting loops (from `_builders.make_loop`) close the same way, with the evidence linked.
  (d) `PostgresLoopStore.transition(suspected_id, "closed")` still raises `InvalidLoopTransitionError`.
  (e) `store.resolve` on a dropped loop returns None and changes nothing.
  (f) `LoopInflow(...).commit_for(text, "email", admission)` with a resolve admission logs no `loop_extraction_failed`. Use `structlog.testing.capture_logs`.
- [ ] T024 [L:loops] [US4] [BE] In `core/cognition/ze-worldstate/ze_worldstate/store.py`:
  - add `resolve(self, loop_id: UUID, evidence: Sequence[EvidenceRef]) -> OpenLoop | None` to the `LoopStore` Protocol and implement it on `PostgresLoopStore`, per `contracts/loop-store.md`;
  - the implementation runs one `async with conn.transaction()`, does a conditional `UPDATE ... WHERE id = $1 AND state IN ('suspected','active','drifting') RETURNING *`, then inserts one `derived_from` relationship per ref with the `link_evidence` SQL;
  - it raises `LoopNotFoundError` when the id is unknown, returns `None` when no row moved, and logs `open_loop_transitioned` with `event="resolve"`;
  - leave `_ALLOWED_TRANSITIONS` and `transition` unchanged.
- [ ] T025 [L:loops] [US4] [BE] In `core/cognition/ze-worldstate/ze_worldstate/extraction.py`:
  - give `_close_matching_loop` an `evidence_refs: list[EvidenceRef]` parameter, and have it call `loop_store.resolve(existing.id, evidence_refs)`, returning `[closed]` or `[]`;
  - pass `evidence_refs` at both call sites (`_commit_admitted`, about line 512, and the 109 fallback branch in `propose_loop_candidates`, about line 640).

  Add `resolve` to every in-memory `LoopStore` fake under `core/cognition/ze-worldstate/tests/` (search for `class .*LoopStore` and `async def transition`). Update `test_extraction.py::test_resolves_existing_closes_matching_loop_instead_of_creating` and `test_intake.py::test_resolve_closes_matching_loop` to assert `resolve` was called with the evidence. T023 passes.
- [ ] T026 [L:loops] [US4] [BE] Run `make test-worldstate`, `make test-pg -k "loop_resolve or loop_evidence or loop_claim_kind"`, and `make lint`. All green. The `loops` lane is ready for review. Tell `lead` that `schemas.py` changed (T021), so the client can be regenerated.

**Checkpoint**: B3 and B12 are fixed. Phase 203 can build on `LoopStore.resolve` and `loop_claim_kind`.

---

## Phase 7: User Story 5 - Executive cannot state facts (Priority: P2)

**Goal**: Executive's licence is {priority, suspicion}.

**Independent Test**: `make test-plugin`.

- [x] T027 [P] [L:jr1] [US5] [BE] In `core/contracts/ze-plugin/tests/test_contribution.py`, extend the two existing parametrize tables. Do not add new test functions.
  - In `test_licensed_claim_kind_is_accepted`, add the row `(SourceFunction.EXECUTIVE, ClaimKind.SUSPICION),`. It already passes; it pins that the narrowing keeps suspicion.
  - In `test_unlicensed_claim_kind_is_rejected`, add these three rows:

    ```python
            (SourceFunction.EXECUTIVE, ClaimKind.FACT),
            (SourceFunction.EXECUTIVE, ClaimKind.INFERENCE),
            (SourceFunction.EXECUTIVE, ClaimKind.IDENTITY),
    ```

  Run `make test-plugin`. Exactly these 3 new rejected cases fail on today's code; that is the failing test.
- [ ] T028 [L:jr1] [US5] [BE] In `core/contracts/ze-plugin/ze_plugin/contribution.py` (lines 52-62), replace the Executive entry with `SourceFunction.EXECUTIVE: frozenset({ClaimKind.PRIORITY, ClaimKind.SUSPICION}),`. Run `make test-plugin test-worldstate test-priority`. All green, and T027 passes.

---

## Phase 8: User Story 6 - Contacts carry where they came from (Priority: P3)

**Goal**: A contact source's provenance follows from its source type, the creating source sets the contact's provenance, co-occurrence origin is `prompt_supplied`, and `zc041` re-stamps existing rows (Clarification Q3).

**Independent Test**: `make test-personal test-prospecting` and `make test-pg -k contact_provenance`.

- [ ] T029 [L:contacts] [US6] [BE] Write failing test-pg tests in a new `apps/ze-api/tests/pg/test_contact_provenance_pg.py`. Each test runs `TRUNCATE contacts CASCADE` first; see `test_contacts_watermark_pg.py`.
  (a) `ContactConsolidator._store_candidate` (built with the real person store on `pg_pool`) with `ContactProposal(source_type="email", ...)` stores a `contact_sources` row with `provenance='prompt_supplied'` and a `contacts` row with `prompt_supplied`. This fails today. Repeat for `calendar` and `conversation`.
  (b) The prospecting tool (`ze_prospecting.agents.tools`, the add-prospect tool) stores a `research` source with `live_search`. This fails today.
  (c) Seed the rows with raw SQL: sources `email` and `research` stored `synthesized`, and a contact whose earliest source is `email`. Run `zc041.REPAIR_SQL` (import `ze_personal.migrations.versions.zc041_contact_source_provenance as zc041`). The sources become `prompt_supplied` and `live_search`, and the contact becomes `prompt_supplied`. A contact with no source is unchanged. A second run changes 0 rows.
- [ ] T030 [L:contacts] [US6] [BE] In `plugins/ze-personal/ze_personal/contacts/`:
  - create `errors.py` with `class ContactSourceTypeError(ZeCoreError)` (import `ZeCoreError` from `ze_sdk.errors`);
  - in `types.py`, make `_SOURCE_TYPE_TO_PROVENANCE` map `manual`, `conversation`, `email` and `calendar` to `PROMPT_SUPPLIED` and `research` to `LIVE_SEARCH`;
  - add `source_provenance(source_type: str) -> Provenance`, which raises `ContactSourceTypeError` for an unknown type;
  - turn `PersonSource.provenance` into a read-only property that returns `source_provenance(self.source_type)` (remove the field);
  - delete the `ContactProposal.provenance` field.

  Add unit tests for `source_provenance` (all five types plus one unknown) to `plugins/ze-personal/tests/contacts/` (new `test_source_provenance.py`).
- [ ] T031 [L:contacts] [US6] [BE] Update the write and read paths:
  - In `contacts/store.py`, stop passing `provenance=` when building `PersonSource` from a row (about lines 54-60); `add_source` keeps writing `source.provenance.value`.
  - In `contacts/extractors.py`, remove the `provenance=` arguments at about lines 66 and 111.
  - In `contacts/consolidator.py` (about line 259), `graph/memory_hooks.py` (about line 240) and `plugins/ze-prospecting/ze_prospecting/agents/tools.py` (about line 66), pass `provenance=source.provenance` when building a new `Person`. In prospecting, build the `PersonSource` before the `Person` so it can.
  - Update `plugins/ze-personal/tests/contacts/`, `plugins/ze-personal/tests/graph/test_memory_hooks.py` and `plugins/ze-prospecting/tests/agents/test_tools.py` where they pass or assert the old provenance.
- [ ] T032 [L:contacts] [US6] [BE] In `plugins/ze-personal/ze_personal/jobs/social_cooccurrence.py:53`, change `Provenance.LIVE_SEARCH` to `Provenance.PROMPT_SUPPLIED` (email and calendar). Conversation keeps `SYNTHESIZED`. Add an assertion to `plugins/ze-personal/tests/jobs/test_social_cooccurrence.py` that email and calendar evidence carry `PROMPT_SUPPLIED` and conversation evidence carries `SYNTHESIZED`. It fails today for email and calendar.
- [ ] T033 [L:contacts] [US6] [PLATFORM] Create `plugins/ze-personal/ze_personal/migrations/versions/zc041_contact_source_provenance.py` (`revision = "zc041"`, `down_revision = "zc040"`):
  - `REPAIR_SQL` first sets `contact_sources.provenance` to `'prompt_supplied'` where `source_type IN ('manual','conversation','email','calendar')` and to `'live_search'` where `source_type = 'research'`, but only where the value differs;
  - it then updates `contacts.provenance` from `SELECT DISTINCT ON (contact_id) contact_id, provenance FROM contact_sources ORDER BY contact_id, created_at`, where the value differs;
  - `upgrade()` logs the row counts with `get_logger`; `downgrade()` is a no-op with a comment.

  T029 passes.
- [ ] T034 [L:contacts] [US6] [BE] Run `make test-personal test-prospecting`, `make test-pg -k contact_provenance` and `make lint`. All green. The `contacts` lane is ready for review.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T035 [L:lead] [PLATFORM] Merge the lane branches into the floor branch in the order `jr1` → `facts` → `contacts` → `loops`, resolving no conflicts by hand in another lane's files (the lanes are disjoint).
- [ ] T036 [L:lead] [PLATFORM] Run `make codegen` and commit the regenerated `packages/ze-client/src/generated/` (`LoopListItem.claim_kind` becomes `string | null`). If floor 198 has landed on main first, rebase and re-run `make codegen` rather than hand-merging generated files.
- [ ] T037 [L:lead] [WEB] Make the three web readers accept a null loop claim kind:
  - `apps/ze-web/src/pages/world/lib/concerns.ts:73`: `claimKind` is already nullable; keep the type check passing;
  - `apps/ze-web/src/widgets/loops-rail/ui/LoopsRail.tsx:44`;
  - `apps/ze-web/src/pages/doing-goal/ui/DoingGoalPage.tsx:165`: render no claim label when `l.claim_kind` is null.

  Add or extend a colocated vitest for `concerns.ts` with a dropped loop (`claim_kind: null`). Run `make typecheck-web test-web`.
- [ ] T038 [L:lead] [PLATFORM] Run the full gates and record each result in the Handoffs note and the state file:
  - `make test-py`
  - `make test-pg`
  - `make lint`
  - `make typecheck-web`
  - `make test-web`
- [ ] T039 [L:lead] [PLATFORM] Check that the fix holds. Every query must return 0:
  - `grep -rn "Provenance.SYNTHESIZED" core/engine/ze-core/ze_core/orchestration/nodes/memory.py core/ops/ze-ingestion/ze_ingestion/sink.py plugins/ze-messenger/ze_messenger/inbound/processor.py`
  - `grep -rn "claim_kind=" core/cognition/ze-worldstate/ze_worldstate`, which should list only `contribution.py`.

  Run `graphify update .`, then run `graphify affected` on `OpenLoop`, `_close_matching_loop`, `submit_perception_facts` and `PersonSource`, and confirm every caller it lists was updated or is unaffected. Record useful or misleading queries with `graphify save-result ... --memory-dir /Users/joaoamatos/coding/ze/graphify-out/memory`.
- [ ] T040 [L:lead] [PLATFORM] Run quickstart.md section 4 against a scratch database: create `ze_199_verify` (`docker exec ze-postgres-1 createdb -U ze ze_199_verify`), run `make migrate` with `DATABASE_URL` and `DATABASE_URL_SYNC` pointed at it, and confirm the `zm026_restamped` log line. Do not run the migration on the shared `ze` DB; the user lands floors.
- [ ] T041 [P] [L:docs] [DOCS] Update the public docs from the finished diff (doc-style skill rules):
  - `docs/dreaming.md:79-80,174-186`: decay and expiry apply to dream insights only, selected by `dream_run_id`;
  - `docs/architecture.md:574,605-606`: post-turn extraction stores `prompt_supplied` facts, and expiry applies to dream insights;
  - `docs/memory.md`: a fact provenance paragraph: perception writes `prompt_supplied`, only the dream writes `synthesized`, and `live_search` means a web search;
  - `docs/goals.md:162`: promotion is `prompt_supplied`, not synthesized (stale before this phase);
  - `docs/features.md:43`: the loop state machine now shows that saying it is done closes a suspected loop; redraw the diagram with the diagram-design skill if it shows edges;
  - `core/cognition/ze-worldstate/README.md`: the claim kind follows the state, the `resolve` event, and `zw006`;
  - `core/cognition/ze-memory/README.md`: decay scope and `zm026`;
  - `plugins/ze-personal/README.md`: contact provenance by source type and `zc041`.
- [ ] T042 [L:docs] [DOCS] Update the indexes and their checks:
  - `AGENTS.md`: add the 199 phase row (Implemented, a one-line summary in the table's style); in Migration ownership, name `zm026` (ze-memory row), `zw006` drops `open_loops.claim_kind` (ze-worldstate row), and `zc041` contact provenance re-stamp (ze-personal row);
  - `specs/README.md`: the 199 Status cell only;
  - `specs/arch/contribution-seam.md`: confirm that no text still attributes candidate loops to Perception;
  - spec.md: set `**Status**` to Implemented.

  Run the `speckit-process-after-implement` skill.
- [ ] T043 [L:docs] [DOCS] Run a coverage check: `git diff main...HEAD --stat -- docs/ AGENTS.md specs/README.md '*README.md'`. Confirm every file listed in T041–T042 appears in it, and list any public doc that names a changed symbol (`grep -rn "creation_method\|claim_kind\|live_search\|synthesized" docs/ */*/README.md */*/*/README.md`) but was not updated, with a reason.

---

## Dependencies & Execution Order

- **T001** comes first.
- **US1 (T002–T010) → US2 (T011–T013)**, both in the `facts` lane. US2 needs only T012's file, but the lane runs them in order.
- **US3 (T014–T022) → US4 (T023–T026)**, both in the `loops` lane. They are sequential because both edit `store.py` and `extraction.py`, and T023's fixtures build on the derived claim kind.
- **US5 (T027–T028)** in `jr1` and **US6 (T029–T034)** in `contacts` are independent of everything else.
- **T035–T040** (`lead`) start once all four lanes are reviewed. T036–T037 depend on T021.
- **T041–T043** (`docs`) start after T035.

## Parallel Example

After T001, four agents start together:

```text
facts:    T002, T004, T006 (three failing tests, different files) → T003, T005, T007 → T008 → T009 → T010 → T011 → T012 → T013
loops:    T014, T015 → T016 → T017 → T018 → T019 → T020 → T021 → T022 → T023 → T024 → T025 → T026
contacts: T029 → T030 → T031 → T032 → T033 → T034
jr1:      T027 → T028
```

## Implementation Strategy

- **MVP**: US1 alone (T002–T010) stops new user-stated facts from decaying. It is the bug with real cost.
- **Then** US2 (the existing rows), US3 and US4 (loops), US5, and US6.
- Each lane is reviewed on its own small diff before `lead` merges it.
- Phase 203 depends on US3 and US4 having landed.
