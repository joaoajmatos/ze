---

description: "Tasks for phase 202 Judgment Surface"
---

# Tasks: Judgment Surface

**Input**: Design documents from `specs/phases/202-judgment-surface/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md), [contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: Required (spec SC-001–SC-006). Each story starts with a test that fails on today's code, through the real interface. Fake System One clients only; no network, no database. Existing decision tests may change only in construction, imports and patch targets (SC-005), never in expected decisions or bars.

**Organization**: Tasks are grouped by user story (spec.md US1–US3).

## Format: `[ID] [P?] [Lane] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Lane]**: The crew lane from plan.md's Lane Plan that owns this task: `[L:lead]`, `[L:engine]`, `[L:ws]`, `[L:calib]`, `[L:docs]`. A task touches only files its lane owns
- **[Story]**: The user story (US1–US3)
- **Tags**: [BE] backend, [PLATFORM] gates, checkpoint and tooling, [DOCS] documentation. No [WEB] task: the trace row shape is unchanged.

**Crew**: the Maestro staffs one agent per lane: Sonnet for `lead`, `engine`, `ws` and `calib`, Haiku for `docs`. The contract step (`[L:lead]`, T001–T007) lands first. The other lanes then run in parallel in their own worktrees, and each is reviewed by Vigil as it finishes.

**Rules for every lane**: tick a task's checkbox in the same commit that finishes it. Run `graphify affected "<Symbol>" --depth 2` before you change a public symbol and update every caller it lists in the same change (plan.md, Blast radius). In the shared worldstate files and in `nodes/memory.py`, edit only the hunks plan.md's "Coordination with 203" gives 202. Tests that assert a warning call `reset_surface_warnings()` first.

---

## Phase 1: Setup

**Purpose**: Confirm the boundaries before any code moves.

- [ ] T001 [L:lead] [PLATFORM] Confirm on the floor branch that no migration is needed (no table changes; next free revisions stay `zc042`, `zm027`, `zw007`) and that `git diff main...HEAD` touches only `specs/phases/202-judgment-surface/`. Post the lane list and each lane's owned files (plan.md Lane Plan) to the "202 Handoffs" Maestri note, and send Tarn (floor 203) a one-line confirmation that the Coordination with 203 split in plan.md is in force.

---

## Phase 2: Foundational (contract step)

**Purpose**: The shared module, the row builder and the checkpoint allowlist every lane builds against. The old `surface_block`, `parse_bar` (in `system_one.py`) and `judgments_from_result` stay until T039, so each lane's branch builds on its own.

- [ ] T002 [L:lead] [BE] Write failing tests in a new `core/contracts/ze-agents/tests/test_judgment.py` against [contracts/judgment-surface.md](contracts/judgment-surface.md):
  - a test surface `class _Demo(SurfaceConfig)` with `SURFACE="demo"`, `BARS={"a_hold": "a", "b_hold": "b"}`, `EXTRAS={"k": <int parser, default 3>}`, two Noul questions `a`, `b`, a pure `decide` and `read`;
  - `from_settings`: missing block → defaults; `enabled` only for literal `True`; bars parsed through `parse_bar` (out of range, bool, string, NaN → `None`); `system_one_bar_invalid` logged once for two parses of the same bad bar; extras parsed; works for a dict and for an object with `.config`;
  - `calibrated`: false when disabled, when any `BARS` field is `None`, or when `consistent()` is false (a subclass overriding it);
  - `bar_for`: `SurfaceBar(name, value)`, `None` when unset; with two bars on one question the first in `BARS` order wins;
  - `gate`: `"disabled"`, then `"uncalibrated"` (logs `system_one_surface_uncalibrated` with `surface="demo"` once across two calls; `reset_surface_warnings()` makes it log again), then `"unavailable"` for `client=None`, else `None`;
  - `judge`: one `evaluate` call with `max_attempts=1`; a raising client gives `SystemOneResult(outcome="skip", skip_reason="error")`, logs `system_one_judgment_error`, and `decide` still runs; the record carries `surface`, `question_kinds` in question order, `consumed`, `bars` per question; `skip_reason` is `error` only when the call raised, the client's reason on a skip result (`timeout` stays `timeout`; a skip with no reason stays `None`), `read().unused_reason` on an ok result, `None` when used.
  Run `make test-agents`: the new tests fail (module missing).
