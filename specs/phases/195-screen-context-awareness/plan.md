# Implementation Plan: Screen Context Awareness

**Branch**: `195-screen-context-awareness` | **Date**: 2026-10-17 | **Spec**: [spec.md](spec.md)

**Input**: `specs/phases/195-screen-context-awareness/spec.md`; normative contract [contracts/screen-context.md](./contracts/screen-context.md).

## Summary

Replace the ad-hoc `context` dict and the workflow-only note with a typed `ScreenContext`, a resolver registry and one honest note built before routing. Contract types live in `ze-agents` (so plugins reach them through `ze_sdk`); the registry and the `resolve_screen` node live in `ze-core`; each core package registers resolvers for the kinds whose data it owns, and plugins add theirs through `ZePlugin.screen_resolvers()`. `fetch_context` copies the note; the trace records it; the user message stores the context so Retry replays it. The web gets one screen-context store that places publish into, the Ask bar and overlay send its snapshot, and every `Module` can carry a "Chat about this" chip that opens the overlay with that component as the subject.

## Technical Context

**Language/Version**: Python 3.12; TypeScript (ze-web, generated clients).

**Primary Dependencies**: existing. New edges: none (resolvers live in packages that already depend on `ze-agents`; `ze-core` already depends on `ze-plugin` for the plugin hook; plugins import resolver types via `ze_sdk`).

**Storage**: one migration on the `zc` chain: `zc039_message_screen_context.py` (`messages.screen_context JSONB NULL`); the number is reserved by the Maestro (migration numbers are Maestro-assigned); T001 re-reads the head (expect `zc038`); `apps/ze-api/tests/test_migrate.py` head assertion moves to `zc039`.

**Testing**: pytest with fakes per resolver; `@pytest.mark.pg` for the new lookups (`NotificationStore.get`, entity one-hop, migration round trip); graph node tests following `tests/orchestration/nodes/test_context.py`; Vitest for the store, publisher, Ask bar snapshot and the chip; eval scenarios with the judge (live, outside default suites).

**Target Platform**: conversation graph (`invoke_raw_turn`), WS inbound `message`, retry path, REST trace.

**Performance Goals**: resolvers in parallel, 300 ms each, 800 ms total; turns with no context add zero work.

**Constraints**: posture set by code; never trust client labels; record text and client strings sanitised; the note is reset each turn by `make_graph_input`, lives in checkpointed state so a confirmation resume keeps it, and is never written to memory or intake; the tier judge's input does not change; routing hint behind a flag until a user-approved calibration (OQ-1); a bad context never fails a turn; pre-v1 hard cuts (`screen`/`goal_id`/`workflow_id`/`execution_id` fields, `_build_screen_context_note`, `resolve-screen.ts`).

**Scale/Scope**: one Sonnet engineer + one junior; about 45 files across 10 packages.

## Constitution Check

| Principle | Assessment |
|---|---|
| I. Spec-First | PASS: spec + contract; two open questions for the user |
| II. Single-User | PASS |
| III. Layered Packages | PASS: protocol in `ze-agents`, registry and node in `ze-core`, resolvers in owning packages, plugins via `ze_sdk`; `ze_core` imports no domain package (resolvers are injected) |
| IV. Typed Python | PASS: dataclasses `ScreenContext`, `ScreenRef`, `ScreenLine`, `ScreenPosture`, `ScreenResolution`, `ScreenTrace`; Pydantic only in ze-api schemas |
| V. Test Discipline | PASS: fail-first unit tests per resolver and for the note builder; eval scenarios outside default suites |
| VI. Explicit Persistence | PASS: raw-SQL Alembic `zc039` in ze-core |
| VII. One Gateway | PASS: no new model call |
| VIII. Pre-v1 Hard Cuts | PASS: old context fields, the workflow note builder and the client resolver deleted with their callers |

## Blast radius

`graphify affected` (depth 2) on 2026-10-17 (floor checkout at 7643051a) for `fetch_context`, `_build_screen_context_note`, `screen_context_note`, `WsScreenContext`, `record_trace`, `MessageTrace`, `build_judgment_state`, `ZePlugin`; completed with `rtk proxy grep -rn "screen_context"` (graphify does not see field reads and has no node for `WsScreenContext` users).

