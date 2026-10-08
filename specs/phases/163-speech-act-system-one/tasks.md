# Tasks: Speech-Act System One

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Required (constitution V, FR-009, SC-005). Write them fail-first. Default suites never POST to OpenRouter. Use a fake `SystemOneClient` (an object with async `evaluate(state, questions, *, max_attempts=None)`) and an `AsyncMock` for `client.complete`.

**Tags**: `[BE]` backend Python · `[PLATFORM]` config / Makefile / eval tooling · `[DOCS]` docs, specs, AGENTS.md · `[WEB]` none in this phase (the 162 `JudgmentsSection` already renders judgments).

**Normative references**:
- decision table: research.md R7;
- question set: [contracts/speech-act-judgment.md](./contracts/speech-act-judgment.md);
- admission flow and trace merge: [contracts/fact-admission.md](./contracts/fact-admission.md);
- client delta: [contracts/system-one-max-attempts.md](./contracts/system-one-max-attempts.md).

---

## Phase 1: Setup

**Purpose**: Default-off surface config.

- [x] **T001** [P] [PLATFORM] Under the existing `system_one:` block, replace `surfaces: {}` with `surfaces.speech_act` (`enabled: false`, `choice_hold: null`, `biography_hold: null`). Mark both bars with the comment `# uncalibrated — set from make calibrate-speech-act`. · `apps/ze-api/config/config.yaml`

---

## Phase 2: Foundational

**Purpose**: Client single attempt, admission types, trace conversion, and the `FactAdmission` hard cut with the pre-163 path preserved. This phase blocks every story.

**⚠️** Start no user-story work until this phase is complete. When it finishes, SC-007 holds: with the surface disabled, facts are identical to pre-163.

**Wave 1 — fail-first tests (different files):**

- [x] **T002** [P] [BE] Fail-first: `SystemOneClient.evaluate` accepts the keyword-only `max_attempts`, and the fake used in tests satisfies `isinstance(fake, SystemOneClient)`. · `core/contracts/ze-agents/tests/test_system_one.py`
- [x] **T003** [P] [BE] Fail-first, mocked `httpx`, patched `asyncio.sleep`:
  - `max_attempts=1` with a 429 makes one POST, never sleeps, and returns skip `overload`;
  - `max_attempts=1` with a 503 makes one POST and returns skip `error`;
  - `max_attempts=None` keeps the three-attempt 162 behavior;
  - `max_attempts=0` returns skip `invalid_request` with no POST;
  - `DisabledSystemOneClient.evaluate(..., max_attempts=1)` returns skip `disabled`.

  · `core/engine/ze-core/tests/openrouter/test_system_one.py`
- [x] **T004** [P] [BE] Fail-first, `judgments_from_result`:
  - an ok result with Choice `speech_act`, Choice `family` and Noul `biography` gives three rows. Choice rows carry `answer`, `probabilities` and `peakedness=confidence`. The Noul row has `answer=noul` and `peakedness=None`. `model` and `input_tokens` come from the result. `consumed` is true only for ids in `consumed`;
  - a skip result with `question_ids=("speech_act","family","biography")` gives three rows with `answer=None`, `skip_reason` set and `consumed=False`;
  - an ok result with `skip_reason="invalid_answer"` stamps that reason on every row.

  · `core/engine/ze-core/tests/conversation/test_judgments.py`
- [x] **T005** [P] [BE] Fail-first, `speech_act_surface_config`:
  - a missing block gives disabled;
  - `enabled: true` with either bar `null` gives `calibrated=False`;
  - a bar out of `[0,1]` or not numeric becomes `None` with a warning;
  - it accepts both a dict and an object with `.config`.

  Also: `SPEECH_ACT_QUESTIONS` keys equal `{"speech_act","family","biography"}`; the `speech_act` options equal `[a.value for a in SpeechAct]` in enum order; the `family` options equal `[f.value for f in PredicateFamily] + ["drop"]` (same set as `KEEP_FAMILIES ∪ {"drop"}`); and `build_state` caps `assistant` at 1000 chars and has only the keys `user` and `assistant` (FR-005).

  · `core/cognition/ze-memory/tests/test_speech_act_judge.py`

**⟶ Wait for Wave 1 to finish, then:**

**Wave 2 — independent (different files):**

