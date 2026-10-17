# Tasks: Screen Context Awareness

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [contracts/screen-context.md](./contracts/screen-context.md).

**Build gate**: 183 landed (Ask bar, overlay, `Module`, places); 184 T037 landed (eval `context`). The user answers OQ-1 (routing hint calibration) and OQ-2 (store context for Retry); tasks follow the recommendations. Spec Architect (Lintel) on call.

**Tests**: required (constitution V). **Fail-first**. Fakes and `AsyncMock` pools; `@pytest.mark.pg` for new SQL; no OpenRouter or System One call in default suites; no live calibration run in this phase.

**Lanes**: `[ENG]` Claude Sonnet lane lead (contract, engine, registry, wiring, migration, gates). `[JR]` OpenCode junior (resolvers with exact store calls, web store/chip, evals). Floor Reviewer reviews per user story.

**Tags**: `[BACKEND]` · `[WEB]` · `[PLATFORM]` · `[DOCS]`.

**Rules for the implementer**
- Before changing a symbol in plan.md "Blast radius", run `graphify affected "<Symbol>" --depth 2` and `rtk proxy grep -rn "screen_context" --include='*.py' core apps plugins packages eval`; update every caller in the same change.
- Posture comes from the record the resolver just loaded; client labels are display hints only.
- The note is runtime-only: never checkpoint it, never pass it to memory or intake.
- New `AgentState` keys are reset in `make_graph_input`.
- Pre-v1 hard cut: old context fields, `_build_screen_context_note`, `resolve-screen.ts` deleted with their callers.
- Shared worktree: `git add <paths>`; `git commit -m ... -- <paths>`; never `git add -A` or `git stash`. Commit only when asked; split by user story.

---

## Phase 0: Gate [ENG]

- [ ] T001 [ENG] [BACKEND] Rebase onto `main`. `graphify update .`; `graphify affected` on `fetch_context`, `_build_screen_context_note`, `record_trace`, `MessageTrace`, `ZePlugin`, `build_judgment_state`, plus the grep in the rules. Record in the Handoffs note: (a) differences from plan.md "Blast radius"; (b) the `zc` head (expect `zc038`); (c) the procedure store's lookup-by-id method name and the contact/reminder/news lookup methods in the three plugins; (d) the TS `ScreenContext` type users in ze-web after 183. Stop and report differences.

## Phase 1: Contract (blocks everything) [US1–US5]

- [ ] T002 [ENG] [BACKEND] Tests first `core/contracts/ze-agents/tests/test_screen.py`: `ScreenContext.from_wire` parses the contract example, applies caps (3/20/30/12, label ≤ 120, route ≤ 200), defaults `origin` to `ask_bar`, drops unknown keys, rejects an unknown `place` with a typed error. Implement `ze_agents/screen.py` (all types + `ScreenResolver` Protocol + `ResolveContext`); re-export from `packages/ze-sdk/ze_sdk/screen.py` and `ze_sdk/__init__.py`; extend `packages/ze-sdk/tests` export test.
- [ ] T003 [JR] [BACKEND] `apps/ze-api/ze_api/api/ws/schemas.py`: reshape `WsScreenContext` (+ `WsScreenRef`, `WsCanvasRef`, `origin`), delete `screen`, `goal_id`, `workflow_id`, `execution_id`; keep 184's `compose`/`topic` and `workspace_placed`. Extend `tests/api/test_ws_conformance.py`; `make codegen`.
- [ ] T004 [ENG] [PLATFORM] `zc039_message_screen_context.py` (ze-core versions dir; `down_revision` = head from T001): add/drop `messages.screen_context JSONB NULL`; `Message.screen_context: dict | None`; the Postgres message store saves and loads it (unit test with a fake pool; `@pytest.mark.pg` round trip in `apps/ze-api/tests/pg/`).

## Phase 2: Registry and note [US1, US2, US3]

- [ ] T005 [ENG] [BACKEND] Tests first `core/engine/ze-core/tests/screen/test_note.py` (pure helpers + fake resolvers): contract note format line by line; posture words (suspicion → "suspected (not confirmed)", inference → "inferred", confidence printed when < 0.9); deixis lines (subject; selection count; nothing singled out); `chat_about` lead line; dedupe across slots; stale when `updated_at > captured_at`; missing; failed (raising resolver); timeout (resolver sleeping past 300 ms); 800 ms total budget; unknown kind; `notification` one-hop to its target's resolver; budget fill to 1200 with "+N more" and `cut` rows; a property test over random ref sets never exceeds 1200. Implement `ze_core/screen/{registry,note}.py` (`DuplicateScreenKindError`).
- [ ] T006 [ENG] [BACKEND] Tests first `tests/orchestration/nodes/test_screen.py`: no context → `{}`; context → `screen_note` and `screen_trace`; `screen_hint` false → `routing_hints` untouched; true → one capped line appended after the plugin's hints. Then `test_context.py`: `fetch_context` copies `state["screen_note"]` into `agent_context.screen_context_note`; delete the workflow-note cases. Then a two-turn graph test: a turn with context, then one without → no note on the second (`make_graph_input` reset). Implement `nodes/screen.py`, `state.py`, `conversation/turn.py`, `graph.py` (both pre-route branches), `nodes/context.py` (delete L313-356 branches and `_build_screen_context_note`), config `system_one.surfaces.routing.screen_hint: false` in `apps/ze-api/config/config.yaml` and the routing surface config type.

