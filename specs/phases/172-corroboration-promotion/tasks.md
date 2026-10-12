# Tasks: Corroboration Promotion

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Unit tests use fakes (`AsyncMock` pools, call-counting fake `SystemOneClient`, fake embedder and graph store as in `tests/test_admission.py`). Real-row tests live in 170's harness `apps/ze-api/tests/pg/` (marker `pg`, `make test-pg`). Default suites never call OpenRouter or System One.

**Lanes**: `[ENG]` = Claude Sonnet lane lead (System One and calibration, store and SQL, concurrency, cross-package wiring, gates). `[JR]` = OpenCode flash junior (exact files and behavior given). See the Lanes section at the end.

**Tags**: `[BE]` backend Python · `[WEB]` ze-web and generated client · `[PLATFORM]` config, Makefile, migration · `[DOCS]` docs, READMEs, specs.

**Normative references**: judgment, independence, effects: [contracts/corroboration-judgment.md](./contracts/corroboration-judgment.md). Source keys, REST, web: [contracts/sources-and-rest.md](./contracts/sources-and-rest.md). Table and types: [data-model.md](./data-model.md). Constants and rationale: [research.md](./research.md) R3 to R9.

**Rules for the implementer**
- Phases 170 and 171 must be on `main` before T002. 170 owns `record_corroboration`, the drift predicate, `_existence_checkers` and declared-path dedup; 169 owns `transition`/`stamp_declared`; 171 owns `review.confirm_loop`, the loops agent tools and the `/loops` page. Do not edit those functions.
- Before changing any signature in plan.md "Blast radius", run `graphify affected "<Symbol>" --depth 2` and update every caller in the same change. graphify misses opaque callables; also `rtk proxy grep -rn "loop_extractor" --include='*.py' .`.
- No `print()`; `get_logger(__name__)`. No bare `Exception`/`ValueError` in domain code. Never `json.loads` a model reply (System One returns typed answers; there is none here).
- The held-out file (T030) is written and committed **before** any live run and never read while tuning (FR-020).
- Shared worktree: `git add <your paths>`; `git commit -m ... -- <paths>`. Never `git add -A`, `git stash`, or reset files you do not own. Commit only when the ENG lead or Maestro asks.
- If a step disagrees with the code you find, stop and report the difference to the ENG lead; do not redesign.

**Ordering**: Phases run in order unless the Lanes section says otherwise. `[P]` tasks touch different files and may run together.

---

## Phase 0: Gate  [ENG]

- [ ] T001 [ENG] [BE] Confirm 170 and 171 are on `main` and rebase `172-corroboration-promotion` onto it. Read both diffs (`git log -p main -- core/cognition/ze-worldstate apps/ze-web/src`). Record in your report: (a) the exact name and signature of 170's declared-path match and of `_existence_checkers`; (b) the extractor callable signature after 170 (`evidence` argument); (c) the file and component that render a loop row on 171's `/loops` page. Run `graphify update .`, then `graphify affected` on `propose_loop_candidates`, `LoopInflow`, `make_loop_extractor_from_parts`, `PostgresLoopStore`, `LoopListItem`, `LoopDetail`. If any differ from plan.md, stop and report to the Spec Architect (or Maestro).

## Phase 1: Setup  [T003 is JR; T002 and T004 are ENG]

- [ ] T002 [P] [ENG] [PLATFORM] In `apps/ze-api/config/config.yaml` under `system_one.surfaces`, after `loop_gate`, add `corroboration:` with `enabled: false`, `corroborate_hold: null`, `promote_hold: null` and the comment `# Phase 172: same-concern Noul for suspected-loop corroboration. Off with null bars until make calibrate-corroboration gives ENABLE on the held-out set.`
- [ ] T003 [P] [JR] [PLATFORM] In `Makefile` add target `calibrate-corroboration:` running `uv run python eval/calibration/corroboration.py`, add it to `.PHONY`, and add the help line `calibrate-corroboration  LIVE System One + E5 baseline over eval/calibration/corroboration.jsonl; costs credits` beside `calibrate-loop-gate`.
- [ ] T004 [ENG] [PLATFORM] Create `core/cognition/ze-worldstate/ze_worldstate/migrations/versions/zw003_open_loop_sources.py` (`revision = "zw003"`, `down_revision = "zw002"`), raw SQL per data-model.md: the table, `UNIQUE (loop_id, inflow, source_ref)`, `ON DELETE CASCADE`, `CHECK (role IN ('origin','corroboration'))`, both indexes; downgrade drops the table. Follow `zw002_drift_columns.py` style.

