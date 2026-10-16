# Tasks: One Commitment Intake

Lanes: **[ENG-A]** memory + worldstate logic, **[ENG-B]** wiring + calibration tooling, **[JR]** mechanical or dataset work, **[WEB]** ze-web + client, **[DOCS]**. `[P]` = parallel-safe. Owned files are exclusive to the lane; shared files are marked **(181)**. Checkboxes are written by the companion script, not by hand.

## Phase 0: Held-out first (blocks all live runs)

- [x] T001 [ENG-B] Write `eval/calibration/commitment_intake_holdout.jsonl` (>= 30 rows per language, schema FR-019, every Choice label per language, hard negatives for each F4 row, mixed-act rows, `turn_created` variants). Commit it before any tuned row exists. Never edit after a run. Owns: that file.
- [ ] T002 [JR] [P] Write `eval/calibration/commitment_intake.jsonl` (tuned, >= 60 rows per language, same schema, no text from the held-out set). Owns: that file.
- [x] T003 [ENG-B] `eval/calibration/commitment_intake.py` skeleton with `--check-sets` only (row counts, labels present, hard negatives present, no held-out text in tuned set). Owns: `eval/calibration/commitment_intake.py`, `tests` for it under `core/cognition/ze-worldstate/tests/test_commitment_calibration_sets.py`.
- [ ] T004 [ENG-B] **Stop point:** ask the Maestro for the user's OK on live spend after T001-T003 are committed.

## Phase 1: Foundations

- [ ] T010 [ENG-A] `ze_memory/types.py`: shrink `SpeechAct` to `FACT, FORGET, INGEST, CLARIFY, NONE`; `extractor.py`: `admit_speech_act` unknown -> `NONE`, Haiku fallback prompt and `_admit_parsed` use the same set (FR-016, FR-017). Update the tests and fixtures that target removed labels (`test_extractor*.py`, `test_speech_act_gate.py`, `test_speech_act_judge.py`, `test_speech_act_system_one.py`, `test_speech_act_calibration_set.py`, `fixtures/speech_act_gold.py`, `ze-core/tests/memory/test_extractor.py`); keep a gold-fact test mapped to `decide_fact`. Owns: `core/cognition/ze-memory/ze_memory/{types.py,extractor.py}`, those memory tests, `packages/ze-sdk/ze_sdk/memory.py`.
- [x] T011 [ENG-A] Rename `speech_act_judge.py` to `fact_judge.py`: keep `family` and `biography` questions, `build_state`, add `decide_fact(choice, family, bio, cfg)` carrying the 163 persist/hold rules; delete the `speech_act` question, `SpeechActSurfaceConfig`, `speech_act_surface_config`, old `decide`. Owns: `ze_memory/fact_judge.py`, `ze_memory/__init__.py`.
- [ ] T012 [JR] Migration `zw004_loop_reminder_link.py` (nullable `reminder_id`), `OpenLoop.reminder_id`, `store.py` row mapping, `create`, new `LoopStore.link()` set-once, Protocol update. Owns: `ze_worldstate/{migrations/versions/zw004_loop_reminder_link.py,types.py,store.py}`.
- [x] T013 [ENG-A] [P] `ze_agents/nested_tools.py`: `TurnCreation` + `turn_creation(tool_calls)` (D-3). **(181)** shared file.
- [ ] T014 [JR] [P] Tests: `turn_creation` table (success, error payload, `success=False`, nested, missing id); `link()` real-Postgres test (`@pytest.mark.pg`); `SpeechAct` consumer test (every label read by a decision path). Owns: `core/contracts/ze-agents/tests/test_turn_creation.py`, `core/cognition/ze-worldstate/tests/pg/test_loop_link.py`, `core/cognition/ze-memory/tests/test_speech_act_labels.py`.

## Phase 2: US1, US3, US4, US5, US6: the decision

