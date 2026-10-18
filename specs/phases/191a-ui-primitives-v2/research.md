# Research: UI Primitives v2 (191a)

## R1. Where a tool action runs
- **Decision**: in ze-api, through the owning agent's `call_tool` via a new `BaseAgent.run_action` (modelled on `run_undo`, without implicit approval); parked writes confirm through a `confirm_request` and resume with `ApprovedCall(parked.call_id)`.
- **Rationale**: `call_tool` already holds the constraint veto, hooks, the asks-first rule and the irreversible summary (181); no model call is needed for an action the user pressed.
- **Alternatives**: a chat turn ("ask Ze to do X": slow, costs a model call, may do something else); direct REST (skips gates; the hole this phase closes).

## R2. Owner check
- **Decision**: `ToolAction.owner` names the agent whose tool list must contain the tool; the server refuses otherwise. Trees are built by code (plugins, composed answers) or by agents' render tools, which cannot set actions.
- **Rationale**: clarification Q1 (tools owned by the tree's producer). The browser is the user's own; the check stops one plugin's tree from calling another plugin's tools, and the write gates still apply.

## R3. Version and fallback
- **Decision**: a `ui_version` string on each transport that carries components; major mismatch older than the client's → refuse; unknown types → fallback node; known types validated strictly.
- **Rationale**: a newer server can add a primitive without breaking an older tab; mistakes stay visible.

## R4. Slot primitives
- **Decision**: `entity_facet`, `stat_row`, `claim_list`, `sparkline`, `card`; keyed table = `table` + `keys` + `row_actions`; timeline = existing `claim_timeline`.
- **Rationale**: each maps to one slot need (FR-006) without a second way to draw the same thing.

## R5. Agents' render tools
- **Decision**: add `render_stat_row`, `render_keyed_table` (no actions), `render_sparkline`; actions and posture are never in render schemas.
- **Rationale**: clarification Q2; a model must never choose a tool action or a posture.

## R6. Gallery
- **Decision**: `/dev/primitives`, compiled only into development builds (`import.meta.env.DEV`), rendering the shared fixtures.
- **Rationale**: clarification Q3; fixtures double as the gallery's content, so the gallery cannot drift from the contract.