- [x] **T006** [P] [BE] Add the keyword-only `max_attempts: int | None = None` to the `SystemOneClient.evaluate` Protocol. · `core/contracts/ze-agents/ze_agents/system_one.py`
- [x] **T007** [P] [BE] Honor `max_attempts` in `OpenRouterSystemOneClient.evaluate`: `None` means `len(_BACKOFFS)`, otherwise `min(n, len(_BACKOFFS))`. `< 1` returns skip `invalid_request` before the network. Never sleep after the final allowed attempt. Map the final retryable status to `overload` (429/529) or `error`. `DisabledSystemOneClient.evaluate` gains the same keyword. · `core/engine/ze-core/ze_core/openrouter/system_one.py`
- [x] **T008** [P] [BE] Add the `FactAdmission` dataclass (`facts`, `path`, `judgment`, `question_ids`, `consumed`, `skip_reason`) per data-model.md, and export it. · `core/cognition/ze-memory/ze_memory/types.py`, `core/cognition/ze-memory/ze_memory/__init__.py`
- [x] **T009** [P] [BE] Add `judgments_from_result(result, *, question_ids, consumed, skip_reason=None) -> list[JudgmentTrace]` per research R4 and data-model.md. · `core/engine/ze-core/ze_core/conversation/messages/judgments.py`
- [x] **T010** [P] [BE] Create `speech_act_judge.py` with:
  - `SpeechActSurfaceConfig` and `speech_act_surface_config(settings)`;
  - `build_state(prompt, response)`;
  - `SPEECH_ACT_QUESTIONS`: a `speech_act` Choice with per-label criteria from 142 R11 / 146 / 147, each criterion holding ≥1 EN and ≥1 PT example; a `family` Choice with per-family criteria and a `drop` criterion; a `biography` Noul whose wording comes from the contract;
  - `AdmissionDecision` (no `decide()` yet; T019 introduces it).

  Import only `ze_agents.system_one` and ze-memory modules, never `ze_core`. · `core/cognition/ze-memory/ze_memory/speech_act_judge.py`

**⟶ Wait for Wave 2 to finish, then:**

**Wave 3 — hard cut of the extractor return type (sequential; same call chain):**

- [x] **T011** [BE] Fail-first: update the existing tests to the `FactAdmission` return:
  - `gather_fact_proposals` with the surface disabled returns `path="haiku"`, the same facts as before and `judgment=None`;
  - with no `openrouter_client` it returns `path="none"`;
  - a trivial prompt returns `path="none"` with no `complete` call.

  · `core/cognition/ze-memory/tests/test_extractor.py`, `core/cognition/ze-memory/tests/test_extractor_admission.py`
- [x] **T012** [BE] Hard-cut `gather_fact_proposals` to return `FactAdmission`. Also short-circuit trivial and `[ERROR]` turns at its top (`path="none"`); `extract_facts` keeps its own trivial check unchanged. When the surface is disabled, there is no `system_one_client`, or the config is uncalibrated, run `extract_facts` (the unchanged pre-163 `_SYSTEM` judge). When uncalibrated, also log `speech_act_system_one_uncalibrated` (warning) and set `skip_reason="uncalibrated"`. Set `fact.agent`. · `core/cognition/ze-memory/ze_memory/extractor.py`
- [x] **T013** [BE] Fail-first, with a fake extractor returning `FactAdmission`. `write_memory`:
  - submits `admission.facts` through the 148 identity filter as before;
  - with `judgment=None` leaves `message_trace` unchanged and returns no `message_trace` key;
  - with an ok judgment and a `message_trace` in state returns `message_trace` with the rows appended after any existing judgments, including in the compaction branch;
  - with `message_trace=None` does not crash;
  - an `eval-` thread never calls the extractor (FR-013).

  · `core/engine/ze-core/tests/orchestration/nodes/test_memory_judgments.py`
- [x] **T014** [BE] Update `write_memory` to consume `FactAdmission`. When `admission.judgment is not None` and `state["message_trace"]` is set, return `message_trace=dataclasses.replace(trace, judgments=[*trace.judgments, *judgments_from_result(...)])` from every return dict. Add `admission_path` to the existing debug log. · `core/engine/ze-core/ze_core/orchestration/nodes/memory.py`
- [x] **T015** [BE] Update the existing fakes and assertions that expect a `list[Fact]` from `fact_extractor` to return or read `FactAdmission`. · `core/engine/ze-core/tests/orchestration/nodes/test_memory.py`, `core/engine/ze-core/tests/orchestration/nodes/test_extractor_dual_write.py`

**Checkpoint**: `make test-agents test-core test-memory` is green. With the default config, admission behaves exactly as before (SC-007).

---