- [x] T020 [ENG-A] Re-read floor 181's diff on `ToolCall`/`call_tool`/`nodes/memory.py`; record in `research.md` whether `success` semantics changed.
- [x] T021 [ENG-A] `ze_worldstate/commitment_judge.py`: questions (criteria name-free, EN+PT examples, F4 cases), `build_state`, `CommitmentIntakeSurfaceConfig` + parser, `IntakeOutcome`, pure `decide()` per `contracts/commitment-judgment.md`. Owns that file.
- [x] T022 [ENG-A] Table tests for every row of the decision table, bar edge (== bar), malformed answers, `tracked`, `created` variants, goal/reminder not created, `waiting_on`, mixed. Owns: `core/cognition/ze-worldstate/tests/test_commitment_judge.py`.
- [x] T023 [ENG-A] `ze_worldstate/intake.py` `CommitmentIntake.admit()`: one request, outcome handling (fact via `write_fact_values`, loop via `LoopInflow` commit helpers, link via D-4, resolve), fallback delegation, never raises, trace rows. Edit `admission.py`: remove conversation `admit`, expose reusable `_commit_for`/`_finish` as needed. Owns: `ze_worldstate/{intake.py,admission.py}`.
- [x] T024 [ENG-A] Tests: single request counted (US7), trivial turn, skip/throw/invalid fallbacks run Haiku paths, `link` sets pointer once and never on terminal loops, no loop on reminder/goal turns (US1-US3), declared/suspected/resolve parity with 168 rows, 109 fallback parity. Owns: `core/cognition/ze-worldstate/tests/{test_intake.py,test_admission.py}` (update).
- [x] T025 [ENG-B] `ze_core/orchestration/nodes/memory.py`: replace the `gather` block with `commitment_intake` (fallback to `fact_extractor` when absent); `judgments_from_result` rows from the single result; keep `tracking_earned`. **(181)** shared file: minimal diff. Update `core/engine/ze-core/tests/orchestration/nodes/test_memory.py` and `test_loop_admission_node.py`.
- [ ] T026 [ENG-B] Wiring: `apps/ze-api/ze_api/container.py` builds `CommitmentIntake` and sets `configurable["commitment_intake"]`; `ze_core/container.py` keeps `_fact_extractor` fallback only; delete the `loop_admission` conversation key. Owns those two files.
- [x] T027 [ENG-B] `config.yaml`: delete `speech_act` block, add `commitment_intake` (enabled false, null bars) and update the header comment; keep `loop_gate`. Owns: `apps/ze-api/config/config.yaml`.

## Phase 3: US8 links on REST and web

- [ ] T030 [JR] REST: `reminder_id` and `goal_id` on list and detail in `ze_api/api/routes/loops.py` and `schemas.py`; TestClient tests. Owns those files and `apps/ze-api/tests/api/test_loops*.py`.
- [ ] T031 [WEB] `make codegen` (never hand-edit generated files), commit regenerated `packages/ze-client`.
- [ ] T032 [WEB] `entities/loop`: `lib/format.ts` helpers `linkChips(loop)`; `widgets/loop-review/ui/LoopReviewList.tsx`: "Has reminder" and "Linked goal" chips; vitest for both, both, neither. Owns: `apps/ze-web/src/entities/loop/**`, `apps/ze-web/src/widgets/loop-review/**`. Run `make test-web typecheck-web`.

## Phase 4: US7 calibration tooling

- [ ] T040 [ENG-B] `eval/calibration/commitment_intake_baseline.py`: frozen 163 questions + decide + `loop_judge.decide` replay (D-6). Owns that file.
- [ ] T041 [ENG-B] Finish `commitment_intake.py`: live run (tuned), report (FR-021), bar grid, reliability tables, `--set holdout --bars`, verdict per FR-022. Delete `eval/calibration/speech_act.{py,jsonl}`. Makefile: `calibrate-commitment-intake` replaces `calibrate-speech-act` (help text + .PHONY). Owns: Makefile calibrate lines, the eval files.
- [ ] T042 [ENG-B] Live tuned run -> choose bars (after T004 OK). Record in `research.md` tuning notes.
- [ ] T043 [ENG-B] Live held-out run once at frozen bars -> verdict. `ENABLE`: set bars and `enabled: true` in `config.yaml`; `KEEP OFF`: leave off and record the failing clause. (User OK required.)

## Phase 5: Docs and polish

- [ ] T050 [DOCS] Update: `docs/system-one.md`, `docs/memory.md`, `docs/configuration.md`, `docs/architecture.md`, `docs/package-architecture.md`, `docs/testing.md`, worldstate and memory package READMEs, root `README.md` if it mentions speech-act, `AGENTS.md` (173 phase row, `zw004` migration row, worldstate layout `commitment_judge.py`/`intake.py`, memory layout, `calibrate-commitment-intake` replacing `calibrate-speech-act`), `specs/README.md` index, `specs/arch/system-one-models.md` (new O-row), `specs/arch/executive-function.md` (F4 fixed, Option 2 done), `specs/phases/163-*` and `168-*` status notes (superseded in part). Follow the `doc-style` skill for `docs/`.
- [ ] T051 [DOCS] Coverage check: `git diff main...HEAD --stat` against T050; every public doc touched by the diff is listed.
- [ ] T052 [ENG-B] `make lint test-memory test-worldstate test-core test test-pg test-web typecheck-web`; `make test-py` (no OpenRouter calls); set spec status Implemented; run the after-implement hook.

## Dependencies

T001 -> T002/T003 -> T004 -> T042 -> T043. T010,T011 -> T021 -> T022,T023 -> T024,T025,T026. T012,T013 -> T023. T030 -> T031 -> T032. T040 after T021. T050 after T043. [P] tasks run beside their phase siblings. Shared-file order for 181: land the smaller diff first; the other rebases (`nodes/memory.py`, `nested_tools.py`).
