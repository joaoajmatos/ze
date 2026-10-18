# Tasks: UI Primitives v2 (191a)

**Input**: [spec.md](./spec.md) (clarifications 2026-10-18), [plan.md](./plan.md) (Lane Plan), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/primitive-actions.md](./contracts/primitive-actions.md), [quickstart.md](./quickstart.md).

**Tests**: required. **Fail-first**: write the test, run it, see it fail for the stated reason, then implement.

**Build gate**: none; runs now, in parallel with the place phases. 191b starts after this lands.

## Format: `[ID] [P?] [Lane] [Story] Description`

- **[Lane]**: `[L:lead]`, `[L:server]`, `[L:ui]`, `[L:web]`, `[L:docs]` (plan.md Lane Plan).
- **[Story]**: US1 typed actions through gates, US2 fallback, US3 slot primitives, US4 contract and gallery.

**Crew**: Sonnet `lead`, `server`, `ui`, `web`; Haiku `docs`. Contract step first; `server`, `ui` and `web` then run in parallel; `lead` merges `server`, `ui`, then `web`. Tick a task's checkbox in the commit that finishes it.

**Rules**: ze-ui has no Ze deps; ze-components depends only on ze-agents and ze-logging; claim posture and actions never appear in render tool schemas; FSD in ze-web; `git add <paths>`, never `-A` or `stash`.

---

## Phase 1: Setup

- [ ] T001 [L:lead] Branch from `main` (e4d57414 or later). `make install && make web-install`; `graphify update .`; `graphify affected` on `Button`, `PRIMITIVE_TYPES`, `render_tool`, `parsePrimitiveTree`, `PrimitiveRenderer`, `PrimitiveRendererActions`, `usePrimitiveRendererActions`, `usePluginScreenActions`, `run_undo`, `handle_confirm`. Then:
  - list every producer of `Button` and of each primitive type outside tests (the audit);
  - list every transport that carries `components` (WS message frame, `PluginPageResponse`, composed answers, anything else);
  - list every caller of `onButtonAction`.
  
  Record the audit (types with no producer, proposed for removal) and the differences from plan.md "Blast radius" in the Handoffs note; stop and report differences to the Spec Architect (Lintel).

---

## Phase 2: Foundational (contract step, lane `lead`)

- [ ] T002 [L:lead] Tests first in `core/kernel/ze-components/tests/test_actions.py` and `test_schema.py` (extend):
  - each action kind serializes with `kind` and its fields; a `NavigateAction` route without a leading `/` raises `InvalidComponentError` (a `ZeError`);
  - `ToolAction.args` accepts only scalar values;
  - `Button(label, action=AskAction("hi"))` serializes `action` as an object; a string action raises;
  - the exported JSON schema has the four action shapes as a discriminated union and the new primitives (`entity_facet`, `stat_row`, `claim_list`, `sparkline`, `card`; `table.keys`, `table.row_actions`);
  - `UI_CONTRACT_VERSION == "2.0"`.

  Implement `ze_components/actions.py`, the new organisms, the `Table` fields, `Button.action: Action` and the helpers, and switch every pattern producer from T001's list (chat choices become `AskAction`). Remove the primitive types the audit marked unused, with their tests. Update the registries.