| Symbol changed | Callers / readers by package |
|---|---|
| `configurable["screen_context"]` (now a `ScreenContext`) | ze-api `api/ws/turns.py` L95-98 (set), retry path L517-531 (now set from the stored message); ze-core `nodes/context.py` L313-356 (read; replaced by `state["screen_note"]`) **and 184's `_compose_preset` / `_preset_envelope` (read `compose`/`topic` as a dict today; move to the typed fields; their summary moves to `AgentContext.preset_note`)**; eval router `api/eval/router.py` (184 T037 passes `context`, now through `from_wire`) |
| `_build_screen_context_note` (deleted) | ze-core `nodes/context.py` L331 (only caller), L372 (definition); tests `tests/orchestration/nodes/test_context.py` (workflow note cases) |
| `AgentContext.screen_context_note` (unchanged field; new producer) | ze-agents `types.py` L122, `base_agent.py` L265 (renders into the system prompt); ze-core `nodes/execution.py` `_prompt_note_kwargs` L44 (copies to subtask contexts), `judgment_state.py` `_tier_focus` L122 (tier state); tests `tests/orchestration/nodes/test_execution_context_notes.py`, `tests/orchestration/test_tier_state.py` |
| `fetch_context` | ze-core `orchestration/nodes/__init__.py`, `graph.py`; tests `test_context.py` (≈30), `apps/ze-api/tests/test_workflow_hold.py` (graph) |
| graph edges (`preprocess`/`inject_routing_context` → `resolve_screen` → `embed_route`) | ze-core `graph.py` L95-100 (both branches), `nodes/__init__.py`; plugin `pre_route_node` (ze-automation `graph/routing_context.py` writes `routing_hints`; `resolve_screen` appends after it) |
| `build_judgment_state` (flagged screen line) / `_tier_focus` (stops reading the note) | ze-core `judgment_state.py` L54-60 (routing/skills state `context`), L116-123 (`_tier_focus`: drop `screen_context_note`); callers `nodes/routing.py` `embed_route` L32, `nodes/skills.py` `match_skills` L42; `routing_hints` itself and the fallback prompt (`nodes/routing.py` L92-94) are untouched; tests `tests/orchestration/test_tier_state.py` (note case becomes "note absent from tier state"); complexity sets contain no screen-note rows (checked 2026-10-17) |
| `AgentContext` (+ `preset_note`) | ze-agents `types.py`; `base_agent.py` L265 (render after the screen note); ze-core `nodes/execution.py` `_prompt_note_kwargs` L44 |
| `useChatWorkspace.sendMessage` (single send path) | ze-web `widgets/chat-workspace/model/useChatWorkspace.ts` L272-295 (context spread + `workspace_placed`); callers: `ChatWorkspace` composer, Try presets (184/187), `AskOverlay` (183), workspace upload |
| migration heads | `apps/ze-api/tests/test_migrate.py` L106 (`{"zc038","zm024"} <= heads`) |
| `eval/calibration/routing.py` (+ `--check-sets`, `screen` column) / `ze-eval` runner (+ `setup:`, `{{name.field}}`, judge context) | `eval/calibration/routing.py`, `Makefile` help; `core/ops/ze-eval/ze_eval/{runner,scenario,judge}.py`; `docs/eval.md` |
| `WsScreenContext` (reshaped) | ze-api `api/ws/schemas.py` L204-217 (+ 184 `compose`/`topic`), `tests/api/test_ws_conformance.py`; generated WS types (`packages/ze-client/src/generated/ws.ts`); ze-web senders: `features/ask-bar` (183), `widgets/chat-workspace` (`useChatWorkspace` `context` option, `ScreenContext` TS type L20-ish) |
| `MessageTrace` (+ `screen`) / `record_trace` | ze-core `conversation/messages/types.py`, `nodes/trace.py`, `conversation/turn.py` (partial frames); ze-api `api/v0/messages/views.py` (`build_view`, `evaluate_retry`), `api/schemas.py` `MessageTraceResponse`, `WsTraceUpdateFrame`; ze-web `widgets/message-trace`, `widgets/chat-workspace/ui/trace-panel/*` |
| `Message` (+ `screen_context`) / message store | ze-core `conversation/messages/types.py` L76, the Postgres message store save/load; ze-api `api/ws/turns.py` (save), retry loader |
| `ZePlugin` (+ `screen_resolvers()`) | ze-plugin `plugin.py`, `bootstrap.py`; ze-sdk re-export; plugins `ze_personal`, `ze_calendar`, `ze_news` (implement); `ze_finance`, `ze_messenger`, `ze_prospecting` (inherit default) |
| `NotificationStore` (+ `get`) | ze-proactive `notification_store.py`; fakes in `apps/ze-api/tests/api/test_workspace_followthrough.py`, `tests/test_governor_acceptance.py` |
| ze-web `Module` (+ `onChatAbout`, `chatAboutLabel`) | `shared/ui/hud/Module.tsx` (183) and every module consumer from 183 onward; 184 claim cards in `@myguyze/ze-ui` `PrimitiveRenderer` (chip via renderer context callback) |

