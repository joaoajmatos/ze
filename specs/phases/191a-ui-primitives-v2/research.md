# Research: UI Primitives v2 (191a)

## R1. Where a tool action runs
- **Decision**: in ze-api, through the owning agent's `call_tool` via a new `BaseAgent.run_action` (modelled on `run_undo`, without implicit approval); parked writes confirm through a `confirm_request` and resume with `ApprovedCall(parked.call_id)`.
- **Rationale**: `call_tool` already holds the constraint veto, hooks, the asks-first rule and the irreversible summary (181); no model call is needed for an action the user pressed.
- **Alternatives**: a chat turn ("ask Ze to do X": slow, costs a model call, may do something else); direct REST (skips gates; the hole this phase closes).

## R2. Owner check
- **Decision**: `ToolAction.owner` names an agent; the tool must be in its `tools`, be a WRITE tool and declare `ui_action=True`. Trees are built by code or by render tools, which cannot set tool actions.
- **Rationale**: the server cannot tell which tree a press came from, so it checks what it can (Gauge A-4); the opt-in keeps arbitrary one-click writes unreachable, and the write gates still apply. READ tools are excluded because a screen action has nowhere to show their result.

## R7. Parking outside the loop
- **Decision**: `run_action` marks its context as in a loop for the one call and passes a fresh `_call_id`, so `call_tool` parks an asks-first write (it raises outside the loop) and the gate holds a real call id; the approved run records the UI request id.
- **Rationale**: `run_undo` never parks (it always passes an approval), so copying it is not enough (Gauge A-1).

## R8. Model-written buttons
- **Decision**: `render_confirm` and `render_choice_group` keep model-written values as chat choices (`AskAction`); GoalAgent's inline gate buttons go, since 181's prompt frames and 188's answer-gate resolve gates.
- **Rationale**: the old regex branch made a model-written string resolve a gate; a hard cut needs one gate path, and it already exists.

## R9. Legacy trees
- **Decision**: no version means legacy; legacy renders best effort with string-action buttons disabled; only the tree is replaced if it cannot render.
- **Rationale**: history must not fill with errors (Gauge A-3); no read-time rewriting of stored trees.

## R3. Version and fallback
- **Decision**: a `ui_version` string on each transport that carries newly built components; unknown types → fallback node; known types validated strictly; no version or 1.x → legacy (R9).
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
