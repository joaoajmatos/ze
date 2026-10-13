# Tasks: Executive Repair

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Unit tests use fakes. Real-row tests live in `apps/ze-api/tests/pg/` (marker `pg`). Never call OpenRouter or System One.

**Lanes**: `[ENG]` = Claude Sonnet lane lead (cross-package design, concurrency, SQL, debugging, integration, gates). `[JR]` = OpenCode flash junior (exact files and behavior given). See the Lanes section at the end.

**Tags**: `[BE]` backend Python · `[WEB]` ze-web and generated client · `[PLATFORM]` config, Makefile, harness · `[DOCS]` docs, READMEs, specs.

**Normative references**: drift and corroboration: [contracts/drift-and-corroboration.md](./contracts/drift-and-corroboration.md). Stuck goals: [contracts/stuck-goals.md](./contracts/stuck-goals.md). Evidence and grounding: [contracts/loop-evidence.md](./contracts/loop-evidence.md). Snapshot REST: [contracts/priority-snapshot.md](./contracts/priority-snapshot.md). Harness: [contracts/pg-harness.md](./contracts/pg-harness.md).

**Rules for the implementer**
- Before changing any signature listed in plan.md "Impact analysis", run `graphify affected "<Symbol>" --depth 2` and update every caller in the same change. graphify misses `ze_sdk` re-exports; also `rtk proxy grep -rn "<name>" --include='*.py' .`.
- Do not touch `PostgresLoopStore.transition` or `stamp_declared` (Phase 169 owns them). Do not add a migration.
- No `print()`; `get_logger(__name__)`. No bare `Exception`/`ValueError` in domain code (use the existing typed errors).
- Run `make lint` before each commit. Do not commit unless asked.
- If a step below disagrees with the code you find, stop and write the difference in your report; do not improvise a redesign.

**Ordering**: Phases run in order. `[P]` tasks touch different files and may run together.

---

## Phase 0: Gate  [ENG]

- [x] **T001** [ENG] [BE] Check whether Phase 169 is on your branch: `git log --oneline -5 -- core/cognition/ze-worldstate/ze_worldstate/store.py` and `grep -n "stamp_declared\|user_asked" core/cognition/ze-worldstate/ze_worldstate/store.py`. If present, read it against `specs/phases/169-loop-track-tool/spec.md` and note any difference from the pinned revive field set (state `active`, confidence 0.9, `confirmed_at = now`, `drift_deadline = now + window`, `drift_rationale` NULL, `updated_at = now`) in your report. 170 changes neither method. If 169 is absent, continue; the one 169-dependent test (T008 row "revive") skips itself. · none

---

## Phase 1: Harness (User Story 6, foundational)  [ENG; T002 and T003 are [JR]]

**Goal**: `make test-pg` runs real-row tests; `make test-py` does not need Docker.

- [x] **T002** [JR] [P] [PLATFORM] Add the `pg` marker to `[tool.pytest.ini_options].markers` in `apps/ze-api/pyproject.toml`: `"pg: needs a real Postgres (run with make test-pg; skipped unless ZE_TEST_PG=1)"`. · `apps/ze-api/pyproject.toml`
- [x] **T003** [JR] [P] [PLATFORM] Makefile: add target `test-pg` exactly as in contracts/pg-harness.md (`ZE_TEST_PG=1 uv run pytest -q -m pg apps/ze-api/tests/pg`), a help line `test-pg  Real-Postgres tests (needs Docker or ZE_TEST_PG_URL); not part of test-py`, and add it to the `.PHONY` list near line 324. Do NOT add it to `TEST_PY_PACKAGES`. · `Makefile`
- [x] **T004** [ENG] [BE] Fail-first, skip rule without Docker: new unit test `apps/ze-api/tests/test_pg_harness_skip.py` that runs `python -m pytest --collect-only -q apps/ze-api/tests/pg` and then `python -m pytest -q apps/ze-api/tests/pg` in a subprocess with `ZE_TEST_PG` unset and a `PATH` whose first entry is a temp dir holding a fake `docker` script that writes a marker file and exits 99. Assert return code 0 (T006 adds the tests that get skipped), the output contains `skipped`, and the marker file was never created (Docker was never called). · `apps/ze-api/tests/test_pg_harness_skip.py`
- [x] **T005** [ENG] [BE] Create the harness package per contracts/pg-harness.md: `apps/ze-api/tests/pg/__init__.py` (empty), `_container.py` (`PgHarnessError(RuntimeError)`, `PgContainer` dataclass with `asyncpg_url` and `stop()`, `start_container()` with the five steps in the contract; image constant `pgvector/pgvector:pg16`; `atexit` stop), `conftest.py` (skip hook, `pg_dsn` session fixture running `ze_api.migrate.upgrade` on the `postgresql+psycopg2://` form, `pg_pool` function fixture truncating `RESET_TABLES`), and `_builders.py` with `make_loop`, `make_goal_with_gates`, `make_episode` (real stores or raw `INSERT`; read `core/automation/ze-automation/ze_automation/goals/store.py` and the `zc*` goal migrations for columns). · `apps/ze-api/tests/pg/`
- [x] **T006** [ENG] [BE] `test_harness_smoke.py` (`pytestmark = pytest.mark.pg`): (a) after migrations the tables `open_loops`, `goal_gates`, `memory_episodes`, `memory_relationships`, `push_log` exist; (b) two tests in one module each insert an `open_loops` row and assert `count(*) == 1` (proves reset between tests); (c) `make_goal_with_gates` returns a goal whose gates read back with the requested `fired_at` values. Run `make test-pg`; all pass. Run `make test` and confirm the pg tests are reported skipped and T004 passes. · `apps/ze-api/tests/pg/test_harness_smoke.py`

