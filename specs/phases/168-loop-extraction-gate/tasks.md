# Tasks: Loop Extraction Gate (System One)

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Required (constitution V, FR-014). Fail-first. Default suites never POST to OpenRouter. Use a fake `SystemOneClient` (async `evaluate(state, questions, *, max_attempts=None)` returning a canned `SystemOneResult`) and a call-counting fake `LLMClient`.

**Tags**: `[BE]` backend Python · `[PLATFORM]` config / Makefile / eval tooling / spec index · `[DOCS]` docs, specs, READMEs. No `[WEB]` task: judgment rows already render in the trace panel and no REST or WS shape changes.

**Normative references**: decision table, state shapes, writer: [contracts/loop-gate-judgment.md](./contracts/loop-gate-judgment.md). Node flow, `LoopAdmission`, wiring: [contracts/node-and-inflow.md](./contracts/node-and-inflow.md).

**Held-out rule**: `eval/calibration/loop_gate_holdout.jsonl` is already committed (f2758964). Never edit it, tune against it, or copy its text into the tuned set (FR-016). Run `graphify affected` on each symbol before changing its signature and update every caller in the same change.

**Ordering**: Phases run in order. `[P]` tasks touch different files and can run together.

---

## Phase 1: Setup

- [x] **T001** [P] [PLATFORM] Under `system_one.surfaces` add `loop_gate` with `enabled: false`, `loop_hold: null`, `explicit_hold: null`, `resolves_hold: null` and a one-line comment pointing at `make calibrate-loop-gate`. · `apps/ze-api/config/config.yaml`
- [x] **T002** [P] [PLATFORM] Add the `calibrate-loop-gate` Makefile target (`uv run python eval/calibration/loop_gate.py`), its help line and `.PHONY` entry, mirroring `calibrate-skills`. · `Makefile`
- [x] **T003** [P] [PLATFORM] Write the tuned set `eval/calibration/loop_gate.jsonl`: at least 40 rows per language (EN, PT), all four provenance text shapes (conversation prompt, email body, calendar `title. summary`, ingestion fact lines), with positives, negatives, hard negatives (marketing deadline, routine event, how-to question, article facts), explicit declarations (conversation only) and resolves rows. Schema per `data-model.md`. No text may equal a held-out text. · `eval/calibration/loop_gate.jsonl`

---

## Phase 2: Foundational (blocks every story)

**Purpose**: Config, questions, state builders, `decide()`, calibration shape tests. With the surface off this phase changes no behavior.

**Wave 1 — fail-first tests (different files):**

- [x] **T004** [P] [BE] Fail-first, `loop_gate_surface_config` and questions: missing or invalid block → disabled; enabled with a null bar → `calibrated` false; bad bars (string, NaN, >1, bool) become `None` with a warning; three question ids exist, all `noul`, none with criteria. · `core/cognition/ze-worldstate/tests/test_loop_judge.py`
- [x] **T005** [P] [BE] Fail-first, state builders: each provenance produces its named key and `source`; each cap is enforced (email 20,000 chars → 1500, conversation 1000, calendar 600, ingestion 1500); no assistant text or extra keys; non-conversation requests omit `explicit_declaration`. · `core/cognition/ze-worldstate/tests/test_loop_judge.py`
- [x] **T006** [P] [BE] Fail-first, `decide()` table (contract rows 1 to 7): skip, missing or invalid Noul, null bar → `fallback`; resolves wins over concern and leaves concern not consumed; below `loop_hold` → `hold`; explicit only on conversation; at-the-bar is positive; consumed sets per row. · `core/cognition/ze-worldstate/tests/test_loop_judge.py`
- [x] **T007** [P] [PLATFORM] Fail-first, calibration dataset shape: tuned set has ≥ 40 rows per language, held-out has ≥ 20 per language, both cover all four provenances with positives and negatives, schema invariants hold (`gold_explicit` implies conversation and loop; `gold_resolves` implies not loop), no held-out text appears in the tuned set. · `apps/ze-api/tests/calibration/test_loop_gate_calibration.py`

