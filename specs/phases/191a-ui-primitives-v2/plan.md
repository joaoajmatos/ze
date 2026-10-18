# Implementation Plan: UI Primitives v2 (191a)

**Branch**: `191a-ui-primitives-v2` | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md with the 2026-10-18 clarifications (user: all recommended); `main` e4d57414.

## Summary

- **Typed actions.** `Button.action` becomes a `PrimitiveAction` (the name avoids `ze_agents.interface.types.Action`, the prompt-frame action): `ask`, `tool`, `navigate` or `compose`. A `tool` action names an agent (`owner`) and one of its write tools that opted in with `@tool(..., ui_action=True)`. The browser sends it as a new `ui_action` WS frame. ze-api runs it through the owning agent's `call_tool`, so the constraint veto, hooks and write gates apply exactly as in chat. An asks-first write parks; ze-api sends one `confirm_request` and runs the approved call on approval; the action ledger records every run. The string actions (`rest:…`, `msg:…`, bare text) are cut for new trees; stored trees render as legacy.
- **Tolerant trees.** `parsePrimitiveTree` validates node by node: a known type must pass its strict validator, and an unknown type becomes a fallback node that renders as a table of its scalar fields, with known children rendered inside. Every transport that carries newly built components also carries `ui_version` (`"2.0"`). A tree with no version (stored before this phase) or a 1.x version renders as legacy, best effort.
- **Slot primitives.** New `entity_facet`, `stat_row`, `claim_list`, `sparkline` and `card` (with actions); `table` gains row `keys` and `row_actions` (the keyed table). The timeline need maps to the existing `claim_timeline`. An audit removes primitives no producer uses.
- **One contract, one gallery.** Shared JSON fixtures under `packages/ze-ui/fixtures/` are validated by pytest and vitest. A development-only `/dev/primitives` route renders every fixture.
- **Agents.** Render tools are added for `stat_row`, `table` with keys (no `row_actions`) and `sparkline`. Claim posture and tool actions are omitted from every render tool schema. `render_confirm` and `render_choice_group` keep their model-written `actions: [{label, value, style}]`; each `value` becomes an `AskAction` (a chat choice, as today), never a tool action.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 5, React 19.
**Primary Dependencies**: none new (ajv, the existing `make codegen`; the README's `make generate-components` does not exist and is corrected in the docs task).
**Storage**: none; no migration.
**Testing**: pytest (ze-components schema and fixtures, ze-api `ui_action` route, `BaseAgent.run_action`); vitest (ze-ui parse and renderer, ze-web host actions, gallery smoke test).
**Target Platform**: Linux container + browser.
**Project Type**: library packages + web service + web app.
**Constraints**: no plugin script in the browser; claim posture set only by code; every write through `call_tool`'s gates; FSD in ze-web.
**Scale/Scope**: 16 primitive types today, 5 added plus one extended; about 10 producer modules of `Button` in ze-components patterns.

## Constitution Check

| Principle | Check |
|---|---|
| I Spec-first | spec, clarifications, plan, research, data model, contract, quickstart, tasks. |
| III Layered packages | Descriptors in ze-components (depends on ze-agents only); contract and renderer in `@myguyze/ze-ui` (no Ze deps); the action route in ze-api; `run_action` on `BaseAgent` in ze-agents; host and gallery in ze-web. |
| IV Typed Python | `PrimitiveAction` dataclasses (`AskAction`, `ToolAction`, `NavigateAction`, `ComposeAction`); errors are `ZeError` subclasses (`UiActionRefusedError`). |
| V Tests | Fail-first; shared fixtures. |
| VIII Hard cuts | String actions removed from `Button`, `usePrimitiveRendererActions` and `usePluginScreenActions` (`rest:`/`msg:` branches); the unknown-type `return null` replaced by the fallback; no compatibility parse of old actions. |

Gate: pass.

## Blast radius

From `git grep` on `main` e4d57414 (T001 re-runs `graphify affected`):

| Symbol | Callers | Change |
|---|---|---|
| `Button.action: str` (`ze_components/atoms/button.py`), helpers `button`/`primary`/`secondary`/`danger` | `ze_components/patterns/{confirm,consent,choice_group,connect_account,review}.py`, plugin settings descriptors (T001 lists them), tests | `action: PrimitiveAction`; helpers take one; chat choices become `AskAction`; `connect_account`'s `connect:{provider}:{id}` becomes `NavigateAction("/governance#connections")`. |
| Model-written action values in agent instructions: `ze_automation/agents/goals/agent.py:53-62` (render_confirm with `goal:approve|redirect|stop:<gate_id>`, "tapping a button resolves the gate directly"), `ze_finance/agents/finance/agent.py:25` (render_confirm "Yes, track it"), companion choice and consent flows | the models | Finance and companion values stay chat choices (`AskAction`). GoalAgent's inline gate buttons are removed: gates are answered through 181's `kind: "prompt"` gate frame and Doing's answer-gate (188), so the instruction text drops the render_confirm gate example and the "resolves directly" claim. The `action` WS frame and `goal_actions.handle_action` stay for prompt frames. |
| `PRIMITIVE_TYPES`, `PRIMITIVE_SUB_TYPES` (`ze_components/__init__.py`) | `schema.export_json_schema`, codegen | Add the new primitives and the action types. |
| `render_tool` registrations (`ze_components/tools.py`) | agents | Add `render_stat_row`, `render_keyed_table`, `render_sparkline`; the schema builder omits `claim`, `row_actions` and `actions`. |
| `packages/ze-ui/src/generated/*` | ze-ui, ze-web | Regenerated. |
| `parsePrimitiveTree`, `validatePrimitiveTree`, `PrimitiveAction` type (`packages/ze-ui/src/parse.ts:11`, today `= string`) | ze-web (`ConnectedPrimitiveTree`, `PluginScreen`, `widgets/connections/ui/PluginSettingsSection.tsx:22`, composed answers) | Node-by-node validation with the fallback node; legacy mode for unversioned trees; `PrimitiveAction` becomes the union. |
| `PrimitiveRenderer` (`packages/ze-ui/src/react/PrimitiveRenderer.tsx`; `default: return null` at :164) | ze-web | Renders new types, the fallback table and typed button actions through `onAction`. |
| `PrimitiveRendererActions.onButtonAction(action: string)` (`src/react/context.tsx`) | `features/primitive-tree/api/{usePrimitiveRendererActions,usePluginScreenActions}.ts` | Replaced by `onAction(action: Action)`; the string branches are deleted. |
| WS frames (`api/ws/schemas.py`, `api/ws/endpoint.py:136-230`) | ze-web ws-client | New client frame `ui_action`, server frame `ui_action_result`; the `confirm` branch looks up UI action gates before graph gates. |
| Transports carrying components: WS `message` frame (`components`), plugin page/settings responses (`PluginPageResponse`), composed answers | ze-web | Gain `ui_version`. |
| `BaseAgent` (`ze_agents/base_agent.py:337` `run_undo`; `call_tool` raises outside the loop for an asks-first park at :436-439; `_call_id` at :455; approval recording at :411-414; `_model_args` at :1092-1104) | ze-api `ui_actions` | New `run_action`, which marks the context as in a loop for the call, passes a call id, filters arguments like the loop does, and records the approval request id. |
| `@tool` (`ze_agents/tool.py:374`) | every tool | New `ui_action: bool = False`; only WRITE tools may set it. |
| Stored message components (`MessageStore`, unread replay on connect, REST history) | ze-web history | No version; rendered as legacy. |

## Design

### ze-components

- `actions.py` (new): `AskAction(kind="ask", text)`, `ToolAction(kind="tool", owner, tool, args: dict[str, str | int | float | bool])`, `NavigateAction(kind="navigate", route)` (must start with `/`; a `#section` hash is allowed), `ComposeAction(kind="compose", compose, topic=None)` (184's preset context). `PrimitiveAction = AskAction | ToolAction | NavigateAction | ComposeAction`, a discriminated union on `kind`.
- `UI_CONTRACT_VERSION = "2.0"` in `ze_components/__init__.py`.
- New primitives (each with `claim: ClaimPosture | None` where it shows a claim):
  - `EntityFacet(title, facts: list[FacetFact(text, claim, source: str | None, at: str | None)], more: PrimitiveAction | None)`;
  - `StatRow(items: list[Stat(label, value, delta: str | None, direction: "up" | "down" | "flat" | None)])`;
  - `ClaimList(title: str | None, items: list[ClaimItem(text, claim, action: PrimitiveAction | None)])`;
  - `Sparkline(label, value: str | None, points: list[float])` (capped at 60 points);
  - `Card(title, body: str | None, children: list[Primitive], actions: list[Button], claim)`.
- `Table` gains `keys: list[str] | None` (one per row) and `row_actions: list[RowAction(label, action)] | None`. In a row action, `ToolAction.args` may use the placeholder `"{key}"`, which the host fills with the row's key before sending.
- Producers: chat-choice buttons in patterns become `AskAction`; `connect_account` becomes `NavigateAction("/governance#connections")`.
- Render tools (lane `server`): `render_stat_row`, `render_keyed_table` (headers, rows, keys; no row actions) and `render_sparkline`. `build_render_schema` omits `claim`, `row_actions`, any `ToolAction`, `NavigateAction` or `ComposeAction` field. `render_confirm` and `render_choice_group` keep `actions: [{label, value, style}]` in their schemas, and their wrappers turn each `value` into `AskAction(text=value)`.
- Audit (T001 lists the results, T002 applies them): for each primitive type, list the producers on `main`. A type with no producer outside tests is removed.

### @myguyze/ze-ui

- `parse.ts`: `parsePrimitiveTree(data, { version })`.
  - No version or major `1` → legacy mode: each node is parsed best effort; a button whose `action` is a string renders disabled with the title "This older button no longer works."; unknown types fall back. If the tree still cannot be parsed, `PrimitiveLegacyError` is thrown and the host replaces only that tree with "This older view can't be shown." The version is never written back.
  - For each node: a known `type` must pass its generated validator, or the tree fails with the node path and field. An unknown `type` becomes `{ type: "__fallback", originalType, fields, children }`: `fields` holds the first 12 scalar fields, and `children` are any arrays of objects, parsed recursively.
- `PrimitiveRenderer`: renders the new types; the fallback renders a two-column table with the note "Unsupported view: <type>". Buttons, card actions, claim-list actions and row actions call `onAction(action)`; a row action fills `{key}` first.
- `PrimitiveRendererActions`: `onAction(action: PrimitiveAction): boolean | Promise<boolean>` replaces `onButtonAction`. `onFormSubmit`, `onCardAction` (the 184 closed card intents) and `onChatAbout` stay.

### ze-api

- WS client frame `{ "type": "ui_action", "id": "<client uuid>", "thread_id": "...", "action": { "kind": "tool", "owner": "...", "tool": "...", "args": {...} } }`. Only `tool` actions reach the server; `ask`, `navigate` and `compose` are handled in the browser. The existing `action` frame stays for prompt-frame choices (goal gates, suggestions); `ui_action` is only for primitive tool actions.
- `api/ws/ui_actions.py`:
  1. Refuse with "That action is not available." (`UiActionRefusedError`) when the owner agent is unknown, the tool is not in its `tools`, the tool is not a WRITE tool, or the tool did not opt in with `ui_action=True`.
  2. Refuse a busy thread with `code: "busy"`.
  3. `result = await agent.run_action(tool, args, session_id=thread_id)`. A bad argument (unknown key, hidden or injected parameter, wrong scalar type) is refused with "That action is not available." before the tool runs.
  4. On `gate == "parked"`: register a `UiActionGate(request_id, thread_id, agent, tool, args, parked, timer)` and send `confirm_request` (`kind: "write"`, one item from `parked.summary` and `effect_phrase`). Otherwise send `ui_action_result`.
- Gate lifecycle (in process; stated in the spec):
  - **Edits:** the UI gate's `confirm_request` item carries no `editable_field`, so no edit control is offered, and any `edits` on the `confirm` frame are ignored: the original args run.
  - **Confirm:** the `confirm` branch in `endpoint.py` pops the gate first, so a second `confirm` finds nothing, and only then runs. Approve → `run_action(..., approval=ApprovedCall(parked.call_id), approval_request_id=request_id)`. Deny → "Okay, I didn't <effect_imperative>."
  - **Unknown id:** a `confirm` for an id that is in neither the UI gates nor the graph gates (for example after a restart) answers `ui_action_result` with `ok: false`, "That request expired."
  - **Timeout:** a timer task per gate (`CONFIRM_TIMEOUT_SECONDS`) pops it and sends "Okay, I didn't <effect_imperative>."; confirm and supersede cancel it. A disconnect does not cancel it.
  - **Supersede:** a new turn on the thread (the same point where `ws/turns.py` records superseded chat gates) pops every UI gate on that thread with "Okay, I didn't <effect_imperative>."
  - **Reconnect:** on connect, after the unread replay, open UI gates for the session are sent again as `confirm_request`.
  - **Limits:** UI gates are not persisted and get no ntfy push, because the user is at the screen. A restart drops them (see "Unknown id").
- Outcome line: success → the tool's `done_phrase` if it declares one, else "Done."; failure → "Couldn't <effect_imperative>." (never the raw error); refusals as above.
- Audit trail: every run (approved, denied, expired, failed) writes an `ActionRecord` through `ActionRecorder.record_action`: `producer_kind` "ui" and `action_kind` "tool_action" (so `action_type` is `ui.tool_action`), `source_record_id` = the UI request id (unique per press, so repeated identical actions never share an idempotency key), `actor` "user", default provenance (`PROMPT_SUPPLIED`), `producer_plugin` = the owner's plugin, and the tool name, args hash and effect phrase in `summary` and `context`. A ledger failure is caught and logged (`ui_action_ledger_failed`) and never fails the action, which has already run. The tools' own ledger producers still fire where they can; T001 checks one (the reminder cancel producer) outside a turn.
- Logging: `ui_action_run` (owner, tool, gate, outcome). No message trace is written, because no turn runs; the ledger is the record.
- `ui_version: "2.0"` is added to the WS `message` frame, `PluginPageResponse` and composed-answer payloads for newly built trees. Stored components are sent as stored.

### ze-agents

- `@tool(..., ui_action: bool = False, done_phrase: str | None = None)`. Registration fails if a READ tool sets `ui_action`.
- `BaseAgent.run_action(tool, args, *, session_id, approval=None, approval_request_id=None) -> ToolCall`:
  - builds `AgentContext(session_id, prompt="", retry_mode=False)` and sets `ctx.loop_active = True` for the call (restored after), so an asks-first write parks instead of raising (`call_tool` :436-439);
  - sets `ctx.approval_request_id = approval_request_id` on an approved run;
  - filters `args` through `_model_args` (drops `_`-prefixed and hidden parameters), refuses unknown keys and non-scalar or wrongly typed values against the tool's schema (`UiActionRefusedError`), then merges deps;
  - calls `call_tool(tool, ctx, _lm_args=args, _call_id=uuid4().hex, _approval=approval, **merged)`.

### ze-web

- `features/primitive-tree/api/usePrimitiveActions.ts` (replacing `usePrimitiveRendererActions` and `usePluginScreenActions`) maps each action kind:
  - `ask` → `sendTurn(threadId, text)` (single send path);
  - `navigate` → `navigate(route)` when `route` starts with `/` and matches a place route, else a notice;
  - `compose` → `sendTurn` with `{ origin: "preset", compose, topic }`;
  - `tool` → `send({ type: "ui_action", … })` and await the matching `ui_action_result` (by id), up to the confirmation timeout, then show the line as a notice. It resolves false if not connected.
  
  `onFormSubmit` keeps its current behaviour.
- `ConnectedPrimitiveTree`, `PluginScreen` and `PluginSettingsSection` catch `PrimitiveLegacyError` per tree: only that tree is replaced by "This older view can't be shown."; the message text renders.
- `pages/dev-primitives` (new): the route `/dev/primitives` is added in `app/router/routes.tsx` only when `import.meta.env.DEV`. It renders every fixture in `packages/ze-ui/fixtures/valid/*.json`, grouped by type, at its natural width and in a 390 px frame.
- Callers of `onButtonAction` are switched to `onAction`.

### Fixtures

- `packages/ze-ui/fixtures/<name>.json`, each with a sibling `<name>.expect.json`: `{ "server": "valid" | { "invalid_at": "<JSON pointer>" }, "client": "valid" | "tolerated" | "legacy" | { "invalid_at": "<JSON pointer>" } }`. An unknown-type fixture is server-invalid and client-tolerated; a pre-191a stored tree (string-action button, plain table, no version) is client-legacy.
- pytest (`core/kernel/ze-components/tests/test_fixtures.py`) validates against `export_json_schema()`; vitest (`packages/ze-ui/src/fixtures.test.ts`) runs `parsePrimitiveTree`. Both normalise error paths to JSON pointers and compare with `expect`. Both check every type in `PRIMITIVE_TYPES` has at least one server-valid fixture.

## Project Structure

### Documentation (this feature)

```text
specs/phases/191a-ui-primitives-v2/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md, tasks.md
├── contracts/{primitive-actions.md}
└── checklists/{requirements,contract}.md
```

### Source Code

```text
core/kernel/ze-components/ze_components/{actions.py (new),atoms/button.py,organisms/{table,entity_facet,stat_row,claim_list,sparkline,card}.py,patterns/*.py,tools.py,schema.py,__init__.py}
core/contracts/ze-agents/ze_agents/base_agent.py (run_action)
apps/ze-api/ze_api/api/ws/{ui_actions.py (new),endpoint.py,schemas.py} ; api/v0/... (PluginPageResponse ui_version) ; interface/native.py (message frame ui_version)
packages/ze-ui/{fixtures/ (new),src/{parse.ts,react/PrimitiveRenderer.tsx,react/context.tsx,generated/*}}
packages/ze-client/src/generated/*
apps/ze-web/src/features/primitive-tree/* ; pages/dev-primitives/ (new) ; app/router/routes.tsx ; shared/api (ws frame types)
```

## Docs touched

- `packages/ze-ui/README.md`: typed actions, fallback, `ui_version`, fixtures, the gallery.
- `core/kernel/ze-components/README.md`: the action types, the new primitives, which render tools agents get; replace the stale `make generate-components` with `make codegen`.
- `docs/frontend.md`: primitive actions and the gallery route.
- `docs/native-interface.md`: `ui_action` / `ui_action_result` frames and how they differ from the existing `action` frame (prompt-frame choices), the UI gate lifecycle, `ui_version` and legacy trees.
- `docs/extending-ze.md`: how a plugin builds a tree with typed actions (191b extends it with modules).
- `AGENTS.md`: phase row 191a; the Learned Workspace Facts line on chat inline UI (`render_*` tools now include stat row, keyed table, sparkline; actions are typed). `specs/README.md` row 191a.

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first; T002–T004):
- **ze-components:** `actions.py`; the new primitive dataclasses and `Table` fields; `Button.action: PrimitiveAction`; every pattern producer switched; the GoalAgent instruction edit; `UI_CONTRACT_VERSION`; registries.
- **Codegen:** `make codegen` for ze-ui types and the generated client.
- **ze-api:** WS schemas for `ui_action`/`ui_action_result` and `ui_version`.
- **ze-ui:** the `PrimitiveRendererActions.onAction` signature.
- **Fixtures:** the fixture directory, with one valid fixture per existing type and the audit removals.

| Lane | Model / role | Owns (disjoint) | Tasks | Starts after | Reviewer |
|---|---|---|---|---|---|
| lead | Sonnet ENG lead | `ze_components/**` except `tools.py`, `ze_automation/agents/goals/agent.py` (the instruction edit), `packages/ze-ui/src/generated/*`, `packages/ze-ui/src/react/context.tsx`, `packages/ze-ui/fixtures/**` (initial set), `packages/ze-client/src/generated/*`, `api/ws/schemas.py`, `interface/native.py`, the `PluginPageResponse` schema; merges, gates | T001–T004, T013, T014 | - | Gauge |
| server | Sonnet ENG | `ze_agents/{base_agent,tool}.py` (`run_action`, `ui_action`, `done_phrase`), `api/ws/{ui_actions,endpoint,turns}.py` (gates, supersede, reconnect replay), `ze_components/tools.py` (render tools), their tests | T005–T007 | contract step | floor Reviewer |
| ui | Sonnet ENG | `packages/ze-ui/src/{parse.ts,react/PrimitiveRenderer.tsx}`, new renderer files, `src/fixtures.test.ts`, added fixtures for the new types | T008–T009 | contract step | floor Reviewer |
| web | Sonnet ENG | `apps/ze-web/src/features/primitive-tree/**`, `widgets/plugin-screen/**`, `widgets/connections/ui/PluginSettingsSection.tsx`, `pages/dev-primitives/**`, `app/router/routes.tsx` (the dev route), the ws-client frame handling for `ui_action_result`, their tests | T010–T012 | contract step | floor Reviewer |
| docs | Haiku DOCS | the files in "Docs touched" | T015–T017 | T014 | floor Reviewer |

**Rules**: one lane per file. The audit's removals happen in the contract step, so no lane builds on a removed type. There is no JR lane: each piece crosses the descriptor contract or the gates.

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| A `ui_action` WS frame instead of a REST route | The write gate's confirmation is a WS `confirm_request`; the frame keeps the request, the confirmation and the result on one channel with the thread's busy rule. | REST `POST /ui/actions` (would need its own confirmation channel). |
| Node-by-node validation | Lets unknown types fall back while known types stay strict. | A permissive schema (would accept malformed known nodes). |
| `owner` on `ToolAction` plus `@tool(ui_action=True)` | The server cannot know which tree a press came from, so the honest check is "one of this agent's opted-in write tools" (clarification Q1, Gauge A-4). | Any registered tool (rejected by the user); server-issued action ids (more machinery than one user needs). |
