# Tasks: Composed Answers and Claim Posture (B1)

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [contracts/](./contracts/).

**Build gate**: the user answers OQ-1a and OQ-1b and confirms OQ-2 (spec Clarifications); tasks follow the recommendations. The Spec Architect (Lintel) stays on call for design questions.

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Unit tests use fakes and `AsyncMock` pools; no OpenRouter call in default suites; `@pytest.mark.pg` for real-Postgres checks (`make test-pg`).

**Lanes**: `[ENG]` Claude Sonnet lane lead (engine, composer, stores, wiring, gates). `[JR]` OpenCode junior (exact files given). Floor Reviewer reviews per user story.

**Tags**: `[BACKEND]` Python · `[WEB]` ze-web, ze-ui, generated clients · `[PLATFORM]` migration, config, Makefile · `[DOCS]` docs and specs.

**Rules for the implementer**
- Before changing a signature in plan.md "Blast radius", run `graphify affected "<Symbol>" --depth 2` and `rtk proxy grep -rn "<symbol>" --include='*.py' core apps plugins packages eval`; update every caller in the same change.
- Posture is set only from a record you just read (OQ-2). Never add `claim` to a `render_*` schema.
- Pre-v1 hard cut: delete `open_items`, `_build_component` (loop surfacing), `workflow_run`, `list_for_display`, the stuck-goal literal in the change that replaces them; no aliases.
- `ze_core` must not import `ze_priority`; use `config["configurable"]` entries.
- `get_logger(__name__)`; typed `ZeError` subclasses; no bare `Exception`/`ValueError` raised in domain code.
- Shared worktree: `git add <paths>`; `git commit -m ... -- <paths>`; never `git add -A` or `git stash`. Commit only when the ENG lead or Maestro asks; split commits by user story.

---

## Phase 0: Gate [ENG]

- [x] T001 [ENG] [BACKEND] Rebase onto `main`. `graphify update .`, then `graphify affected` on `build_render_schema`, `export_json_schema`, `surface_loops`, `TurnSurfacing`, `fetch_context`, `AgentState`, `PostgresGoalStore`, `GoalListItem`, `WorkflowExecution`, `ProactiveNotifier`, `NotificationRow`, `NotificationStore`. Record in the Handoffs note: (a) differences from plan.md "Blast radius"; (b) the `zpro` chain head (expect `zpro004`); (c) confirm the compound branch of `execute_tool` still returns no `components` key and `make_graph_input` still lists every per-turn key (plan.md ze-core design depends on both). Stop and report differences to the Spec Architect.

## Phase 1: Descriptor contract (blocks US1–US4) [US4]

- [x] T002 [ENG] [BACKEND] Tests first `core/kernel/ze-components/tests/test_claims.py`: `ClaimPosture` serializes with nested fields and omits `None`; `headline_text()` uppercases, strips characters outside `A–Z 0–9 · : -` and space, truncates to 40; `claim_tone()` table (slipped → hot; needs_user → cream; suspicion/inference → dotted; else default; slipped beats needs_user). Implement `ze_components/claims.py`.
- [x] T003 [ENG] [BACKEND] Tests first in `test_schema.py`: `export_json_schema()` has `ClaimPosture`, `Readout`, `CardAction`, `TimelineEntry` in `$defs`, discriminators `headline`, `claim_card`, `claim_timeline`, and an optional `claim` on every primitive; `ClaimCard.claim` required; `CardAction.intent` enum is exactly the six intents. Implement the three organisms and add `claim` to every existing primitive dataclass; register in `PRIMITIVE_TYPES` / `PRIMITIVE_SUB_TYPES`.
- [x] T004 [ENG] [BACKEND] Tests first in `test_schema.py` and `test_tools.py`: for every registered `render_*` tool, the schema has no `claim` key at any depth; calling a render tool with `claim={...}` yields a component without `claim` and logs `render_tool_claim_dropped`. Implement the `omit` in `schema.py` and the pop in `tools.py`.
- [x] T005 [P] [JR] [BACKEND] `ze_components/summary.py` names `headline`, `claim_card` ("a card"), `claim_timeline` ("a timeline"); extend `tests/test_summary.py`.
- [x] T006 [JR] [WEB] `make codegen`; commit the regenerated `packages/ze-ui/src/generated/*` and `docs/component-schema.json`. Tests first in `packages/ze-ui/src/react/PrimitiveRenderer.test.tsx`: `headline` renders its text; `claim_card` renders title, lines, readouts and one button per action calling `onAction({ intent, ref_id })`; `claim_timeline` renders entries in order; a primitive with `claim` renders unchanged. Implement the three cases (plain markup; W3 restyles).

