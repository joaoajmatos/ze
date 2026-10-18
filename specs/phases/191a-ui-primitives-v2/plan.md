# Implementation Plan: UI Primitives v2 (191a)

**Branch**: `191a-ui-primitives-v2` | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md with the 2026-10-18 clarifications (user: all recommended); `main` e4d57414.

## Summary

- **Typed actions.** `Button.action` becomes an `Action`: `ask`, `tool`, `navigate` or `compose`. A `tool` action names the producer (`owner`) and a tool that producer owns. The browser sends it as a new `ui_action` WS frame. ze-api runs it through the owning agent's `call_tool`, so the constraint veto, hooks and write gates apply exactly as in chat. An asks-first write parks; ze-api sends one `confirm_request` and runs the approved call on approval. The string actions (`rest:…`, `msg:…`, bare text) are cut.
- **Tolerant trees.** `parsePrimitiveTree` validates node by node: a known type must pass its strict validator, and an unknown type becomes a fallback node that renders as a table of its scalar fields, with known children rendered inside. Every transport that carries components also carries `ui_version` (`"2.0"`); the client refuses an older major version.
- **Slot primitives.** New `entity_facet`, `stat_row`, `claim_list`, `sparkline` and `card` (with actions); `table` gains row `keys` and `row_actions` (the keyed table). The timeline need maps to the existing `claim_timeline`. An audit removes primitives no producer uses.
- **One contract, one gallery.** Shared JSON fixtures under `packages/ze-ui/fixtures/` are validated by pytest and vitest. A development-only `/dev/primitives` route renders every fixture.
- **Agents.** Render tools are added for `stat_row`, `table` with keys (no `row_actions`) and `sparkline`. Actions and claim posture are omitted from every render tool schema.

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
| IV Typed Python | Action dataclasses (`AskAction`, `ToolAction`, `NavigateAction`, `ComposeAction`); errors are `ZeError` subclasses (`UiActionRefusedError`). |
| V Tests | Fail-first; shared fixtures. |
| VIII Hard cuts | String actions removed from `Button`, `usePrimitiveRendererActions` and `usePluginScreenActions` (`rest:`/`msg:` branches); the unknown-type `return null` replaced by the fallback; no compatibility parse of old actions. |

Gate: pass.

## Blast radius

From `git grep` on `main` e4d57414 (T001 re-runs `graphify affected`):

| Symbol | Callers | Change |
|---|---|---|
| `Button.action: str` (`ze_components/atoms/button.py`), helpers `button`/`primary`/`secondary`/`danger` | `ze_components/patterns/{confirm,consent,choice_group,connect_account,review}.py`, plugin settings descriptors (T001 lists them), tests | `action: Action`; helpers take an `Action`; every producer builds a typed action (chat choices become `AskAction`). |
| `PRIMITIVE_TYPES`, `PRIMITIVE_SUB_TYPES` (`ze_components/__init__.py`) | `schema.export_json_schema`, codegen | Add the new primitives and the action types. |
| `render_tool` registrations (`ze_components/tools.py`) | agents | Add `render_stat_row`, `render_keyed_table`, `render_sparkline`; the schema builder omits `claim`, `row_actions` and `actions`. |
| `packages/ze-ui/src/generated/*` | ze-ui, ze-web | Regenerated. |
| `parsePrimitiveTree`, `validatePrimitiveTree` (`packages/ze-ui/src/parse.ts`) | ze-web (`ConnectedPrimitiveTree`, `PluginScreen`, composed answers) | Node-by-node validation with the fallback node; version check. |
| `PrimitiveRenderer` (`packages/ze-ui/src/react/PrimitiveRenderer.tsx`; `default: return null` at :164) | ze-web | Renders new types, the fallback table and typed button actions through `onAction`. |
| `PrimitiveRendererActions.onButtonAction(action: string)` (`src/react/context.tsx`) | `features/primitive-tree/api/{usePrimitiveRendererActions,usePluginScreenActions}.ts` | Replaced by `onAction(action: Action)`; the string branches are deleted. |
| WS frames (`api/ws/schemas.py`, `api/ws/endpoint.py:136-230`) | ze-web ws-client | New client frame `ui_action`, server frame `ui_action_result`; the `confirm` branch looks up UI action gates before graph gates. |
| Transports carrying components: WS `message` frame (`components`), plugin page/settings responses (`PluginPageResponse`), composed answers | ze-web | Gain `ui_version`. |
| `BaseAgent` (`ze_agents/base_agent.py:337` `run_undo` is the model) | ze-api `ui_actions` | New `run_action(tool, args, *, session_id, approval=None)`. |

## Design