**Checkpoint**: `make test-pg` green with Docker; `make test` green with Docker stopped.

---

## Phase 2: User Story 1 - A quiet loop drifts (P1)  [ENG]

**Goal**: FR-001 to FR-005.

- [x] **T007** [ENG] [US1] [BE] Fail-first, real rows: `apps/ze-api/tests/pg/test_drift.py` implementing the matrix in contracts/drift-and-corroboration.md. Build loops through the real code paths: declared (`PostgresLoopStore.create` with `state=ACTIVE, confirmed_at=now` then `set_drift_deadline`), and suspected then `ze_worldstate.review.confirm_loop`. Fast-forward with `UPDATE open_loops SET drift_deadline = now() - interval '1 day' WHERE id = $1` (never `sleep`). The rows: past deadline → `list_drift_candidates` returns it and `DriftSweepJob(store).run()` makes it `drifting` with a rationale containing "before the implied window elapsed"; future deadline → not a candidate; `record_corroboration` cases (past deadline → deadline ≥ now+7d; 30-day deadline unchanged; no-op on drifting/closed/suspected without error); two loops, one past; revive row: `pytest.skip("Phase 169 not on this branch")` unless `hasattr(PostgresLoopStore, "stamp_declared")`, else drifting loop → `transition(id, "active", user_asked=True)` + `stamp_declared(id, confidence=0.9, deadline=<past>)` → candidate again. Expected failure now: no candidates are returned (F1) and `record_corroboration` does not exist. · `apps/ze-api/tests/pg/test_drift.py`
- [x] **T008** [ENG] [P] [US1] [BE] Fail-first, unit: in `core/cognition/ze-worldstate/tests/test_drift.py` replace the `is_drift_eligible` cases with the new rule (active + deadline not after now; naive datetime treated as UTC; `confirmed_at`/`updated_at` ignored; non-active false; no deadline false) and assert the new rationale text from FR-004; in `tests/jobs/test_drift_sweep.py` add: the sweep continues when one `transition` raises `InvalidLoopTransitionError` (logs `open_loop_drift_skipped`), and no longer imports `is_stale`; in `tests/test_store.py` (`make_pool`) assert `list_drift_candidates` SQL contains `drift_deadline <= now()` and does not contain `updated_at` or `confirmed_at`, and `record_corroboration` issues one `execute` whose SQL contains `GREATEST`, `state = 'active'` and passes `window_days` as `$2`. · `core/cognition/ze-worldstate/tests/test_drift.py`, `tests/jobs/test_drift_sweep.py`, `tests/test_store.py`
- [x] **T009** [ENG] [US1] [BE] `store.py`: change the `list_drift_candidates` SQL; add `record_corroboration` to the `LoopStore` Protocol and `PostgresLoopStore` exactly as in the contract (import `DEFAULT_DRIFT_WINDOW_DAYS` from `ze_worldstate.drift`; check there is no import cycle). Find every in-repo `LoopStore` fake (`graphify explain LoopStore`; `rtk proxy grep -rn "def set_drift_rationale" --include='*.py' .`) and add `record_corroboration` (an `AsyncMock` or a no-op). · `core/cognition/ze-worldstate/ze_worldstate/store.py` and fakes
- [x] **T010** [ENG] [US1] [BE] `drift.py`: `is_drift_eligible` per FR-003; `compose_absence_rationale` per FR-004 (drop the `confirmed_at` text). `jobs/drift_sweep.py`: iterate `list_drift_candidates()`, skip if not `is_drift_eligible`, `transition` + `set_drift_rationale`, catch `InvalidLoopTransitionError` per loop; remove the `is_stale` import. Make T007 (drift rows) and T008 pass. · `core/cognition/ze-worldstate/ze_worldstate/drift.py`, `jobs/drift_sweep.py`

**Checkpoint**: `make test-worldstate`, `make test-pg` (drift file) green.

---

## Phase 3: User Story 2 - Stuck goals found, alerted, ranked (P1)  [ENG]

**Goal**: FR-006, FR-007.