## Phase 3: Core resolvers [US2]

Each task: tests first with a fake store (ok, missing, posture fields, summary content per the contract table, never raw error text), then `screen_resolvers.py` with `build_screen_resolvers(...)`.

- [ ] T007 [P] [JR] [BACKEND] ze-automation: `goal`, `goal_gate`, `workflow`, `workflow_execution` (uses 184 `failure_summary`), `held_write`.
- [ ] T008 [P] [JR] [BACKEND] ze-worldstate: `loop`.
- [ ] T009 [P] [JR] [BACKEND] ze-memory: `entity` (one-hop relation names, cap 5), `fact` (value sentence, never the raw key), `procedure` (method from T001(c)); `@pytest.mark.pg` for the entity one-hop query.
- [ ] T010 [P] [JR] [BACKEND] ze-skills `skill`; ze-workspace `workspace_run` and `workspace_placed` (the existing text, moved from `fetch_context`); ze-correlation `hypothesis`.
- [ ] T011 [P] [JR] [BACKEND] ze-proactive: `NotificationStore.get(id)` (+ fake-store updates in `apps/ze-api/tests/api/test_workspace_followthrough.py`, `tests/test_governor_acceptance.py`, `@pytest.mark.pg`), `notification` resolver returning its target ref for the one-hop.

## Phase 4: Plugins and wiring [US2, US5]

- [ ] T012 [ENG] [BACKEND] `ZePlugin.screen_resolvers()` (default `[]`) in ze-plugin + test; ze-api `wiring/container.py` builds `ScreenResolverRegistry` from every core factory (T007–T011) and every plugin's `screen_resolvers()`, puts it in `configurable["screen_resolvers"]`; duplicate kind fails startup (test).
- [ ] T013 [P] [JR] [BACKEND] Plugins: ze-personal `contact`, ze-calendar `reminder`, ze-news `news_article` resolvers (via `ze_sdk.screen` only) returned from `screen_resolvers()`; tests per plugin; `packages/ze-sdk/tests/test_plugin_boundaries.py` passes.
- [ ] T014 [ENG] [BACKEND] `api/ws/turns.py`: parse with `ScreenContext.from_wire`, store on the user message, set `config_extra["screen_context"]`; retry path passes the stored context (OQ-2). Tests: message turn stores and passes it; retry passes the stored one; a message without context passes none.

## Phase 5: Trace [US4]

- [ ] T015 [ENG] [BACKEND] Tests first: `record_trace` writes `MessageTrace.screen` (contract shape incl. `origin`); REST `getMessageTrace` and the partial `trace_update` frame carry it. Implement `ScreenTrace` in `conversation/messages/types.py`, `nodes/trace.py`, `api/schemas.py` `MessageTraceResponse`, `api/v0/messages/views.py`, WS frame; `make codegen`.

## Phase 6: Web — store, Ask bar, chip [US5, US8]

- [ ] T016 [ENG] [WEB] Tests first `entities/screen-context/model/*.test.ts`: publisher registers/updates/removes on unmount; snapshot merges in mount order, applies caps, sets `captured_at`; `place` from `placeOf`. Implement `entities/screen-context`.
- [ ] T017 [ENG] [WEB] `features/ask-bar`: replace `resolve-screen.ts` with `screenSnapshot` (delete the file and its test); explicit `askAbout` context still merges over it; `chatAbout(ref, element?)` per FR-022 and `model/suggestions.ts` (spec table, EN/PT, fallback); the overlay shows suggestion chips (keys 1–3) when opened by `chatAbout` with an empty bar and calls `glance(element)`. Tests: snapshot sent on submit; queued item keeps the submit-time snapshot; `chatAbout` subject/origin/suggestions/glance; picking a suggestion submits it; reduced motion skips the glance.
- [ ] T018 [P] [JR] [WEB] `shared/ui/hud/ChatAboutChip.tsx` and `Module` props `onChatAbout`, `chatAboutLabel` per FR-021. Tests: accessible name "Chat about <label>"; reveal class under `(hover: hover)`, always visible under `(hover: none)` (mocked `matchMedia`); click fires; `c` inside the module fires, `c` inside an input does not; no chip without `onChatAbout`.
- [ ] T019 [JR] [WEB] `packages/ze-ui` `PrimitiveRenderer`: renderer-context `onChatAbout(claim)`; a `claim_card` shows the chip when the callback exists; ze-web `ConnectedPrimitiveTree` wires it to `chatAbout({ kind: claim.subject, id: claim.ref_id, label: title, component: "claim_card" })`. Tests on both sides.
- [ ] T020 [JR] [WEB] Interim pages: goal detail publishes `{ kind: "goal" }` and wires `onChatAbout` on its main module; workflow detail publishes `workflow` (+ `workflow_execution` from `?execution=`) and wires it on the workflow module and execution rows; the interim trace panel shows the "Asked from / Asked about" line from `trace.screen`. Tests per page.