## Phase 2: Foundational  [ENG]

**Purpose**: types, store methods, the pure judge and the pure independence rule. Every story needs them.

- [ ] T005 [ENG] [BE] `core/cognition/ze-worldstate/ze_worldstate/types.py`: add `SourceKey` (frozen), `LoopSourceRole` (StrEnum), `LoopSource` per data-model.md; add `source: SourceKey | None = None` to `LoopAdmission`.
- [ ] T006 [ENG] [BE] Fail-first: in `core/cognition/ze-worldstate/tests/test_store.py` add tests with an `AsyncMock` pool for `add_source` (SQL contains `ON CONFLICT (loop_id, inflow, source_ref) DO NOTHING RETURNING`; returns `None` when `fetchrow` returns `None`), `list_sources` (ordered by `created_at`), `list_sources_for` (one `fetch` with `ANY($1)`, grouped by loop id), `promote` (SQL guarded `WHERE id = $1 AND state = 'suspected'`, uses `GREATEST(confidence, $2)` and `make_interval(days => $3)`; returns `None` when no row), `mark_source_promoted`.
- [ ] T007 [ENG] [BE] `core/cognition/ze-worldstate/ze_worldstate/store.py`: add the five methods to the `LoopStore` Protocol and `PostgresLoopStore` (research R6, R7), plus `_source_from_row`. Log `open_loop_promoted` (loop id) on a successful promote. T006 passes.
- [ ] T008 [ENG] [BE] Real rows: new `apps/ze-api/tests/pg/test_loop_sources_pg.py` (`pytestmark = pytest.mark.pg`): migration applied; a duplicate `(loop_id, inflow, source_ref)` insert returns `None`; deleting the loop deletes its sources; `promote` on a suspected loop sets `active`, `confidence = max(old, 0.7)`, `drift_deadline - confirmed_at = 7 days`, and a second `promote` returns `None`; `promote` on a dropped loop returns `None`; a promoted loop whose deadline is moved one day into the past is returned by `list_drift_candidates()` (170 predicate); `list_sources_for` groups correctly.
- [ ] T009 [P] [ENG] [BE] Fail-first: new `core/cognition/ze-worldstate/tests/test_corroboration_judge.py`: every row of the decision table (contract), an answer of exactly each bar counts as at-or-above, config parsing (missing block, null, NaN, bool, out of range, `corroborate_hold > promote_hold` → uncalibrated), state shape (`loop` capped at 200, `source`, the 168 per-inflow key and cap), question id `same_concern` and type `noul`.
- [ ] T010 [ENG] [BE] New `core/cognition/ze-worldstate/ze_worldstate/corroboration_judge.py`: `Q_SAME`, the question (research R4 wording), `build_state(loop_title, text, inflow)` reusing `loop_judge.build_state`, `CorroborationSurfaceConfig`, `corroboration_surface_config(settings)` (copy the tolerant reader from `loop_judge.loop_gate_surface_config`), `CorroborationDecision`, pure `decide(result, cfg)`. T009 passes.
- [ ] T011 [P] [ENG] [BE] Fail-first: new `core/cognition/ze-worldstate/tests/test_corroboration.py`, section independence: one test per clause of `is_independent` (`no_key` for `None` and empty ref, `same_source`, `same_evidence`, `dropped_source`, `independent`), and a loop with no origin row checked against corroboration rows and evidence only.
- [ ] T012 [ENG] [BE] New `core/cognition/ze-worldstate/ze_worldstate/corroboration.py`: constants `CORROBORATION_WEIGHT = 0.5`, `CORROBORATED_CAP = 0.6`, `PROMOTED_CONFIDENCE = 0.7`, window from `drift.DEFAULT_DRIFT_WINDOW_DAYS`; pure `is_independent(...) -> tuple[bool, str]`; pure `corroborated_confidence(c, s)`. T011 passes.

**Checkpoint**: `make test-worldstate` green; `make test-pg` green.

---

## Phase 3: User Story 1 - An independent mention promotes a suspected loop (P1)  [ENG]

**Goal**: corroborate and promote effects wired into both suspected match paths, origin rows on create.

**Independent Test**: spec US1; fake client answering 0.93 on an email commit against a suspected loop with a conversation origin row.

