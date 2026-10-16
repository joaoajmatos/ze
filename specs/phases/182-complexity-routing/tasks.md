# Tasks: Complexity Routing

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Build gate**: Scope signed off by the user on 2026-10-16 (spec Clarifications). The Spec Architect (Corbel) stays on call for design questions.

**Tests**: Required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Unit tests use fakes: a call-counting fake `SystemOneClient` (`core/engine/ze-core/tests/support/routing.py`), `register_agent(..., model=, model_simple=)` helpers, `AsyncMock` pools. Default suites never call OpenRouter or System One.

**Lanes**: `[ENG]` = Claude Sonnet lane lead (engine, judgment, graph, calibration, gates). `[JR]` = OpenCode junior (exact files and behavior given). `[BLIND]` = a fresh agent that never sees the tuned set (T025 only). See Lanes at the end.

**Tags**: `[BE]` backend Python · `[WEB]` ze-web and generated client · `[PLATFORM]` config, Makefile, migration · `[DOCS]` docs, READMEs, specs.

**Normative references**: decision table, state, trace text: [contracts/tier-judgment.md](./contracts/tier-judgment.md). Types and calibration row: [data-model.md](./data-model.md). Blast radius: [plan.md](./plan.md). Held-out rules: [contracts/holdout-brief.md](./contracts/holdout-brief.md).

**Rules for the implementer**
- Before changing a signature in plan.md "Blast radius", run `graphify affected "<Symbol>" --depth 2` and update every caller in the same change. graphify has no unique node for `ComplexityEstimator` and does not see field reads; also run `rtk proxy grep -rn "complexity\|_resolve_model\|model_simple" --include='*.py' core apps eval`.
- Pre-v1 hard cut: no fallback to the regex, no compatibility kwargs, no kept-but-unused fields.
- No `print()`; `get_logger(__name__)`. No bare `Exception`/`ValueError` in domain code.
- The held-out file (T025) is written by the `[BLIND]` author and committed **before** the tuned set exists and before any live run; the ENG lead never opens it before T031 (FR-019).
- Enabling the surface is never part of these tasks' commits (FR-020); T033 is a separate commit, and only after an ENABLE verdict.
- Shared worktree: `git add <your paths>`; `git commit -m ... -- <paths>`. Never `git add -A`, `git stash`, or reset files you do not own. Commit only when the ENG lead or Maestro asks.
- If a step disagrees with the code you find, stop and report to the ENG lead; do not redesign.

**Ordering**: Phases run in order unless the Lanes section says otherwise. `[P]` tasks touch different files and may run together.

---

## Phase 0: Gate  [ENG]

- [x] T001 [ENG] [BE] Rebase onto `main`. Record: (a) the `zc` chain head (`ls core/engine/ze-core/ze_core/migrations/versions core/automation/ze-automation/ze_automation/migrations/versions plugins/ze-personal/ze_personal/migrations/versions`) and the next free number for T004; (b) `graphify update .` then `graphify affected` on `build_embedding_router`, `RoutingSurfaceConfig`, `EmbeddingRouter`, `MessageTrace`, `graph_builder`; (c) any difference from plan.md "Blast radius". Stop and report to the Spec Architect (or Maestro) on a difference.

## Phase 1: Setup

- [x] T002 [P] [ENG] [PLATFORM] `apps/ze-api/config/config.yaml`: under `system_one.surfaces.routing` delete `complexity_lookup_max` and its comment; after `corroboration` add `complexity:` with `enabled: false`, `simple_max: null` and the comment `# Phase 182: needs_deep_reasoning Noul picks model_simple after fetch_context/match_skills. Off = every agent runs its full model. Enable only after a held-out ENABLE in EN and PT (make calibrate-complexity).`
- [x] T003 [P] [JR] [PLATFORM] `Makefile`: add `calibrate-complexity:` running `uv run python eval/calibration/complexity.py $(ARGS)`, add it to `.PHONY`, and the help line `calibrate-complexity  LIVE System One over eval/calibration/complexity.jsonl; costs credits (--check-sets offline; --set holdout = the one verdict run)` beside `calibrate-corroboration`.
- [x] T004 [ENG] [PLATFORM] Create `core/engine/ze-core/ze_core/migrations/versions/zc0NN_drop_routing_log_tier.py` (number from T001(a); `down_revision` = chain head): upgrade `ALTER TABLE routing_log DROP COLUMN IF EXISTS complexity, DROP COLUMN IF EXISTS model_selected`; downgrade re-adds both as nullable `TEXT`. Follow `zc032_message_rollback.py` style.

