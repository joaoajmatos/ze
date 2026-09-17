# Research: Workspace Chat-First

## Decision 1 — Gate is action × origin, not mode

**Decision**: `WorkspaceGate.decide(action=, origin=)` with no mode argument. Conversation: reads allow; writes, deletes, ingest, runs, scripts, reset confirm. Unattended: reads/writes/runs/scripts allow; reset deny. User REST (chat attach + map list): reads/place/retrieve/delete allow; runs deny; reset confirm if the REST reset path remains.

**Rationale**: Spec pins always-on access and chat confirmations. A stored mode was the second policy plane.

**Alternatives considered**: Map all origins to old Auto (no chat confirm) — rejected; user still wants confirmations in the thread. Keep a hidden default Ask column — rejected (shim).

## Decision 2 — Drop the mode column

**Decision**: Alembic `zws005` `ALTER TABLE workspace_state DROP COLUMN mode`. `WorkspaceState` has no mode. `get_mode` / `set_mode` deleted.

**Rationale**: Principle VIII; leftover TEXT would still be a product.

**Alternatives considered**: Stop reading the column but leave it — rejected.

## Decision 3 — Map UI vs REST leftovers

**Decision**: `/workspace` page: tree + available / bytes / busy (and last-used if already shown as a fact). No mode switcher, upload, reset, retrieve button, run list, live banner. Chat attachment still uses `POST /files`. Run cancel and live output stay on the conversation surfaces that already have them.

**Rationale**: Spec FR-005/FR-007. Chat attach is conversation (FR-001), not the map.

**Alternatives considered**: Delete upload REST entirely — rejected; chat attach needs it.

## Decision 4 — Unattended helper loses get_mode

**Decision**: `unattended_workspace(gate)` only sets origin and optionally consults `decide_named(action=, origin="unattended")`. Container stops injecting `store.get_mode`.

**Rationale**: Duck-typed automation must not keep a mode callback.

## Decision 5 — Trace has no mode

**Decision**: Remove `mode` from `WorkspaceUsageTrace` and the trace panel. Show used / unavailable / script / runs / files.

**Rationale**: Showing a dead mode is index dishonesty.
