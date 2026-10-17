# Tasks: Screen Context Awareness

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [contracts/screen-context.md](./contracts/screen-context.md).

**Build gate**: 183 and 184 landed (184's `_compose_preset`/`_preset_envelope`, `failure_summary`, `list_progress`, `zpro005`, T037). The Maestro reserved migration `zc039`. The user answered on 2026-10-17: OQ-1 routing hint built off behind the flag, enabled only after a user-approved live calibration; OQ-2 store the context for Retry. Spec Architect (Lintel) on call.

**Tests**: required (constitution V). **Fail-first**. Fakes and `AsyncMock` pools; `@pytest.mark.pg` for new SQL; no OpenRouter or System One call in default suites; **no live calibration run** in this phase.

**Lanes**: `[ENG]` Claude Sonnet lane lead (contract, engine, registry, wiring, migration, send path, eval harness, calibration tooling, gates). `[JR]` OpenCode junior (resolvers with the store calls listed in the contract, web chip, evals). Floor Reviewer reviews per user story.

**Tags**: `[BACKEND]` · `[WEB]` · `[PLATFORM]` · `[DOCS]`.

**Rules for the implementer**
- Before changing a symbol in plan.md "Blast radius", run `graphify affected "<Symbol>" --depth 2` and `rtk proxy grep -rn "screen_context" --include='*.py' core apps plugins packages eval`; update every caller in the same change.
- Posture comes from the record the resolver just loaded; client labels are display hints only; every string entering the note is sanitised (FR-009).
- The note is reset each turn by `make_graph_input`, stays in checkpointed state within the turn (confirmation resume), and is never written to memory or passed to the intake.
- The tier judge's state never gains screen text; `routing_hints` is never modified.
- A bad or partial context never fails a turn.
- FSD: no feature or entity imports `features/ask-bar` across slices; callbacks go down by props from widgets.
- Pre-v1 hard cut: old context fields, `_build_screen_context_note`, `resolve-screen.ts` deleted with their callers.
- Shared worktree: `git add <paths>`; `git commit -m ... -- <paths>`; never `git add -A` or `git stash`. Commit only when asked; split by user story.

---

## Phase 0: Gate [ENG]

- [x] T001 [ENG] [BACKEND] Rebase onto `main`. `graphify update .`; `graphify affected` on `fetch_context`, `_build_screen_context_note`, `record_trace`, `MessageTrace`, `ZePlugin`, `build_judgment_state`, `_compose_preset`, plus the grep in the rules. Record in the Handoffs note: (a) differences from plan.md "Blast radius"; (b) the `zc` head (expect `zc038`) and the reserved number; (c) the lookup-by-id call for **every** kind in the contract table (confirm or correct each row, including the procedure store and the contact, reminder and news lookups in the three plugins); (d) the TS `ScreenContext` users in ze-web after 183 and every caller of `useChatWorkspace.sendMessage`; (e) that `eval/calibration/complexity*.jsonl` still has no screen-note rows. Stop and report differences.

## Phase 1: Contract (blocks everything) [US1–US5]

- [x] T002 [ENG] [BACKEND] Tests first `core/contracts/ze-agents/tests/test_screen.py`: `ScreenContext.from_wire` parses the contract example; applies every cap (refs 3/20/30/12; `kind`/`id`/`parent_id` 64; `label` 120; `component` 40; `route` 200; `focused_module` 80); accepts a missing `place` (`None`); drops an unknown `place`, malformed refs and unknown keys, returning warnings, never raising; clamps a future `captured_at` to the receipt time; defaults `origin` to `ask_bar`; parses a 184 partial `{ compose: "slipping" }`. Implement `ze_agents/screen.py` (all types, `ScreenResolver` Protocol, `ResolveContext`, sanitiser helpers); re-export from `packages/ze-sdk/ze_sdk/screen.py` and `ze_sdk/__init__.py`; extend the ze-sdk export test.
- [x] T003 [JR] [BACKEND] `apps/ze-api/ze_api/api/ws/schemas.py`: reshape `WsScreenContext` (+ `WsScreenRef` with `parent_id`/`as_of`/`component`, `WsCanvasRef`, `origin`), delete `screen`, `goal_id`, `workflow_id`, `execution_id`; keep `compose`/`topic` and `workspace_placed`. Extend `tests/api/test_ws_conformance.py`; `make codegen`.
- [x] T004 [ENG] [PLATFORM] `zc039_message_screen_context.py` (reserved number; `down_revision` = head from T001): add/drop `messages.screen_context JSONB NULL`; update `apps/ze-api/tests/test_migrate.py` heads (`zc039`); `Message.screen_context: dict | None`; the Postgres message store saves and loads it (fake-pool unit test; `@pytest.mark.pg` round trip in `apps/ze-api/tests/pg/`).

## Phase 2: Registry and note [US1, US2, US3]

- [x] T005 [ENG] [BACKEND] Tests first `core/engine/ze-core/tests/screen/test_note.py` (pure helpers + call-counting fake resolvers): contract note format line by line; posture words from 184's vocabulary; binding variants (subject; lone selection with no subject → "this"; selection "shown above" with "M more not shown"; nothing singled out); PT wording hint present; `chat_about` line only with `origin: "chat_about"`; dedupe across slots; `changed` when `updated_at > ref.as_of`, no check without `as_of`; `missing`; `failed` (raising); `timeout` (sleeping past 300 ms); 800 ms total; unknown kind; `notification` one hop builds the target ref with `parent_id`; budget planned before loading — refs not admitted are never passed to a resolver and are counted and traced `cut`; property test over random ref sets: note ≤ 1200 and cut refs never loaded; sanitising: a title with a newline and a forged `"this" = …` line or `[Screen:` header renders as one inert line. Implement `ze_core/screen/{registry,note}.py` (`DuplicateScreenKindError`).
- [x] T006 [ENG] [BACKEND] Tests first `tests/orchestration/nodes/test_screen.py`: no context → `{}`; no registry → `{}`; a raising builder → `{}` and a warning; context → `screen_note`, `screen_trace`, `screen_subject_line`. `tests/orchestration/test_judgment_state.py` / `test_tier_state.py`: routing state unchanged with `screen_hint` off; one capped line appended to the routing `context` with it on; the skills state (`match_skills`) unchanged with it on; tier state never contains the note or the subject line (both cases); `routing_hints` unchanged. `test_context.py`: `fetch_context` copies `screen_note` into `screen_context_note`; delete the workflow-note cases; a 184 preset turn with a screen note has both `screen_context_note` and `preset_note` set and both rendered by `BaseAgent` (order: screen, then preset). Graph tests: two turns on one thread (context, then none) → no note on the second; a turn paused at `await_write_confirmation` and resumed still has the note in the executing agent's context. Implement `nodes/screen.py`, `state.py`, `conversation/turn.py` (`make_graph_input` resets the three keys), `graph.py` (both pre-route branches), `judgment_state.py` (a `screen_line` parameter on `build_judgment_state`, passed only by `nodes/routing.py`), `nodes/context.py` (delete L313-356 branches and `_build_screen_context_note`; 184 preset helpers on typed fields → `preset_note`), ze-agents `AgentContext.preset_note`, `base_agent.py`, `nodes/execution.py` `_prompt_note_kwargs`, config `system_one.surfaces.routing.screen_hint: false` in `apps/ze-api/config/config.yaml` and the routing surface config type. Update 184's context tests to the typed context.

## Phase 3: Core resolvers [US2]

Each task: tests first with a fake store (ok, missing, posture fields, summary per the contract table, sanitised, never raw error text), then `screen_resolvers.py` with `build_screen_resolvers(...)`.

- [x] T007 [P] [JR] [BACKEND] ze-automation: `goal` (uses 184 `list_progress` fields when present), `goal_gate`, `workflow`, `workflow_execution` (`get_execution(parent_id, id)`; no `parent_id` → `failed` "missing parent"; 184 `failure_summary`), `held_write`.
- [x] T008 [P] [JR] [BACKEND] ze-worldstate: `loop` (flags from the row only: "has a reminder", "linked to a goal").
- [x] T009 [P] [JR] [BACKEND] ze-memory: `entity` (one-hop relation names, cap 5), `fact` (value sentence, never the raw key), `procedure` (method from T001(c)); `@pytest.mark.pg` for the entity one-hop query.
- [x] T010 [P] [JR] [BACKEND] ze-skills `skill`; ze-workspace `workspace_run` and `workspace_placed` (existing text moved from `fetch_context`); ze-correlation `hypothesis`.
- [x] T011 [P] [JR] [BACKEND] ze-proactive: `NotificationStore.get(id)` (+ fake-store updates in `apps/ze-api/tests/api/test_workspace_followthrough.py`, `tests/test_governor_acceptance.py`; `@pytest.mark.pg`), `notification` resolver returning the target ref with `parent_id` from `target_parent_id` (184 `zpro005`).

## Phase 4: Plugins and wiring [US2, US5, US6]

- [x] T012 [ENG] [BACKEND] `ZePlugin.screen_resolvers()` (default `[]`) + test; ze-api `wiring/container.py` builds `ScreenResolverRegistry` from every core factory (T007–T011) and every plugin's `screen_resolvers()` into `configurable["screen_resolvers"]`; duplicate kind fails startup (test).
- [x] T013 [P] [JR] [BACKEND] Plugins: ze-personal `contact`, ze-calendar `reminder`, ze-news `news_article` resolvers via `ze_sdk.screen`, returned from `screen_resolvers()`; tests per plugin; `packages/ze-sdk/tests/test_plugin_boundaries.py` passes.
- [x] T014 [ENG] [BACKEND] `api/ws/turns.py`: `from_wire` (warnings → `screen_context_invalid` for the trace), store on the user message, `config_extra["screen_context"]`; retry passes the stored context (OQ-2). Tests: stores and passes; invalid context → turn proceeds with warnings traced; retry passes the stored one; retry of a stored ref whose record changed since → `changed`; no context → none. The eval router passes `context` through `from_wire` too.

## Phase 5: Trace [US4]

- [x] T015 [ENG] [BACKEND] Tests first: `record_trace` writes `MessageTrace.screen` (contract shape incl. `origin`, `invalid`); REST `getMessageTrace` and the partial `trace_update` frame carry it. Implement `ScreenTrace` in `ze_core.conversation.messages.types` (serde allowlist), `nodes/trace.py`, `api/schemas.py`, `api/v0/messages/views.py`, the WS frame; `make codegen`.

## Phase 6: Web — store, send path, chip [US5, US8]

- [x] T016 [ENG] [WEB] Tests first `entities/screen-context/model/*.test.ts`: publisher registers/updates/removes on unmount; refs keep `as_of` and `parent_id`; snapshot merges in mount order, applies caps, sets `captured_at`; `place` from `placeOf`. Implement `entities/screen-context`.
- [x] T017 [ENG] [WEB] One send path: `useChatWorkspace.sendMessage` builds `{ ...screenSnapshot(), ...explicitContext }`; tests per caller: Ask composer, overlay queued item (keeps its submit-time snapshot), Try preset (`origin: "preset"`), workspace upload (`workspace_placed` merged). `features/ask-bar`: delete `resolve-screen.ts` (+ test); explicit `askAbout` context kept until close; `origin` reverts to `ask_bar` after the first send (test: first message `chat_about`, second `ask_bar`, same subject).
- [x] T018 [P] [JR] [WEB] `shared/ui/hud/ChatAboutChip.tsx` and `Module` props per FR-022. Tests: accessible name "Chat about <label>"; under `(hover: hover)` present in the DOM and reachable by Tab while visually hidden (no `display:none`/`visibility:hidden`); visible under `(hover: none)`; click fires; `c` inside the module fires, inside an input does not; no chip without `onChatAbout`.
- [x] T019 [ENG] [WEB] `chatAbout(ref, element?)` in `features/ask-bar` with `model/suggestions.ts` (EN/PT table): off `/ask` opens the overlay (subject, suggestions keys 1–3, empty focused bar); on `/ask` sets the composer subject chip (with remove), suggestions above the composer, focus; both call `glance(element)` (skipped under reduced motion); picking a suggestion submits it. Tests for both places and the glance.
- [x] T020 [JR] [WEB] `packages/ze-ui` `PrimitiveRenderer`: renderer-context `onChatAbout(claim)`; a `claim_card` shows the chip when present. `features/primitive-tree/ConnectedPrimitiveTree` takes an `onChatAbout` prop and forwards it (no import of `features/ask-bar`); `widgets/chat-workspace`'s message list passes `chatAbout`. Tests on both sides.
- [x] T021 [JR] [WEB] Interim pages (widgets/pages layer): goal detail publishes `{ kind: "goal", as_of }` and passes `onChatAbout` to its main module; workflow detail publishes `workflow` and, from `?execution=`, `workflow_execution` with `parent_id`, and passes `onChatAbout` to the workflow module and execution rows; the interim trace panel shows "Asked from / Asked about" from `trace.screen`. Tests per page.

## Phase 7: Eval harness, evals, calibration tooling [US1, US7, US8]

- [x] T022 [ENG] [BACKEND] `ze-eval` runner: scenario `setup:` (rows created through the REST API where one exists, otherwise inserted through the verifier's DB connection only into tables the verifier already touches, with every NOT NULL and linked row filled; bound to names, deleted after the scenario; each kind's insert covered by a runner test against the real schema, `@pytest.mark.pg`), `{{name.field}}` substitution in `context:` and `turns`, the judge's turn description includes the context; tests in `core/ops/ze-eval/tests`; `docs/eval.md`.
- [ ] T023 [JR] [BACKEND] `eval/scenarios/screen_context.yaml` per FR-020 and FR-025 using `setup:`; Governance case tagged skip until 190. Run on `make dev-eval`; record results in the Handoffs note.
- [x] T024 [ENG] [BACKEND] `eval/calibration/routing.py`: `--check-sets` (schema and per-language row counts; no network; mirrors the other calibration scripts) and a per-row `screen` column appended to the state's `context` exactly as `build_judgment_state` does with `screen_hint` on; `Makefile`: change the `calibrate-routing` recipe to `uv run python eval/calibration/routing.py $(ARGS)` (it ignores `ARGS` today, so the gate would run live) and add the help line; a test that parses the Makefile and asserts the recipe contains `$(ARGS)`; tests in `core/engine/ze-core/tests/routing/test_calibration_script.py`. Never run `make calibrate-routing` (or the script without `--check-sets`) before this task lands.
- [x] T025 [JR] [BACKEND] `eval/calibration/routing_screen.jsonl` (EN + PT rows: prompt asked from a screen, `screen` subject line, gold agent); `make calibrate-routing ARGS=--check-sets` passes offline. No live run.

## Phase 8: Gates [ENG]

- [ ] T026 [ENG] [PLATFORM] `make test-py`, `make test-pg`, `make lint`, `make test-web`, `make typecheck-web`, `make web-build`, `make calibrate-routing ARGS=--check-sets` (only after T024 lands); SC-004 greps; capture of "Chat about this" on the interim goal page at 1440 and 390 (hover, keyboard Tab, touch emulation). Record results and commit.

## Phase 9: Docs [DOCS]

- [ ] T027 [P] [DOCS] `docs/native-interface.md`, `docs/architecture.md`, `docs/extending-ze.md`, `docs/sdk.md`, `docs/frontend.md`, `docs/system-one.md` (screen hint flag; tier judge unchanged), `docs/eval.md` (setup block) per plan.md. `doc-style` skill.
- [ ] T028 [P] [DOCS] `DESIGN.md` Components: the "Chat about this" chip (bracketed chip, reveal on hover/focus while focusable, visible on touch, `c` key). Package READMEs: ze-core, ze-automation, ze-worldstate, ze-memory, ze-skills, ze-workspace, ze-proactive, ze-correlation, ze-personal, ze-calendar, ze-news.
- [ ] T029 [DOCS] `AGENTS.md` (graph flow with `resolve_screen`, migration table `zc039` messages.screen_context, layout note `ze_core/screen/`, phase row 195), `specs/README.md` row; status Implemented after T026.
- [ ] T030 [DOCS] Coverage check against `git diff main...HEAD --stat`.

---

## Dependencies

- 183 and 184 landed → T001 → all.
- T002 → T003, T005, T007–T014. T004 → T014.
- T005 → T006 → T014 → T015. T007–T011 → T012. T012 + T013 → T023.
- T003 → T016 → T017 → T019; T018 → T019, T020, T021; T019 → T020, T021.
- T022 → T023 (also needs T014 and 184 T037). T024 → T025.
- T026 after everything; docs after T026 (drafts earlier).

## Parallel examples

- T007 ∥ T008 ∥ T009 ∥ T010 ∥ T011 (different packages).
- T018 ∥ T016. T022 ∥ T024.
- T027 ∥ T028.

## Lanes

### Lane ENG (Claude Sonnet, lane lead)

Tasks: T001, T002, T004–T006, T012, T014–T017, T019, T022, T024, T026. Owns `core/contracts/ze-agents/ze_agents/{screen.py,types.py (preset_note only),base_agent.py (note render only)}`, `packages/ze-sdk/ze_sdk/screen.py` (+ `__init__`), `core/contracts/ze-plugin/ze_plugin/plugin.py`, `core/engine/ze-core/**`, `apps/ze-api/ze_api/{api/ws/turns.py,api/schemas.py,api/v0/messages/**,api/eval/router.py,wiring/**}`, `apps/ze-api/config/config.yaml`, `apps/ze-api/tests/test_migrate.py`, `apps/ze-web/src/{entities/screen-context,features/ask-bar}/**`, `apps/ze-web/src/widgets/chat-workspace/model/useChatWorkspace.ts`, `core/ops/ze-eval/**`, `eval/calibration/routing.py`, `Makefile` (help line), `docs/eval.md`, this phase's `tasks.md`.

### Lane JR (OpenCode junior)

Tasks: T003, T007–T011, T013, T018, T020, T021, T023, T025. Owns `apps/ze-api/ze_api/api/ws/schemas.py` (+ conformance test), each package's `screen_resolvers.py` and tests, `core/contracts/ze-proactive/ze_proactive/notification_store.py` (`get`), the three plugins' resolvers and `plugin.py` hook, `apps/ze-web/src/shared/ui/hud/{Module,ChatAboutChip}.tsx`, `packages/ze-ui/src/react/**`, `apps/ze-web/src/features/primitive-tree/**`, `apps/ze-web/src/widgets/chat-workspace/ui/**` (message list prop and trace line only), the interim goal/workflow detail pages, `eval/scenarios/screen_context.yaml`, `eval/calibration/routing_screen.jsonl`.

### Docs (Docs Steward)

Tasks: T027–T030.