## Phase 2: Foundational  [ENG]

**Purpose**: the tier module and trace type every story needs.

- [x] T005 [ENG] [BE] Fail-first `core/engine/ze-core/tests/routing/test_tier.py`: `complexity_surface_config` (missing block, invalid bar → None, `enabled` must be `True`); `resolve_agent_model` (simple with and without `model_simple`; `models.overrides[agent]` wins for both tiers; unknown agent → default); `decide_tier` for every row of the contracts decision table, including `noul == simple_max` → simple, NaN, out-of-range, wrong type, skip.
- [x] T006 [ENG] [BE] Create `core/engine/ze-core/ze_core/routing/tier.py` per plan "Design" and the contract: `Q_DEEP`, `TIER_INSTRUCTIONS` (research R2 draft), `ComplexitySurfaceConfig`, `complexity_surface_config`, `resolve_agent_model`, `build_tier_question`, `TierDecision`, `decide_tier`, `TierJudge`, `TierOutcome`. Rename `judge._bar` to public `parse_bar` and use it in both modules. T005 passes.
- [x] T007 [ENG] [BE] `core/engine/ze-core/ze_core/routing/factory.py`: add `build_tier_judge(*, config, system_one_client) -> TierJudge`; drop the `estimator` kwarg from `build_embedding_router`. Extend `tests/routing/test_router_factory.py`: the judge carries the client and the parsed surface; off by default.
- [x] T008 [ENG] [BE] `core/engine/ze-core/ze_core/conversation/messages/types.py`: add `TierTrace` and `MessageTrace.tier: TierTrace | None = None`; `orchestration/state.py`: add `tier` to `AgentState`. Extend the trace JSON-safety test (117) with a `tier` value.

## Phase 3: User Story 1 — Flag off: every agent runs its full model; regex and Score cut (P1)

**Goal**: shipped config → full model everywhere, no tier request, regex gone, routing request without the Score.
**Independent test**: spec US1.

- [x] T009 [ENG] [US1] [BE] Fail-first: in `tests/routing/test_router.py` replace `test_uses_model_simple_for_simple_prompt` with `test_route_assigns_full_model` (short EN, short PT, long prompt; agent with `model_simple`) covering `route`, `route_forced` and the single-agent envelope; in `tests/routing/test_router_choice.py` assert the routing request's questions are exactly `{"agent", "multi_specialist"}` and delete the Score/complexity assertions (L26, L94, L125, L193-320); in `tests/routing/test_routing_judge.py` delete complexity cases (L72-77, L96-110 complexity entries, L336-364) and add "`RoutingSurfaceConfig` has no `complexity_lookup_max`".
- [x] T010 [ENG] [US1] [BE] `ze_core/routing/judge.py`: delete `Q_COMPLEXITY`, `_COMPLEXITY_*`, `COMPLEXITY_SCORE_MAX`, `normalise_complexity_score`, `_complexity`, `RoutingSurfaceConfig.complexity_lookup_max`, `RoutingDecision.complexity`; `QUESTION_IDS` = agent + multi. `ze_core/routing/router.py`: drop `estimator`; replace `_resolve_model` with `_full_model(agent)` → `resolve_agent_model(agent, "full", self._app_config)`; remove complexity from `_envelope`, `_single_agent_envelope`, `route_forced`. `ze_core/routing/types.py`: delete `RoutingEnvelope.complexity` and `complexity_source`. Delete `ze_core/routing/complexity.py` and `tests/routing/test_complexity.py`. `ze_core/bootstrap.py`: delete `EngineStack.estimator` and its construction. Update `tests/support/routing.py` (no Score answer). T009 passes.
- [x] T011 [ENG] [US1] [BE] Fail-first then fix `ze_core/orchestration/nodes/routing.py`: `decompose` sets every subtask to `resolve_agent_model(agent, "full", router._app_config)` with no classify; `apply_conductor_rewrite` stops copying complexity. `ze_core/orchestration/nodes/context.py` `_open_query_envelope`: full model, no complexity fields. Update `tests/orchestration/nodes/test_routing_nodes.py` (L413-567: delete Score-tier tests; add "decompose assigns full models") and `test_context.py` (L432-450).
- [x] T012 [ENG] [US1] [BE] `ze_core/routing/store.py`: `write_log` inserts without `complexity` / `model_selected`; update its test (SQL has neither column). Run `make migrate` on dev to check T004 applies and downgrades.
- [x] T013 [P] [JR] [US1] [BE] `eval/calibration/routing.py`: delete every complexity code path (lookup-bar suggestion, Score histogram, `gold_complexity` reads, the `complexity_lookup_max` grid term at `grid_metrics` and `report`). Delete the `gold_complexity` field from `eval/calibration/routing.jsonl`, `routing_holdout.jsonl`, `routing_holdout2.jsonl` with a script that changes nothing else (diff shows only that key removed). Update `core/engine/ze-core/tests/routing/test_calibration_script.py` (L43-132) and `test_calibration_dataset.py` (L25-82) to match. `python eval/calibration/routing.py --recall` still runs.
- [x] T014 [P] [JR] [US1] [BE] `core/engine/ze-core/tests/conversation/test_judgments.py` (L98-139) and `apps/ze-api/tests/api/test_feedback_evidence.py` (L60, L95): replace the `complexity` Score fixtures with the `needs_deep_reasoning` Noul (kind `noul`). No production change.