## Phase 2: Goal progress (needed by the composer) [US6]

- [x] T007 [ENG] [BACKEND] Tests first `core/automation/ze-automation/tests/goal_engine/test_goal_progress.py` (fake pool returning joined rows): counts, next milestone, open gate, `last_progress_at`, `stuck_since` for an active idle goal (7+ days) and for a gate fired 7+ days ago, `None` otherwise; exactly one `fetch` call; the cooldown column `last_stuck_alert_at` does not affect `stuck_since`; an active goal with no completed milestone uses `created_at` as reference and `last_progress_at` null. Replace `test_list_for_display_includes_planning_and_paused` in `test_postgres_goal_store.py` with a `list_progress` status-filter test. Add `GoalProgress` (`goals/types.py`), `STUCK_IDLE_DAYS = 7` (`goals/__init__.py`), `PostgresGoalStore.list_progress()` and the Protocol method; delete `list_for_display` from both. Replace the literal in `jobs/stuck_goals.py`.
- [x] T008 [ENG] [BACKEND] `apps/ze-api/tests/pg/test_goal_progress_pg.py` (`@pytest.mark.pg`): seeded goals with milestones and gates return the expected progress through real SQL.
- [x] T009 [JR] [BACKEND] Tests first in `apps/ze-api/tests/api/test_web_routes.py` (update fake stores from `list_for_display` to `list_progress`, also in `test_goal_learnings.py`): `GET /api/v0/goals` returns the eight new fields. Implement `GoalListItem` fields and `list_goals` in `api/v0/goals/{schemas,router}.py`.

## Phase 3: Composer [US1, US2, US3]

- [x] T010 [ENG] [BACKEND] `core/arbitration/ze-priority/pyproject.toml` adds `ze-components`; `uv sync`. Move `_MATCH_FLOOR`/`_cosine` from `tools.py` to `ze_priority/matching.py` as `MATCH_FLOOR`/`cosine`; update `tools.py` and `tests/test_tools.py`.
- [x] T011 [ENG] [BACKEND] Tests first `core/arbitration/ze-priority/tests/compose/test_rules_slipping.py`: the US1 independent test and acceptance scenarios 1–3 from pure `rules.slipping(snapshot, now)` (snapshot built from factories), including order, caps (6 per kind, 12 total, 2 persons), timeline window, `sources_failed` passthrough, summary lines, and that the suspected loop is excluded. Implement `compose/types.py` and `compose/rules.py` (slipping + card builders + summary).
- [x] T012 [ENG] [BACKEND] Tests first `tests/compose/test_rules_decisions.py`: US2 independent test and acceptance (order, intents and ids, tones cream/dotted, expired held write absent, empty headline). Implement `rules.decisions`.
- [x] T013 [ENG] [BACKEND] Tests first `tests/compose/test_rules_topic.py` with a dict-keyed fake embedder: US3 independent test and acceptance (floor, order loops→goals→workflows→hypotheses, cap 6 each, workflow states `ok`/`failed`/`never_run`/`off` with `failure_summary` line, headline truncation, no-embedder summary). Implement `rules.topic`. (Needs T018 for `failure_summary`; stub the import until T018 lands or schedule after it.)
- [x] T014 [ENG] [BACKEND] Tests first `tests/compose/test_composer.py`: `WorldComposer` gathers sources in parallel, records a raising source in `sources_failed` and still composes, returns `COULD NOT READ THE WORLD` when all fail, serializes components with `serialize_primitive`. Implement `compose/composer.py`; export `WorldComposer`.
- [x] T015 [ENG] [BACKEND] Tests first `tests/compose/test_tools.py`: each tool appends the composition's components in order inside a collection context and returns `{summary, sources_failed}`; with the injected `preset` equal to its own key it returns the summary without appending; with `preset=None` or another key it appends; `show_topic("billing")` with `preset="topic:ledgerlite"` appends (keys `topic:<normalized>`, exact match). Implement `compose/tools.py` (injected `world_composer`, `preset`) and add `ze_priority.compose.tools` to `_AGENT_MODULE_PATHS` before `ze_priority.agent` (test: `agent_module_paths()` order).