## Phase 7: Evals and calibration rows [US1, US7, US8]

- [ ] T021 [JR] [BACKEND] `eval/scenarios/screen_context.yaml` per FR-019 and FR-024 (deixis per place EN+PT; one `chat_about` per core kind; Governance case tagged skip until 190), seeded fixtures, judge criteria from the spec. Run on `make dev-eval`; record results in the Handoffs note.
- [ ] T022 [JR] [BACKEND] `eval/calibration/routing_screen.jsonl` (EN + PT rows: prompt asked from a screen, the subject line as it would be appended, gold agent); `make calibrate-routing --check-sets` passes offline. No live run.

## Phase 8: Gates [ENG]

- [ ] T023 [ENG] [PLATFORM] `make test-py`, `make test-pg`, `make lint`, `make test-web`, `make typecheck-web`, `make web-build`; SC-004 grep; capture of "Chat about this" on the interim goal page at 1440 and 390 (chip visible on hover and on touch emulation). Record results and commit.

## Phase 9: Docs [DOCS]

- [ ] T024 [P] [DOCS] `docs/native-interface.md`, `docs/architecture.md`, `docs/extending-ze.md`, `docs/sdk.md`, `docs/frontend.md`, `docs/system-one.md`, `docs/eval.md` per plan.md. `doc-style` skill.
- [ ] T025 [P] [DOCS] `DESIGN.md` Components: the "Chat about this" chip on modules (bracketed chip, reveal on hover/focus, visible on touch, `c` key). Package READMEs: ze-core, ze-automation, ze-worldstate, ze-memory, ze-skills, ze-workspace, ze-proactive, ze-correlation, ze-personal, ze-calendar, ze-news.
- [ ] T026 [DOCS] `AGENTS.md` (graph flow with `resolve_screen`, migration table `zc039` messages.screen_context, layout note `ze_core/screen/`, phase row 195), `specs/README.md` row; status Implemented after T023.
- [ ] T027 [DOCS] Coverage check against `git diff main...HEAD --stat`.

---

## Dependencies

- T001 → all. T002 → T003, T005, T007–T013. T004 → T014.
- T005 → T006 → T014 → T015. T007–T011 → T012. T012 + T013 → T021.
- T003 → T016 → T017; T018 → T019, T020; T017 → T020.
- T021, T022 after T006 and T012. T023 after everything; docs after T023 (drafts earlier).

## Parallel examples

- T007 ∥ T008 ∥ T009 ∥ T010 ∥ T011 (different packages).
- T018 ∥ T016.
- T024 ∥ T025.

## Lanes

### Lane ENG (Claude Sonnet, lane lead)

Tasks: T001, T002, T004–T006, T012, T014–T017, T023. Owns `core/contracts/ze-agents/ze_agents/screen.py`, `packages/ze-sdk/ze_sdk/screen.py` (+ `__init__`), `core/contracts/ze-plugin/ze_plugin/plugin.py`, `core/engine/ze-core/**`, `apps/ze-api/ze_api/{api/ws/turns.py,api/schemas.py,api/v0/messages/**,wiring/**}`, `apps/ze-api/config/config.yaml`, `apps/ze-web/src/{entities/screen-context,features/ask-bar}/**`, this phase's `tasks.md`.

### Lane JR (OpenCode junior)

Tasks: T003, T007–T011, T013, T018–T022. Owns `apps/ze-api/ze_api/api/ws/schemas.py` (+ conformance test), each package's `screen_resolvers.py` and its tests, `core/contracts/ze-proactive/ze_proactive/notification_store.py` (`get`), the three plugins' `screen_resolvers.py` and `plugin.py` hook, `apps/ze-web/src/shared/ui/hud/{Module,ChatAboutChip}.tsx`, `packages/ze-ui/src/react/**`, `apps/ze-web/src/features/primitive-tree/**`, the interim goal/workflow detail pages and trace-panel line, `eval/scenarios/screen_context.yaml`, `eval/calibration/routing_screen.jsonl`.

### Docs (Docs Steward)

Tasks: T024–T027.