**Checkpoint**: `make test-core` green; `grep -rn ComplexityEstimator core apps eval` empty.

## Phase 4: User Story 2 — The tier follows the task (P1)

**Goal**: `choose_tier` after `match_skills`, with the task state.
**Independent test**: spec US2.

- [x] T015 [ENG] [US2] [BE] Fail-first `core/engine/ze-core/tests/orchestration/test_tier_state.py`: `build_tier_state` from a synthetic `AgentState` with `routing_hints` (two active goals), `agent_context` (10 messages, a resume recap, `screen_context_note`, `procedure_matches`, two `active_skills`), `memory_context` with 7 chunks. Assert field names exactly `task, conversation, recap, memory, focus, skill` (the `agent` field was dropped after tuning, FR-006 amended; see research R12); every cap from research R3; the last 8 prior messages kept, oldest dropped; the current message not duplicated in `conversation`; empty fields omitted; image turns use the caption; the routing suffix text is absent from the instruction.
- [x] T016 [ENG] [US2] [BE] Implement `build_tier_state` in `ze_core/orchestration/judgment_state.py` (reuse `_extract_memory_chunks` logic from `conversation/turn.py` by moving it to a shared helper in `conversation/messages/` if needed; update `turn.py` to import it). T015 passes.
- [x] T017 [ENG] [US2] [BE] Fail-first `core/engine/ze-core/tests/orchestration/nodes/test_tier_node.py`: graph-level `choose_tier` with a recording fake client: (a) the state it receives is `build_tier_state(state)`; (b) the call uses `max_attempts=1`; (c) judgment rows are appended after existing routing and skill rows; (d) cost agent context is `router` during the call and restored after; (e) a planning-exchange fixture ("ok go ahead with that plan", EN and PT) sends the earlier turns.
- [x] T018 [ENG] [US2] [BE] Create `ze_core/orchestration/nodes/tier.py` (`choose_tier`) per plan "Design"; export it in `nodes/__init__.py`; in `orchestration/graph.py` add the node and replace `match_skills → capability_check` with `match_skills → choose_tier → capability_check`. Add `"tier_judge"` to `Container._build_config` (`ze_core/container.py`) and `ZeContainer._build_config` (`apps/ze-api/ze_api/container.py`), built with `build_tier_judge` beside `build_embedding_router` in both containers. Add a container test per call site asserting `tier_judge` reaches `configurable` with the YAML surface. T017 passes.

## Phase 5: User Story 3 — Light model only when System One is sure (P1)

**Independent test**: spec US3.

