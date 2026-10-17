# Implementation Plan: Composed Answers and Claim Posture (B1)

**Branch**: `184-composed-answers-posture` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

**Input**: `specs/phases/184-composed-answers-posture/spec.md`; normative contracts in [contracts/](./contracts/): `claim-descriptors.md`, `composition-rules.md`, `failure-summary.md`, `notification-targets.md`.

## Summary

Add claim posture to the server-driven UI contract and let the backend compose the three HUD answers from the stores. `ze-components` gains `ClaimPosture` (on every primitive, never in a `render_*` schema) and three primitives (`headline`, `claim_card`, `claim_timeline`). `ze-priority` gains `WorldComposer` (pure composition rules over records it fetches) and three READ tools for companion. A preset chip's `context.compose` makes `fetch_context` reroute to companion and prepend the composition; the model writes only the sentence. `surface_loops` drops its raw `open_items` dict for claim cards. Separately: a pure `failure_summary` for failed workflow executions, goal progress fields on `listGoals` through one new store query, and `notifications.target_parent_id` with corrected workflow and gate targets. ze-web regenerates its clients and renders the new primitives and fields minimally.

## Technical Context

**Language/Version**: Python 3.12; TypeScript (codegen + minimal renderers).

**Primary Dependencies**: existing. New package edge: `ze-priority → ze-components` (no cycle: `ze-components → ze-agents`). `ze-personal` already depends on `ze-priority`.

**Storage**: one migration, `zpro005_notification_parent.py` on the ze-proactive `zpro` chain (head `zpro004`). No `zc` migration (failure summary is derived; goal progress is a query).

**Testing**: pytest with fakes and `AsyncMock` pools (ze-components, ze-priority, ze-automation, ze-proactive, ze-core, ze-api, ze-personal suites); `@pytest.mark.pg` tests for `list_progress` and `zpro005`; Vitest for `PrimitiveRenderer` and the ze-web fields; eval scenarios with the judge (live, not in default suites).

**Target Platform**: conversation graph, REST `/api/v0/goals`, `/api/v0/workflows/*/executions*`, `/api/v0/notifications`, WS `notification` frame, inbound `message.context`.

**Performance Goals**: preset composition ≤ 2 s (timeout), typically one `PriorityView.rank()` plus three store reads in parallel (`asyncio.gather`); `listGoals` one SQL statement.

**Constraints**: posture from records only (OQ-2); pre-v1 hard cuts (`open_items`, `workflow_run`, `list_for_display`, the stuck-goal literal); `ze_core` never imports `ze_priority` (duck-typed `world_composer` and `turn_surfacer` in `configurable`); plugins import through `ze_sdk` except the already-declared `ze_priority` edge.

**Scale/Scope**: one Sonnet engineer + one junior; about 30 files.

## Constitution Check

| Principle | Assessment |
|---|---|
| I. Spec-First | PASS: spec with contracts; two open questions for the user with recommendations |
| II. Single-User | PASS |
| III. Layered Packages | PASS: descriptors in `ze-components` (kernel; claim vocabulary mirrored as literals, no `ze_agents.claims` import needed beyond the string values); composition in `ze-priority` (arbitration layer, already reads worldstate, automation, correlation); engine sees only duck-typed `configurable` entries; ze-api wires; companion receives the composer by constructor |
| IV. Typed Python | PASS: dataclasses (`ClaimPosture`, `Composition`, `GoalProgress`); Pydantic only in `ze_api` schemas; `get_logger` |
| V. Test Discipline | PASS: fail-first unit tests per FR; pure functions (composition rules, tone, headline text, failure summary) tested without I/O |
| VI. Explicit Persistence | PASS: raw-SQL Alembic `zpro005` in the owning package |
| VII. One Gateway | PASS: no new model call; the sentence is the existing companion turn |
| VIII. Pre-v1 Hard Cuts | PASS: `open_items` dict, `_build_component` (loop surfacing), `workflow_run`, `list_for_display`, the `idle_days=7` literal deleted at every caller in the same change |

## Blast radius