- [x] **T011** [ENG] [US2] [BE] Fail-first, real rows: `apps/ze-api/tests/pg/test_stuck_goals.py` with the matrix in contracts/stuck-goals.md. Primary fixture `make_goal_with_gates(status="awaiting_gate", gates=[("approved", fired 40d ago, resolved), ("awaiting_approval", fired 10d ago), ("pending", None), ("pending", None), ("pending", None)])`. Cases include `PriorityView(PostgresLoopStore, PostgresGoalStore, PostgresHypothesisStore).rank()` (`sources_failed == set()`, goal item present) and `StuckGoalJob.run()` with a recording notifier (one `push_notification`, `last_stuck_alert_at` set afterwards). Expected failure now: `AttributeError: 'NoneType' object has no attribute 'tzinfo'`. · `apps/ze-api/tests/pg/test_stuck_goals.py`
- [x] **T012** [ENG] [P] [US2] [BE] Unit: in `core/automation/ze-automation/tests/proactive_jobs/test_stuck_goals.py` keep the existing cases (they use a fake store); add one for the Python guard by calling `PostgresGoalStore.list_stuck` with a `make_pool`-style fake whose second `fetch` returns a row dict with `fired_at=None`: it must return no entry and log `list_stuck_open_gate_without_fired_at` (inspect how the file builds fake rows; copy its helper). · `core/automation/ze-automation/tests/proactive_jobs/test_stuck_goals.py`
- [x] **T013** [ENG] [US2] [BE] `goals/postgres.py` `list_stuck`: replace the gate query with the contract SQL (`DISTINCT ON (g.id)`, `fired_at IS NOT NULL` in the join, `ORDER BY g.id, vg.fired_at ASC`), add the Python guard before `fired_at.tzinfo`. Leave the active-goal half, `is_stale` check, `StuckGoal` construction and final sort unchanged. Make T011 and T012 pass. · `core/automation/ze-automation/ze_automation/goals/postgres.py`

**Checkpoint**: `make test-automation`, `make test-priority`, `make test-pg` (stuck file) green.

---

## Phase 4: User Story 3 - Loops carry evidence (P1)  [ENG; T017 and T022 are [JR]]

**Goal**: FR-008 to FR-014.

**Wave 1: fail-first tests**

- [x] **T014** [ENG] [P] [US3] [BE] `ze-memory`: test that `PostgresMemoryStore.write_episode` returns the `id` from `fetchrow` and returns `None` when the pool raises (existing test file for retriever/episodes: `rtk proxy grep -rln "write_episode" core/cognition/ze-memory/tests`). · `core/cognition/ze-memory/tests/`
- [x] **T015** [ENG] [P] [US3] [BE] `ze-worldstate` tests (`test_admission.py`, `test_extraction.py`): (a) `admission.commit([ref])` passes `evidence_refs=[ref]` to `propose_loop_candidates` and the created loop gets `link_evidence` called with `("episode", id)`; (b) declared path with a matching open loop (fake `find_matching_loop` result): no `create`, evidence linked, `record_corroboration` called once for an `active` match, not called for `suspected`/`drifting` matches or when no evidence is given, state/confidence untouched; (c) declared path with no match: `create` called and `check_episode_exists`/`check_fact_exists` passed to `submit_and_detect_collisions` (assert via the recording patch used in existing tests); (d) suspected path matched branch calls `record_corroboration` only for `active` + non-empty evidence; (e) fingerprint table in contracts/loop-evidence.md (dropped `{A}` vs new `{A}` suppressed, vs `{B}` creates, empty vs empty suppressed, empty vs `{B}` creates); (f) `extract(text, prov, evidence=[ref])` forwards evidence through `_commit_for`. · `core/cognition/ze-worldstate/tests/`
- [x] **T016** [ENG] [P] [US3] [BE] `ze-core` node: extend `core/engine/ze-core/tests/orchestration/test_loop_admission_node.py`: with a fake `store.write_episode` returning an id and a fake `loop_admission` whose `commit` records its argument, after the node returns and pending tasks are drained (`await asyncio.sleep(0)` loops or gather of `asyncio.all_tasks()` minus current) the commit received `[EvidenceRef("episode", id)]`; when `write_episode` raises or returns `None` the commit receives `[]`; the node returns before a deliberately slow `write_episode` completes. · `core/engine/ze-core/tests/orchestration/test_loop_admission_node.py`
- [x] **T017** [JR] [P] [US3] [BE] Inflow owners: `plugins/ze-messenger/tests/test_inbound_processor.py` (the processor passes `evidence=[EvidenceRef("episode", id)]` to `loop_extractor`, and `[]` when `write_episode` returns `None`; update the existing assertion that expects two positional args); `core/ops/ze-ingestion/tests/test_sink.py` (extractor gets `evidence=[EvidenceRef("ingestion", uuid)]` for a UUID id, `[]` for a non-UUID id); the calendar job test (`rtk proxy grep -rln "loop_extractor" plugins/ze-calendar/tests`) asserts the extractor is called with two positional args and no evidence. · those files
- [x] **T018** [ENG] [P] [US3] [BE] Grounding and summaries: in `core/cognition/ze-worldstate/tests/test_surfacing.py` add `passes_push_bar` cases with an NLI stub that records its pairs: the pair hypothesis is `loop.title`, not the rationale; no labels → passes; add a `test_rest.py` case (or extend an existing one) that `_fetch_evidence_summaries` issues the `messenger` branch SQL (assert the SQL string contains `agent = 'messenger'` and `left(response, 500)`) and returns the fetched text. · `core/cognition/ze-worldstate/tests/test_surfacing.py`, `tests/test_rest.py`