- [x] T019 [ENG] [US3] [BE] Extend `test_tier_node.py`: Noul below / equal / above `simple_max` → `simple` / `simple` / `full` with the resolved `model_simple` or full model on `envelope.subtasks[0].model`; skip, raising client, timeout skip, malformed answer → full with `decided_by` `skip` / `skip` / `skip` / `invalid_answer`; surface off → `off` and zero calls; `simple_max` null → `uncalibrated`, zero calls, one warning across two turns; agent without `model_simple` and agent with an override that equalises tiers → `no_simple_model`, zero calls. Implement any missing branch.
- [x] T020 [ENG] [US3] [BE] Confirmation and retry: a test that runs a draft turn to `await_confirmation`, resumes, and asserts `choose_tier` ran once and the resumed `execute_tool` used the decided model; a retry-mode turn judges again.

## Phase 6: User Story 4 — Compound and conductor turns stay full (P2)

- [x] T021 [ENG] [US4] [BE] Extend `test_tier_node.py`: a two-subtask parallel envelope, an `is_compound` envelope, and a conductor-rewritten envelope with `conductor_hint` → every subtask on its full model, `decided_by == "compound"`, zero calls. Assert `tests/.../test_delegate*.py` still passes unchanged (delegates run `self.model`).

## Phase 7: User Story 5 — The tier is explainable (P2)

- [x] T022 [ENG] [US5] [BE] `ze_core/orchestration/nodes/trace.py` `record_trace` copies `state["tier"]` to `MessageTrace.tier`; `ze_core/conversation/turn.py` sends a partial `trace_update` `{"tier": {...}}` on `on_chain_end` of `choose_tier`. Tests: the persisted trace and the partial frame carry the record for each `decided_by`.
- [x] T023 [JR] [US5] [BE] `apps/ze-api/ze_api/api/schemas.py`: `TierTraceResponse` (`agent`, `tier: Literal["simple","full"]`, `decided_by`, `model`); `tier: TierTraceResponse | None = None` on `MessageTraceResponse` (the batch `MessageTraceEntry` wraps it, so it carries no `tier` of its own); the WS `trace_update` schema the same. Extend the message-trace route test and the WS frame schema test. Run `make codegen` and commit `packages/ze-client` generated files.
- [x] T024 [JR] [US5] [WEB] `apps/ze-web/src/widgets/message-trace/ui/RoutingBadge.tsx`: optional `tier` prop rendering one line with the text table in contracts/tier-judgment.md (nothing for `no_simple_model`); pass `trace.tier` from `MessageTracePanel.tsx` and `widgets/trace-panel/ui/RoutingSection.tsx`. Vitest `RoutingBadge.test.tsx` covers each text and the absent case. `make test-web` and `make typecheck-web` green.

## Phase 8: User Story 6 — Calibration and the held-out verdict (P1)

**Order matters**: T025 (blind) is committed before T026 starts.

- [ ] T025 [BLIND] [US6] [BE] Quoin (a fresh junior) with only [contracts/holdout-brief.md](./contracts/holdout-brief.md) writes `eval/calibration/complexity_holdout.jsonl` (≥ 24 rows per language, quotas in the brief), checks the schema and quotas by hand against the brief, and commits only that file. After T026 lands, the ENG lead runs `make calibrate-complexity ARGS="--check-sets"` (it prints counts only, never held-out row text) and sends any quota gap back to the same author.
- [x] T026 [ENG] [US6] [BE] `eval/calibration/complexity.py` (pattern: `loop_gate.py`): `--check-sets` (offline: schema, quotas from the brief, per-language counts; prints counts, never row text, for the held-out file), `--set tuned|holdout`, `--simple-max`, `--live` guard; builds each row's state through `build_tier_state` on a synthetic `AgentState`/`AgentContext`; one request per row with `max_attempts=1`; records Noul, latency, skip reason. Pure functions `suggest_simple_max(rows)` (research R8 rule) and `verdict(rows, simple_max)` (FR-016). Report per language: false downgrades, light recall, precision, skipped/invalid share, latency p50/p90, per-agent counts, Noul histogram by gold tier, verdict.
- [x] T027 [P] [JR] [US6] [BE] `apps/ze-api/tests/calibration/test_complexity_calibration.py`: `suggest_simple_max` (separable → highest value below every `full` row, rounded down to 0.05; overlapping → None); `verdict` (one false downgrade in one language → KEEP OFF; recall 0.49 → KEEP OFF; 11% skipped → KEEP OFF; all pass → ENABLE per language and overall only if both); `--check-sets` on fixture files flags a missing quota.
- [x] T028 [ENG] [US6] [BE] Write `eval/calibration/complexity.jsonl` (tuned, ≥ 40 rows per language, same quotas scaled, own wording). The ENG lead does not open `complexity_holdout.jsonl`.
- [x] T029 [ENG] [US6] [BE] Live tuned run (`make calibrate-complexity`, costs credits). Iterate `TIER_INSTRUCTIONS` and the R3 caps on the tuned set only. Record each run's figures in research.md as "R12 tuning notes".
- [x] T030 [ENG] [US6] [DOCS] Freeze: write the chosen `simple_max`, the final instruction text and the date into research.md R12 and commit before T031.
- [x] T031 [ENG] [US6] [BE] One held-out run at the frozen bar (`ARGS="--set holdout --simple-max <frozen>"`). Record the full report and the verdict in research.md R12 and spec.md Clarifications. Update the `complexity:` comment in `config.yaml` with the date and figures; keep `enabled: false` and `simple_max: null` in this commit either way.
- [x] T032 [P] [ENG] [US6] [BE] Report-only routing check after the Score cut: `make calibrate-routing` on the tuned `routing.jsonl` once; record accuracy and ECE beside 167's in research.md R12. Not gating; a drop beyond 167's figures is reported to the Maestro.
- [x] T033 [ENG] [US6] [PLATFORM] **Only after an ENABLE for EN and PT and the user's go-ahead via the Maestro**: a separate commit sets `system_one.surfaces.complexity.enabled: true` and `simple_max: <frozen>` with the dated held-out figures. On KEEP OFF, skip this task and record why in the Handoffs note.