### ze-components

- `actions.py` (new): `AskAction(kind="ask", text)`, `ToolAction(kind="tool", owner, tool, args: dict[str, str | int | float | bool])`, `NavigateAction(kind="navigate", route)` (must start with `/`), `ComposeAction(kind="compose", compose, topic=None)` (184's preset context). `Action = AskAction | ToolAction | NavigateAction | ComposeAction`, a discriminated union on `kind`.
- `UI_CONTRACT_VERSION = "2.0"` in `ze_components/__init__.py`.
- New primitives (each with `claim: ClaimPosture | None` where it shows a claim):
  - `EntityFacet(title, facts: list[FacetFact(text, claim, source: str | None, at: str | None)], more: Action | None)`;
  - `StatRow(items: list[Stat(label, value, delta: str | None, direction: "up" | "down" | "flat" | None)])`;
  - `ClaimList(title: str | None, items: list[ClaimItem(text, claim, action: Action | None)])`;
  - `Sparkline(label, value: str | None, points: list[float])` (capped at 60 points);
  - `Card(title, body: str | None, children: list[Primitive], actions: list[Action-bearing Button], claim)`.
- `Table` gains `keys: list[str] | None` (one per row) and `row_actions: list[RowAction(label, action)] | None`. In a row action, `ToolAction.args` may use the placeholder `"{key}"`, which the host fills with the row's key before sending.
- Render tools: `render_stat_row`, `render_keyed_table` (headers, rows, keys; no row actions) and `render_sparkline`. `build_render_schema` also omits `actions`, `row_actions` and any `Action` field (code-only), as it omits `claim`.
- Audit (T001 lists the results, T004 applies them): for each primitive type, list the producers on `main`. A type with no producer outside tests is removed, unless the gallery is its only consumer by design (none expected).

### @myguyze/ze-ui

- `parse.ts`: `parsePrimitiveTree(data, { version })`.
  - Major version older than `2` → `PrimitiveContractError` ("This view needs a newer Ze").
  - For each node: a known `type` must pass its generated validator, or the tree fails with the node path and field. An unknown `type` becomes `{ type: "__fallback", originalType, fields, children }`: `fields` holds the first 12 scalar fields, and `children` are any arrays of objects, parsed recursively.
- `PrimitiveRenderer`: renders the new types; the fallback renders a two-column table with the note "Unsupported view: <type>". Buttons, card actions, claim-list actions and row actions call `onAction(action)`; a row action fills `{key}` first.
- `PrimitiveRendererActions`: `onAction(action: Action): boolean | Promise<boolean>` replaces `onButtonAction`. `onFormSubmit`, `onCardAction` (the 184 closed card intents) and `onChatAbout` stay.

### ze-api

- WS client frame `{ "type": "ui_action", "id": "<client uuid>", "thread_id": "...", "action": { "kind": "tool", "owner": "...", "tool": "...", "args": {...} } }`. Only `tool` actions reach the server; `ask`, `navigate` and `compose` are handled in the browser.
- `api/ws/ui_actions.py`:
  1. Resolve the owner agent (registry). Refuse with `UiActionRefusedError` when the agent is unknown, the tool is not in its `tools`, or the tool is unknown. The line is "That action is not available."
  2. `result = await agent.run_action(tool, args, session_id=thread_id)`.
  3. On `gate == "parked"`: register a `UiActionGate(request_id, agent, tool, args, parked)` in an in-process registry with `CONFIRM_TIMEOUT_SECONDS`, and send `confirm_request` (`kind: "write"`, one item from `parked.summary`/`effect_phrase`).
  4. Otherwise send `{ "type": "ui_action_result", "id", "ok": success, "line": <plain outcome>, "thread_id" }`.
  
  The busy rule: an action on a thread with a running turn is refused with `busy`, as turns are.
- The `confirm` branch in `endpoint.py` checks the UI action gate registry first. On approve, it calls `run_action(..., approval=ApprovedCall(parked.call_id))`. On deny or timeout, the result line is "Okay, I didn't <effect>." (`effect_imperative`). Either way it sends `ui_action_result`.
- Logging: `ui_action_run` (owner, tool, gate, outcome). The tool's own action-ledger producers fire as they do in chat. No message trace is written, because no turn runs.
- `ui_version: "2.0"` is added to the WS `message` frame, `PluginPageResponse` and the composed-answer component payloads.

### ze-agents

- `BaseAgent.run_action(tool, args, *, session_id, approval=None) -> ToolCall`: like `run_undo`, but with no implicit approval. It builds an `AgentContext(session_id, prompt="", retry_mode=False)`, merges deps, and calls `call_tool(tool, ctx, _lm_args=args, _approval=approval, **merged)`.

### ze-web

- `features/primitive-tree/api/usePrimitiveActions.ts` (replacing `usePrimitiveRendererActions` and `usePluginScreenActions`) maps each action kind:
  - `ask` → `sendTurn(threadId, text)` (single send path);
  - `navigate` → `navigate(route)` when `route` starts with `/` and matches a place route, else a notice;
  - `compose` → `sendTurn` with `{ origin: "preset", compose, topic }`;
  - `tool` → `send({ type: "ui_action", … })` and await the matching `ui_action_result` (by id), up to the confirmation timeout, then show the line as a notice. It resolves false if not connected.
  
  `onFormSubmit` keeps its current behaviour.
- `pages/dev-primitives` (new): the route `/dev/primitives` is added in `app/router/routes.tsx` only when `import.meta.env.DEV`. It renders every fixture in `packages/ze-ui/fixtures/valid/*.json`, grouped by type, at its natural width and in a 390 px frame.
- Callers of `onButtonAction` are switched to `onAction`.

### Fixtures

- `packages/ze-ui/fixtures/valid/<type>-<state>.json` and `invalid/<case>.json`. Each invalid fixture has a sibling `<case>.expect.json` naming the failing field path.
- pytest (`core/kernel/ze-components/tests/test_fixtures.py`) validates them against `export_json_schema()`. vitest (`packages/ze-ui/src/fixtures.test.ts`) runs `parsePrimitiveTree`. Both check every type in `PRIMITIVE_TYPES` has at least one valid fixture.

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
- `docs/native-interface.md`: `ui_action` / `ui_action_result` frames, `ui_version`.
- `docs/extending-ze.md`: how a plugin builds a tree with typed actions (191b extends it with modules).
- `AGENTS.md`: phase row 191a; the Learned Workspace Facts line on chat inline UI (`render_*` tools now include stat row, keyed table, sparkline; actions are typed). `specs/README.md` row 191a.

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first; T002–T004):
- **ze-components:** `actions.py`; the new primitive dataclasses and `Table` fields; `Button.action: Action`; every pattern producer switched; `UI_CONTRACT_VERSION`; registries.
- **Codegen:** `make codegen` for ze-ui types and the generated client.
- **ze-api:** WS schemas for `ui_action`/`ui_action_result` and `ui_version`.
- **ze-ui:** the `PrimitiveRendererActions.onAction` signature.
- **Fixtures:** the fixture directory, with one valid fixture per existing type and the audit removals.