## Design

### `ze-agents` (`ze_agents/screen.py`, new)

`ScreenRef(kind, id, label=None, component=None)`, `CanvasRef(index, type, ref=None)`, `ScreenContext(place, route, origin="ask_bar", subject=(), selection=(), visible=(), focused_module=None, canvas=(), captured_at=None, compose=None, topic=None, workspace_placed=None)` with `from_wire(dict)` (validates caps, drops unknown keys), `ScreenPosture(kind, source, confidence, updated_at)`, `ScreenLine(ref, label, summary, posture, status)`, `ScreenResolver` Protocol, `ResolveContext(now, captured_at, origin)`. `ze_sdk` re-exports them (`ze_sdk.screen`).

### `ze-core` (`ze_core/screen/`, new)

- `registry.py`: `ScreenResolverRegistry.register(resolver)`; `DuplicateScreenKindError(ZeError)`.
- `note.py`: `build_screen_note(ctx, registry, now) -> ScreenResolution` — dedupe refs by `(kind, id)` keeping the highest slot; group by kind; `asyncio.wait_for` per resolver call (300 ms) inside an overall 800 ms `asyncio.wait`; `notification` lines ask the registry for their target one hop; stale check `posture.updated_at > ctx.captured_at`; format per contract; budget fill; trace rows. Pure formatting helpers (`format_line`, `posture_words`, `fill_budget`) unit-tested without I/O.
- `orchestration/nodes/screen.py`: `resolve_screen(state, config)` → `{screen_note, screen_trace, screen_subject_line}`; no context or no registry → `{}`; the whole body in `try/except` (warning, `{}`).
- `judgment_state.py`: `build_judgment_state(state, screen_line=None)`; only `nodes/routing.py` passes `state["screen_subject_line"]` when `screen_hint` is on (the skills state never gets it); `_tier_focus` no longer reads `screen_context_note`.
- `state.py`: `screen_note`, `screen_trace`, `screen_subject_line`; `conversation/turn.py` `make_graph_input` resets all three.
- `graph.py`: insert the node on both pre-route branches.
- `nodes/context.py`: delete L313-356 workflow/workspace branches and `_build_screen_context_note`; set `agent_context.screen_context_note = state.get("screen_note")`; 184's preset helpers read `ScreenContext.compose/topic` and set `agent_context.preset_note`. ze-agents `AgentContext.preset_note`; `BaseAgent` renders it after the screen note; `_prompt_note_kwargs` copies it.
- `nodes/trace.py` + `conversation/messages/types.py`: `ScreenTrace`, `MessageTrace.screen`; `Message.screen_context`; migration `zc039`.
- `ze_core/settings` / routing surface config: `system_one.surfaces.routing.screen_hint: bool = False`.

### Resolvers (owning packages)