## Phase 9: Polish and docs

- [x] T034 [P] [JR] [DOCS] `docs/configuration.md`: delete `complexity_lookup_max` from the routing surface (L419-465); add the `system_one.surfaces.complexity` block (keys, off by default, what off means, the bar rule, `make calibrate-complexity`); fix the `model_simple` sentence (L136). `docs/system-one.md`: add the surface row (phase 182, Noul `needs_deep_reasoning`, runs after `match_skills`, ships off) and remove the Score from the routing description (L71-119). Follow the `doc-style` skill.
- [x] T035 [P] [JR] [DOCS] `docs/architecture.md`: rewrite "Cost-aware routing" (L78-93) for the tier step; add `choose_tier` to the graph flow; agent table "default model tier" (L337). `docs/adding-an-agent.md` (L194, L230) and `docs/sdk.md` (L184): `model_simple` is used only when the complexity surface is on and System One judges the task light. `docs/package-architecture.md` (L161) and `core/engine/ze-core/README.md` (L11, L26): replace `ComplexityEstimator` with `routing/tier.py`. `README.md` L63: replace the word-count sentence. `docs/eval.md`: `make calibrate-complexity`. Follow the `doc-style` skill; diagram only if the graph-flow figure in architecture.md is already a diagram.
- [x] T036 [P] [JR] [DOCS] `AGENTS.md`: layout line under `routing/` (EmbeddingRouter, tier judge; no ComplexityEstimator); LangGraph graph flow (`match_skills → choose_tier → capability_check`); essential commands `make calibrate-complexity`; migration ownership row for ze-core (the `routing_log` drop); phase table row 182. `specs/README.md` index row. Status notes on `specs/phases/164-routing-choice-after-e5/spec.md` and `167-routing-choice-criteria/spec.md` ("complexity Score removed by 182"), and on the stale routing design in `specs/core/ze-core.md` (L23, L29, L79) and `specs/core/04-routing.md` (the `ComplexityEstimator` section, `_resolve_model`, `routing_log.model_selected`): mark each "superseded by 182" (Soffit review L4).
- [x] T037 [JR] [DOCS] `specs/arch/system-one-models.md` (after T031): O2 note that 182 replaced the Score; new "Specified now" row O11 (tier judgment, Noul, after `match_skills`, phase 182, ship state); Sequencing item 7; Appendix A `ComplexityEstimator` row → "182: tier Noul after match_skills; full model on off/skip"; Appendix B file index rows (`routing/tier.py`, `orchestration/nodes/tier.py`); a "182 tuning notes" block quoting R12.
- [ ] T038 [ENG] [BE] Gates: `make lint`, `make test-py`, `make test-web`, `make typecheck-web`, `make test-pg` (the migration), `make calibrate-complexity ARGS="--check-sets"`; quickstart.md offline steps; the grep in quickstart.md returns only `specs/` history.
- [ ] T039 [ENG] [DOCS] Docs coverage check: `git diff --stat main...HEAD`; confirm each changed public surface (config keys, Make target, graph node, trace field, REST/WS field, migration, deleted regex) appears in at least one doc from T034–T037 and in AGENTS.md; list and fix gaps.
- [ ] T040 [ENG] [DOCS] Set spec.md **Status** to `Implemented (surface off)` or `Implemented (surface enabled)`; check off tasks via `python3 .specify/extensions/companion/scripts/write-context.py --append ...` then `--materialize` (never hand-edit checkboxes); run the speckit after-implement hook.

