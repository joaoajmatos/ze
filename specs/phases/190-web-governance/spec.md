# Feature Specification: Governance (W6)

**Feature Branch**: `190-web-governance`

**Created**: 2026-10-17

**Status**: Ready to implement on `main` with 183 and 184 (the user answered Q-1 and Q-2 on 2026-10-18) (plan and tasks written 2026-10-17 against `main` b5fdc1c1). The budget readout waits for 185 and the screen-context publishing for 195 (split task phases); the rest starts now, alongside 186 and 189.

**Input**: Maestro brief 2026-10-17, phase W6; overhaul plan sections a (Governance), b.5, e (Phase W6). User decision 5: palette is a Governance setting.

**Governed by**: `DESIGN.md` ("no chart without a question"), `PRODUCT.md` ("Interruption is a budget"), phases 17/120 (costs), 62 (data portability), 177 (quiet hours, budget), 115 (workspace files).

**Depends on**: 183 (shell, palette control). Split tasks: the budget readout and push outcomes need 185 (`getAttentionBudget`, `listNotifications` filters); screen-context publishing needs 195. 194 (default tier, collisions, Gmail connection status) is out of scope.

**Doctrine function served**: governance (is Ze behaving: spend, attention, data, connections).

---

## Clarifications

### Session 2026-10-17 (planning against the code, parallel build)

- **No Reset module (user decision 2026-10-18, Q-2 (a): "drop Reset, keep Delete in Data, rename the local action 'Forget this server', delete the unused WS reset commands, and log the ResetService cascade bug for 194").** `ResetService` truncates with `CASCADE`, so it destroys tables its preview never counts (`open_loops` through `goals`), and its lists miss the tables added since phase 128; `full_dev` always raises. Its WS commands `reset_preview`/`reset` answer with a chat message and nothing in the app calls them. This phase deletes the two WS commands (hard cut; `scripts/reset_personal_state.py` keeps the service for developers) and logs the cascade bug for 194. Governance keeps one destructive action, Data › Delete all data; the local "Reset configuration" is renamed "Forget this server".
- **Files stay read-only (user decision 2026-10-18, Q-1 (a)).** The workspace view is a map (tree and info), not a console; upload stays in chat.
- **Spend uses the API's 30 days.** `getCostSummary` always covers the last 30 days. "Am I spending normally?" compares the last 7 days' daily average with the 30-day daily average (both from `by_day`), names the anomaly count, and shows the per-flow 30-day totals. Totals print two decimals; run and baseline costs under $1 print four.
- **The spend trend needs a series primitive.** `shared/ui/hud/Spark` draws a two-point confidence change, not a series; this phase adds `SeriesSpark` (a line over N points, DESIGN.md tokens) in `shared/ui/hud`.
- **Redirect hints need a field.** `RedirectTo` appends the incoming hash, so a hint cannot sit in `to`. The redirect table gains an optional `hint`; `RedirectTo` replaces the incoming hash with it (mapping the old `your-data` to `data`) and keeps the query.
- **The activity heatmap route goes too.** `GET /api/v0/activity/heatmap` and its aggregator lose their only consumer with the costs heatmap; pre-v1, they are deleted here.
- **The budget readout waits for 185.** 185 removes `held_count` and `max_discretionary_per_day` from `getQuietHours` and adds `getAttentionBudget`. Until 185 is on `main`, the Attention module shows the quiet-hours form and no budget numbers (never a guessed maximum).
- **Pie charts stay.** `@myguyze/ze-ui` `PrimitiveRenderer` renders the server-driven `pie` chart kind, so `pie-chart` and its context stay. Only `heatmap-chart` and `heatmap-data` (used only by the costs heatmap) are deleted. `optional-charts` and `ChartsToggle` are deleted by whichever of 189 and 190 lands second (both carry the same conditional task).
- **There is no channels or Gmail connection REST route.** Connections shows the server URL and key test, the server version, plugin settings from the UI manifest, and the palette; Gmail status is a gap for 194.
- **The workspace page is a file map only** (status and file list). Governance › Files takes all of it, read-only, and `pages/workspace` and `widgets/workspace-management` are deleted here; 188's Runs module uses `listWorkspaceRuns` and does not touch them.
- **"Chat about this" on Governance rows needs resolver kinds 195 does not have** (`cost_anomaly`, `data_domain`, `workspace_file`). This phase publishes the place and focused module only; per-row chips and the eval case wait for 194.
- **The Tailwind `@theme` remap stays** for 193 to delete (other interim pages may still be standing when 190 lands).