**Wave 2 — implementation:**

- [x] **T008** [BE] Create `loop_judge.py`: `LoopGateSurfaceConfig`, `loop_gate_surface_config(settings)`, the three Noul questions (wording per research R10), cap constants, per-provenance `build_state`, `LoopGateDecision`, pure `decide()`. Local bar validator copy (plan Complexity Tracking). Makes T004 to T006 pass. · `core/cognition/ze-worldstate/ze_worldstate/loop_judge.py`

**Checkpoint**: `make test-worldstate` passes; nothing imports the new module in production yet.

---

## Phase 3: User Story 4 — Fallback keeps 109 behavior (P1)

**Goal**: The Haiku gate is intact as the fallback and every 109/110 test passes unchanged in outcome. Land this before the System One path so regressions show first.

- [x] **T009** [US4] [BE] Fail-first: with the surface off, with `calibrated` false, with a skipping client and with a malformed-answer client, `propose_loop_candidates` produces exactly the 109 results for the existing `test_extraction.py` fixtures, makes no System One request when off or uncalibrated, and logs the uncalibrated warning once per call. · `core/cognition/ze-worldstate/tests/test_admission.py`
- [x] **T010** [US4] [BE] Run `graphify affected "propose_loop_candidates" --depth 2` and `"make_loop_extractor_from_parts"`; record callers in the commit message. Extend `propose_loop_candidates(..., admission: LoopAdmission | None = None)`; `None` runs the System One gate when configured, else the existing Haiku gate. Keep `_run_extraction_gate` and its prompt byte-for-byte. · `core/cognition/ze-worldstate/ze_worldstate/extraction.py`

---

## Phase 4: User Story 1 — Ordinary turns cost no Haiku call (P1)

**Goal**: Trivial and negative turns make no Haiku call and create no loop; the trace shows the decider rows.

- [x] **T011** [P] [US1] [BE] Fail-first, gate: a negative Noul makes zero LLM calls and no `loop_store.create`; a trivial conversation turn makes no System One request and no rows; a positive answer returns an admission whose `commit` is not `None`. · `core/cognition/ze-worldstate/tests/test_admission.py`
- [x] **T012** [P] [US1] [BE] Fail-first, node: with a fake `loop_admission` the node appends loop rows after the 163 rows without replacing them; `consumed` only on deciders; skip rows carry the reason; no loop gate on `is_eval` or `is_retry`; an exception in `loop_admission` does not fail the turn; the 163 and loop calls run concurrently. · `core/engine/ze-core/tests/orchestration/test_loop_admission_node.py`
- [x] **T013** [US1] [BE] Create `admission.py`: `LoopAdmission`, `LoopInflow.admit()` (trivial skip, one `evaluate(..., max_attempts=1)`, `decide`, structured warning on uncalibrated, fail-open on any exception). · `core/cognition/ze-worldstate/ze_worldstate/admission.py`
- [x] **T014** [US1] [BE] In `write_memory`, run `fact_extractor` and `loop_admission` with `asyncio.gather` (per-call exception containment), merge both row sets into one trace replace, `fire_and_forget(admission.commit())`. Duck-type the admission; no `ze_worldstate` import. · `core/engine/ze-core/ze_core/orchestration/nodes/memory.py`
- [x] **T015** [US1] [BE] In `ZeContainer._build_config` add `"loop_admission"`, remove `conversation_memory_hook` from `memory_hooks` (keep plugin hooks), and delete `conversation_memory_hook` from `inflow.py`. Update `test_retry_mode.py` only if it referenced the removed hook. · `apps/ze-api/ze_api/container.py`, `core/cognition/ze-worldstate/ze_worldstate/inflow.py`

---

## Phase 5: User Stories 2 and 3 — Create and resolve with the writer (P1)

**Goal**: Created loops equal the 109 results; "it's done" still closes the match.