## Phase 3: User Story 1 — A timed reminder is not stored as biography (Priority: P1) 🎯 MVP

**Goal**: With the surface calibrated, System One decides act/family/biography. Non-`fact` acts hold. A confident durable preference persists through the value writer.

**Independent Test**: Use a fake client with gold answers. "Remind me Tuesday at 3 to call the dentist" and the PT equivalent give zero facts and zero `complete` calls. "I prefer aisle seats" and the PT equivalent give one `preference` fact written by the value writer. A "remember to … at 3" utterance gives `reminder`, not `fact`.

### Tests (fail-first)

- [ ] **T016** [P] [BE] [US1] Gold fixture module: build `SystemOneResult` ok answers for EN+PT utterances: timed reminder, "remember to call Mom at 3", loop ("I need to figure out whether to switch jobs"), goal ("ship the thesis by June"), ingest, aisle-seat preference, peanut-allergy constraint. Each row holds the utterance, gold act, gold family, a high-confidence Choice distribution and a Noul. · `core/cognition/ze-memory/tests/fixtures/speech_act_gold.py`
- [ ] **T017** [P] [BE] [US1] Fail-first `decide()` rules 5 and 10 (R7):
  - each non-`fact` gold act gives `hold`/`not_fact` with `consumed={"speech_act"}`;
  - confident `fact`, a keep family and a Noul above the bar give `persist(family)` with all three consumed;
  - an unknown label (`"remind"`) goes through `admit_speech_act` to `drop` and gives `hold`.

  · `core/cognition/ze-memory/tests/test_speech_act_judge.py`
- [ ] **T018** [P] [BE] [US1] Fail-first `gather_fact_proposals` with a calibrated config, a gold fake client and an `AsyncMock` `complete`. Cover:
  - reminder, loop and goal fixtures (EN+PT) give `facts==[]`, `path="system_one"` and `complete.await_count == 0`;
  - the aisle preference gives `complete` called once with the value-writer system prompt (not `_SYSTEM`), and one fact with `predicate == "preference"` and `confidence == 0.8`;
  - a value-writer response that includes `speech_act`/`family` keys still uses the System One family;
  - a value-writer parse failure, empty list or exception gives `facts==[]` with no second call;
  - the client was called with `max_attempts=1` and `build_state(...)`.

  · `core/cognition/ze-memory/tests/test_speech_act_system_one.py`

### Implementation

- [ ] **T019** [BE] [US1] Implement `decide()` rules 1–5 and 10 from R7. Both labels pass through `admit_speech_act` / `admit_family`. Until US3 lands, rules 6–9 are implemented conservatively: any `fact` answer that is not confidently a keep family with a Noul at or above the bar **holds** (reason `hold`), so FR-004 is never violated by the MVP. US3 replaces this with the exact R7 reasons and rule 4. · `core/cognition/ze-memory/ze_memory/speech_act_judge.py`
- [ ] **T020** [BE] [US1] Add the `_VALUE_SYSTEM` prompt and `write_fact_values(client, *, prompt, response, family, model) -> list[Fact]`. The output schema is `{"facts":[{"value": "..."}]}`, with `max_tokens=200` and the `fact_extraction_model` model. Ignore any act or family keys. Confidence is fixed at `0.8`. Log exceptions and return `[]`. · `core/cognition/ze-memory/ze_memory/extractor.py`
- [ ] **T021** [BE] [US1] Wire the System One path into `gather_fact_proposals`. A calibrated surface plus a client calls `evaluate(build_state(...), SPEECH_ACT_QUESTIONS, max_attempts=1)` and then `decide`. `persist` calls `write_fact_values`; `hold` returns `[]`. Fill in `judgment`, `question_ids`, `consumed` and `path="system_one"`. Log `speech_act_system_one_decision` with kind, reason, family and latency, but never user text. · `core/cognition/ze-memory/ze_memory/extractor.py`

**Checkpoint**: US1 tests are green. SC-001 holds with mocked gold answers.

---

## Phase 4: User Story 2 — Cancel language is not forget-biography (Priority: P1)

**Goal**: The eight-way Choice separates `forget` (biography retract) from `reminder`/`loop`/`goal` cancel. Neither one persists a fact.

**Independent Test**: The gold pair "Forget the dentist" / "Esquece o dentista" gives `reminder`, and "Forget that I like aisle seats" / "Esquece que prefiro lugar no corredor" gives `forget`. Both give `facts==[]`. The criteria text encodes the separation rule.

### Tests (fail-first)