**Wave 2: implementation**

- [x] **T019** [ENG] [US3] [BE] `write_episode` returns `UUID | None`: Protocol in `ze_memory/store.py`, impl in `ze_memory/retriever.py` (`return episode_id` at the end of the `try`, `return None` in the `except`). Update test doubles that implement it. Makes T014 pass. · `core/cognition/ze-memory/ze_memory/store.py`, `retriever.py`
- [x] **T020** [ENG] [US3] [BE] Worldstate plumbing: `types.py` (`LoopAdmission.commit` type; `DriftingLoopMention` is deleted in T033A, not here), `admission.py` (`_commit_for` returns `async def _commit(evidence=()): ... evidence_refs=list(evidence)`; `extract(text, provenance, evidence=())` passes it), `inflow.py` (callables forward `evidence`), `extraction.py`: new helper `_existence_checkers(memory_store)` returning the two checker callables currently built inline in `_create_suspected_loop`; `_create_declared_loop` gains `graph_store`, `embedder`, `memory_store` params, runs the dedup step from contracts/loop-evidence.md, passes the checkers; update the three call sites (`USER_DECLARED` direct, `_commit_admitted`, Haiku fallback gate); `_create_suspected_loop` matched branch calls `record_corroboration` per the contract. Makes T015 pass. · `core/cognition/ze-worldstate/ze_worldstate/{types,admission,inflow,extraction}.py`
- [x] **T021** [ENG] [US3] [BE] `write_memory`: keep the task returned by `fire_and_forget(store.write_episode(...), label="write_episode")`, add `_commit_with_episode` exactly as in the contract, import `EvidenceRef` from `ze_plugin.contribution`, schedule `fire_and_forget(_commit_with_episode(loop_result.commit, episode_task), label="loop_commit")`. Keep the `not is_eval and not is_retry` guard. Makes T016 pass. · `core/engine/ze-core/ze_core/orchestration/nodes/memory.py`
- [x] **T022** [JR] [US3] [BE] Owners: messenger processor (`episode_id = await self._memory.write_episode(...)`; build refs; call `self.loop_extractor(msg.body, "email", evidence=refs)`; import `EvidenceRef` from `ze_sdk.contribution`; update the attribute type hint to `Callable[..., Awaitable[None]] | None`), ingestion sink (pass the `evidence` list it already builds; same hint change), calendar job (hint change; `log.debug("calendar_loop_no_evidence", event_id=...)` before calling). Makes T017 pass. · `plugins/ze-messenger/ze_messenger/inbound/processor.py`, `core/ops/ze-ingestion/ze_ingestion/sink.py`, `plugins/ze-calendar/ze_calendar/jobs/calendar_reminder.py`
- [x] **T023** [ENG] [US3] [BE] `surfacing.py`: grounding uses `loop.title` (novelty keeps `rationale`); `rest.py` `_fetch_evidence_summaries`: episode query per the contract. Makes T018 pass. · `core/cognition/ze-worldstate/ze_worldstate/surfacing.py`, `rest.py`
- [x] **T024** [ENG] [US3] [BE] Real rows: `apps/ze-api/tests/pg/test_loop_evidence.py`: insert a `memory_episodes` row with `make_episode`, call `propose_loop_candidates` (declared and suspected) with `evidence_refs=[EvidenceRef("episode", id)]`, real `PostgresLoopStore`, fake embedder/LLM/graph where needed, and real `memory_store` existence checkers backed by the pool; assert `list_evidence` returns the ref; second call with the same text and a second episode on an `active` match: still one loop, evidence count 2, `drift_deadline` moved to ≥ now+7d; drop a loop then replay with the same evidence (no new loop) and with a new episode (new `suspected` loop); `_fetch_evidence_summaries` for a `messenger` episode returns subject and body text; `LoopSurfacer.passes_push_bar` with an NLI stub (entailment 0.1 for the rationale, 0.9 for the title) returns true and false when both are low. · `apps/ze-api/tests/pg/test_loop_evidence.py`

**Checkpoint**: `make test-worldstate test-core test-memory test-messenger test-ingestion test-calendar` and `make test-pg` green.

---