- [x] **T016** [P] [US2] [BE] Fail-first, writer and create: suspected 0.3 with conversation provenance, declared active 0.9 `user_declared` with the written window and with the 7-day default, window ignored when not a positive whole number, empty title or writer failure creates nothing, dismissal and attach-to-existing rules unchanged. · `core/cognition/ze-worldstate/tests/test_admission.py`
- [x] **T017** [P] [US3] [BE] Fail-first, resolve: a resolves answer closes the matching loop; no match closes and creates nothing; resolves wins when both Nouls are positive. · `core/cognition/ze-worldstate/tests/test_admission.py`
- [x] **T018** [US2] [BE] Add the Haiku title writer (narrow prompt, `{"title", "implied_window_days"?}`, creates-only window, validation) and the commit paths in `extraction.py` consuming a `LoopAdmission`; reuse `_create_declared_loop`, `find_matching_loop`, `submit_and_detect_collisions` unchanged. · `core/cognition/ze-worldstate/ze_worldstate/extraction.py`, `admission.py`

---

## Phase 6: User Story 5 — Other inflows, log only (P1)

- [x] **T019** [P] [US5] [BE] Fail-first: the three extractors built through the factories judge with their own capped shape; a negative makes no Haiku call; a positive creates `suspected` with the right provenance; none ever creates `active`; `explicit_declaration` is absent from their requests; each logs `loop_gate_judgment`; a missing client falls back. · `core/cognition/ze-worldstate/tests/test_admission.py`
- [x] **T020** [US5] [BE] Add `system_one_client` and `settings` to `make_loop_extractor_from_parts` and `make_loop_extractor`, route them through `LoopInflow.extract`, and pass both at every site (`build_container` ingestion at container.py:596, `make_loop_extractor` at :833). Confirm `ze_seed._apply` and `app.py` lifespan need no change with `graphify affected`. · `core/cognition/ze-worldstate/ze_worldstate/inflow.py`, `apps/ze-api/ze_api/container.py`

---

## Phase 7: User Story 6 — Calibration with Haiku baseline (P2)

- [x] **T021** [US6] [PLATFORM] Write `eval/calibration/loop_gate.py`: `--check-sets` (offline, exits non-zero on shape violations, prints counts); live mode over the tuned and held-out sets with the production questions (option order irrelevant, Nouls only), and the production Haiku gate as baseline side by side. Report per language and per provenance: precision, recall, false creates, false resolve, false declared, explicit and resolves accuracy, a reliability table per Noul, a bar grid over the three bars, suggested bars from the tuned set only. Log agreement of the 163 `loop` speech-act with the gate on conversation rows. Default `--set tuned` never reads or prints held-out rows; the held-out verdict (`ENABLE` or `KEEP OFF` with the failing clause per language, FR-018) runs only with an explicit `--set holdout` and prints a warning that tuning after it voids the set (FR-016). Never collected by pytest. · `eval/calibration/loop_gate.py`
- [x] **T022** [US6] [PLATFORM] Run `--check-sets` and make T007 pass. Run `make calibrate-loop-gate` (default `--set tuned`) once on the tuned set to pick bars and wording. Do not read the held-out result until bars and wording are frozen; then run the held-out verdict once with `--set holdout`. If wording or bars change after that run, write a fresh held-out file (new name, committed before the next run) before the next verdict. Record in the plan's tuning note: baseline numbers (SC-004), chosen bars, verdict, failing clause if any.
- [x] **T023** [US6] [PLATFORM] If both languages return `ENABLE`: set `enabled: true` and the three bars in `config.yaml` with a dated comment (rows, precision, recall, false creates, baseline). Otherwise leave `enabled: false` with null bars and a comment recording the failing clause. · `apps/ze-api/config/config.yaml`

---

## Phase 8: Docs and index [DOCS]

**Rule**: docs are part of done. Public docs follow the `doc-style` skill.