- [ ] T003 [L:lead] Run `make codegen` (ze-ui generated types, schema, validators; ze-client). Change `PrimitiveRendererActions` in `packages/ze-ui/src/react/context.tsx` to `onAction(action: Action)`, removing `onButtonAction`. Add `ui_version: "2.0"` to the WS `message` frame (`api/ws/schemas.py`, `interface/native.py`), `PluginPageResponse` and each composed-answer payload from T001's list, plus the WS frames `ui_action` (client) and `ui_action_result` (server). Tests: `apps/ze-api/tests/api/test_ws_schemas.py` (the new frames round-trip; the message frame carries `ui_version`). Commit the generated code with the task.
- [ ] T004 [L:lead] Create `packages/ze-ui/fixtures/{valid,invalid}/` with one valid fixture per existing primitive type (after the audit), named `<type>-<state>.json`, plus invalid fixtures each with a `.expect.json` naming the failing path: a string button action, a navigate route without `/`, and a `table` row count different from `keys`. Add `core/kernel/ze-components/tests/test_fixtures.py`: every valid fixture validates against `export_json_schema()`, every invalid one fails at the expected path, and every type in `PRIMITIVE_TYPES` has a valid fixture (this fails until lane `ui` adds the new types' fixtures; mark those types `xfail` with the reason, and lane `ui` removes the marks).

**Checkpoint**: lanes start.

---

## Phase 3: User Story 1 - Actions ask first, like chat (P1) 🎯 MVP

- [ ] T005 [L:server] [US1] Tests first `core/contracts/ze-agents/tests/test_run_action.py`: `run_action` calls `call_tool` with no approval, so an asks-first write returns a parked `ToolCall`, a READ tool runs, and the constraint veto applies; with `approval=ApprovedCall(call_id)` the parked call runs. Implement `BaseAgent.run_action`.
- [ ] T006 [L:server] [US1] Tests first `apps/ze-api/tests/api/ws/test_ui_actions.py` (fake agent registry and connection manager):
  - a reversible write tool action runs once and sends `ui_action_result` with `ok: true` and the tool's line;
  - an irreversible tool action sends one `confirm_request` (`kind: "write"`, one item with the summary); a `confirm` approve runs it once with `ApprovedCall`, deny sends "Okay, I didn't <effect>.", and the gate timeout sends the same line;
  - an unknown owner, an unknown tool, or a tool not in the owner's `tools` sends "That action is not available." and runs nothing;
  - an action on a busy thread sends `code: "busy"`;
  - the `confirm` branch in `endpoint.py` checks the UI action gates before graph gates, and a graph gate's confirm is unaffected;
  - every run logs `ui_action_run` with owner, tool, gate and outcome.

  Implement `api/ws/ui_actions.py` and the `ui_action` and `confirm` branches in `api/ws/endpoint.py`.
- [ ] T007 [L:server] [US3] Tests first `core/kernel/ze-components/tests/test_render_tools.py` (extend): `render_stat_row`, `render_keyed_table` and `render_sparkline` register as READ render tools; their schemas omit `claim`, `actions`, `row_actions` and any action field; a keyed table whose `keys` length differs from its rows raises; a sparkline over 60 points is truncated. Implement in `ze_components/tools.py`.

---

## Phase 4: User Story 2 - Unknown views degrade to a table (P1)

- [ ] T008 [L:ui] [US2] Tests first `packages/ze-ui/src/parse.test.ts` (extend) and `src/react/PrimitiveRenderer.test.tsx` (extend):
  - a tree with a known and an unknown node parses, and the unknown one becomes `__fallback` with its first 12 scalar fields, nested object arrays parsed as children;
  - a known node missing a required field fails, and the error names the node path and field;
  - `ui_version` `"1.4"` is refused with `PrimitiveContractError`; `"2.3"` parses (unknown types fall back);
  - the fallback renders a two-column table with "Unsupported view: <type>" and its known children inside;
  - no node type renders `null` silently.

  Implement in `parse.ts` and `PrimitiveRenderer.tsx`.

---

## Phase 5: User Story 3 - Slot primitives (P2)

- [ ] T009 [L:ui] [US3] Add valid fixtures for each new primitive in every state (empty where allowed, normal, long text, each posture tone, with and without actions), then tests first in `PrimitiveRenderer.test.tsx` (extend):
  - `entity_facet` shows each fact with its posture tone and source;
  - `stat_row` shows value and change with a direction word or icon label (not color alone);
  - `claim_list` shows each item's posture;
  - `sparkline` draws at most 60 points and its label;
  - `card` renders children and its action buttons;
  - a keyed table's row action calls `onAction` with `{key}` filled from the row;
  - every button, card action, claim-list action and row action calls `onAction` with the typed action;
  - every interactive element has the 44 px class.

  Implement the renderers. Remove T004's `xfail` marks; `src/fixtures.test.ts` parses every fixture and checks every type has one.

---

## Phase 6: Web host and gallery (US1, US4)

- [ ] T010 [L:web] [US1] Tests first `features/primitive-tree/api/usePrimitiveActions.test.ts`:
  - `ask` calls `sendTurn` on the selected thread;
  - `navigate` to `/mind/x` navigates, while a route not starting with `/` or not a place route shows a notice;
  - `compose` sends with `{ origin: "preset", compose }`;
  - `tool` sends one `ui_action` frame with a fresh id, resolves on the matching `ui_action_result`, and shows its line as a notice; it resolves false while disconnected;
  - a second press while one is pending is ignored.

  Implement `usePrimitiveActions.ts`, delete `usePrimitiveRendererActions.ts` and `usePluginScreenActions.ts` (with the `rest:`/`msg:`/goal-regex branches), and switch `ConnectedPrimitiveTree` and `PluginScreen` to it. Route `ui_action_result` frames from the ws client to the pending action.
- [ ] T011 [L:web] [US4] Tests first `pages/dev-primitives/ui/DevPrimitivesPage.test.tsx` and `app/router/routes.test.tsx` (extend): the page renders one section per primitive type with each fixture state and a 390 px frame; the route exists when `import.meta.env.DEV` is true and is absent otherwise (mock the env). Implement `pages/dev-primitives` and the conditional route.
- [ ] T012 [L:web] Tests: `ConnectedPrimitiveTree.test.tsx` and `PluginScreen.test.tsx` (extend) render trees from the shared fixtures with `ui_version`, and refuse a `"1.x"` tree with the plain line "This view needs a newer Ze". Implement the version pass-through from each transport.

---

## Phase 7: Polish and cross-cutting

- [ ] T013 [L:lead] Merge `server`, `ui`, then `web`. `make codegen` if a schema moved. Gates: `make test-py`, `make test-web`, `make typecheck-web`, `make web-build`, `make lint`. The quickstart grep returns nothing.
- [ ] T014 [L:lead] Run [quickstart.md](./quickstart.md) against `make dev-full`, with captures of the gallery at 1440 and 390 and of an irreversible action's confirmation; record them in the Handoffs note.
- [ ] T015 [P] [L:docs] `packages/ze-ui/README.md`, `core/kernel/ze-components/README.md` (also replace `make generate-components` with `make codegen`), `docs/frontend.md`, `docs/native-interface.md`, `docs/extending-ze.md`; doc-style skill.
- [ ] T016 [P] [L:docs] `AGENTS.md` phase row 191a and the Learned Workspace Facts line on chat inline UI; `specs/README.md` row 191a → Implemented; spec status.
- [ ] T017 [L:docs] Coverage check: `git diff main...HEAD --stat` against plan.md "Docs touched"; record in the Handoffs note.

---

## Dependencies & Execution Order

- T001 → T002 → T003 → T004 (contract) → lanes.
- `server`: T005 → T006; T007. `ui`: T008 → T009. `web`: T010 → T011, T012.
- T013 after the three lanes; T014 after T013; T015–T016 after T014; T017 last.

## Parallel Example

```text
After the contract step:
  server: T005 → T006, T007
  ui:     T008 → T009
  web:    T010 → T011 | T012
```

## Implementation Strategy

- MVP = US1 (typed actions through the gates) on the contract step: it closes the `rest:` hole. US2 makes trees tolerant; US3 adds the slot vocabulary 191b needs; US4 keeps the contract honest.