One module per package, `screen_resolvers.py`, exporting a factory `build_screen_resolvers(...) -> list[ScreenResolver]`, constructed in ze-api wiring with the stores already built there: ze-automation (`GoalScreenResolver` for `goal`/`goal_gate`, `WorkflowScreenResolver` for `workflow`/`workflow_execution` using 184's `failure_summary`, `HeldWriteScreenResolver`), ze-worldstate (`LoopScreenResolver`), ze-memory (`EntityScreenResolver`, `FactScreenResolver`, `ProcedureScreenResolver`), ze-skills (`SkillScreenResolver`), ze-workspace (`WorkspaceRunScreenResolver`, `WorkspacePlacedScreenResolver`), ze-proactive (`NotificationScreenResolver` + `NotificationStore.get`), ze-correlation (`HypothesisScreenResolver`). Plugins: ze-personal `ContactScreenResolver`, ze-calendar `ReminderScreenResolver`, ze-news `NewsArticleScreenResolver`, returned from `screen_resolvers()`.

### `ze-api`

- `api/ws/schemas.py`: reshaped `WsScreenContext` (+ `WsScreenRef`, `WsCanvasRef`, `origin`); conformance test.
- `api/ws/turns.py`: parse with `ScreenContext.from_wire` (warnings → `config_extra["screen_context_invalid"]` for the trace; never fails the turn); store on the user `Message`; `config_extra["screen_context"]`; retry path reads the stored context (OQ-2).
- `wiring/container.py`: build the registry from core factories + `plugin.screen_resolvers()`; put it in `configurable["screen_resolvers"]`.
- `api/schemas.py` / `api/v0/messages/views.py`: `MessageTraceResponse.screen`; `trace_update` frame; `make codegen`.

### Web

- `entities/screen-context/`: store (`publications: Map<token, Partial>`), `useScreenPublisher(partial)` (register on mount, update on change, remove on unmount), `screenSnapshot(place, route)` merging publications in mount order with caps, `captured_at`.
- One send path: `useChatWorkspace.sendMessage` builds `{ ...screenSnapshot(), ...explicitContext }` for every caller (composer, overlay, presets with `origin: "preset"`, workspace uploads); 187 moves it with the canvas. `features/ask-bar` passes explicit context only; `resolve-screen.ts` deleted; `origin` reverts to `ask_bar` after the first send.
- `features/ask-bar`: `chatAbout(ref, element?)` — off `/ask`: overlay with subject, suggestions, empty focused bar; on `/ask`: composer subject chip (with remove), suggestions above the composer, focus; both glance. `model/suggestions.ts` (EN/PT table).
- FSD: `ConnectedPrimitiveTree` gets `onChatAbout` by prop; `widgets/chat-workspace` (message list) and each place's widgets read `chatAbout` and pass callbacks to rows, marks and cards.
- `shared/ui/hud/Module.tsx`: `onChatAbout`, `chatAboutLabel`; `shared/ui/hud/ChatAboutChip.tsx` (bracketed `.ctl.cmd` chip; under `(hover: hover)` hidden with opacity/transform but in the DOM and focusable, revealed on `:hover`/`:focus-within`; always shown under `(hover: none)`); `c` key handler on the module root.
- `@myguyze/ze-ui` `PrimitiveRenderer`: a renderer-context callback `onChatAbout(claim)` so a 184 `claim_card` shows the chip; `ConnectedPrimitiveTree` forwards its `onChatAbout` prop into that context.
- Interim pages: goal detail and workflow detail call `useScreenPublisher` with their subject and wire `onChatAbout` on their header/module (183 interim pages).
- Trace panel (183 interim): one "Asked from / Asked about" line from `trace.screen`.

### Evals and calibration

- `ze-eval` runner: `setup:` rows inserted through the verifier's DB connection, bound to names and removed after the scenario; `{{name.field}}` substitution in `context:` and `turns`; the judge's turn description includes the context. (Phase 184's T029 has the same fixture need; reported to the Maestro.)
- `eval/scenarios/screen_context.yaml`: deixis per place + one `chat_about` per core kind (FR-020, FR-025) using `setup:`.
- `Makefile`: `calibrate-routing` recipe gains `$(ARGS)` (it ignores it today).
- `eval/calibration/routing.py`: `--check-sets` (schema, row counts per language; no network) and a per-row `screen` column appended to the state's `context` exactly as `build_judgment_state` does; `eval/calibration/routing_screen.jsonl` (EN + PT); a live run only after the user's OK (OQ-1).

## Project Structure

### Documentation (this feature)

```
specs/phases/195-screen-context-awareness/
├── spec.md
├── plan.md
├── tasks.md
└── contracts/screen-context.md
```

### Source Code

```
core/contracts/ze-agents/ze_agents/screen.py                         # NEW
packages/ze-sdk/ze_sdk/screen.py                                      # NEW re-export
core/contracts/ze-plugin/ze_plugin/plugin.py                          # screen_resolvers()
core/engine/ze-core/ze_core/screen/{registry,note}.py                # NEW
core/engine/ze-core/ze_core/orchestration/{graph.py,state.py,nodes/{screen,context,trace}.py}
core/engine/ze-core/ze_core/conversation/{turn.py,messages/types.py,messages/store*.py}
core/engine/ze-core/ze_core/migrations/versions/zc039_message_screen_context.py
core/automation/ze-automation/ze_automation/screen_resolvers.py      # NEW
core/cognition/ze-worldstate/ze_worldstate/screen_resolvers.py        # NEW
core/cognition/ze-memory/ze_memory/screen_resolvers.py                # NEW
core/cognition/ze-correlation/ze_correlation/screen_resolvers.py      # NEW
core/automation/ze-skills/ze_skills/screen_resolvers.py               # NEW
core/ops/ze-workspace/ze_workspace/screen_resolvers.py                # NEW
core/contracts/ze-proactive/ze_proactive/{notification_store.py,screen_resolvers.py}
plugins/{ze-personal,ze-calendar,ze-news}/…/screen_resolvers.py + plugin.py
apps/ze-api/ze_api/{api/ws/{schemas,turns}.py,api/schemas.py,api/v0/messages/views.py,wiring/container.py}
apps/ze-api/config/config.yaml                                        # screen_hint: false
apps/ze-web/src/{entities/screen-context,features/ask-bar,shared/ui/hud/{Module,ChatAboutChip}.tsx,pages/{goal-detail,workflow-detail},widgets/…trace panel line}
packages/ze-ui/src/react/PrimitiveRenderer.tsx                        # onChatAbout callback for claim cards
eval/scenarios/screen_context.yaml; eval/calibration/routing_screen.jsonl
core/ops/ze-eval/ze_eval/{runner,scenario,judge}.py (setup:, substitution, judge context); eval/calibration/routing.py (--check-sets, screen column); apps/ze-api/tests/test_migrate.py
apps/ze-web/src/widgets/chat-workspace/model/useChatWorkspace.ts (single send path)
```

## Docs touched ([DOCS] tasks)

- `docs/native-interface.md` (the `context` shape, `origin`, "Chat about this", trace `screen`), `docs/architecture.md` (graph flow: `resolve_screen`), `docs/extending-ze.md` and `docs/sdk.md` (`screen_resolvers()`, `ze_sdk.screen`), `docs/frontend.md` (screen-context store, publisher, chip), `docs/system-one.md` (`screen_hint` flag, calibration rows), `docs/eval.md` (screen scenarios), `DESIGN.md` Components (the "Chat about this" chip on modules), package READMEs of ze-core and each package that gained a resolver, `AGENTS.md` (graph flow line, migration table `zc039`, phase row), `specs/README.md`.
- Coverage check against `git diff main...HEAD --stat`.

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| New node before routing | Routing runs before `fetch_context`; the subject must exist when routing could use it, and the note is needed in every subtask context | Resolving inside `fetch_context` (no routing hint possible; routing hint becomes a second resolver pass) |
| Resolvers in owning packages | Keeps domain knowledge out of `ze_core` and lets plugins add kinds | One central resolver in ze-core (would import every domain package) |
| Stored context on messages | Retry is otherwise about nothing; the context is small (refs, labels) | No storage (retry loses the screen, the 184 known gap stays) |