- [ ] T003 [L:lead] [BE] Create `core/contracts/ze-agents/ze_agents/judgment.py` exactly as [contracts/judgment-surface.md](contracts/judgment-surface.md) and [data-model.md](data-model.md) define it: `SurfaceBar`, `SurfaceConfig` (frozen base with `enabled`, `SURFACE`, `BARS`, `EXTRAS`, `from_settings`, `calibrated`, `consistent`, `bar_for`), `DecisionUse`, `Judgment`, `NotAsked`, `surface_block`, `parse_bar(value, name, *, surface)`, `gate`, `judge`, `reset_surface_warnings`. The warn-once helpers are `functools.lru_cache`d functions (plan.md Complexity Tracking). Leave `system_one.py` unchanged for now. T002 passes; `make test-agents lint`.
- [ ] T004 [L:lead] [BE] Add failing tests to `core/engine/ze-core/tests/conversation/test_judgments.py` for `judgment_rows(judgment)`: build each `Judgment` with `ze_agents.judgment.judge` against a fake client, using the `_Demo`-style surface from T002 (a two-Noul surface declared in the test file), and assert the rows match today's rules (data-model.md, Trace rows): skip result → one row per question with the record's `skip_reason`, `surface` and `bar`; ok result → answer, probabilities and peakedness for a Choice, `consumed` per question, a missing answer gives its own skip row; each `SurfaceBar` becomes `JudgmentBar(name, value)`; an unset bar gives `bar=None`. No test passes a bar map, a kind map or a surface name. Keep the existing `judgments_from_result` tests until T039.
- [ ] T005 [L:lead] [BE] Add `judgment_rows(judgment: Judgment) -> list[JudgmentTrace]` to `core/engine/ze-core/ze_core/conversation/messages/judgments.py`, beside `judgments_from_result` (which T039 deletes). T004 passes; `make test-core`.
- [ ] T006 [L:lead] [PLATFORM] Add `"ze_agents.judgment"` and `"ze_agents.system_one"` to `CORE_CHECKPOINT_MODULES` in `core/engine/ze-core/ze_core/checkpoint_serde.py`. In `core/engine/ze-core/tests/test_checkpoint_serde.py`, add a test that `build_checkpoint_serde()` round-trips a `RoutingEnvelope` whose `judgment` is a `Judgment` holding an ok `SystemOneResult` with a Choice answer (assign it with `dataclasses.replace` or the constructor; `RoutingEnvelope.judgment` is retyped in T011, so type-check the test only after T011), and that the allowlist contains `("ze_agents.judgment", "Judgment")` and `("ze_agents.system_one", "SystemOneResult")`. `make test-core`.
- [ ] T007 [L:lead] [PLATFORM] Land the contract step on the floor branch: `make test-agents test-core lint` green. Post the contract commit hash to the "202 Handoffs" note; `engine`, `ws` and `calib` branch from it.

**Checkpoint**: the shared module exists and is tested; no surface uses it yet.

---

## Phase 3: User Story 1 - Every judgment that was attempted shows on the trace (Priority: P1) 🎯 MVP

**Goal**: routing, skills, complexity and the commitment intake all go through `gate`/`judge`, every attempted call yields a record, and a raised call writes one skip row per question with reason `error`.

**Independent Test**: `uv run pytest core/engine/ze-core/tests/orchestration/nodes/test_judgment_surface_errors.py core/cognition/ze-worldstate/tests/test_intake.py -q` (quickstart.md §2).

### Tests for User Story 1

- [ ] T008 [P] [L:ws] [US1] [BE] In `core/cognition/ze-worldstate/tests/test_intake.py`, add failing tests for `CommitmentIntake.admit` with the shipped six bars and a client whose `evaluate` raises: `admission.outcome == IntakeOutcome("fallback", "error")`; `admission.judgment` is a `Judgment` with `surface="commitment_intake"`, `question_kinds` equal to `{qid: q.type for qid, q in COMMITMENT_QUESTIONS.items()}` in that order, `skip_reason="error"`, `bars` naming the six holds (`choice_hold` on `commitment`, …, `resolves_hold` on `resolves_existing`, data-model.md); the Haiku fact path ran (`admission.fact.path == "haiku"` with the existing fake). Add the same with a client returning `SystemOneResult(outcome="skip", skip_reason="timeout")`: `skip_reason="timeout"`. Add: enabled with one null bar → no `evaluate` call, `admission.judgment is None`, one `system_one_surface_uncalibrated` warning across two calls (call `reset_surface_warnings()` first). They fail today.
- [ ] T009 [P] [L:engine] [US1] [BE] Write a failing test module `core/engine/ze-core/tests/orchestration/nodes/test_judgment_surface_errors.py`, reusing the fakes and builders already in `test_routing_nodes.py`, `test_skills_node.py`, `test_tier_node.py` and `test_memory_judgments.py`:
  - `embed_route` with a calibrated `EmbeddingRouter` whose System One client raises → rows `agent`, `multi_specialist`, `surface="routing"`, `skip_reason="error"`, bars `choice_trust` 0.5 and `multi_specialist_hold` 0.5;
  - `match_skills` with a calibrated `SkillMatcher` whose client raises → rows `skill`, `needs_skill`, `surface="skills"`, `skip_reason="error"`, bars `choice_trust`, `needs_skill_hold`;
  - `choose_tier` with a calibrated `TierJudge` whose client raises → one row `needs_deep_reasoning`, `surface="complexity"`, `skip_reason="error"`, bar `simple_max`; the tier stays `full`;
  - `write_memory` with a fake `commitment_intake` returning a `SimpleNamespace` with `outcome=SimpleNamespace(kind="fallback", reason="error", link_kind=None)`, `fact=<an empty FactAdmission(path="haiku")>`, `loop=None`, `links=()` and `judgment` built by `ze_agents.judgment.judge` from a raising client over six questions → six rows with `skip_reason="error"` and the six bars, plus the `intake_outcome` row `fallback:error`;
  - a timeout result keeps `timeout` on every routing row;
  - an enabled, uncalibrated routing surface makes no call and writes no rows.
  They fail today (the nodes take `RoutingJudgment`-style carriers and bar maps).