## Overview

Governance answers "is Ze behaving?" at `/governance`: spend, attention budget and quiet hours, data, connections and settings, workspace files. It replaces the interim Governance sections from 183 (Usage, Data, Settings) and the workspace files part of `/workspace`.

## Modules

- **Spend**: last 7 days' daily average against the 30-day daily average, anomaly count (coral when > 0), per-flow 30-day totals, one `SeriesSpark` over the 30 days (`getCostSummary`, `getCostAnomalies`). Totals two decimals; run and baseline costs under $1 four.
- **Attention budget**: one line on getting pushes (ntfy topic, "Open ntfy"), quiet hours form (`getQuietHours`, `updateQuietHours`); after 185: pushes used of max in the rolling 24-hour window as `Dots`, next slot, held count (`getAttentionBudget`), and recent push outcomes (`listNotifications` with `delivery` filters).
- **Data**: domains as rows with counts in plain names (closed map from `listDataDomains` ids; no mono table names, no "IMPORTABLE" badge); import keeps the `.zip` file input; export, import, delete with the intent step (`createDeleteIntent`, `deleteData`); export progress as a draw-on rule with "preparing".
- **Connections**: server URL and API key test (`healthCheck`, `getVersion`), plugin settings operations from the UI manifest (News settings here), palette (183's control, moved into this module). Gmail status and the model tier default wait for 194.
- **Files** (read-only map): workspace status (available, bytes used of ceiling, busy) and the file tree (`getWorkspace`, `listWorkspaceFiles`), sidecar-off state.

## User Scenarios & Testing *(mandatory)*

1. **"Am I spending normally?" in one look (P1)**: total, anomaly count, sparkline. Test with fixtures incl. an anomaly.
2. **Quiet hours round-trip (P1)** with validation.
3. **Export / import / delete with the intent token (P1).**
4. **Forget this server (P2)** clears the saved URL and key after one confirmation.
5. **Connection test (P2)** reports server version or the failing reason.
6. **Phone (P1)**: Attention budget → Spend → Connections → Data → Files.

## Requirements *(mandatory)*

- **FR-001**: `pages/governance`; widgets `spend`, `attention`, `data`, `connections`, `files`; `shared/ui/hud/SeriesSpark`.
- **FR-002**: Hard cuts: `pages/{costs,data,settings,workspace}`, `widgets/{costs-overview,data-overview,settings-workspace,workspace-management}`, the activity heatmap, `heatmap-chart` and `heatmap-data` in `@myguyze/ze-ui/charts` (pie stays: the renderer uses it), `shared/lib/optional-charts.ts` and `ChartsToggle` if no user remains, `pages/governance/ui/GovernanceInterim.tsx`, the Doing interim's Workspace section, the WS commands `reset_preview` and `reset`, `GET /api/v0/activity/heatmap` with its aggregator and tests, `queryKeys.activityHeatmap`.
- **FR-002a**: Screen context (phase 195): Governance publishes `place: "governance"` and the focused module. Per-row "Chat about this" on anomalies, data domains and files, and the Governance eval case, wait for resolver kinds in 194.
- **FR-003**: Acceptance: critique ≥ 29/40; detector 0; captures.

## Success Criteria *(mandatory)*

- **SC-001**: No chart renders without the question it answers as its module label.
- **SC-002**: `make test-web`, `make typecheck-web`, `make web-build`, lint pass.

## Out of Scope

- Collisions view (needs 194 gap 8; added to Governance when 194 lands).
- Gmail and channel connection status, default model tier, per-row screen-context chips (194).
- A "Start over" reset (Q-2 (a)); the `ResetService` cascade bug is logged for 194.

## Owning packages

ze-web, `@myguyze/ze-ui` (heatmap deletion), ze-api (WS reset command cut, activity route cut); no migration.