## Phase 5: User Story 4 - The priority page says what it could not load (P2)  [JR]

**Goal**: FR-015 to FR-017.

- [x] **T025** [JR] [P] [US4] [BE] Fail-first: `core/arbitration/ze-priority/tests/test_rest.py` (new or extend): `get_snapshot` with a view whose `rank()` returns `sources_failed={"goal"}` gives `PrioritySnapshotResult(items=[...], sources_failed=("goal",))`; `apps/ze-api/tests/api/test_priority_routes.py` (new or extend, follow the style of the other route tests in `tests/api/`): (a) a ranking with a `relationship` item returns 200 and `source_kind == "relationship"` (today a validation error), (b) body keys are exactly `items` and `sources_failed`, (c) `sources_failed` lists failed kinds, (d) `POST /priority/override` still returns one `PrioritySnapshotItem`. · those files
- [x] **T026** [JR] [US4] [BE] `ze_priority/types.py` add `PrioritySnapshotResult`; `ze_priority/rest.py` `get_snapshot` returns it, `_snapshot_row_for` uses `.items`; `apps/ze-api/ze_api/api/schemas.py`: add `SourceKindLiteral` and `PrioritySnapshotResponse`, switch the Literals in `PrioritySnapshotItem`, `PriorityOverrideSchema` and `PriorityOverrideRequestSchema`; `routes/priority.py` GET returns `PrioritySnapshotResponse` (summary/description mention `sources_failed`). Make T025 pass. · `core/arbitration/ze-priority/ze_priority/{types,rest}.py`, `apps/ze-api/ze_api/api/{schemas.py,routes/priority.py}`
- [x] **T027** [JR] [US4] [WEB] Run `make codegen`; commit the changed files under `packages/ze-client/src/generated/`. If the generator output differs in unrelated places, report it and keep only the priority-related hunks plus whatever the generator requires. · `packages/ze-client/src/generated/`
- [x] **T028** [JR] [US4] [WEB] Fail-first then implement: `PrioritySnapshot.test.tsx` (new) renders with `{items: [], sourcesFailed: ["goal"]}` and finds the text "Couldn't load: Goal" and with `[]` finds no notice; a row with `source_kind: "relationship"` shows the label "Relationship". Then: `usePrioritySnapshotQuery.ts` returns `{ items, sourcesFailed }`; `PrioritySnapshot.tsx` adds the notice and `relationship: "Relationship"` to `SOURCE_LABEL`; update `useReprioritizeMutation.ts`, `useUnpinPriorityOverrideMutation.ts` and any code reading the cached array. Run `make test-web typecheck-web`. · `apps/ze-web/src/entities/priority-item/`, `apps/ze-web/src/widgets/priority-snapshot/`

**Checkpoint**: `make test-priority`, `make test` (ze-api), `make test-web`, `make typecheck-web` green.

---

## Phase 6: User Story 5 - Dead pieces and false switches are gone (P2)  [JR; T033A is [ENG]]

**Goal**: FR-018 to FR-020.