`graphify affected` (depth 1–2) on 2026-10-17 against the ground graph (main 586bcce3), completed with `rtk proxy grep` where graphify has no unique node (`Notification`, `list_for_display`, `_workflow_failure_handler`, `_build_component`, `CompanionAgent`, `list_workflow_executions`, `PostgresNotificationStore`) or does not see field reads.

| Symbol changed | Callers / readers by package |
|---|---|
| `build_render_schema` (omit `claim`) | ze-components: `tools.py` `render_tool`; tests `test_schema.py` (5 tests). Indirect: every render tool registered by `goals/agent.py` (ze-automation), `calendar/agent.py` (ze-calendar), `research/agent.py`, `companion` (ze-personal), `ze_api/wiring/container.py`, `ze-api/tests/conftest.py`, `ze-personal/tests/agents/companion/test_render_tools.py` |
| `export_json_schema`, `PRIMITIVE_TYPES`, `PRIMITIVE_SUB_TYPES` (+ `ClaimPosture`, 3 primitives, `claim` everywhere) | ze-components `schema.py`, `__init__.py`; tests `test_schema.py` (4 export tests); `scripts/codegen.ts` → `packages/ze-ui/src/generated/{schema.json,types.gen.ts,validators.gen.ts}`; `docs/component-schema.json` |
| `serialize_primitive` / `serialize_tree` (must emit `claim` and nested sub-types) | ze-components `context.append`, `serialize.py`; test `test_schema.py` L115 |
| `describe_components` (new names) | ze-core `nodes/memory.py` `write_memory` L261; ze-api `interface/native.py` `_send_message` L229; tests `test_summary.py` |
| `surface_loops` / `_build_component` (loop surfacing; hard cut) | ze-core `orchestration/nodes/__init__.py`, `graph.py` L60; tests `test_loop_surfacing.py` (11 tests incl. `test_component_is_json_serializable…`), `test_context.py` `test_whats_open_does_not_also_append_inline_mentions`, `test_graph_no_plan_sequential.py`, `test_loop_admission_node.py`, `test_nodes.py`, `test_retry_mode.py` |
| `TurnSurfacing` (+ `mention_cards`) | ze-priority `turn.py`, `__init__.py`; ze-api `wiring/container.py` `build_container` L514; tests `ze-priority/tests/test_turn.py`, `ze-api/tests/pg/test_loop_confirmation_pg.py` |
| `fetch_context` (preset path) / `AgentState` (+ `preset_components`) / `make_graph_input` (reset) / `AgentContext` (+ `preset`) | ze-core `nodes/context.py` (+ `_open_query_envelope` sibling), `state.py`, `conversation/turn.py` `make_graph_input` L41-70 (per-turn reset), ze-agents `types.py` `AgentContext`, both `AgentContext` constructors in `nodes/execution.py` (L388-410, L494), `nodes/execution.py` `execute_tool` L438 (prepend); readers of `AgentState` in `edges.py`, `judgment_state.py`, `graph.py` (no change); tests `test_context.py` (≈30 tests; new class for presets), `test_state_extensions.py` |
| `execute_tool` components (prepend presets) | ze-core `nodes/execution.py`: single-agent path sets `components` from `pop_components` (L433-440); the compound/subtask path returns no `components` key today, so it returns `components = preset_components` |
| `WsScreenContext` (+ `compose`, `topic`) | ze-api `api/ws/schemas.py` L204-217; `tests/api/test_ws_conformance.py`; generated WS types in `@myguyze/ze-client` |
| `EvalChatRequest` (+ `context`) | ze-api `api/eval/schemas.py` L24-27, `api/eval/router.py` L58 (`config_extra`); `core/ops/ze-eval` runner and scenario schema; `docs/eval.md` |
| `ze_priority._AGENT_MODULE_PATHS` (+ `ze_priority.compose.tools`) | ze-priority `__init__.py` L25-35 `import_agent_modules()`, called by ze-api `wiring/agents.py` `bootstrap_agent_layer` before `bootstrap_agents` |
| `CompanionAgent` (ctor `world_composer`, tools, instructions) | ze-personal `agents/companion/agent.py` (tool names, ctor, `run()` deps); ze-api `wiring/agents.py` `build_dep_map` (adds `WorldComposer`); tests `ze-api/tests/agents/test_bootstrap.py` `test_bootstrap_registers_companion_and_research`, `ze-personal/tests/agents/companion/*` |
| `PostgresGoalStore.list_for_display` (deleted) → `list_progress` | ze-automation `goals/store.py` Protocol L36, `goals/postgres.py` L189; ze-api `api/v0/goals/router.py` L54; tests `apps/ze-api/tests/api/test_web_routes.py`, `test_goal_learnings.py` (fake stores implementing `list_for_display`), `core/automation/ze-automation/tests/goal_engine/test_postgres_goal_store.py` L229-236 (`test_list_for_display_includes_planning_and_paused`) |
| `GoalListItem` (+ 8 fields) | ze-api `api/v0/goals/schemas.py`, `router.py` `list_goals`, `api/v0/__init__.py` re-export; tests `test_web_routes.py`, `test_goal_learnings.py`; `@myguyze/ze-client`; ze-web `entities/goal`, `widgets/goals-overview` |
| `jobs/stuck_goals.py` literal → `STUCK_IDLE_DAYS` | ze-automation `jobs/stuck_goals.py` L31; ze-api `wiring/jobs.py` (job construction); tests `apps/ze-api/tests/pg/test_stuck_goals.py` |
| `WorkflowExecution` readers (+ derived `failure_summary`) | ze-automation `rest.py` `list_workflow_executions`/`get_workflow_execution`, `agents/workflow/tools.py` `_serialize_execution` (called by `get_workflow`, `list_workflow_executions` tools), `bootstrap.py` `_workflow_failure_handler`; ze-api `api/v0/workflows/{router,schemas}.py` `WorkflowExecutionResponse`; tests `apps/ze-api/tests/api/test_workflows_route.py` (7 tests), `ze-automation/tests/workflow_agent/test_tools.py`; ze-web `widgets/workflow-executions` |
| `ProactiveNotifier.notify` / `_notify` (+ `target_parent_id`) | ze-proactive `notifier.py` (`notify`, `_notify`, `_push_silent`, `_deliver`, `_frame`, held release); callers: ze-automation `bootstrap.py` (failure handler, `wire_goal_executor_push`), `goals/executor.py` (gate push L1028, goal push L208), `goals/proposal.py`, `holds/resumer.py`, `jobs/{accountability,cost_anomaly,goal_narrative,goal_suggestion}.py`; ze-worldstate `surfacing.py`; ze-correlation `push.py`; ze-personal `jobs/{contacts,insights}.py`; ze-calendar `reminders/{store,calendar}.py`; ze-api `wiring/container.py` (`_NotifierPushSender`, workspace push L188), `wiring/agents.py`, `wiring/jobs.py`, `api/ws/confirmation.py` L285. Only the failure handler and the gate push change their arguments; the rest are unaffected by an optional kwarg |
| `NotificationRow` / `Notification` / store (+ column) | ze-proactive `types.py`, `notification_store.py` (`_row_to_dataclass`, `_row_to_notification`, `create`, `list_page`, `list_held`), `notifier.py`, `jobs/prune_notifications.py`, `bootstrap.py`; ze-api `api/v0/notifications/{router,schemas}.py` (`NotificationItem(**vars(n))`), `interface/native.py` L332, `wiring/{stores,agents,container,jobs}.py`; tests `ze-proactive/tests/{test_notifier,test_notification_store}.py`, `ze-api/tests/api/test_notifications_route.py`, `test_workspace_followthrough.py`, `test_governor_acceptance.py` (fake `create` signatures) |
| ze-ui `PrimitiveRenderer` (3 new cases) | `packages/ze-ui/src/react/PrimitiveRenderer.tsx` (+ test); consumers in ze-web: `features/primitive-tree/ui/ConnectedPrimitiveTree.tsx` (action dispatch), `widgets/chat-workspace/ui/MessageBubble.tsx`, `widgets/plugin-screen`, `widgets/settings-workspace/ui/PluginSettingsSection.tsx`, `pages/workflow-detail`, `widgets/workflow-graph/ui/StepDetailPanel.tsx`, `pages/jarvis/views/AssembleView.tsx` |