- [ ] T013 [ENG] [US1] [BE] Fail-first in `tests/test_corroboration.py`, section effects: corroborate at s = 0.8 from c = 0.3 gives 0.58 via `set_confidence` and one `add_source(role=corroboration, promoted=False, same_concern=0.8, model, latency_ms)`; a second corroborate is capped at 0.6; promote calls `promote(id, confidence=0.7, window_days=7)` then `mark_source_promoted`; `promote` returning `None` leaves `promoted` false; `add_source` returning `None` stops before confidence or promote (log `reason=duplicate_source`); an exception anywhere yields the 170 behavior and logs `corroboration_failed`; every judged match logs `corroboration_judgment` with `loop_id`, `inflow`, `outcome`, `reason`, `score`, `latency_ms`, `skip_reason`.
- [ ] T014 [ENG] [US1] [BE] In `corroboration.py` implement `async corroborate_match(*, existing, text, inflow, key, evidence_refs, entity_ids, dropped, loop_store, system_one_client, settings, link) -> None` following the contract flow exactly. `link` is the existing 170 link callable, so the non-counted branches reuse it unchanged. Independence runs before linking. T013 passes.
- [ ] T015 [ENG] [US1] [BE] `ze_worldstate/extraction.py`: add `source: SourceKey | None = None`, `system_one_client: Any = None`, `settings: Any = None` to `propose_loop_candidates`, `_commit_admitted`, `_create_suspected_loop` and the 170 declared path. After every successful create (suspected and declared) with a key, `add_source(role=origin, key, evidence=first evidence ref or None)`. In `_create_suspected_loop`'s matched branch and in the declared-path match, when `existing.state == suspected` call `corroborate_match` (passing the `dismissed` loop already looked up; add the same dropped lookup on the declared path); for other states keep 170 exactly.
- [ ] T016 [ENG] [US1] [BE] `ze_worldstate/admission.py`: `admit(configurable, *, prompt)` stops deleting `configurable` and sets `admission.source = SourceKey("conversation", thread_id)` when `configurable.get("thread_id")` is truthy; `extract(text, provenance, evidence=(), source_ref=None)` builds the key; `_commit_for` passes `source`, `self._system_one`, `self._settings`. No change to `inflow.py` arguments.
- [ ] T017 [ENG] [US1] [BE] Tests in `tests/test_extraction.py` and `tests/test_admission.py`: end-to-end promote (email commit, fake client 0.93, loop becomes active at 0.7, two source rows); corroborate band stays suspected; origin row written for each create path with a key and none without; `admit` puts the thread key on the admission; Story 1 scenario 3 (third source promotes a 0.6 loop).

## Phase 4: User Story 2 - The same source cannot corroborate itself (P1)  [ENG for T018; JR for T019-T021]

**Independent Test**: spec US2; call-counting fake records zero System One calls for every non-independent case.