- [x] **T029** [JR] [P] [US5] [BE] Fail-first: (a) `core/cognition/ze-worldstate/tests/test_bootstrap.py` (new or extend): `loop_push_settings(settings)` parses `enabled`, `thresholds`, `inline_cooldown_hours` with defaults (`enabled=True`, thresholds `{}` , cooldown 12.0) and ignores unknown keys; (b) `core/arbitration/ze-priority/tests/test_arbitration.py`: `AttentionArbitrationJob(..., loop_push=LoopPushSettings(enabled=False,...))` never calls `loop_surfacer.eligible_candidates`; with settings, `eligible_candidates` is awaited with `thresholds=` and `inline_cooldown_hours=`; existing tests keep passing without the new argument (default `None` means enabled with defaults); (c) `core/cognition/ze-correlation/tests/` (find the file testing `CorrelationPushCandidateSource`): `enabled=False` → `eligible_candidates()` is `[]` and `hypothesis_store.list_unsurfaced` is not called; `enabled=True, dry_run=True` → `[]` and log `correlation_push_dry_run` once per eligible hypothesis; `enabled=True, dry_run=False` → previous behavior; (d) `apps/ze-api/tests/test_shipped_config_keys.py` (new): load `config/config.yaml`, assert `worldstate.drift` has keys exactly `{enabled, cron}`, `worldstate.push` keys exactly `{enabled, inline_cooldown_hours, thresholds}` with thresholds keys exactly `{tau_confidence, tau_relevance, novelty_similarity_max, grounding_threshold}` and `grounding_threshold == 0.3`, `correlation.push` has `enabled` and `dry_run`, and `loop_push_settings` returns the shipped values. · those files
- [x] **T030** [JR] [US5] [BE] Implement: `ze_worldstate/bootstrap.py` add `@dataclass(frozen=True) class LoopPushSettings(enabled: bool = True, thresholds: dict = field(default_factory=dict), inline_cooldown_hours: float = 12.0)` and `loop_push_settings(settings) -> LoopPushSettings` reading `settings.config["worldstate"]["push"]` defensively like `register_proactive_jobs` does; `ze_priority/arbitration.py` accept `loop_push: LoopPushSettings | None = None`, skip the loop half when `enabled` is false, pass settings to `eligible_candidates`; `ze_api/compose.py` build and pass it. · `core/cognition/ze-worldstate/ze_worldstate/bootstrap.py`, `core/arbitration/ze-priority/ze_priority/arbitration.py`, `apps/ze-api/ze_api/compose.py`
- [x] **T031** [JR] [US5] [BE] `ze_correlation/push.py` `CorrelationPushCandidateSource.eligible_candidates`: return `[]` first when `not self._cfg.enabled`; when `self._cfg.dry_run`, compute the candidates through the push bar, log `correlation_push_dry_run` (hypothesis id, summary) for each and return `[]`; otherwise unchanged. Leave `CorrelationPushConsumer.run_once` as is. · `core/cognition/ze-correlation/ze_correlation/push.py`
- [x] **T032** [JR] [US5] [PLATFORM] `apps/ze-api/config/config.yaml`: delete `worldstate.drift.window_days`; set `worldstate.push.thresholds.grounding_threshold: 0.3` with a one-line comment (matches the code default; was 0.5 and unread); delete the `correlation.salience.feedback` block and `correlation.salience.surfacing.min_evidence` after re-running `rtk proxy grep -rn "min_evidence\|salience.*feedback" --include='*.py' apps core plugins | grep -v /tests/ | grep -v surfacing.py` and confirming no other reader (if one appears, keep the key and report); comment on `correlation.push` that `enabled` and `dry_run` are honored by the arbitration path. Makes T029(d) pass. · `apps/ze-api/config/config.yaml`
- [x] **T033** [JR] [US5] [BE] Delete, one symbol at a time, after `graphify affected` and `grep` show only test callers: `core/cognition/ze-memory/ze_memory/surfacing.py` and every `SurfacingGate`/`SurfacingConfig` test in `core/cognition/ze-memory/tests/test_salience.py` (keep the `RelevanceModel` demotion tests and `test_build_admission_gate_reads_salience_config`; read research R7); `core/arbitration/ze-priority/ze_priority/learning_context.py` and `tests/test_learning_context.py`. The worldstate deletions are T033A (ENG lane, same files as T023). Keep `OpenLoop.goal_id`. Run `make test-memory test-priority lint`. Put the "writer-less `demoted_topics`/`news_exclusions` reader" observation in your report. · listed files
- [x] **T033A** [ENG] [BE] Delete `LoopSurfacer.inline_candidates` (and its `worldstate_loop_inline` push-log call inside it only; `TurnSurfacing` keeps writing that key), `DriftingLoopMention` in `types.py`, and their tests in `core/cognition/ze-worldstate/tests/test_surfacing.py`, after `graphify affected` confirms test-only callers. Do this after T023 (same files). Run `make test-worldstate`. · `core/cognition/ze-worldstate/ze_worldstate/{surfacing,types}.py`, `tests/test_surfacing.py`

**Checkpoint**: all unit suites green; `make lint` clean.

---

## Phase 7: Acceptance runs and polish  [ENG; Docs are [JR]]

- [x] **T034** [ENG] [US1] [BE] Acceptance A: `apps/ze-api/tests/pg/test_acceptance.py::test_declared_loop_drifts_and_is_a_push_candidate` (SC-001): create a declared loop through `_create_declared_loop` with `implied_window_days=1`, move its deadline to the past, run `DriftSweepJob`, assert `drifting`; `PriorityView.rank()` (real loop store; goal and hypothesis stores real) lists it with `priority.value` greater than its confidence; build `LoopSurfacer` with the real loop and graph stores, a fake relevance model (`build()` → set, `score()` → value 1.0), a fake embedder that never finds a similar recent push, an NLI stub returning high entailment, real `PushLogStore` on the pool; `eligible_candidates()` returns the loop. · `apps/ze-api/tests/pg/test_acceptance.py`
- [x] **T035** [ENG] [US2] [BE] Acceptance B (SC-002) in the same file: the T011 dev-shape goal; `PriorityView.rank()` contains it once with `sources_failed == set()`; call the route function through `TestClient` with the app dependencies overridden to the real stores (`get_priority_view`, `get_priority_override_store`) and assert the goal title is in `items`. · `apps/ze-api/tests/pg/test_acceptance.py`
- [x] **T036** [ENG] [BE] Full gate: `make lint`, `make test-py` (no Docker needed: confirm by stopping Docker or running with `PATH` lacking `docker`), `make test-pg`, `make test-web typecheck-web`. Paste the pass counts and the pg skip line in your report. Record in the report, per finding, the failure message each fail-first test showed before its fix. · none

### Docs (part of done)

