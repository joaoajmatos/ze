# Feature Specification: Governance (W6)

**Feature Branch**: `190-web-governance`

**Created**: 2026-10-17

**Status**: Ready to implement on `main` with 183 and 184 (plan and tasks written 2026-10-17 against `main` b5fdc1c1). The budget readout waits for 185 and the screen-context publishing for 195 (split task phases); the rest starts now, alongside 186 and 189.

**Input**: Maestro brief 2026-10-17, phase W6; overhaul plan sections a (Governance), b.5, e (Phase W6). User decision 5: palette is a Governance setting.

**Governed by**: `DESIGN.md` ("no chart without a question"), `PRODUCT.md` ("Interruption is a budget"), phases 17/120 (costs), 62 (data portability), 177 (quiet hours, budget), 115 (workspace files).

**Depends on**: 183 (shell, palette control). Split tasks: the budget readout and push outcomes need 185 (`getAttentionBudget`, `listNotifications` filters); screen-context publishing needs 195. 194 (default tier, collisions, Gmail connection status) is out of scope.

**Doctrine function served**: governance (is Ze behaving: spend, attention, data, connections).

---

## Clarifications

### Session 2026-10-17 (planning against the code, parallel build)

- **Reset has no structured surface.** The WS commands `reset_preview` and `reset` answer with a chat message of raw table counts. This phase adds `GET /api/v0/reset/preview?scope=` (`previewReset`) and `POST /api/v0/reset` (`resetState`, body `{scope, confirm: "RESET"}`) over the existing `ResetService` and deletes the two WS commands (hard cut). The UI offers `memory` and `personal_state`; `full_dev` stays API-only.
- **The budget readout waits for 185.** 185 removes `held_count` and `max_discretionary_per_day` from `getQuietHours` and adds `getAttentionBudget`. Until 185 is on `main`, the Attention module shows the quiet-hours form and no budget numbers (never a guessed maximum).
- **Pie charts stay.** `@myguyze/ze-ui` `PrimitiveRenderer` renders the server-driven `pie` chart kind, so `pie-chart` and its context stay. Only `heatmap-chart` and `heatmap-data` (used only by the costs heatmap) are deleted. `optional-charts` and `ChartsToggle` are deleted by whichever of 189 and 190 removes their last user.
- **There is no channels or Gmail connection REST route.** Connections shows the server URL and key test, the server version, plugin settings from the UI manifest, and the palette; Gmail status is a gap for 194.
- **The workspace page is a file map only** (status and file list). Governance › Files takes all of it, and `pages/workspace` and `widgets/workspace-management` are deleted here; 188's Runs module uses `listWorkspaceRuns` and does not touch them.
- **"Chat about this" on Governance rows needs resolver kinds 195 does not have** (`cost_anomaly`, `data_domain`, `workspace_file`). This phase publishes the place and focused module only; per-row chips and the eval case wait for 194.
- **The Tailwind `@theme` remap stays** for 193 to delete (other interim pages may still be standing when 190 lands).

## Overview

Governance answers "is Ze behaving?" at `/governance`: spend, attention budget and quiet hours, data, connections and settings, workspace files, reset. It replaces the interim Governance sections from 183 (Usage, Data, Settings) and the workspace files part of `/workspace`.

## Modules

- **Spend**: 7-day total, per-flow readouts, anomalies coral, one trend sparkline (`getCostSummary`, `getCostAnomalies`). Money with two decimals.
- **Attention budget**: quiet hours form (`getQuietHours`, `updateQuietHours`); after 185: pushes used of max in the rolling 24-hour window as `Dots`, next slot, held count (`getAttentionBudget`), and recent push outcomes (`listNotifications` with `delivery` filters).
- **Data**: domains as rows with counts in plain names (no mono table names, no "IMPORTABLE" badge); export, import, delete with the intent step (`createDeleteIntent`, `deleteData`); export progress as a draw-on rule with "preparing".
- **Connections**: server URL and API key test (`healthCheck`, `getVersion`), plugin settings operations from the UI manifest (News settings here), palette (183's control, moved into this module). Gmail status and the model tier default wait for 194.
- **Files**: workspace status (available, bytes used of ceiling, busy), files list, upload, delete (`getWorkspace`, `listWorkspaceFiles`, `uploadWorkspaceFile`, `deleteWorkspaceFile`), sidecar-off state.
- **Reset**: scoped reset with preview (counts in plain names) and typed confirmation (`previewReset`, `resetState`).

## User Scenarios & Testing *(mandatory)*

1. **"Am I spending normally?" in one look (P1)**: total, anomaly count, sparkline. Test with fixtures incl. an anomaly.
2. **Quiet hours round-trip (P1)** with validation.
3. **Export / import / delete with the intent token (P1).**
4. **Reset preview then typed confirm (P1).**
5. **Connection test (P2)** reports server version or the failing reason.
6. **Phone (P1)**: Attention budget → Spend → Connections → Data → Files → Reset.

## Requirements *(mandatory)*

- **FR-001**: `pages/governance`; widgets `spend`, `attention-budget`, `data`, `connections`, `files`, `reset`.
- **FR-002**: Hard cuts: `pages/{costs,data,settings,workspace}`, `widgets/{costs-overview,data-overview,settings-workspace,workspace-management}`, the activity heatmap, `heatmap-chart` and `heatmap-data` in `@myguyze/ze-ui/charts` (pie stays: the renderer uses it), `shared/lib/optional-charts.ts` and `ChartsToggle` if no user remains, `pages/governance/ui/GovernanceInterim.tsx`, the Doing interim's Workspace section, the WS commands `reset_preview` and `reset`.
- **FR-002b**: Backend: `previewReset` and `resetState` REST routes in ze-api over `container.reset_service`; no migration.
- **FR-002a**: Screen context (phase 195): Governance publishes `place: "governance"` and the focused module. Per-row "Chat about this" on anomalies, data domains and files, and the Governance eval case, wait for resolver kinds in 194.
- **FR-003**: Acceptance: critique ≥ 29/40; detector 0; captures.

## Success Criteria *(mandatory)*

- **SC-001**: No chart renders without the question it answers as its module label.
- **SC-002**: `make test-web`, `make typecheck-web`, `make web-build`, lint pass.

## Out of Scope

- Collisions view (needs 194 gap 8; added to Governance when 194 lands).
- Gmail and channel connection status, default model tier, per-row screen-context chips (194).

## Owning packages

ze-web, `@myguyze/ze-ui` (heatmap deletion), ze-api (reset routes, WS command cut); no migration.