No `ze_sdk` signature change (companion imports `WorldComposer` from `ze_priority`, an existing declared edge). No `ze_core` import of `ze_priority`.

## Design

### `ze-components`

- `ze_components/claims.py` (new): `ClaimPosture`, `Readout`, `CardAction`, `TimelineEntry`, `headline_text()`, `claim_tone()`.
- `ze_components/organisms/{headline,claim_card,claim_timeline}.py` (new) with factory functions; registered in `PRIMITIVE_TYPES`; sub-types in `PRIMITIVE_SUB_TYPES`.
- Every existing primitive dataclass gains `claim: ClaimPosture | None = None` before `type`.
- `schema.py`: `_dataclass_schema(cls, *, omit=frozenset({"claim"}))` used by `build_render_schema`, applied recursively; `_export_*` unchanged (export includes `claim`).
- `tools.py` `render_tool._wrapper`: `if kwargs.pop("claim", None) is not None: log.warning("render_tool_claim_dropped", tool=name)`.
- `serialize.py`: verify nested dataclasses and `None` omission; `claim: None` is omitted from the wire to keep payloads small.
- `summary.py`: `_NAMES` adds `headline → headline`, `claim_card → card`, `claim_timeline → timeline`.
- `pyproject.toml` unchanged.

### `ze-priority`