- [x] **T037** [JR] [P] [DOCS] `docs/testing.md`: add `make test-pg` to the quick-reference table and a short section "Real-Postgres tests" (what runs, `ZE_TEST_PG`, `ZE_TEST_PG_URL`, why `test-py` skips them, the image used). Follow `.claude/skills/doc-style/SKILL.md`. · `docs/testing.md`
- [x] **T038** [JR] [P] [DOCS] `docs/scheduled-jobs.md`: update "Open-loop upkeep" (lines ~416 to 428): `DriftSweepJob` moves `active` loops to `drifting` when the drift deadline passes, and new evidence on an active loop moves the deadline; update "Stuck goal detection" (lines ~278 to 290): one entry per goal, from the first open gate that has fired; update "Attention arbitration" (~437 onward) to say hypothesis pushes require `correlation.push.enabled: true` and `dry_run: false` and loop pushes honor `worldstate.push.enabled`. If `docs/diagrams/docs/job-cadence-board.*` text changes, leave the diagram (cadence unchanged). · `docs/scheduled-jobs.md`
- [x] **T039** [JR] [P] [DOCS] `docs/configuration.md`: add a `worldstate` section (`drift.enabled/cron`, `push.enabled/inline_cooldown_hours/thresholds`, `stale_suspicion`) and document `correlation.push.enabled/dry_run` semantics (off / dry-run logs / live); state that the default drift window (7 days) is a code constant, not config. · `docs/configuration.md`
- [x] **T040** [JR] [P] [DOCS] `docs/goals.md` line ~178: stuck-gate detection counts the first gate that has fired and ignores gates not yet reached. · `docs/goals.md`
- [x] **T041** [JR] [P] [DOCS] Package READMEs (check each against `docs/package-readme-template.md`): `core/cognition/ze-worldstate/README.md` (drift via deadline and corroboration; evidence on loops; remove the "inline mentions" claim if it names `LoopSurfacer.inline_candidates`; push grounding checks the title), `core/arbitration/ze-priority/README.md` (snapshot response `{items, sources_failed}`; `relationship` kind; remove `LearningContextAdapter` if listed), `core/automation/ze-automation/README.md` (stuck-goal sentence), `core/cognition/ze-memory/README.md` (remove any `SurfacingGate` mention). · those files
- [x] **T042** [JR] [P] [DOCS] `README.md` line ~58 (Priority page): add one sentence that the page says when a source could not be read. `docs/package-architecture.md`: remove any row for deleted modules (`ze_memory/surfacing.py`, `ze_priority/learning_context.py`). `docs/architecture.md`: check for `SurfacingGate`/`inline_candidates` mentions and fix. · `README.md`, `docs/package-architecture.md`, `docs/architecture.md`
- [x] **T043** [JR] [DOCS] `AGENTS.md`: add the phase 170 row ("Executive Repair" — drift on deadline plus `record_corroboration`, `list_stuck` one row per goal, loop evidence and title grounding, `sources_failed` on the snapshot, `make test-pg` harness, dead code removed; no migration) and add `make test-pg` to the "Testing" command list and Essential commands; mirror in `CLAUDE.md` only if it carries its own phase table (it imports AGENTS.md). `specs/README.md`: add 170 to the index. · `AGENTS.md`, `specs/README.md`
- [x] **T044** [JR] [DOCS] `docs/cognitive-architecture.md` (executive function section): replace "closed" language with the verified state after 170 (drift now fires; confirmation path is Phase 171; double-booking is Phase 173) and link `specs/arch/executive-function.md`. `specs/arch/executive-function.md`: mark F1, F3, F9, F13 "fixed in Phase 170" in §4 and update the phase table row 170 to Implemented once merged. `specs/arch/ze-doctrine.md`: no change. · `docs/cognitive-architecture.md`, `specs/arch/executive-function.md`
- [x] **T045** [ENG] [DOCS] Coverage check: run `git diff main...HEAD --name-only` and confirm each public doc listed above that the diff made stale has been edited; list any file that mentions `drift`, `stuck`, `priority/snapshot`, `SurfacingGate`, `LearningContext`, `worldstate.push`, `correlation.push` (`rtk proxy grep -rniE "..." docs README.md core/*/*/README.md`) and was not touched, with a reason. Set `spec.md` Status to Implemented and the `.spec-context.json` through the companion `write-context.py` hooks (never hand-edit checkboxes). · none

---

## Dependencies and parallelism

- T002, T003 parallel; T004 before T005; T005 before T006 and every `pg` test (T007, T011, T024, T034, T035).
- Phases 2, 3 are independent after Phase 1. Phase 4 depends on Phase 2 only for `record_corroboration` (T009). Phase 5 and 6 are independent of 4, except T033A (deleting `inline_candidates`) must come after T023 (same file).
- Docs T037 to T044 can start after their code tasks; T045 last.

## Implementation strategy