| Lane | Model / role | Owns (disjoint) | Tasks | Starts after | Reviewer |
|---|---|---|---|---|---|
| lead | Sonnet ENG lead | `ze_components/**` except `tools.py`, `packages/ze-ui/src/generated/*`, `packages/ze-ui/src/react/context.tsx`, `packages/ze-ui/fixtures/**` (initial set), `packages/ze-client/src/generated/*`, `api/ws/schemas.py`, `interface/native.py`, the `PluginPageResponse` schema; merges, gates | T001–T004, T013, T014 | - | Gauge |
| server | Sonnet ENG | `ze_agents/base_agent.py` (`run_action`), `api/ws/{ui_actions,endpoint}.py`, `ze_components/tools.py` (render tools), their tests | T005–T007 | contract step | floor Reviewer |
| ui | Sonnet ENG | `packages/ze-ui/src/{parse.ts,react/PrimitiveRenderer.tsx}`, new renderer files, `src/fixtures.test.ts`, added fixtures for the new types | T008–T009 | contract step | floor Reviewer |
| web | Sonnet ENG | `apps/ze-web/src/features/primitive-tree/**`, `pages/dev-primitives/**`, `app/router/routes.tsx` (the dev route), the ws-client frame handling for `ui_action_result`, their tests | T010–T012 | contract step | floor Reviewer |
| docs | Haiku DOCS | the files in "Docs touched" | T015–T017 | T014 | floor Reviewer |

**Rules**: one lane per file. The audit's removals happen in the contract step, so no lane builds on a removed type. There is no JR lane: each piece crosses the descriptor contract or the gates.

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| A `ui_action` WS frame instead of a REST route | The write gate's confirmation is a WS `confirm_request`; the frame keeps the request, the confirmation and the result on one channel with the thread's busy rule. | REST `POST /ui/actions` (would need its own confirmation channel). |
| Node-by-node validation | Lets unknown types fall back while known types stay strict. | A permissive schema (would accept malformed known nodes). |
| `owner` on `ToolAction` | The server must know which agent's tools the tree may call (clarification Q1). | Any registered tool (rejected by the user). |