- [ ] T018 [ENG] [US2] [BE] Tests in `tests/test_extraction.py`: same email thread, same chat thread, already-linked evidence, no key → zero client calls, confidence and sources unchanged, 170 link done, `corroboration_skipped` logged with the reason; a second chat thread → judged.
- [ ] T019 [P] [JR] [US2] [BE] `plugins/ze-messenger/ze_messenger/inbound/processor.py` L157: pass `source_ref=msg.thread_id or msg.message_id` to `self.loop_extractor(...)` (keep 170's evidence argument); widen the attribute's `Callable` annotation to `Callable[..., Awaitable[None]]`. Test in `plugins/ze-messenger/tests/test_inbound_processor.py`: a recording extractor receives the thread id, and the message id when `thread_id` is empty.
- [ ] T020 [P] [JR] [US2] [BE] `plugins/ze-calendar/ze_calendar/jobs/calendar_reminder.py` L61: pass `source_ref=signal.external_ref`; widen the annotation as in T019. Test in `plugins/ze-calendar/tests/jobs/test_reminders.py`: the recording extractor receives the external ref.
- [ ] T021 [P] [JR] [US2] [BE] `core/ops/ze-ingestion/ze_ingestion/sink.py` L67: pass `source_ref=ingestion_id`; widen the annotation. Test in `core/ops/ze-ingestion/tests/test_sink.py`: the recording extractor receives the ingestion id.

## Phase 5: User Story 3 - Same person, different matter (P1)  [ENG]

- [ ] T022 [ENG] [US3] [BE] Test in `tests/test_extraction.py`: a suspected loop "Reply to Ana about the budget" linked to entity Ana is the only entity-linked loop; an independent email titled "RSVP to Ana's party" matches it through the single-entity shortcut; fake answer 0.08 → no source row, confidence 0.3, state suspected, 170 link done, `corroboration_judgment outcome=not_same`. No production change expected; if it fails, fix `corroborate_match`.

## Phase 6: User Story 4 - Dropping is respected (P1)  [ENG]

- [ ] T023 [ENG] [US4] [BE] Tests in `tests/test_extraction.py` and `tests/test_review.py`: a dropped loop with source `(email, G1)` and a new suspected loop matching it; a text on `G1` → zero calls, nothing changes (`dropped_source`); a text on `G2` → judged. `review.drop_loop` on a promoted loop never calls a source delete (assert on the fake store). `closed`/`dropped` matches are never judged.

## Phase 7: User Story 5 - Off, unsure and failing paths change nothing (P1)  [ENG]

- [ ] T024 [ENG] [US5] [BE] Tests in `tests/test_corroboration.py` and `tests/test_extraction.py`: surface off → zero calls and the 170 result; enabled with a null bar or with `corroborate_hold > promote_hold` → zero calls and one warning; client skip, exception and invalid answer → 170 result with the skip reason logged; origin rows still written with the surface off. Run 170's existing `test_extraction.py` and `test_admission.py` cases unchanged and green (SC-005).

## Phase 8: User Story 6 - The user can see why a loop is tracked (P2)  [JR]

**Independent Test**: spec US6.

- [ ] T025 [JR] [US6] [BE] `core/cognition/ze-worldstate/ze_worldstate/rest.py`: `list_loops` calls `loop_store.list_sources_for([ids])` once and adds `promoted` (any corroboration row with `promoted`) and `source_inflows` (distinct inflows in first-seen order) to each item; `get_loop` adds `sources` (role, inflow, evidence_kind, same_concern, promoted, created_at ISO) in time order. Test in `core/cognition/ze-worldstate/tests/test_rest.py` (create if missing) with a fake store.
- [ ] T026 [JR] [US6] [BE] `apps/ze-api/ze_api/api/schemas.py`: add `promoted: bool` and `source_inflows: list[str]` to `LoopListItem`, new `LoopSourceItem`, `sources: list[LoopSourceItem]` on `LoopDetail` (data-model.md). `apps/ze-api/ze_api/api/routes/loops.py`: update `summary`/`description` of list and detail to mention promotion and sources. Extend `apps/ze-api/tests/api/test_loops_route.py`: a promoted loop returns `promoted: true`, two `source_inflows`, and two `sources`.
- [ ] T027 [JR] [US6] [WEB] Run `make codegen` and commit `packages/ze-client/src/generated/*`.
- [ ] T028 [JR] [US6] [WEB] `apps/ze-web/src/entities/loop/lib/format.ts` (new): `sourceLabel(inflow)` (conversation → "chat", email → "email", calendar → "calendar", ingestion → "a document", anything else → the raw string) and `promotedLine(item)` returning `"Promoted · seen in: chat, email"` or `null`; export from `entities/loop/index.ts`; vitest `format.test.ts`. Render `promotedLine` as a muted line in the loop row component named in T001(c), with a vitest render test. Run `make test-web` and `make typecheck-web`.

## Phase 9: User Story 7 - Calibration decides whether the surface turns on (P2)  [ENG; T032 is JR]

- [ ] T029 [ENG] [US7] [BE] Write `eval/calibration/corroboration_holdout.jsonl` first: at least 20 rows per language (EN, PT), schema in data-model.md, every inflow at least 2 rows per language, at least a third hard negatives (`same_entity_other`, `same_topic_other`), some `cross_lingual`. Commit it alone (`Spec 172: corroboration held-out set`) before any script runs live.
- [ ] T030 [ENG] [US7] [BE] Write `eval/calibration/corroboration.jsonl` (tuned): at least 40 rows per language, every inflow at least 4 rows per language, same kind mix; no text shared with the held-out file.
- [ ] T031 [ENG] [US7] [BE] New `eval/calibration/corroboration.py`, modeled on `eval/calibration/loop_gate.py`: `--check-sets` (offline, FR-018 checks, exit non-zero with counts); default `--set tuned` (live System One via the production client with `corroboration_judge.build_state`/question; E5 baseline `cosine(new_title, loop_title) >= 0.75` using the production embedder; per language and inflow: corroborate precision and recall, false promotions, reliability table, grid over `corroborate_hold`/`promote_hold` 0.50–0.95 with `C <= P`, suggested bars per research R9; never reads the held-out file); `--set holdout --bars C,P` (the single verdict per language: `ENABLE` or `KEEP OFF` and the failing clause, FR-020).
- [ ] T032 [P] [JR] [US7] [BE] New `apps/ze-api/tests/calibration/test_corroboration_calibration.py` (pattern: `test_loop_gate_calibration.py` in the same folder): both files pass `--check-sets` logic imported from the script; no held-out `text` appears in the tuned file; the module's live path is never executed under pytest (no client constructed at import).
- [ ] T033 [ENG] [US7] [BE] Run `make calibrate-corroboration` (tuned). Iterate wording and bars on the tuned set only. Then run the held-out verdict once with frozen wording and bars. On `ENABLE` for both EN and PT: set the bars and `enabled: true` in `config.yaml` with a comment recording date, row counts, verdict and E5 baseline numbers (as the `loop_gate` comment does). On `KEEP OFF`: leave the surface off and record the failing clause in the same comment. Either way write a "Tuning notes" section at the end of this phase's `research.md` (run date, model id, row counts, grid summary, chosen bars, verdict per language, E5 baseline numbers). Any change after the held-out run requires a new held-out file before another verdict.

## Phase 10: Polish, docs and gates

- [ ] T034 [P] [JR] [DOCS] `core/cognition/ze-worldstate/README.md`: corroboration section (independence rule table, `same_concern` Noul, two bars, effects and constants, `open_loop_sources`, fail-open), module list adds `corroboration.py`, `corroboration_judge.py`, migration `zw003`.
- [ ] T035 [P] [JR] [DOCS] `docs/system-one.md`: add the corroboration surface (question, state, bars, decision table, ships off, calibration command and acceptance rule); `docs/configuration.md`: the `system_one.surfaces.corroboration` block; `docs/ingestion.md`: ingestion passes its id as the loop source key. Follow the `doc-style` skill.
- [ ] T036 [P] [JR] [DOCS] `docs/cognitive-architecture.md` and `docs/architecture.md`: open-loop lifecycle gains "suspected → active by independent corroboration (System One same-concern bar)" and the source provenance table; `README.md` "Open loops" paragraph: one sentence on corroboration promotion. Update `docs/diagrams/root/open-loops.html`/`.svg` with a corroborate/promote edge using the `diagram-design` skill. Follow `doc-style`.
- [ ] T037 [P] [JR] [DOCS] `specs/arch/system-one-models.md`: add a "Specified now" row for corroboration (Noul `same_concern`, E5 shortlist via `find_matching_loop`, E5 baseline, phase 172), sequencing item, Appendix A row, Appendix B file index rows (`corroboration_judge.py`, `corroboration.py`). After T033, add a "172 tuning notes" paragraph copied from the "Tuning notes" section of this phase's `research.md`.
- [ ] T038 [P] [JR] [DOCS] `AGENTS.md`: phase table row 172; ze-worldstate layout lines for `corroboration.py`, `corroboration_judge.py` and `migrations/` (zw001–zw003); migration ownership row `ze-worldstate | zw | open_loops, open_loop_sources (zw003)`; essential commands line for `make calibrate-corroboration`. `specs/README.md`: index row 172. If `specs/arch/executive-function.md` is on `main`, mark row 172 in §7 as Implemented with a link to this spec.
- [ ] T039 [ENG] [DOCS] Set `spec.md` **Status** to `Implemented` and check off tasks via `python3 .specify/extensions/companion/scripts/write-context.py --append ...` then `--materialize` (never hand-edit checkboxes).
- [ ] T040 [ENG] Gates: `make test-worldstate test test-messenger test-calendar test-ingestion test-web typecheck-web lint` and `make test-pg`; ask Tally for the end-to-end check (quickstart "Manual check" with the surface on in a local config copy). Fix or report failures with output.
- [ ] T041 [ENG] [DOCS] Docs coverage check: `git diff --stat main...HEAD` and confirm each changed public surface (config key, Make target, REST fields, migration, ze-worldstate modules) appears in at least one of the docs from T034–T038; list any gap and fix it before review.

---

## Dependencies & Execution Order

- T001 → everything. T002, T003 parallel with T004.
- Phase 2 (T005–T012) before any story. T006→T007→T008; T009→T010; T011→T012.
- US1 (T013–T017) before US2–US5 (they test the integrated path). T019–T021 need T016 (the `source_ref` keyword exists).
- US3, US4, US5 (T022–T024) are tests on the US1 code; run in any order after T017.
- US6: T025 needs T007; T026 needs T025; T027 needs T026; T028 needs T027.
- US7: T029 before T030 before any live run; T031 needs T010; T032 needs T031; T033 needs T031 and US1–US5 green.
- Docs T034–T038 after the code they describe lands; T039–T041 last.

### Parallel examples

- After T012: ENG works T013–T017 while JR-A does T003 (if not done) and waits for T016 to start T019–T021.
- After T007: JR-B starts T025–T028 while ENG continues US1.
- T034–T038 in parallel (different files).

## Implementation Strategy

MVP = Phase 2 + US1 + US5 (promotion path and the fail-open guarantee), with the surface off. Then US2–US4 tests, US6 visibility, and US7 calibration, which alone decides whether the surface ships on.

---

## Lanes

Parallel lanes never share files. Shared files belong to the ENG lane. Juniors report to the ENG lead; the Floor Reviewer reviews per phase; the ENG lead integrates, runs the gates (T040), asks Tally for the end-to-end check, sets the floor to review and reports to the Maestro.

### Lane ENG (Claude Sonnet, lane lead)

Tasks: T001, T002, T004–T018, T022–T024, T029–T031, T033, T039–T041.

Owns:
- `core/cognition/ze-worldstate/ze_worldstate/{types,store,extraction,admission,corroboration,corroboration_judge}.py` and `migrations/versions/zw003_open_loop_sources.py`
- `core/cognition/ze-worldstate/tests/{test_store,test_extraction,test_admission,test_review,test_corroboration,test_corroboration_judge}.py`
- `apps/ze-api/tests/pg/test_loop_sources_pg.py`
- `eval/calibration/corroboration.py`, `corroboration.jsonl`, `corroboration_holdout.jsonl`
- `apps/ze-api/config/config.yaml` (T002, T033)
- `spec.md`, `tasks.md`, `research.md` of this phase

Order: T001; T004; Phase 2; US1; then US3–US5 tests; US7 (T029 → T030 → T031 → T033) can start after T010 and run beside the story tests; T039–T041 last after every JR lane has landed.

### Lane JR-A (OpenCode flash): setup and plugin inflows

Tasks: T003, then T019, T020, T021 after the ENG lead says "T016 landed", then T032 after "T031 landed".

Owns:
- `Makefile`
- `plugins/ze-messenger/ze_messenger/inbound/processor.py` and `plugins/ze-messenger/tests/test_inbound_processor.py`; `plugins/ze-calendar/ze_calendar/jobs/calendar_reminder.py` and `plugins/ze-calendar/tests/jobs/test_reminders.py`; `core/ops/ze-ingestion/ze_ingestion/sink.py` and `core/ops/ze-ingestion/tests/test_sink.py`
- `apps/ze-api/tests/calibration/test_corroboration_calibration.py`

### Lane JR-B (OpenCode flash): REST, client, web

Tasks: T025, T026, T027, T028 after the ENG lead says "T007 landed" (T028 also needs T001(c), the 171 row component).

Owns:
- `core/cognition/ze-worldstate/ze_worldstate/rest.py`, `core/cognition/ze-worldstate/tests/test_rest.py`
- `apps/ze-api/ze_api/api/schemas.py` (loop section only), `apps/ze-api/ze_api/api/routes/loops.py`, `apps/ze-api/tests/api/test_loops_route.py`
- `packages/ze-client/src/generated/**`
- `apps/ze-web/src/entities/loop/**` and the 171 loop row component

### Docs (Docs Steward, or JR-A/JR-B when their lanes are done)

Tasks: T034–T038 (all `[JR]`).

Owns: `core/cognition/ze-worldstate/README.md`, `docs/**`, `README.md`, `AGENTS.md`, `specs/README.md`, `specs/arch/system-one-models.md` (T037 after T033), `specs/arch/executive-function.md` (§7 row only). No code files. Start each after its code lands (T034 after T024; T035 and T037 after T033; T036 and T038 after T028). ENG's T041 follows.

### Cross-lane files

A JR lane that needs a change in another lane's file asks the ENG lead and does not edit it. Known touch points: JR-B's `rest.py` calls ENG's `list_sources_for` (T007); JR-A's inflow edits call ENG's `LoopInflow.extract(source_ref=...)` (T016) through the opaque callable; T037 reads ENG's tuning notes in `research.md`; it never edits `research.md`.