- [ ] **T022** [P] [BE] [US2] Add the dentist-cancel and aisle-retract gold rows (EN+PT) to the fixtures. · `core/cognition/ze-memory/tests/fixtures/speech_act_gold.py`
- [ ] **T023** [P] [BE] [US2] Fail-first:
  - the dentist rows give `hold`/`not_fact` with `speech_act` consumed and answer `reminder`;
  - the aisle rows give `hold`/`not_fact` with answer `forget`;
  - neither calls `complete`;
  - the `speech_act` criteria for `forget` and `reminder` each contain the cancel-vs-retract rule and a PT example (string assertions on `SPEECH_ACT_QUESTIONS`);
  - an unknown label gives `drop` (US2 scenario 3).

  · `core/cognition/ze-memory/tests/test_speech_act_system_one.py`

### Implementation

- [ ] **T024** [BE] [US2] Tighten the `forget` / `reminder` / `loop` / `goal` criteria in `SPEECH_ACT_QUESTIONS`. Cancel, drop or abandon aimed at a ping, loop or goal is that act. Only retracting a standing self-fact is `forget`. Include the PT examples. · `core/cognition/ze-memory/ze_memory/speech_act_judge.py`

**Checkpoint**: SC-002 holds on the mocked gold pair.

---

## Phase 5: User Story 3 — Unsure does not silently persist (Priority: P2)

**Goal**: Low peakedness or a middling biography Noul holds with no generative call. Skip runs exactly one Haiku judge. Uncalibrated or malformed answers go to Haiku and are recorded.

**Independent Test**: A fake near-uniform `speech_act` distribution gives zero facts and zero `complete` calls. Choice `fact` with Noul 0.5 gives zero facts. A timeout skip gives exactly one `complete` call with `_SYSTEM`, and the trace rows show `skip_reason="timeout"`. Enabled with a null bar logs a warning and takes the Haiku path.

### Tests (fail-first)

- [ ] **T025** [P] [BE] [US3] Fail-first `decide()`:
  - rule 6: `fact` below `choice_hold` gives `act_unsure`;
  - rule 7: a `drop`/unknown family gives `family_drop`;
  - rule 8: a family below `choice_hold` gives `family_unsure`;
  - rule 9: a Noul below `biography_hold` gives `not_biography`, including Noul 0.5 with a confident `fact`;
  - rule 4: a missing answer, a Choice with no `confidence` or a Noul with no `noul` gives `skip`/`invalid_answer`;
  - `choice_hold` and `biography_hold` are read independently: a test sets them to different values and checks each one gates only its own question (FR-002).

  · `core/cognition/ze-memory/tests/test_speech_act_judge.py`
- [ ] **T026** [P] [BE] [US3] Fail-first `gather_fact_proposals`:
  - hold cases give `complete.await_count == 0` (SC-006);
  - a client skip (`timeout`, `overload`, `missing_key`, `disabled`) gives exactly one `complete` call with `_SYSTEM`, `path="haiku"`, `judgment` set and `consumed` empty;
  - `invalid_answer` gives one Haiku call and `skip_reason="invalid_answer"`;
  - uncalibrated config gives no `evaluate` call, one Haiku call and the warning logged.

  · `core/cognition/ze-memory/tests/test_speech_act_system_one.py`
- [ ] **T027** [P] [BE] [US3] Fail-first (SC-004): in `write_memory` with a skip-path `FactAdmission` plus a same-turn `remember_fact ok` of the same identity, the submitted facts contain no duplicate identity, and the trace gets skip rows with `consumed=False`. · `core/engine/ze-core/tests/orchestration/nodes/test_memory_judgments.py`

### Implementation

- [ ] **T028** [BE] [US3] Replace T019's conservative hold with `decide()` rules 4 and 6–9 in exact R7 order and reasons. · `core/cognition/ze-memory/ze_memory/speech_act_judge.py`
- [ ] **T029** [BE] [US3] In `gather_fact_proposals`, route `decide().kind == "skip"` (client skip or `invalid_answer`) to one `extract_facts` call. Keep `judgment` and `question_ids`, set `consumed=frozenset()`, and set `skip_reason` from the decision. Log `speech_act_system_one_invalid_answer` on rule 4. · `core/cognition/ze-memory/ze_memory/extractor.py`

**Checkpoint**: SC-003, SC-004 and SC-006 hold. FR-006: there is never a Haiku tie-break on an unsure answer.

---

## Phase 6: Calibration set and opt-in run (FR-012, SC-008)

**Purpose**: Measured bars. Default runs never execute this phase.

