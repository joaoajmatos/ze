# Feature Specification: Governance (W6)

**Feature Branch**: `190-web-governance`

**Created**: 2026-10-17

**Status**: Draft (spec level; plan and tasks follow once scheduled)

**Input**: Maestro brief 2026-10-17, phase W6; overhaul plan sections a (Governance), b.5, e (Phase W6). User decision 5: palette is a Governance setting.

**Governed by**: `DESIGN.md` ("no chart without a question"), `PRODUCT.md` ("Interruption is a budget"), phases 17/120 (costs), 62 (data portability), 177 (quiet hours, budget), 115 (workspace files).

**Depends on**: 183 (shell, palette control), 195 (screen context, "Chat about this"). Uses 185 (budget used today, push log) and 194 (default tier, collisions) when available.

**Doctrine function served**: governance (is Ze behaving: spend, attention, data, connections).

---

## Overview

Governance answers "is Ze behaving?" at `/governance`: spend, attention budget and quiet hours, data, connections and settings, workspace files, reset. It replaces the interim Governance sections from 183 (Usage, Data, Settings) and the workspace files part of `/workspace`.

## Modules

- **Spend**: 7-day total, per-flow readouts, anomalies coral, one trend sparkline (`getCostSummary`, `getCostAnomalies`). Money with two decimals.
- **Attention budget**: pushes used today of max as `Dots` (185 `getPushBudget`; until then "max N a day" only), quiet hours form (`getQuietHours`, `updateQuietHours`), held pushes, recent push log rows (185).
- **Data**: domains as rows with counts in plain names (no mono table names, no "IMPORTABLE" badge); export, import, delete with the intent step (`createDeleteIntent`, `deleteData`); export progress as a draw-on rule with "preparing".
- **Connections**: server URL and API key test (`healthCheck`, `getVersion`), Gmail and plugin connections, plugin settings operations from the UI manifest (News settings here), palette (183's control, moved into this module), model tier default (194 when available).
- **Files**: workspace files list, upload, delete (`listWorkspaceFiles`, `uploadWorkspaceFile`, `deleteWorkspaceFile`), sidecar-off state.
- **Reset**: scoped reset with preview and typed confirmation (WS `command: reset_preview` / `reset`).

## User Scenarios & Testing *(mandatory)*

1. **"Am I spending normally?" in one look (P1)**: total, anomaly count, sparkline. Test with fixtures incl. an anomaly.
2. **Quiet hours round-trip (P1)** with validation.
3. **Export / import / delete with the intent token (P1).**
4. **Reset preview then typed confirm (P1).**
5. **Connection test (P2)** reports server version or the failing reason.
6. **Phone (P1)**: Attention budget → Spend → Connections → Data → Files → Reset.

## Requirements *(mandatory)*

- **FR-001**: `pages/governance`; widgets `spend`, `attention-budget`, `data`, `connections`, `files`, `reset`.
- **FR-002**: Hard cuts: `pages/{costs,data,settings}`, `pages/workspace` (files part; the page is gone once 188 took runs), `widgets/{costs-overview,data-overview,settings-workspace,workspace-management}`, the activity heatmap and every pie/heatmap chart in `@myguyze/ze-ui/charts` that no screen uses after this phase (`pie-chart`, `pie-slice`, `pie-context`, `heatmap-chart`, `heatmap-data` and their tests) plus `@uiw/react-heat-map` if present, `shared/lib/optional-charts.ts` and `ChartsToggle` if unused, `pages/governance/ui/GovernanceInterim.tsx`, and, if this is the last interim page standing, the Tailwind `@theme` remap from 183 FR-003.
- **FR-002a**: Screen context (phase 195): Governance publishes the selected anomaly, data domain or file as `subject` and wires "Chat about this" (callbacks passed down by props from widgets, 195 FR-024) on spend anomalies, data domains and file rows (and enables the Governance case in `eval/scenarios/screen_context.yaml`).
- **FR-003**: Acceptance: critique ≥ 29/40; detector 0; captures.

## Success Criteria *(mandatory)*

- **SC-001**: No chart renders without the question it answers as its module label.
- **SC-002**: `make test-web`, `make typecheck-web`, `make web-build`, lint pass.

## Out of Scope

- Collisions view (needs 194 gap 8; added to Governance when 194 lands).

## Owning packages

ze-web, `@myguyze/ze-ui` (chart deletions); no backend, no migration.