## Phase 4: Preset path and companion [US1, US2, US3]

- [x] T016 [ENG] [BACKEND] Tests first, new class in `core/engine/ze-core/tests/orchestration/nodes/test_context.py`: `context.compose="slipping"` reroutes a single-agent goals envelope to companion with `routing_method="preset"`; compound and forced routes keep their envelope but still get `preset_components`; invalid compose value or missing topic → no change and a warning; composer timeout (fake sleeping 3 s) → no preset components, turn completes; the note is in `agent_context.screen_context_note` and contains the summary. `agent_context.preset` is set. Then `nodes/execution.py` tests: `preset_components` precede agent components on the single-agent path; the compound branch returns `components == preset_components`; both `AgentContext` constructors carry `preset`. Then a two-turn graph test on one thread: a preset turn, then a plain turn → the plain turn has no preset cards (`make_graph_input` reset). Then a retry test: retrying a preset turn answers through normal routing with no preset components (spec edge case). Implement `state.py`, `conversation/turn.py` (`make_graph_input`), ze-agents `AgentContext.preset`, `nodes/context.py`, `nodes/execution.py`.
- [x] T017 [ENG] [BACKEND] `plugins/ze-personal`: tests first in `tests/agents/companion/` — companion lists the three tools; `run()` passes `world_composer` and `ctx.preset` in `deps` (fake `agentic_loop` captures them); its instructions contain the composed-answer block; existing tests calling `tool_deps()` still pass (signature unchanged); `apps/ze-api/tests/agents/test_bootstrap.py` still registers companion with the composer in the dep map and `validate_registry` passes. Implement `agents/companion/agent.py`, `ze_api/wiring/agents.py` and `wiring/container.py` (construct `WorldComposer`; `configurable["world_composer"]`). No `plugin.py` change.

## Phase 5: Workflow failure line [US5]

- [x] T018 [P] [JR] [BACKEND] Tests first `core/automation/ze-automation/tests/workflow_engine/test_failure_summary.py`: every row of `contracts/failure-summary.md` (reasons, attempts, unknown step count, before-first-step only when no step ran, "after step k" for each execution-level reason after successful steps, no reason, completed → `None`) and the no-raw-text property. Implement `workflow/failure.py`.
- [x] T019 [JR] [BACKEND] Wire `failure_summary` into `ze_automation/rest.py` execution dicts, `agents/workflow/tools.py` `_serialize_execution`, and `WorkflowExecutionResponse` (`api/v0/workflows/schemas.py`). Tests: `apps/ze-api/tests/api/test_workflows_route.py` (failed and completed executions), `ze-automation/tests/workflow_agent/test_tools.py`.

## Phase 6: Notification deep links [US7]