MVP is Phase 1 + 2 + 3 (the harness, the drift fix, the stuck-goal fix): they restore two dead monitors. Phase 4 follows because it changes four packages. Phases 5 and 6 are independent cleanups. Each phase ends at a green checkpoint so a reviewer can review per phase.

---

## Lanes

Parallel lanes never share files. Shared files belong to the ENG lane. Juniors report to the ENG lead; the Floor Reviewer reviews per phase; the ENG lead integrates, runs the full gates (T036) and asks Tally for the end-to-end check (`make test-pg` plus the two acceptance runs).

### Lane ENG (Claude Sonnet, lane lead)

Tasks: T001, T004, T005, T006, T007 to T016, T018 to T021, T023, T024, T033A, T034, T035, T036, T045.

Owns:
- `apps/ze-api/tests/pg/**`, `apps/ze-api/tests/test_pg_harness_skip.py`
- `core/cognition/ze-worldstate/ze_worldstate/{store,drift,extraction,admission,inflow,types,surfacing,rest}.py` and `jobs/drift_sweep.py`, plus every test under `core/cognition/ze-worldstate/tests/` except `test_bootstrap.py`
- `core/automation/ze-automation/ze_automation/goals/postgres.py` and `core/automation/ze-automation/tests/proactive_jobs/test_stuck_goals.py`
- `core/cognition/ze-memory/ze_memory/{store,retriever}.py` and the `write_episode` test (T014)
- `core/engine/ze-core/ze_core/orchestration/nodes/memory.py` and its node test

Order: T001, then T004, T005, T006 (harness) before any `pg` test. Then Phase 2 and Phase 3 (independent). Phase 4 after T009 (needs `record_corroboration`); T019 and T020 first because JR-A's T022 waits for the new signatures. T033A after T023. T034, T035 after every JR lane has landed. T036 and T045 last.

### Lane JR-A (OpenCode flash): harness glue, priority REST and web, plugin inflows

Tasks: T002, T003 (first, they unblock ENG's T004), T025, T026, T027, T028, then T017 and T022 once ENG has landed T020.

Owns:
- `apps/ze-api/pyproject.toml`, `Makefile`
- `core/arbitration/ze-priority/ze_priority/{types,rest}.py`, `core/arbitration/ze-priority/tests/test_rest.py`
- `apps/ze-api/ze_api/api/{schemas.py,routes/priority.py}`, `apps/ze-api/tests/api/test_priority_routes.py`
- `packages/ze-client/src/generated/**`, `apps/ze-web/src/entities/priority-item/**`, `apps/ze-web/src/widgets/priority-snapshot/**`
- `plugins/ze-messenger/ze_messenger/inbound/processor.py` and `plugins/ze-messenger/tests/test_inbound_processor.py`; `core/ops/ze-ingestion/ze_ingestion/sink.py` and `core/ops/ze-ingestion/tests/test_sink.py`; `plugins/ze-calendar/ze_calendar/jobs/calendar_reminder.py` and its test

Order: T002 and T003 immediately; T025 to T028 in order; T017/T022 wait for ENG's message "T020 landed".

### Lane JR-B (OpenCode flash): switches, config, dead code

Tasks: T029, T030, T031, T032, T033.

Owns:
- `core/cognition/ze-worldstate/ze_worldstate/bootstrap.py` and new `core/cognition/ze-worldstate/tests/test_bootstrap.py`
- `core/arbitration/ze-priority/ze_priority/arbitration.py`, `ze_priority/learning_context.py` (delete), `tests/test_arbitration.py`, `tests/test_learning_context.py` (delete)
- `apps/ze-api/ze_api/compose.py`, `apps/ze-api/config/config.yaml`, `apps/ze-api/tests/test_shipped_config_keys.py`
- `core/cognition/ze-correlation/ze_correlation/push.py` and its test
- `core/cognition/ze-memory/ze_memory/surfacing.py` (delete) and `core/cognition/ze-memory/tests/test_salience.py`

Order: independent of ENG and JR-A. T029 before T030 to T032. T033 last in the lane.

### Docs (Docs Steward or JR-B after T033)

Tasks: T037 to T044 (all `[JR]`).

Owns: `docs/**`, `README.md`, package READMEs, `AGENTS.md`, `specs/README.md`, `specs/arch/executive-function.md`, `docs/cognitive-architecture.md`. No code files. Start each doc task after its code task lands (T037 after T006; T038 after T010 and T031; T039 after T032; T040 after T013; T041 and T042 after Phases 4 to 6; T043 and T044 last). ENG's T045 coverage check follows.

### Cross-lane files

If a JR lane needs a change in a file owned by another lane, it asks the ENG lead; it does not edit it. Known touch points: `ze_priority/arbitration.py` (JR-B) calls `LoopSurfacer.eligible_candidates` (ENG file) with `thresholds=` and `inline_cooldown_hours=`, which already exist on that method; no ENG edit is needed.
