# Feature Specification: Judgment Surface

**Feature Branch**: `202-judgment-surface`

**Created**: 2026-10-22

**Status**: Ready to implement

**Depends on**: 198 (audit bug floor, landed). Shares `ze_worldstate/admission.py`, `intake.py`, `types.py`, `commitment_judge.py`, `corroboration.py` and `nodes/memory.py` with 203, which also edits them. 202 lands first and 203 rebases onto it; the hunk split is in [plan.md](plan.md#coordination-with-203).

**Input**: Architecture review 2026-10-22, candidate C6: "One System One judgment-surface module that owns config parsing, the calibrated rule, the single-attempt call, exception → skip, warn-once and one Judgment record carrying surface and bars; the trace rows come from it, with `judgment_bars.py` and the five carrier types deleted; plus one shared calibration harness that `eval/calibration` runners use, calling the production surface. Each surface keeps its questions, state, bars and `decide()`, as the ADR requires. Unify the drifted semantics (trace rows on exception, `skip_reason`)."

## Context

Ze asks System One typed questions at seven **judgment points** (config key `system_one.surfaces.<name>`):

| Surface | Questions and pure decide | Orchestration |
|---|---|---|
| routing | `ze_core/routing/judge.py` (197 lines) | `EmbeddingRouter._judge`, `routing/router.py:159-192` |
| complexity | `routing/tier.py:104-119` | `TierJudge.choose`, `tier.py:146-180`, gate in `nodes/tier.py:49-53` |
| skills | `ze_skills/judge.py` (192) | `SkillMatcher.match`, `ze_skills/matching.py:134-184` |
| loop_gate | `ze_worldstate/loop_judge.py` (125) | `LoopInflow._judge`, `admission.py:146-191` |
| corroboration | `corroboration_judge.py` (99) | `corroboration._judge` and `_corroborate`, `corroboration.py:59-78`, `136-146` |
| commitment_intake | `commitment_judge.py` (340) | `CommitmentIntake.admit`, `intake.py:121-177` |
| fact_judge (Haiku-path label) | `ze_memory/fact_judge.py` (97) | `nodes/memory.py:178-193` (unreachable, see below) |

Each orchestration repeats the same steps:

1. Read the config block (`surface_block(...)`, called in 7 places, including `judgment_bars.py:34`).
2. Check enabled, then calibrated, and warn.
3. Call `evaluate(..., max_attempts=1)` inside try/except.
4. Map an exception to a skip.
5. Run `decide()`.
6. Pack the result into a carrier.
7. At the node, rebuild trace rows with a question-to-bar map written by hand.

There are five carrier shapes with the same four fields (result, question kinds, consumed, skip reason):

- `RoutingJudgment` (`routing/types.py:24`), shared by routing and complexity;
- `SkillsJudgment` (`ze_skills/types.py:138`);
- `LoopAdmission` (`ze_worldstate/types.py:128`);
- `IntakeAdmission` (`intake.py:61`);
- `FactAdmission` (`ze_memory/types.py:123`).

### Verified drift

Checked against main at `5426cce1` (198 and 199 landed), 2026-10-26.

- **Exception handling differs.**
  - Routing, complexity and skills turn an exception into `SystemOneResult(outcome="skip", skip_reason="error")`, so the trace gets one skip row per question (`router.py:175-179`, `tier.py:151-155`, `matching.py:151-155`).
  - Commitment intake on an exception falls back with `judgment=None` (`intake.py:146-157`), so the conversation trace shows **no** judgment rows for that turn.
  - Loop admission and corroboration also return no result on an exception (`admission.py:173-180`, `corroboration.py:72-74`). Those two inflows log their judgments and write no trace rows by design (phase 168), so this drift shows only in their logs.
- **`skip_reason` means three different things.**
  - Complexity sets it only for `invalid_answer` (`tier.py:162-164`).
  - Routing and skills set it for "decision skip while the outcome is ok" (`router.py:186-190`, `matching.py:162-166`).
  - Intake and loop admission set it for every fallback.
- **Check order differs.**
  - `corroboration_judge.decide` checks `enabled` and `calibrated` itself (`corroboration_judge.py:85-88`).
  - `loop_judge.decide` checks the answer is valid before the bars (`loop_judge.py:106-113`).
  - The orchestrations differ in the same way.
- **Warnings differ.** Complexity warns once per `TierJudge` (`TierJudge.warn_uncalibrated_once`). Routing, skills, loop gate, corroboration and intake log their uncalibrated warning on every call (`router.py:166`, `matching.py:138`, `admission.py:156`, `corroboration.py:141`, `intake.py:126`). The worldstate surfaces re-parse their config on every call, so an invalid bar also warns on every call.
- **Bar names are stored twice.**
  - The commitment intake's bar names are in `commitment_judge._BAR_NAMES` (`commitment_judge.py:157`) and again in `judgment_bars._INTAKE_BARS`, which also parses the config a second time, because ze-core cannot import ze-worldstate (`judgment_bars.py:11-38`).
  - The routing, skills and complexity bar maps are written inline at the nodes (`nodes/routing.py:85-88`, `nodes/skills.py:58-61`, `nodes/tier.py:83`).
- **Validation is copied.** `decide_tier` re-implements `valid_noul` inline (`tier.py:109-116`).
- **Unreachable decision kind.** `loop_judge.DecisionKind` lists `create_declared`, but `loop_judge.decide` can no longer return it (`loop_judge.py:90-125`). Only the intake's remap (`intake.py:45-49`) produces it. Phase 203 owns this fix (FR-009).
- **Dead trace path.** `write_memory`'s non-intake branch builds `fact_judge` rows from `FactAdmission.judgment` with `bars={}` (`nodes/memory.py:182-193`). The only production fact extractor, `gather_fact_proposals` (`ze_memory/extractor.py:439-467`), never sets a judgment. Only the commitment intake does (`intake.py:262`, `306`), and the node reads `intake.judgment`, not the fact admission's. The branch and `FactAdmission`'s four judgment fields have no production reader.

### Calibration

`eval/calibration` holds nine Python files (4,838 lines): six System One runners, the commitment-intake baseline, `open_query.py` and `companion_research_check.py`. Each System One runner re-implements the same pieces:

- `load_rows`, `_norm`, `check_sets`, the set-shape core and the reliability report (`loop_gate.py:80-92` matches `corroboration.py:88-100`);
- `suggest_bars`, the bar grid, the verdict printout, and (only `commitment_intake.py`) saving and loading results;
- its own read of the surface config from `config.yaml` (`config_model`, `system_one_config`).

The runners already call the production `decide()`. They do not call the production config parser: they build the surface config dataclasses positionally. That has already drifted: `loop_gate.py:536` builds `LoopGateSurfaceConfig(True, 0.9, 0.9, 0.9)`, four values for a class that has had three fields since phase 173, so the "no bar pair passes" path of `make calibrate-loop-gate` raises `TypeError`.

### Blast radius

`graphify affected <symbol> --depth 2` on the symbols this phase changes (full list by package in [plan.md](plan.md#blast-radius)):

- `judgments_from_result` reaches 4 production nodes (`embed_route`, `match_skills`, `choose_tier`, `write_memory`) and 13 test modules in `core/engine/ze-core/tests`;
- the six surface-config parsers reach their production callers (`routing/factory.py`, `ze_skills/bootstrap.py`, `api/v0/system/models.py`, `admission.py`, `corroboration.py`, `intake.py`), their surface tests and the calibration runners;
- `RoutingEnvelope.judgment` is checkpointed with the graph state, so the record type joins the checkpoint allowlist.

### What does not change

`system-one-models.md` holds that each surface keeps its own questions, state builder, bars and pure `decide()`, and that code owns arithmetic and policy. This phase moves only the orchestration and trace pattern. The bars in `config.yaml` stay as they are, and the System One client contract (`SystemOneClient`, two adapters) is unchanged.

## Clarifications

### Session 2026-10-26

- Q: The `fact_judge` trace path (`nodes/memory.py:182-193`) is unreachable in production. Keep it with real bars, or delete it? → A: Delete it. The branch and `FactAdmission`'s `judgment`, `question_ids`, `consumed` and `skip_reason` fields are removed (pre-v1 hard cut). FR-004 and the edge cases say so.
- Q: SC-004's 40% line drop is out of reach without rewriting per-surface scoring. Restate it? → A: Yes. SC-004 is structural: row loading, the set-shape core, reliability bins, the bar grid, the verdict printout, saving and loading results, and the config read are each defined once, in the harness, with zero copies in the runners. Calibration lines drop by at least 25% (floor superseded on 2026-10-27: at least 12%).
- Q: 202 and 203 both edit the loop decision kinds. Who owns FR-009? → A: 203 owns it entirely. 202 lands first and changes no decision kinds; 203 rebases onto 202.

### Session 2026-10-27

- Q: Review (Vigil, `5426cce1..d9a6d685`) measured the duplicated helper code at 1,155 lines; a 25% drop needs 1,210, so the 2026-10-26 floor cannot be met without rewriting the per-surface scoring FR-011 protects. Lower the floor? → A: Floor of 12%. The structural half of SC-004 stays exactly as chosen on 2026-10-26 (each shared helper defined once in the harness, zero copies in the runners, checked by T036's scan); calibration lines drop by at least 12% (at most 4,257 of 4,838, harness included). This replaces the 25% floor.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every judgment that was attempted shows on the trace (Priority: P1)

The user opens the trace panel for a reply. The System One call behind a conversation-turn judgment point (routing, skills, complexity, or commitment intake) failed or timed out. The panel shows that the question was asked and skipped, with the reason. It never shows nothing.

**Why this priority**: The trace is Ze's honesty surface. Today a failed commitment-intake call leaves no rows, while a failed routing call leaves skip rows, so the same failure reads differently.

**Independent Test**: Make the fake System One client raise for each of the four conversation-turn surfaces in turn. For each, the turn's `MessageTrace.judgments` holds one row per question, with the surface name, the bar in force, and `skip_reason="error"`.

**Acceptance Scenarios**:

1. **Given** the commitment intake is enabled and calibrated, **When** its System One call raises, **Then** the trace shows six commitment-intake question rows marked skipped with reason `error`, plus the `intake_outcome` row (`fallback:error`), and the Haiku fallback still runs.
2. **Given** routing is calibrated, **When** its call times out, **Then** the trace shows routing rows with reason `timeout` (the client's own skip reason), exactly as today.
3. **Given** a surface is enabled but uncalibrated, **When** a turn runs, **Then** no request is made, no rows are written, and the uncalibrated warning is logged once per process for that surface.

---

### User Story 2 - Adding a judgment point is questions, state and decide (Priority: P2)

A maintainer adds a new System One judgment point. They write its questions, its state builder, its bar names and its pure `decide()`, and they register the surface. Config parsing, the calibrated check, the single attempt, the skip on error, the warn-once rule, the trace rows and the bar labels on those rows all come from the shared module.

**Why this priority**: Every recent System One phase (163, 166, 168, 172, 173, 182) wrote about 80 lines of glue plus a node edit. This is the leverage the module exists for.

**Independent Test**: A test surface defined only by questions, a state builder, bar names and `decide()` runs end to end against a fake client, and its trace rows carry the right surface and bars, with no other code.

**Acceptance Scenarios**:

1. **Given** a surface definition with two Noul questions and two bar names, **When** it is judged against a fake client, **Then** the result is one judgment record that carries the surface name, each question's kind, the consumed set, the skip reason and the bar for each question.
2. **Given** the same definition, **When** a node turns the record into trace rows, **Then** it needs no bar map and no question-kind map.

---

### User Story 3 - Calibration runs the production surface (Priority: P3)

The calibration operator runs `make calibrate-<surface>`. The runner parses the surface config, checks calibration and calls `decide()` through the same module that production uses. Row loading, set-shape checks, the live loop, the reliability and bar-grid reports, the verdict printout and saving results come from one shared harness. Each runner keeps only its gold columns and its acceptance rule.

**Why this priority**: It removes the copied calibration code and stops calibration verdicts from drifting from production behaviour. But it changes no runtime behaviour.

**Independent Test**: For every runner, `--check-sets` gives the same output as before, and a recorded results file gives the same report and verdict as before.

**Acceptance Scenarios**:

1. **Given** a saved results file from a past run, **When** the runner rebuilds its report, **Then** the counts, the suggested bars and the verdict match the old output exactly.
2. **Given** a spent held-out set, **When** a runner is pointed at it, **Then** the same refusal and acceptance rules apply as today; those stay per runner.

---

### Edge Cases

- **A result with outcome `ok` but a missing answer for one question.** That question gets its own skip row with the decision's skip reason, as today (`judgments.py:37-48`).
- **The client returns `skip` with its own reason** (timeout, overload). The client's reason wins over a decision reason.
- **A surface whose decision consumes no questions** (a hold). Rows are written with `consumed=false`.
- **Commitment intake with a reminder or goal created this turn, which suppresses the loop.** Rows still cover all six questions. Suppression is a decision outcome, not a skip.
- **Email, calendar and ingestion loop gates and corroboration.** They write no trace rows (phase 168), but their logged judgment line uses the same record and the same skip semantics.
- **No commitment intake wired.** `write_memory` runs the Haiku fact extractor and writes no fact judgment rows; the old `fact_judge` row path is deleted (it had no production producer).
- **A bar invalid in config** (out of [0, 1], a boolean or a string). It parses to unset, logs once per surface and bar per process, and the surface reads as uncalibrated, as today.
- **Corroboration with `corroborate_hold` above `promote_hold`.** The surface reads as uncalibrated, as today (`corroboration_judge.py:56`). The shared calibrated rule takes a per-surface consistency check.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: One judgment-surface module MUST sit beside the `SystemOneClient` contract in ze-agents. It owns:
  - reading `system_one.surfaces.<name>`;
  - parsing named bars and surface extras (for example `shortlist_k`);
  - the "calibrated" rule: enabled and every required bar set, plus an optional per-surface consistency check;
  - the single-attempt call;
  - mapping any exception to a skip result with reason `error`;
  - logging the uncalibrated warning once per surface per process.
- **FR-002**: Each judgment point MUST define only:
  - its questions;
  - its state builder;
  - its bar names, with the question each bar governs;
  - its extras;
  - its pure `decide()`.
  The existing `decide()` functions keep their behaviour and their tests.
- **FR-003**: Judging MUST return one judgment record with these fields: surface name, the raw result, each question's kind, the consumed set, the skip reason, and the bar in force for each question (name and value, or unset).
- **FR-004**: The five carrier shapes MUST stop carrying their own copies of the judgment fields:
  - `RoutingJudgment` and `SkillsJudgment` are deleted;
  - `LoopAdmission` and `IntakeAdmission` hold one judgment record instead of their loose fields;
  - `FactAdmission` loses its `judgment`, `question_ids`, `consumed` and `skip_reason` fields, which have no production reader (Clarifications 2026-10-26).
- **FR-005**: Turning a judgment record into trace rows MUST need nothing else.
  - `ze_core/orchestration/judgment_bars.py` (`bar_map`, `intake_bars`, `_INTAKE_BARS`) is deleted.
  - The four nodes stop building bar maps.
  - The `fact_judge` row branch in `write_memory` is deleted.
- **FR-006**: An exception during the call MUST produce a skip result for every surface. A conversation-turn surface (routing, skills, complexity, commitment intake) then writes one skip row per question with reason `error`. Today the commitment intake writes none.
- **FR-007**: `skip_reason` MUST have one meaning across all surfaces: why the surface's answer was not used.
  - It is the client's skip reason when the outcome is `skip`.
  - Otherwise it is the decision's fallback or skip reason (for example `invalid_answer`, `uncalibrated`).
  - It is empty when the answer was used, or deliberately held under a bar (for example routing's `abstain` and the intake's `hold`).
- **FR-008**: Answer validation MUST use the shared `valid_noul` and `valid_choice`. The inline copy in `decide_tier` is removed.
- **FR-009**: Delivered by phase 203 (Clarifications 2026-10-26). 203's single commit-decision vocabulary removes the intake's string remap and leaves `loop_judge.DecisionKind` with only the kinds `loop_judge.decide` returns. 202 changes no decision kinds.
- **FR-010**: A shared calibration harness MUST provide:
  - row loading with duplicate-id checks;
  - per-language set-shape checks;
  - the live run loop;
  - reliability bins and the bar-grid report;
  - the verdict printout;
  - saving and loading results.
- **FR-011**: Every runner in `eval/calibration` that calibrates a System One surface MUST parse its config and call `decide()` through the production surface module. This is routing, skills, complexity, loop_gate, corroboration and commitment_intake; `open_query` and `companion_research_check` are not System One surfaces and may use only the harness's row helpers. Each runner keeps only its gold columns, its baseline (Haiku or E5) and its acceptance rule.
- **FR-012**: The shipped bar values, the enabled flags and every surface's decision behaviour MUST be unchanged. A replay of each surface's existing decision tests passes without edits to expected outcomes.

### Key Entities

- **Judgment point (surface)**: One place where Ze asks System One typed questions. It has a name, its questions, its bars and its pure decision.
- **Judgment record**: One attempted System One request at one judgment point (a call that raised counts as attempted). It holds what was asked, what came back, which answers the decision used, why the answer was not used (if it was not), and the bar each question was held to. A surface that was not asked (off, uncalibrated, no client) has no record.
- **Bar**: A threshold in [0, 1], set by calibration, that a question's answer must clear before the decision acts on it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For each of the four conversation-turn surfaces, a forced client exception yields one trace row per question with reason `error`. Today: 3 of 4 surfaces; target: 4 of 4.
- **SC-002**: Adding a test surface needs only questions, a state builder, bar names and `decide()`. Zero node edits and zero trace-glue lines.
- **SC-003**: `surface_block` is called from one module only (today: 7).
- **SC-004**: Row loading, the set-shape core, reliability bins, the bar grid, the verdict printout, saving and loading results, and the config read are each defined once, in the harness, with zero copies in the runners. Calibration lines (the nine Python files in `eval/calibration`, today 4,838, plus the harness) drop by at least 12%, to at most 4,257. `--check-sets` output and the verdicts on recorded results stay identical.
- **SC-005**: Every existing surface decision test and node judgment test passes. The only edits allowed are construction, import and patch-target changes, never expected decisions or bars.
- **SC-006**: Each surface's uncalibrated warning appears at most once per process.

## Assumptions

- **Where the module lives.** It lives in `ze_agents` next to `system_one.py`, so ze-core, ze-skills, ze-worldstate and ze-memory can all use it without new dependency edges. The trace row type stays in ze-core, which converts records to rows.
- **Out of scope.** The email, calendar and ingestion loop gates and corroboration keep writing no trace rows. Adding trace rows to background inflows is out of scope.
- **The loop commit vocabulary.** It is redesigned in 203, which also owns FR-009.
- **No live calibration.** No live calibration runs are needed. The calibration refactor is verified offline: golden `--check-sets` output and golden reports from a deterministic replay client, captured before the refactor.
- **No migration, no REST or WS change.** `JudgmentTrace` keeps its shape.
- **Pre-v1 hard cut** (constitution Principle VIII). The carrier types, `judgment_bars.py`, the six `*_surface_config` functions and the `fact_judge` row branch are deleted, not deprecated.