### Implementation for User Story 1 (`engine`)

- [ ] T010 [L:engine] [US1] [BE] In `core/engine/ze-core/ze_core/routing/judge.py`, make `RoutingSurfaceConfig` subclass `SurfaceConfig` (keep its fields, order and defaults; declare `SURFACE="routing"`, `BARS={"choice_trust": Q_AGENT, "multi_specialist_hold": Q_MULTI}`, `EXTRAS={"shortlist_k": _shortlist_k, "screen_hint": <literal True>}`), delete its own `calibrated`, delete `routing_surface_config` and the `_bar` partial, and add `read_decision(decision) -> DecisionUse` (research R4). Update `core/engine/ze-core/ze_core/routing/factory.py` to `RoutingSurfaceConfig.from_settings(config)`. Update `core/engine/ze-core/tests/routing/test_routing_judge.py` and `test_router_factory.py`: construction and import edits only.
- [ ] T011 [L:engine] [US1] [BE] In `core/engine/ze-core/ze_core/routing/router.py`, rewrite `EmbeddingRouter._judge`: keep the `state is None`/fewer-than-2-ranked early return, then `gate(self._surface, self._system_one)` (a reason → no record), build the shortlist (fewer than 2 → no record), then `judge(..., decide=lambda r: decide(r, surface, names), read=read_decision)`. Retype `RoutingEnvelope.judgment` in `core/engine/ze-core/ze_core/routing/types.py` to `Judgment | None` and `_envelope`'s parameter to match. Update `core/engine/ze-core/tests/routing/test_router.py` and `test_router_choice.py`: construction and import edits only.
- [ ] T012 [L:engine] [US1] [BE] In `core/engine/ze-core/ze_core/routing/tier.py`: `ComplexitySurfaceConfig` subclasses `SurfaceConfig` (`SURFACE="complexity"`, `BARS={"simple_max": Q_DEEP}`); delete `complexity_surface_config`; `decide_tier` uses `valid_noul(answer)` instead of its inline checks (FR-008; outcomes unchanged, research R12); add `read_decision`; `TierJudge.choose` calls `judge()`; `TierOutcome.judgment` is `Judgment | None`; delete `TierJudge.warn_uncalibrated_once` and `_uncalibrated_warned`. In `core/engine/ze-core/ze_core/orchestration/nodes/tier.py`, replace the `enabled`/`calibrated` checks with `gate(judge.surface, <the judge's client>)` mapping `"disabled"` → `off` and `"uncalibrated"` → `uncalibrated` (expose the client as a `TierJudge` property if needed). Update `routing/factory.py` (`ComplexitySurfaceConfig.from_settings`) and `apps/ze-api/ze_api/api/v0/system/models.py`. Delete `RoutingJudgment` from `routing/types.py`. Update `core/engine/ze-core/tests/routing/test_tier.py`, `tests/orchestration/nodes/test_tier_node.py` (patch `ze_agents.judgment.log` instead of `ze_core.routing.tier.log`, call `reset_surface_warnings()`), `tests/orchestration/test_tier_graph.py`, `tests/test_container_tier_judge.py` and `apps/ze-api/tests/test_container_tier_judge.py`: construction, import and patch-target edits only.
- [ ] T013 [L:engine] [US1] [BE] In `core/automation/ze-skills/ze_skills/judge.py`, `SkillsSurfaceConfig` subclasses `SurfaceConfig` (`SURFACE="skills"`, `BARS={"choice_trust": Q_SKILL, "needs_skill_hold": Q_NEEDS}`, `EXTRAS={"shortlist_k": _shortlist_k, "shortlist_floor": _shortlist_floor}`); delete `skills_surface_config` and the `_bar` partial (the floor parser calls `parse_bar(..., surface="skills")`); add `read_decision`. In `ze_skills/matching.py`, `SkillMatcher.match` uses `gate` then `judge` (keep the E5 fallbacks and the shortlist step). Delete `SkillsJudgment` from `ze_skills/types.py`; `SkillMatchOutcome.judgment` is `Judgment | None`. Update `ze_skills/bootstrap.py` (`SkillsSurfaceConfig.from_settings`). Update `core/automation/ze-skills/tests/` (`test_skills_judge.py`, `test_matching.py`, `test_types.py`, `test_bootstrap.py`): construction and import edits only. `make test-skills`.
- [ ] T014 [L:engine] [US1] [BE] In `core/engine/ze-core/ze_core/orchestration/nodes/routing.py`, `skills.py` and `tier.py`, build rows with `judgment_rows(judgment)` and drop the bar maps and the `surface=` arguments. In `core/engine/ze-core/ze_core/orchestration/nodes/memory.py` (judgment-row code only: `_outcome_row` and the row-building intake branch of `write_memory`; lines 83-101 and 156-177 on `5426cce1`), build intake rows with `judgment_rows(intake.judgment)` and make `_outcome_row` read `intake.judgment.result.latency_ms` and `intake.judgment.skip_reason`; drop the `intake_bars` import. T009 passes.