- [ ] **T030** [P] [PLATFORM] Write a labeled set per data-model.md "Calibration row", with ≥3 EN and ≥3 PT rows per act. It must include every `memory_speech_act_*` and `memory_admission_*` prompt from `eval/scenarios/memory.yaml` and the 146 dentist/aisle pair in both languages. · `eval/calibration/speech_act.jsonl`
- [ ] **T031** [PLATFORM] Write the opt-in calibration script. It loads the JSONL and builds `OpenRouterSystemOneClient` from env `OPENROUTER_API_KEY` with the model `typesafe/jev-1.13` (or the `system_one.model` from config). It uses the production `SPEECH_ACT_QUESTIONS` with option order shuffled per row (eval only) and `build_state`.

  Per language it reports:
  - exact-act accuracy and a confusion matrix;
  - a Choice-confidence reliability table with ECE;
  - fact precision/recall where predicted persist means rules 5–10 hold at each bar on a grid;
  - suggested `choice_hold` and `biography_hold`, chosen as the lowest pair with fact precision = 1.0 on the set.

  It exits non-zero without a key. It is not a pytest module and is not collected. · `eval/calibration/speech_act.py`
- [ ] **T032** [PLATFORM] Add a `calibrate-speech-act` target that runs `uv run python eval/calibration/speech_act.py`, and a `make help` line marking it live and costing credits. · `Makefile`

---

## Phase 7: Polish & Cross-Cutting

- [ ] **T033** [P] [DOCS] Document the `system_one` block and `surfaces.speech_act` keys: off by default, uncalibrated bars, the calibration command, and the fact that the Noul bar is not the Choice bar. · `docs/configuration.md`
- [ ] **T034** [P] [DOCS] Update the admission section. The post-turn judge is System One when calibrated: a Haiku value writer on persist, the Haiku judge on skip, and judgments on the trace. `admit_*` remain the filters. · `specs/core/ze-memory.md`
- [ ] **T035** [P] [DOCS] Mark sequencing step 2 / O1 as Implemented and set Appendix A's "Extractor `speech_act`" row to System One with Haiku fallback. Record the value-writer and single-attempt decisions as notes under O1. · `specs/arch/system-one-models.md`
- [ ] **T036** [P] [DOCS] Add the phase-table row `163 | Speech-act System One — …` with status Implemented. · `AGENTS.md`
- [ ] **T037** [BE] Run `make test-agents test-core test-memory test lint`. SC-005: confirm every new test injects a fake `SystemOneClient` or mocks `httpx` transport, and that no new test constructs `OpenRouterSystemOneClient` against a real transport. Fix any failures. · repo root
- [ ] **T038** [DOCS] Set spec `**Status**:` to Implemented. · `specs/phases/163-speech-act-system-one/spec.md`

---

## Dependencies & Execution Order

- **Setup (T001)** → **Foundational (T002–T015)** → user stories.
- **US1 (T016–T021)** is the MVP and must land first: it creates the System One path in `gather_fact_proposals` that US2 and US3 extend.
- **US2 (T022–T024)** depends on US1 (T019, T021). It touches only criteria and fixtures, so it can run in parallel with US3.
- **US3 (T025–T029)** depends on US1 (T019, T021).
- **Calibration (T030–T032)** depends only on T010 (questions) and T007 (client), so it can start after Foundational and run beside the stories.
- **Polish (T033–T038)** runs after all stories. T037 runs before T038.

Within each story the order is: tests fail first, then implementation, then the checkpoint.

## Parallel Examples

- Foundational Wave 1: T002, T003, T004, T005 together.
- Foundational Wave 2: T006, T007, T008, T009, T010 together.
- After US1: US2 (T022–T024) and US3 (T025–T029) in parallel. T024 and T028 both edit `speech_act_judge.py`, so serialize those two.
- Calibration T030 can run alongside any story phase.
- Polish docs T033–T036 together.

## Implementation Strategy

1. Do Setup and Foundational first. The hard cut ships with zero behavior change (SC-007), which is a safe stopping point.
2. Do US1 next as the MVP. With a calibrated config, timed reminders and loop/goal utterances stop persisting and preferences persist through the value writer.
3. Then US2 and US3 to close the forget/cancel confusion and the unsure-hold rule.
4. Calibration is run once by a maintainer to set the bars. The surface stays `enabled: false` in committed config until the user decides to turn it on.
5. Finally Polish: docs, AGENTS.md and status.

Commit split by user story when asked: Foundational, US1, US2, US3, Calibration, Docs.