---

## Dependencies

- T001 → everything. T002–T004 setup. T005–T008 before any story.
- US1 (T009–T014) before US2 (the router must assign full models before the node swaps).
- US2 (T015–T018) before US3/US4 (T019–T021) and US5 (T022).
- T022 before T023 → T024.
- US6: T025 (blind) committed first; T026 after T016 (needs `build_tier_state`); T027 after T026; T028 after T025 is committed; T029 → T030 → T031 → (T033 only on ENABLE). T032 after T013 any time.
- Docs: T034–T036 after their code lands; T037 after T031; T038 → T039 → T040 last.

## Parallel examples

- T003 (Makefile) ∥ T002/T004.
- T013 ∥ T014 ∥ T011 (different files).
- T023 ∥ T019–T021 once T022 lands; T024 after T023.
- T027 ∥ T028.
- T034 ∥ T035 ∥ T036.

## Lanes

Parallel lanes never share files. Shared files belong to ENG. Juniors report to the ENG lead; the Floor Reviewer (Soffit, Claude Sonnet, read-only) reviews per user story; the ENG lead integrates, runs T038, sets the floor to review and reports to the Maestro.

### Lane ENG — Purlin (Claude Sonnet, lane lead)

Tasks: T001, T002, T004–T012, T015–T022, T026, T028–T033, T038–T040.

Owns: `core/engine/ze-core/ze_core/{routing,orchestration,conversation}/**`, `ze_core/{bootstrap,container}.py`, `ze_core/migrations/versions/zc0NN_drop_routing_log_tier.py`, their tests under `core/engine/ze-core/tests/` except T013/T014 files; `apps/ze-api/ze_api/container.py`; `apps/ze-api/config/config.yaml`; `eval/calibration/complexity.py`, `complexity.jsonl`; this phase's `spec.md`, `research.md`, `tasks.md`.

### Lane JR-A (OpenCode junior): setup, calibration cleanup, API, web

Tasks: T003; T013 and T014 after "T010 landed"; T023 after "T022 landed"; T024 after T023; T027 after "T026 landed".

Owns: `Makefile`; `eval/calibration/routing.py`, `routing*.jsonl`; `core/engine/ze-core/tests/routing/test_calibration_{script,dataset}.py`; `core/engine/ze-core/tests/conversation/test_judgments.py`; `apps/ze-api/tests/api/test_feedback_evidence.py`; `apps/ze-api/ze_api/api/schemas.py` (trace section only) and its route/WS tests; `packages/ze-client/src/generated/**`; `apps/ze-web/src/widgets/{message-trace,trace-panel}/ui/**`; `apps/ze-api/tests/calibration/test_complexity_calibration.py`.

### Lane BLIND — Quoin (fresh Haiku junior, one task)

Task: T025. Gets only the brief's path. Never on this floor's canvas before T025 is committed; never reads `complexity.jsonl`, `complexity.py` or `routing/tier.py`.

### Docs (Docs Steward, or JR-A when its lane is done)

Tasks: T034–T037. Owns `docs/**`, `README.md`, `core/engine/ze-core/README.md`, `AGENTS.md`, `specs/README.md`, `specs/arch/system-one-models.md`, the status notes in specs 164, 167, `specs/core/ze-core.md` and `specs/core/04-routing.md`. No code files. T037 reads research.md R12 and never edits it.

### Cross-lane files

A JR lane that needs a change in another lane's file asks the ENG lead. Touch points: JR-A's schema (T023) mirrors ENG's `TierTrace` (T008); JR-A's routing cleanup (T013) follows ENG's `judge.py` cut (T010); T027 tests ENG's pure functions from T026.
