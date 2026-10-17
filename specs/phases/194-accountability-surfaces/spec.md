# Feature Specification: Accountability Surfaces (B4)

**Feature Branch**: `194-accountability-surfaces`

**Created**: 2026-10-17

**Status**: Draft (spec level; plan and tasks follow once scheduled; the plan marks B4 "nice to have")

**Input**: Maestro brief 2026-10-17, backend floor B4: overhaul plan section d, gaps 7, 8, 11. Gap 13 (screen context on the trace) moved to phase 195 on 2026-10-17.

**Governed by**: `PRODUCT.md` principle 4 ("Unattended work is accountable"), phases 135–136 (action-record ledger and instrumentation), 126–127 (contribution collisions), 182 (model tier on the trace), 89/112 (message trace, screen context note).

**Depends on**: nothing unfinished. Feeds 188 (Doing › Runs and detail pages) and 190 (Governance) when it lands; neither blocks on it.

**Doctrine functions served**: action (what Ze did on its own), governance (disagreements between the user and the executive are observable; the tier Ze runs is printed honestly).

---

## Overview

Three small read surfaces, each over data that already exists:

1. **Action-record ledger over REST (gap 7).** `action_records` (zm021) holds what Ze did, citing domain records. No REST lists them.
2. **Contribution collisions over REST (gap 8).** `GET /api/v0/collisions` exists only on the dev/eval router. Governance needs it in the product API.
3. **Configured default tier (gap 11).** The trace carries the tier per turn (182); Governance needs the configured state (complexity surface on/off, `simple_max`, which agents have a light model) to print it honestly.

### Gaps logged while planning 185–190 (2026-10-17/18; not yet scoped into this phase's requirements)

These came out of planning against the code. Each needs a decision before this phase's plan: in scope here, or its own phase.

- **ResetService cascade (user decision 2026-10-18: log for 194).** `ResetService.reset` truncates its listed tables with `RESTART IDENTITY CASCADE`, so it also wipes every table with a foreign key to a listed table (`open_loops` through `goals.id`, then `open_loop_sources`) without counting them in `preview`. Its lists predate phases 128–184 (they miss `sessions`, `notifications`, `push_log`, `correlation_hypothesis`, `memory_signals`, `action_records`, `feedback_records`, `held_writes`, `priority_overrides`, `ingested_content`), so `personal_state` leaves sessions whose messages are gone. `full_dev` always raises. Only `scripts/reset_personal_state.py` still uses it: 190 deletes the WS commands and Governance has no reset.
- **Component → tool call link (from 187).** Top-level message components carry no `call_index`, so Ask's "Why?" opens the trace section by origin, not the exact call.
- **`listLoops` has no `since` filter (from 186).** World's "Touched · 7 d" downloads every closed loop and filters in the browser.
- **No channels or Gmail connection status over REST (from 190).** Governance › Connections omits it.
- **No screen-context resolver kinds for `cost_anomaly`, `data_domain`, `workspace_file` (from 190).** Governance publishes only its place and focused module; per-row "Chat about this" and the Governance eval case wait for them.

## User Scenarios & Testing *(mandatory)*

1. **What Ze did unattended (P1).** `GET /api/v0/actions?subject_type=&subject_id=&since=&cursor=` lists action records (actor, action kind, lifecycle, outcome, subject reference, cited domain record, time) in plain fields; Doing's goal and workflow details can filter by their id.
2. **Collisions in Governance (P2).** `GET /api/v0/collisions` moves from `api/eval/collisions.py` to the product router (`api/v0/collisions/`) with `operation_id="listCollisions"`; the eval router keeps no copy (pre-v1 hard cut).
3. **Tier configuration is printable (P2).** `GET /api/v0/version` (or a new `GET /api/v0/settings/models`) returns `{ complexity_enabled, simple_max, agents: [{ name, model, model_simple }] }` from the live config, no secrets.

## Requirements *(mandatory)*

- **FR-001**: `ze_memory` (owner of `action_records`) exposes a read function for the ledger; the route lives in ze-api; `response_model`, `summary`, `description`, `operation_id="listActionRecords"`.
- **FR-002**: Collisions route moved to `api/v0`, eval copy deleted, eval client updated.
- **FR-003**: Models settings route reads the same config objects the router and `choose_tier` use (one source).
- **FR-004**: Docs: `docs/native-interface.md`, `docs/memory.md` (ledger REST), `docs/system-one.md` (tier settings route), `AGENTS.md` phase row.

## Success Criteria *(mandatory)*

- **SC-001**: Route tests for each surface; no eval-only collisions route remains.
- **SC-002**: `make test-py`, `make lint`, `make test-web` (codegen consumers) pass.

## Out of Scope

- Any web page work (188 and 190 add the modules when this lands).

## Owning packages

ze-memory (ledger read), ze-collision (unchanged store), ze-api (routes); no migration.