- [ ] **T024** [P] [DOCS] ADR `specs/arch/system-one-models.md`: O4 row and an "O4 implementation notes (168)" paragraph (three Nouls, Haiku title writer returning the window, window moved to a later date-parser phase, conversation gate in `write_memory`, other inflows log only, off with null bars until calibrated); fix "windows in code"; add 168 to Sequencing and Appendix A (Loop extraction row) and Appendix B (`loop_judge.py`, `admission.py`); if any `specs/core/*.md` lists ze-worldstate files, add the two modules; fix the header line and the Fit analysis text that say 166 is off (config has skills enabled, calibrated 2026-10-12).
- [ ] **T025** [P] [DOCS] `AGENTS.md`: add the 168 phase row (leave 167, which lives on another floor); correct the 166 row ("ships on, calibrated 2026-10-12"); update the ze-worldstate layout comment (`extraction.py`, new `loop_judge.py`, `admission.py`).
- [ ] **T026** [P] [DOCS] `specs/README.md`: add the 168 row to the phase index.
- [ ] **T027** [P] [DOCS] `docs/system-one.md`: add the loop gate to the surfaces list, the three questions, the fallback, and the calibration command.
- [ ] **T028** [P] [DOCS] `docs/configuration.md`: document `system_one.surfaces.loop_gate` (keys, null bars, how to calibrate).
- [ ] **T029** [P] [DOCS] `docs/cognitive-architecture.md` and `docs/architecture.md`: update the open-loop extraction description (gate, title writer, conversation gate placement, other inflows).
- [ ] **T030** [P] [DOCS] `docs/ingestion.md`: the ingestion loop extraction now uses the gate and logs only.
- [ ] **T031** [P] [DOCS] `core/cognition/ze-worldstate/README.md` and root `README.md`: where they describe loop extraction, name the gate and the fallback.
- [ ] **T032** [P] [DOCS] `docs/diagrams/root/open-loops.html` and `.svg` (use the `diagram-design` skill): show gate then title writer then commit if the diagram draws extraction; re-export.
- [ ] **T033** [DOCS] Coverage check: run `git diff main...HEAD --stat`; every public doc whose subject changed (root `README.md`, each affected `docs/*.md`, package READMEs, the ADR, AGENTS, specs index) appears in the diff or has a recorded reason. List any gap and close it.

---

## Phase 9: Verify and close

- [x] **T034** [BE] `make test-worldstate`, `make test-core`, `make test`, `make lint` pass; default suites make no OpenRouter or System One call (FR-014). Run the companion after-implement step and set the spec status to Implemented only after T022 and T023.
- [x] **T035** [BE] Re-run `graphify update .`, then `graphify affected` on `propose_loop_candidates`, `make_loop_extractor_from_parts` and the removed `conversation_memory_hook`; confirm no stale caller remains. Run `graphify path "ze_worldstate" "ze_core"` to confirm the boundary: no import from ze-worldstate into ze-core or the reverse.

---

## Dependencies

T001 to T003 → T004 to T008 → T009, T010 → T011 to T015 → T016 to T018 → T019, T020 → T021 to T023 → T024 to T033 → T034, T035. T024 to T032 can start after T008 but their final wording waits for T022/T023.

## Coverage map (requirement → tasks)

| Requirement | Tasks |
|---|---|
| FR-001 batched Nouls, separate bars | T006, T008, T013 |
| FR-002 pure decision | T006, T008 |
| FR-003 title writer only | T016, T018 |
| FR-004 loop semantics unchanged | T009, T016, T017, T018 |
| FR-005 explicit only on conversation | T005, T006, T019 |
| FR-006 node placement, hook removed | T012, T014, T015 |
| FR-007 trivial skip | T011, T013 |
| FR-008 per-provenance capped state | T005, T008 |
| FR-009 log-only inflows | T019, T020 |
| FR-010 constructor injection at all sites | T020, T035 |
| FR-011 surface config | T001, T004, T008 |
| FR-012 fail open | T009, T012, T013 |
| FR-013 Haiku gate kept as fallback | T009, T010 |
| FR-014 no live calls in default suites | T034 |
| FR-015 datasets | T003, T007 |
| FR-016 held-out discipline | T007, T021, T022 |
| FR-017 calibration script | T002, T021 |
| FR-018 acceptance rule | T021, T022, T023 |
| FR-019 ADR + AGENTS | T024, T025 |
| SC-001..SC-007 | T011, T009, T022, T022, T012, T019, T034 |