- [x] T020 [ENG] [PLATFORM] `core/contracts/ze-proactive/ze_proactive/migrations/versions/zpro005_notification_parent.py` (`down_revision="zpro004"`): add/drop `target_parent_id TEXT NULL`. Follow `zpro004` style. `make migrate` on a dev DB; `@pytest.mark.pg` round-trip test in `apps/ze-api/tests/pg/`.
- [x] T021 [ENG] [BACKEND] Tests first in `core/contracts/ze-proactive/tests/{test_notifier,test_notification_store}.py`: `notify(..., target_parent_id=…)` persists, is returned by `list_page` and `list_held`, survives the quiet-hours held release, and appears in the frame; default `None`; dedup key unchanged. Implement `types.py`, `notification_store.py`, `notifier.py`. Update fake stores in `apps/ze-api/tests/api/test_workspace_followthrough.py` and `tests/test_governor_acceptance.py`.
- [x] T022 [ENG] [BACKEND] Tests first: failure handler (`ze_automation/bootstrap.py`) sends body = `failure_summary(execution)`, `target_type="workflow_execution"`, `target_id` = execution id, `target_parent_id` = workflow id; gate push (`goals/executor.py`) sets `target_parent_id` = goal id. Implement; `git grep -nE '(^|[^_a-z])"workflow_run"|target_type="workflow_run"' -- core apps plugins packages` returns nothing (the `cancel_workflow_run` tool and the prototype's `event_type` check are unrelated and stay).
- [x] T023 [JR] [BACKEND] `NotificationItem.target_parent_id` (`api/v0/notifications/schemas.py`), `interface/native.py` frame key, WS frame schema in `api/ws/schemas.py` if declared there; tests in `apps/ze-api/tests/api/test_notifications_route.py` and the native interface frame test.

## Phase 7: Inline mentions as claim cards [US4]

- [x] T024 [ENG] [BACKEND] Tests first `core/arbitration/ze-priority/tests/test_turn.py`: `mention_cards(mentions)` returns one serialized `claim_card` per mention with posture from the loop/goal record (loop: kind, confidence, provenance as source, state, `slipped` when drifting). Then rewrite `core/engine/ze-core/tests/orchestration/nodes/test_loop_surfacing.py` for cards (JSON-serializable, existing components preserved, compound turn unchanged text behaviour). Implement `TurnSurfacing.mention_cards`; `surface_loops` extends components with it; delete `_build_component` and every `open_items` string (`rtk proxy grep -rn "open_items\"" core apps` → only the state flag `open_items_query`, which stays).

## Phase 8: Web (minimal) [WEB]

- [x] T025 [JR] [WEB] `make codegen` (after T009, T019, T023); `features/primitive-tree/ui/ConnectedPrimitiveTree.tsx` maps card intents: `confirm_loop` → `confirmLoop`, `drop_loop` → `dropLoop`, `approve_held_write`/`deny_held_write` → `decideHeldWrite`, `approve_gate` → `action` frame `goal:approve:<ref_id>`, `open` → navigate via a `claimHref(subject, ref_id)` helper. Tests per intent.
- [x] T026 [P] [JR] [WEB] `widgets/workflow-executions`: render `failure_summary`; delete any parsing of `error`. `widgets/goals-overview` (start from a base that includes 183 T012, which removes `FloatingButton` from `GoalsOverview.tsx`; if 183 has not landed, coordinate the merge order with the Maestro): done/total meter text, next milestone, "waiting on you since …" for an open gate, stuck since. Tests.
- [x] T027 [P] [JR] [WEB] Notification links: phase 183 owns `notificationHref` in `widgets/app-shell/lib/notification-format.ts`. Here: add `target_parent_id` to the generated `NotificationItem` consumers and extend the `notificationHref` table tests for `workflow_execution` and `goal_gate` parents. If 183 has not landed, implement `notificationHref(n)` per `contracts/notification-targets.md` with current paths and record that 183 T010 must re-point it.
- [x] T028 [JR] [WEB] Gates: `make test-web`, `make typecheck-web`, `make web-build`.

## Phase 8b: Wire contracts for the preset [WEB] [BACKEND]

- [x] T036 [JR] [BACKEND] `apps/ze-api/ze_api/api/ws/schemas.py` `WsScreenContext`: `compose: Literal["slipping","decisions","topic"] | None = None`, `topic: str | None` (max 120). Extend `apps/ze-api/tests/api/test_ws_conformance.py`; `make codegen` for the WS types. Must land before T016's graph tests run against the real schema.
- [x] T037 [ENG] [BACKEND] Eval context: `apps/ze-api/ze_api/api/eval/schemas.py` `EvalChatRequest.context: dict | None`; `api/eval/router.py` passes it as `config_extra["screen_context"]`; `core/ops/ze-eval` runner forwards a scenario-level `context:` key and validates it; tests for router and runner; `docs/eval.md` documents the key. Needed by T029.

## Phase 9: Eval and gates [ENG]

- [x] T029 [ENG] [BACKEND] `eval/scenarios/composed_answers.yaml`: six scenarios (slipping, decisions, topic; EN and PT) sending a scenario `context:` with `compose` (T037), `expected_agent: companion`, criteria per plan.md Eval. Run against `make dev-eval` with seeded fixtures for loops, goals and held writes; record results in the Handoffs note.
- [x] T030 [ENG] [BACKEND] SC-001 spot check on `make dev` seed data: 10 cards across the three presets compared with their rows; SC-003 query over failed executions. Record in the Handoffs note.
- [ ] T031 [ENG] [PLATFORM] Gates: `make test-py`, `make test-pg`, `make lint`, `make test-web`, `make typecheck-web`. Record command, result and commit.

## Phase 10: Docs [DOCS]

- [ ] T032 [P] [DOCS] `docs/native-interface.md` (`message.context.compose`/`topic`, new primitives, `claim`, notification `target_parent_id` + target table), `core/kernel/ze-components/README.md`, `packages/ze-ui/README.md`, `core/arbitration/ze-priority/README.md`. Follow the `doc-style` skill.
- [ ] T033 [P] [DOCS] `docs/workflows.md` (failure summary), `docs/goals.md` (list progress fields, `STUCK_IDLE_DAYS`), `docs/scheduled-jobs.md` (if it names the 7-day literal), `docs/architecture.md` (preset reroute in `fetch_context`), `docs/package-architecture.md` (`ze-priority → ze-components`).
- [ ] T034 [DOCS] `AGENTS.md`: dependency graph line for ze-priority, migration table (`zpro005` notifications.target_parent_id), layout note for `ze_priority/compose/`, phase table row 184; `specs/README.md` row 184. Status → Implemented only after T031.
- [ ] T035 [DOCS] Coverage check against `git diff main...HEAD --stat`; list gaps in the Handoffs note.

---

## Dependencies

- T001 → all. T002 → T003 → T004 → T006, T011–T015, T024. T005 any time after T003.
- T007 → T008, T009, T011 (composer reads `list_progress`). T018 → T013, T019, T022.
- T010 → T011. T011 → T012 → T013 → T014 → T015 → T016 → T017.
- T020 → T021 → T022, T023.
- T036 → T016 (schema) ; T037 → T029.
- T009, T019, T023 → T025–T027 → T028. T017, T024 → T029. Everything → T031 → docs status (T034).

## Parallel examples

- T005 ∥ T007 ∥ T018 ∥ T020 (different packages).
- T026 ∥ T027.
- T032 ∥ T033.

## Lanes

### Lane ENG (Claude Sonnet, lane lead)

Tasks: T001–T004, T007, T008, T010–T017, T020–T022, T024, T029–T031, T037. Owns `core/kernel/ze-components/ze_components/{claims.py,organisms/*,schema.py,tools.py,serialize.py,__init__.py}`, `core/arbitration/ze-priority/**`, `core/engine/ze-core/ze_core/orchestration/**`, `core/automation/ze-automation/ze_automation/{goals/**,jobs/stuck_goals.py,bootstrap.py}`, `core/contracts/ze-proactive/**`, `apps/ze-api/ze_api/wiring/**`, `plugins/ze-personal/ze_personal/agents/companion/agent.py`, `eval/scenarios/composed_answers.yaml`, `apps/ze-api/ze_api/api/eval/**`, `core/ops/ze-eval/**`, `docs/eval.md`, `core/contracts/ze-agents/ze_agents/types.py` (`AgentContext.preset` only), `core/engine/ze-core/ze_core/conversation/turn.py`, and this phase's `tasks.md`.

### Lane JR (OpenCode junior)

Tasks: T005, T006, T009, T018, T019, T023, T025–T028, T036. Owns `ze_components/summary.py` (+ test), `packages/ze-ui/**`, `packages/ze-client/src/generated/**`, `docs/component-schema.json`, `apps/ze-api/ze_api/api/v0/{goals,workflows,notifications}/**`, `apps/ze-api/ze_api/interface/native.py`, `apps/ze-api/ze_api/api/ws/schemas.py`, `core/automation/ze-automation/ze_automation/{workflow/failure.py,rest.py,agents/workflow/tools.py}`, their tests, and `apps/ze-web/src/{features/primitive-tree,widgets/workflow-executions,widgets/goals-overview,widgets/app-shell/lib}/**`.

### Docs (Docs Steward)

Tasks: T032–T035. `AGENTS.md`, `specs/README.md` and `docs/native-interface.md` are also edited by phase 183's docs lane: do both floors' docs in one Docs Steward pass in the merge order the Maestro sets. Owns the docs listed there, `AGENTS.md`, `specs/README.md`, this spec's status line.

### Cross-lane touch points

T022 (ENG) edits `bootstrap.py` and consumes JR's `failure_summary` (T018). T025 (JR) consumes ENG's descriptor contract (T003) after codegen. If 183 lands first, T027 uses its `places.ts` paths; otherwise current paths, and 183's T010 updates the one function.