### Implementation for User Story 1 (`ws`)

- [ ] T015 [L:ws] [US1] [BE] In `core/cognition/ze-worldstate/ze_worldstate/commitment_judge.py`, `CommitmentIntakeSurfaceConfig` subclasses `SurfaceConfig` (`SURFACE="commitment_intake"`, `BARS` = the six holds mapped to their questions, data-model.md); delete `commitment_intake_surface_config`, `_BAR_NAMES` and the `_bar` partial; add `read_decision(outcome)`. Do not touch `decide()` or `IntakeOutcome` (203 owns the loop kinds). Update `core/cognition/ze-worldstate/tests/test_commitment_judge.py` and `tests/commitment_fixtures.py`: construction and import edits only.
- [ ] T016 [L:ws] [US1] [BE] The intake builds its loop admission through `LoopInflow.finish`, so the loop side moves first. In `core/cognition/ze-worldstate/ze_worldstate/loop_judge.py`, `LoopGateSurfaceConfig` subclasses `SurfaceConfig` (`SURFACE="loop_gate"`, `BARS={"loop_hold": Q_CONCERN, "resolves_hold": Q_RESOLVES}`); delete `loop_gate_surface_config` and the `_bar` partial; add `read_decision`; leave `DecisionKind`, `LoopGateDecision` and `decide` alone (203). In `ze_worldstate/types.py`, `LoopAdmission` keeps `decision`, `commit`, `source` and gets `judgment: Judgment | None = None` in place of `judgment`, `question_ids`, `question_kinds`, `consumed`, `skip_reason`. In `ze_worldstate/admission.py`: `finish(text, provenance, decision, *, judgment=None)`; `_judge` uses `gate` (`disabled`/`uncalibrated`/`unavailable` → `LoopGateDecision("fallback", <reason>)`, with the provenance check kept before the call) and `judge()`, and passes the record to `finish`; `_log` logs `consumed` and `skip_reason` from the record, else the decision reason for a fallback (research R10). Do not touch `commit_for` or the commit attachment (203). Update `core/cognition/ze-worldstate/tests/test_loop_judge.py`, `test_admission.py` and `test_loop_evidence_plumbing.py`: construction and import edits only.
- [ ] T017 [L:ws] [US1] [BE] In `core/cognition/ze-worldstate/ze_worldstate/intake.py`: `IntakeAdmission` keeps `outcome`, `fact`, `loop`, `links` and gets `judgment: Judgment | None = None` (delete `question_kinds`, `consumed`, `skip_reason` and the `question_ids` property); `admit()` uses `gate` (`disabled`/`uncalibrated`/`unavailable` → `_fallback` with that reason and no record) and `judge()` (an exception yields a record and `decide()` returns `fallback/error`); `CommitmentIntake._fallback` takes `judgment` and puts it on the admission; `CommitmentIntake._apply` puts the record on the `IntakeAdmission` it builds; stop setting `fact.skip_reason` (in `_fallback`) and `FactAdmission(judgment=…, question_ids=…, consumed=…)` (in `_apply` and its fact helper). In `_loop_admission` (203's function), only drop the `skip_reason=` argument that `finish` no longer takes. Leave `_LOOP_KIND` and `_apply`'s loop branch alone (203). T008 passes; `make test-worldstate`.
- [ ] T018 [L:ws] [US1] [BE] In `core/cognition/ze-memory/ze_memory/types.py`, `FactAdmission` keeps `facts` and `path` only (delete `judgment`, `question_ids`, `consumed`, `skip_reason`; Clarifications 2026-10-26). Update `core/cognition/ze-memory/tests/test_extractor_admission.py` and the remaining `core/cognition/ze-worldstate/tests/` files (`test_intake.py`, `test_corroboration_flow.py`): construction and import edits only. `make test-memory test-worldstate`.

**Checkpoint**: US1 holds on the `engine` and `ws` branches. After `lead` merges both (engine first), `make test-py` is green.

---

## Phase 4: User Story 2 - Adding a judgment point is questions, state and decide (Priority: P2)

**Goal**: no node builds a bar map, the glue is gone, and the background surfaces use the same module.

**Independent Test**: T002's `_Demo` surface and T004's rows (lead), plus `uv run pytest core/engine/ze-core/tests/orchestration/nodes/test_judgment_bars.py -q` (quickstart.md §3).

- [ ] T019 [P] [L:engine] [US2] [BE] Rework `core/engine/ze-core/tests/orchestration/nodes/test_judgment_bars.py` to build each surface's record through its real orchestration (router, matcher, tier judge, a fake intake carrying a `Judgment`) and assert each node's rows carry the surface and the bars from the record alone; keep "reads the surface in force each turn" for the intake (two settings, two records). Delete `test_fact_fallback_rows_have_fact_judge_surface_and_no_bar`. It fails until T020.
- [ ] T020 [L:engine] [US2] [BE] Delete `core/engine/ze-core/ze_core/orchestration/judgment_bars.py`. In `core/engine/ze-core/ze_core/orchestration/nodes/memory.py`, delete the non-intake judgment branch of `write_memory` (the `if fact_result is not None and fact_result.judgment is not None:` block, lines 182-193 on `5426cce1`; the `else:` keeps only the `_run_fact_extractor` call) and the `FACT_QUESTIONS` import (FR-005, research R11). Update the remaining ze-core tests that import `judgment_bars`, build carriers or call `judgments_from_result` through the nodes: `tests/orchestration/nodes/{test_routing_nodes,test_memory,test_memory_judgments,test_extractor_dual_write}.py`, `tests/orchestration/{test_skills_node,test_nodes,test_loop_admission_node,test_context_continuity_composition,test_compaction_readout}.py`, `tests/conversation/{test_tool_sink,test_retry_rewind,test_turn_telemetry_stamp}.py`, `tests/telemetry/{test_turn_stub,test_turn_telemetry}.py`: construction, import and patch-target edits only. T019 passes; `make test-core`.
- [ ] T021 [P] [L:ws] [US2] [BE] In `core/cognition/ze-worldstate/ze_worldstate/corroboration_judge.py`, `CorroborationSurfaceConfig` subclasses `SurfaceConfig` (`SURFACE="corroboration"`, `BARS={"corroborate_hold": Q_SAME, "promote_hold": Q_SAME}`, `consistent()` = `corroborate_hold <= promote_hold`); delete `corroboration_surface_config` and the `_bar` partial; add `read_decision`; leave `decide` alone. In `ze_worldstate/corroboration.py`, `_corroborate` uses `gate` (any reason → link only, as today) and `_judge` returns `judge()`'s `(record, decision)`; the log line reads the record. Do not touch the effect side (203). Update `core/cognition/ze-worldstate/tests/test_corroboration_judge.py`, `test_corroboration.py` (call `reset_surface_warnings()` in `test_enabled_uncalibrated_warns`) and `test_corroboration_flow.py`: construction, import and patch-target edits only. `make test-worldstate`.
- [ ] T022 [L:engine] [US2] [PLATFORM] Engine lane gate: `make test-core test-skills lint` and `uv run pytest apps/ze-api/tests/test_container_tier_judge.py -q` green; `rg -n "RoutingJudgment|SkillsJudgment|judgment_bars|bar_map|intake_bars|routing_surface_config|complexity_surface_config|skills_surface_config|warn_uncalibrated_once" --type py core apps` returns nothing outside `eval/`. Ask Vigil to review the lane.
- [ ] T023 [L:ws] [US2] [PLATFORM] Worldstate lane gate: `make test-worldstate test-memory lint` green; `rg -n "loop_gate_surface_config|corroboration_surface_config|commitment_intake_surface_config|_BAR_NAMES|question_ids|\.question_kinds" --type py core/cognition` returns nothing. Ask Vigil to review the lane.

**Checkpoint**: every surface uses `ze_agents.judgment`; no node holds trace glue.

---

## Phase 5: User Story 3 - Calibration runs the production surface (Priority: P3)

**Goal**: one harness; every System One runner parses its config and calls `decide()` through the production surface; `--check-sets` and verdicts unchanged.

**Independent Test**: `uv run pytest apps/ze-api/tests/calibration -q` and the quickstart.md §4–§5 checks.

### Golden capture (on the contract-step commit, before any surface changes)

- [ ] T024 [L:calib] [US3] [BE] Create `apps/ze-api/tests/calibration/replay.py` with `ReplayClient` (deterministic answers from `sha256(json.dumps(state, sort_keys=True) + question_id)`: Noul in [0, 1], a Choice over the question's criteria keys with probabilities summing to 1 and a confidence, fixed `model="replay"`, `latency_ms` from the hash), `HashEmbedder` (`encode_query`/`encode_passage` returning unit vectors from SHA-256, `normalize_embeddings` accepted) and `FakeHaiku` (the LLM client the loop-gate baseline calls, returning a deterministic JSON gate reply). Add `apps/ze-api/tests/calibration/test_replay.py`: the same input gives the same answer twice; Choice answers are always among the criteria keys.
- [ ] T025 [L:calib] [US3] [PLATFORM] Create `apps/ze-api/tests/calibration/capture_golden.py`, which runs each mode in [contracts/calibration-harness.md](contracts/calibration-harness.md#golden-checks) in-process with the fakes patched in (`OPENROUTER_API_KEY=replay`, `ze_core.openrouter.system_one.OpenRouterSystemOneClient`, each runner's embedder loader, the loop-gate Haiku client, complexity's `VERDICT_MARKER` pointed at a temp path), normalises wall-clock lines, and writes stdout and the exit code to `apps/ze-api/tests/calibration/golden/<runner>-<mode>.txt`. Run it on the T007 contract commit (before `engine` or `ws` merge) and commit the golden files. Record the commit it ran on in the "202 Handoffs" note.
- [ ] T026 [L:calib] [US3] [BE] Create `apps/ze-api/tests/calibration/test_calibration_golden.py`, which re-runs every captured mode the same way and compares output and exit code to its golden file exactly. It passes on the contract commit.

### Harness and runners (after `engine` and `ws` are merged; rebase first)

- [ ] T027 [L:calib] [US3] [BE] Create `eval/calibration/harness.py` with the interface in [contracts/calibration-harness.md](contracts/calibration-harness.md#harness-interface) (rows, set shape, config through `from_settings`, live run, reliability bins, bar grid, verdict printout, save/load, CLI). Add `apps/ze-api/tests/calibration/test_harness.py`: `load_jsonl` rejects duplicate ids; `surface_config(LoopGateSurfaceConfig, loop_hold=0.9, resolves_hold=0.9)` is calibrated and equals `LoopGateSurfaceConfig.from_settings(...)`; `save_results` then `load_results` round-trips `SystemOneResult` maps (ok and skip, Choice and Noul answers); `reliability_bins` and `bar_grid` match hand-computed values on a small input.
- [ ] T028 [L:calib] [US3] [BE] Move `eval/calibration/loop_gate.py` onto the harness: keep its `Row` gold columns, quotas, `Counts`, scoring, Haiku baseline and acceptance rule; build every config with `harness.surface_config` (this fixes the `LoopGateSurfaceConfig(True, 0.9, 0.9, 0.9)` call at `loop_gate.py:536`, research R15); add `--save`/`--load`. Add a test in `apps/ze-api/tests/calibration/test_loop_gate_calibration.py` that forces the "no bar pair passes" path with `ReplayClient` and runs without error. Update the rest of that file: construction and import edits only. T026 stays green.
- [ ] T029 [L:calib] [US3] [BE] Move `eval/calibration/corroboration.py` onto the harness (same rules as T028; keep the E5 baseline and the per-language verdict). Update `apps/ze-api/tests/calibration/test_corroboration_calibration.py`: construction and import edits only. T026 stays green.
- [ ] T030 [L:calib] [US3] [BE] Move `eval/calibration/complexity.py` onto the harness (keep `Quota`, `Verdict`, the infrastructure-failure exit 3, `VERDICT_MARKER` and `--rerun`; build configs with `harness.surface_config(ComplexitySurfaceConfig, simple_max=...)`). Update `apps/ze-api/tests/calibration/test_complexity_calibration.py`: construction and import edits only. T026 stays green.
- [ ] T031 [L:calib] [US3] [BE] Move `eval/calibration/skills.py` onto the harness (keep `--recall`, the roster and the shortlist recall; `surface_defaults()` reads `harness.configured(SkillsSurfaceConfig)`). Update `apps/ze-api/tests/calibration/test_skills_calibration.py`: construction and import edits only. T026 stays green.
- [ ] T032 [L:calib] [US3] [BE] Move `eval/calibration/routing.py` onto the harness (keep `--dataset`, `--recall`, `--k`, the per-set verdicts and the research-to-companion check; build grid configs with `harness.surface_config(RoutingSurfaceConfig, ...)`). Update `core/engine/ze-core/tests/routing/test_calibration_script.py` and `test_calibration_dataset.py`: construction and import edits only. T026 stays green.
- [ ] T033 [L:calib] [US3] [BE] Move `eval/calibration/commitment_intake.py` and `commitment_intake_baseline.py` onto the harness (keep `SPENT_SETS`, `--replay` semantics, the old-pipeline baseline, `suggest_bars` and the verdict rule; `parse_bars` becomes `harness.parse_bar_list` plus `harness.surface_config(CommitmentIntakeSurfaceConfig, ...)`). Leave the loop-kind string literals as they are (203 edits them after rebasing). T026 stays green.
- [ ] T034 [L:calib] [US3] [BE] Move `eval/calibration/open_query.py` onto the harness row helpers only (`load_jsonl`, `norm`, `blind_overlap`, `shape_report`). Update `core/arbitration/ze-priority/tests/test_open_query.py`: import edits only. Leave `companion_research_check.py` and `core/engine/ze-core/tests/routing/test_companion_research_check.py` unchanged unless an import breaks. T026 stays green.
- [ ] T035 [L:calib] [US3] [PLATFORM] In the `Makefile`, make `calibrate-skills`, `calibrate-loop-gate` and `calibrate-corroboration` pass `$(ARGS)` like the other `calibrate-*` recipes (the docs already show `--set holdout` and `--recall` for them).
- [ ] T036 [L:calib] [US3] [BE] Extend `apps/ze-api/tests/calibration/test_calibration_golden.py`: for each System One runner's live modes, run with `--save <tmp>` then `--load <tmp>` (commitment intake: its `--replay`) and assert the reloaded report equals the golden file; add a test that `rg`-style scans `eval/calibration/*.py` and finds no direct `*SurfaceConfig(` construction and no definition of `load_rows`, `_norm`, `report_reliability`, `report_grid`, `save_results`, `load_results`, `parse_bars`, `config_model`, `system_one_config` or `config_system_one` outside `harness.py`.
- [ ] T037 [L:calib] [US3] [PLATFORM] Measure SC-004: `wc -l eval/calibration/*.py` (harness included) against the 4,838 baseline; the total must be at most 3,628. Run `make calibrate-routing ARGS=--check-sets`, `make calibrate-complexity ARGS=--check-sets`, `make calibrate-loop-gate ARGS=--check-sets`, `make calibrate-corroboration ARGS=--check-sets`, `make calibrate-commitment-intake ARGS=--check-sets` and `make calibrate-open-query ARGS=--check-sets` (offline). Post the line counts and the outputs' exit codes to the "202 Handoffs" note.
- [ ] T038 [L:calib] [US3] [PLATFORM] Calibration lane gate: `make test lint` and `uv run pytest apps/ze-api/tests/calibration core/engine/ze-core/tests/routing/test_calibration_script.py core/engine/ze-core/tests/routing/test_calibration_dataset.py core/arbitration/ze-priority/tests/test_open_query.py -q` green. Ask Vigil to review the lane.

**Checkpoint**: calibration runs the production surface; golden output unchanged.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [ ] T039 [L:lead] [BE] After `engine`, `ws` and `calib` are merged: delete `surface_block` and `parse_bar` from `core/contracts/ze-agents/ze_agents/system_one.py` and move their tests from `core/contracts/ze-agents/tests/test_system_one.py` into `test_judgment.py` (new signature `parse_bar(value, name, *, surface)`); delete `judgments_from_result` and its old tests from `core/engine/ze-core/ze_core/conversation/messages/judgments.py` and `tests/conversation/test_judgments.py`. Run the quickstart.md §5 structural checks: `surface_block(` appears only in `ze_agents/judgment.py` (SC-003); no hit for the deleted names.
- [ ] T040 [L:lead] [PLATFORM] Full gates: `make test-py lint`; the quickstart.md §2–§6 commands; the §6 diff review shows no changed expected decision or bar in the surface decision tests (SC-005).
- [ ] T041 [L:lead] [PLATFORM] `graphify update .` on the floor, then `graphify affected` on `Judgment`, `judgment_rows`, `gate`, `judge` and `SurfaceConfig` to confirm the callers match plan.md's table, and on each deleted symbol to confirm none remains. Record the outcome with `graphify save-result ... --memory-dir /Users/joaoamatos/coding/ze/graphify-out/memory`.
- [ ] T042 [L:lead] [PLATFORM] Send Tarn (floor 203) the final floor commit, the new `LoopInflow.finish` signature and the `LoopAdmission`/`IntakeAdmission` shapes, so 203 can rebase once 202 lands, and name any golden file under `apps/ze-api/tests/calibration/golden/` that prints a loop-kind string 203 will rename; append it to the "202 Handoffs" note.

### Documentation (runs last, from the finished diff)

- [ ] T043 [P] [L:docs] [DOCS] Update `docs/system-one.md` (the "six surfaces" pattern paragraph names `ze_agents.judgment`, `SurfaceConfig` and `gate`/`judge`; add a short "Adding a judgment point" section: questions, state builder, a `SurfaceConfig` subclass with `SURFACE`/`BARS`/`EXTRAS`, pure `decide()`, `read_decision`; the Trace section says a failed call on any conversation-turn surface, the commitment intake included, writes skip rows with reason `error`; the calibration paragraph names `eval/calibration/harness.py` and `--save`/`--load`), `docs/configuration.md` (line 613 and every other uncalibrated or invalid-bar log name becomes `system_one_surface_uncalibrated` / `system_one_bar_invalid` with a `surface` field, logged once per process; `make calibrate-skills|loop-gate|corroboration` take `ARGS=`), `docs/eval.md` (the System One calibration section: the shared harness, `--save`/`--load`, the golden test), and `docs/testing.md` (the calibration golden test and `reset_surface_warnings()` for warning assertions). Check `docs/architecture.md` and fix any mention of `judgment_bars`, `RoutingJudgment` or per-node bar maps. Follow the `doc-style` skill.
- [ ] T044 [P] [L:docs] [DOCS] Update the package READMEs: `core/contracts/ze-agents/README.md` (a `judgment.py` row: surface config base, gate, judge, judgment record), `core/engine/ze-core/README.md` (trace rows come from `judgment_rows`; `judgment_bars.py` is gone), `core/automation/ze-skills/README.md`, `core/cognition/ze-worldstate/README.md` (surfaces declare `SurfaceConfig`; `LoopAdmission`/`IntakeAdmission` carry one `Judgment`) and `core/cognition/ze-memory/README.md` (`FactAdmission` is facts and path). Check `specs/arch/system-one-models.md` and add one line naming `ze_agents.judgment` as the shared orchestration if it describes the per-surface glue.
- [ ] T045 [L:docs] [DOCS] Update `AGENTS.md`: the `ze-agents` tree gains `judgment.py # SurfaceConfig, gate, judge, Judgment record — one orchestration for every System One surface`; the `ze_core/orchestration/` line drops anything about bar maps; the `eval/calibration/` line names `harness.py`; the phase table gains the 202 row (Implemented, one line in the table's style). Set the 202 row in `specs/README.md` and the Status line in `specs/phases/202-judgment-surface/spec.md` to Implemented.
- [ ] T046 [L:docs] [DOCS] Coverage check: `git diff --stat main...HEAD` and `rg -n "judgment_bars|RoutingJudgment|SkillsJudgment|judgments_from_result|_surface_config|commitment_intake_uncalibrated|loop_gate_uncalibrated|routing_surface_uncalibrated|skills_surface_uncalibrated|complexity_surface_uncalibrated|corroboration_uncalibrated" README.md docs core/*/*/README.md AGENTS.md specs/arch` return no stale mention; every public doc listed in T043–T045 is in the diff or noted as checked-unchanged in the "202 Handoffs" note.

---

## Dependencies & Execution Order

- **Setup (T001)** → **Contract step (T002–T007)**, all `lead`, in order.
- After T007, in parallel:
  - `calib` T024–T026 (golden capture on the contract commit, before any surface changes);
  - `engine` T009–T014, then T019–T022;
  - `ws` T008, T015–T018, then T021, T023.
- `lead` merges `engine`, then `ws` (engine first: it deletes the ze-core tests that build `FactAdmission` with judgment fields).
- `calib` rebases onto the merged floor branch, then T027–T038; `lead` merges it.
- `lead` T039–T042, then `docs` T043–T046, then `lead` merges `docs` and runs T040 again.
- Floor 203 rebases onto 202 after 202 lands (plan.md, Coordination with 203).

### Within each lane

- Tests first (T008, T009, T019, T024–T026) and fail before the code changes (T026 passes on the old code by design: it is the baseline).
- `engine`: T010 → T011 → T012 (deletes `RoutingJudgment` after router and tier use `Judgment`) → T013 → T014 → T019 → T020 → T022.
- `ws`: T015 → T016 → T017 → T018 → T021 → T023.
- `calib`: T024 → T025 → T026 → (rebase) → T027 → T028–T034 (one runner per task, T026 green after each) → T035 → T036 → T037 → T038.

## Parallel Opportunities

- After T007: `engine`, `ws` and `calib` (T024–T026) run at the same time in their own worktrees.
- Within `docs`: T043 and T044 touch different files.
- T008 (ws) and T009 (engine) are written at the same time.

```text
# After the contract step lands:
engine: T009 → T010 … T014
ws:     T008 → T015 … T018
calib:  T024 → T025 → T026
```

## Implementation Strategy

- **MVP (US1)**: contract step plus T008–T018. Every attempted judgment on a conversation turn leaves rows; the commitment intake no longer goes silent on an error.
- **US2** finishes the hard cut: no glue at the nodes, background surfaces on the same module.
- **US3** is independent of runtime behaviour and lands last; its golden baseline is captured first so the refactor can be checked runner by runner.
- Stop at any checkpoint and the floor branch is green.