- `pyproject.toml`: add `ze-components`.
- `ze_priority/matching.py` (new): `MATCH_FLOOR = 0.55`, `cosine()`; `tools.py` imports them (delete its private copies).
- `ze_priority/compose/types.py`: `Composition`, `SourceSnapshot` (records per source + failed set).
- `ze_priority/compose/rules.py`: pure `slipping(snapshot, now)`, `decisions(snapshot, now)`, `topic(snapshot, topic_vec, embed, now)`, card builders per subject, summary writers. Contract: `composition-rules.md`.
- `ze_priority/compose/composer.py`: `WorldComposer(priority_view, loop_store, goal_store, workflow_store, held_write_store, embedder, clock=…)` with `compose_*` that gather the snapshot (`asyncio.gather(..., return_exceptions=True)`), call the rules, serialize with `serialize_primitive`.
- `ze_priority/compose/tools.py`: the three `@tool(access=READ)` functions (contract § Tools).
- `turn.py`: `TurnSurfacing.mention_cards(mentions) -> list[dict]` builds `ClaimCard`s from the loop/goal records it already reads for mentions (loop store `get`; goal via the ranking item's signal), serialized.
- `__init__.py` exports `WorldComposer`.

### `ze-core`

- `state.py`: `preset_components: list[dict]`; `conversation/turn.py` `make_graph_input` resets it to `[]` with the other per-turn keys (a checkpointed thread must not carry a preset into the next turn). ze-agents `types.py`: `AgentContext.preset: str | None = None`.
- `nodes/context.py`: `_preset_envelope()` mirroring `_open_query_envelope` with `routing_method="preset"`; `_compose_preset(config)` reads `screen_context.compose/topic`, calls `configurable["world_composer"]` with a 2 s timeout; returns `preset_components`, sets `agent_context.preset`, and appends the note to `agent_context.screen_context_note` (the same channel `_build_screen_context_note` uses).
- `nodes/execution.py`: both `AgentContext` constructors copy `preset` (next to the prompt-note kwargs); `components = list(state.get("preset_components") or []) + popped` on the single-agent path; the compound branch's return adds `"components": list(state.get("preset_components") or [])` (synthesis unchanged).
- `nodes/loop_surfacing.py`: `component = surfacer.mention_cards(mentions)` (list) appended with `extend`; delete `_build_component`.

### `ze-automation`

- `goals/types.py`: `GoalProgress`; `goals/__init__.py`: `STUCK_IDLE_DAYS = 7`.
- `goals/postgres.py`: `list_progress()` — one statement: goals in display statuses `LEFT JOIN LATERAL` milestone aggregates (`count(*) filter (where status in ('completed','skipped'))`, `count(*)`, `max(completed_at)`), `LEFT JOIN LATERAL` next milestone (`status in ('pending','in_progress')` order by `sequence` limit 1), `LEFT JOIN LATERAL` earliest fired open gate (`status in ('pending','awaiting_approval') and fired_at is not null` order by `fired_at` limit 1); Python computes `stuck_since` with `is_stale`. Delete `list_for_display` from Postgres store and Protocol.
- `jobs/stuck_goals.py`: use `STUCK_IDLE_DAYS`.
- `workflow/failure.py`: `failure_summary()` per contract; `rest.py` and `agents/workflow/tools.py` add the key; `bootstrap.py` failure handler body + `target_type="workflow_execution"`, `target_id=str(execution.id)`, `target_parent_id=str(workflow.id)`.
- `goals/executor.py` gate push: `target_parent_id=str(goal.id)`.

### `ze-proactive`

- `migrations/versions/zpro005_notification_parent.py`; `types.py`, `notification_store.py`, `notifier.py` per contract.

### `ze-api`

- `wiring/container.py`: construct `WorldComposer` after `PriorityView` and `TurnSurfacing`; put it in `configurable["world_composer"]` (where `turn_surfacer` is set) and in the agent dep map (`wiring/agents.py`).
- `api/v0/goals/{schemas,router}.py`: fields + `list_progress`.
- `api/v0/workflows/schemas.py`: `failure_summary: str | None`.
- `api/v0/notifications/schemas.py`: `target_parent_id`.
- `api/ws/schemas.py` `WsScreenContext`: `compose: Literal["slipping", "decisions", "topic"] | None = None`, `topic: str | None = Field(None, max_length=120)` (the context dict is already passed through as `screen_context`, `api/ws/turns.py` L98); conformance test.
- `api/eval/schemas.py` `EvalChatRequest.context: dict | None`; `api/eval/router.py` passes it as `config_extra["screen_context"]`.
- `interface/native.py`: frame key.

### `ze-personal`

- `agents/companion/agent.py`: tools `show_slipping`, `show_decisions`, `show_topic`; ctor `world_composer: WorldComposer | None = None`; `run()` passes `deps={**self.tool_deps(), "world_composer": self._world_composer, "preset": ctx.preset}` (no `BaseAgent.tool_deps` signature change); instructions block (contract wording): "What's slipping / late / drifting → show_slipping. What needs me / what should I decide → show_decisions. How is <project> going → show_topic. The modules are shown to the user; write one or two sentences from the returned summary only, never list every card, never add items it does not contain. If sources_failed is not empty, say which part you could not read."
- `plugin.py`: unchanged (registration lives in `ze_priority._AGENT_MODULE_PATHS`).

### `ze-priority` registration

- `__init__.py`: `_AGENT_MODULE_PATHS = ["ze_priority.tools", "ze_priority.compose.tools", "ze_priority.agent"]`.

### Web (minimal, interim)

- `make codegen`.
- `packages/ze-ui/src/react/PrimitiveRenderer.tsx`: `headline`, `claim_card`, `claim_timeline` cases (plain markup; `claim_card` actions call `onAction({ intent, ref_id })` through the existing renderer context); test.
- `features/primitive-tree/ui/ConnectedPrimitiveTree.tsx`: map intents to existing mutations (`confirmLoop`, `dropLoop`, `decideHeldWrite`) and the `action` frame for `approve_gate`; `open` navigates per `notificationHref`-style mapping.
- `widgets/workflow-executions`: show `failure_summary`; stop parsing `error`.
- `widgets/goals-overview`: show done/total, next milestone, gate open since, stuck since.
- `widgets/app-shell/lib/notification-format.ts`: owned by phase 183 (`notificationHref`); this phase adds `target_parent_id` to the generated type and extends its table tests. If 184 lands first, implement `notificationHref` here and 183 re-points it.

### Eval

`eval/scenarios/composed_answers.yaml`: six scenarios (slipping, decisions, topic × EN/PT) sent with a scenario-level `context:` key that the `ze-eval` runner forwards to `EvalChatRequest.context` (new), asserting `expected_agent: companion` (a preset reroute records `routing_method="preset"`, not a forced route), component types present, and judge criteria "names only items present in the composition; does not list every card; offers at most one next step".

## Project Structure

### Documentation (this feature)

```
specs/phases/184-composed-answers-posture/
├── spec.md
├── plan.md
├── tasks.md
└── contracts/
    ├── claim-descriptors.md
    ├── composition-rules.md
    ├── failure-summary.md
    └── notification-targets.md
```

### Source Code

```
core/kernel/ze-components/ze_components/{claims.py,organisms/{headline,claim_card,claim_timeline}.py,schema.py,tools.py,serialize.py,summary.py,__init__.py}
core/arbitration/ze-priority/{pyproject.toml,ze_priority/{matching.py,tools.py,turn.py,__init__.py,compose/{types,rules,composer,tools}.py}}
core/engine/ze-core/ze_core/{orchestration/{state.py,nodes/{context,execution,loop_surfacing}.py},conversation/turn.py}; core/contracts/ze-agents/ze_agents/types.py
core/automation/ze-automation/ze_automation/{goals/{types,postgres,store,__init__,executor}.py,jobs/stuck_goals.py,workflow/failure.py,rest.py,agents/workflow/tools.py,bootstrap.py}
core/contracts/ze-proactive/ze_proactive/{types,notification_store,notifier}.py + migrations/versions/zpro005_notification_parent.py
apps/ze-api/ze_api/{wiring/{container,agents}.py,api/v0/{goals,workflows,notifications}/*.py,api/ws/schemas.py,interface/native.py}
plugins/ze-personal/ze_personal/agents/companion/agent.py
apps/ze-api/ze_api/api/eval/{schemas,router}.py; core/ops/ze-eval/ (runner forwards scenario context); docs/eval.md
packages/ze-ui/src/{generated/*,react/PrimitiveRenderer.tsx}; packages/ze-client/src/generated/*
apps/ze-web/src/{features/primitive-tree,widgets/{workflow-executions,goals-overview,app-shell/lib}}
eval/scenarios/composed_answers.yaml
```

## Docs touched ([DOCS] tasks)

- `docs/native-interface.md`: `message.context.compose`/`topic`; the three new primitives and `claim`; `notification` frame `target_parent_id` and the target table.
- `docs/component-schema.json` regenerated; `core/kernel/ze-components/README.md` (posture rule: code-only), `packages/ze-ui/README.md` (new types).
- `core/arbitration/ze-priority/README.md`: `WorldComposer`, tools, preset path.
- `docs/workflows.md` (failure summary), `docs/goals.md` (list progress fields, `STUCK_IDLE_DAYS`), `docs/scheduled-jobs.md` (stuck-goal constant if it names 7 days), `docs/architecture.md` (graph flow note: preset reroute in `fetch_context`), `docs/package-architecture.md` and `AGENTS.md` dependency graph (`ze-priority → ze-components`), `AGENTS.md` migration table (`zpro005` notifications.target_parent_id) and phase table row, `specs/README.md` row.
- Coverage check against `git diff main...HEAD --stat`.

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| Preset intent on `context.compose` | A chip is an explicit user choice; routing it by text would need new routing criteria and a paid calibration, and "what am I still sitting with?" already routes to loops | Routing-only (OQ-1a alternative) |
| `claim` on every primitive | Gap 2 asks for posture on every descriptor so later phases (W3, W5) can attach it to any module without another contract change | Posture only on the new card (forces another schema break when the canvas renders a chart or table about one claim) |
| Derived `failure_summary` (no column) | Pure function of fields already stored; works for old rows; no migration | Stored column written at finish time (two writers, backfill) |
