# Implementation Plan: Governance (W6)

**Branch**: `190-web-governance` | **Date**: 2026-10-17 (revised 2026-10-18 after Gauge's review G-1..G-5) | **Spec**: [spec.md](./spec.md)

**Input**: spec.md (Clarifications are binding; the user chose Q-1 (a) and Q-2 (a) on 2026-10-18), `main` at b5fdc1c1 (183 and 184 landed). Built in parallel with 186 and 189; the 185 budget readout and the 195 publishing are the last two task phases.

## Summary

Governance becomes one page at `/governance` that answers "is Ze behaving?" in five modules: Spend, Attention, Data, Connections and Files. It replaces the interim Usage, Data and Settings pages and the workspace file map. Spend answers its question against a real baseline: the last 7 days' daily average against the 30-day average. It draws its trend with a new `SeriesSpark`, because the HUD `Spark` only draws a two-point change. The costs heatmap, its chart, its REST route, and the unused and unsafe WS reset commands are deleted. Old paths land on the right module through a `hint` field in the redirect table.

## Technical Context

**Language/Version**: TypeScript 5, React 19, TanStack Query 5 (ze-web, `@myguyze/ze-ui`); Python 3.12 (ze-api deletions only).
**Primary Dependencies**: none new.
**Storage**: no migration. `localStorage` stays for the existing client config (server URL, key) and palette.
**Testing**: vitest + Testing Library; pytest for the WS command and route deletions.
**Constraints**: FSD; DESIGN.md "no chart without a question" (SC-001); money: totals two decimals, sub-dollar run and baseline costs four; 44 px targets (asserted by class, measured in captures).
**Scale**: single user.

## Constitution Check

| Principle | Check |
|---|---|
| Spec first | spec.md + Clarifications; plan and tasks here. |
| Honest claims | No budget number before 185; Spend compares like with like (30-day API window); no Reset that undercounts what it destroys; Gmail status omitted (no API). |
| Package boundaries | ze-api deletions only; ze-onboarding's `ResetService` untouched (its bug logged for 194). |
| Pre-v1 hard cuts | WS reset commands, activity heatmap route and aggregator, old pages, widgets, heatmap chart deleted. |
| Tests | Fail-first per task. |
| Docs are part of done | [DOCS] tasks cover "Docs touched". |

## Blast radius

`graphify affected` on `main` b5fdc1c1 plus `rtk proxy grep`:

| Symbol | Callers | Change |
|---|---|---|
| `CostsOverview` (+ `AgentHeatmap`, `ActivityHeatmapPanel`, `DayDetailPopover`, `HeatmapLegend`) | `pages/costs` | Deleted; `widgets/spend`. |
| `DataOverview` | `pages/data` | Deleted; `widgets/data`. |
| `SettingsWorkspace`, `QuietHoursSettings`, `PluginSettingsSection` | `pages/settings` | Deleted; ntfy line and quiet hours → `widgets/attention`; URL/key, plugin settings, palette, "Forget this server" → `widgets/connections`. 185 T005 edits `QuietHoursSettings`: if 185 lands first, Phase 6 reuses its budget hook; if 190 lands first, 185 rebases onto `widgets/attention`. |
| `WorkspaceManagement` | `pages/workspace` (Doing interim `workspace` loader) | Deleted; `widgets/files` (read-only). |
| `GovernanceInterim` (grep), `ChoosePalette` | `routes.tsx`, its test; `features/choose-palette` stays, rendered in Connections | Interim deleted. |
| `HeatmapChart`, `heatmap-data` (`@myguyze/ze-ui/charts`) | `AgentHeatmap`, `CostsOverview` and ze-ui's own test (grep) | Deleted with their export. `PieChart` stays (`PrimitiveRenderer` `pie`). |
| `useOptionalCharts`, `ChartsToggle` | `widgets/memory-graph/ui/GraphToolbar.tsx` (189 deletes it) | Deleted by whichever of 189 and 190 lands second (same conditional task in both). |
| `entities/activity`, `queryKeys.activityHeatmap` (+ `query-keys.test.ts`), the `shared/config/agents.ts` comment | `ActivityHeatmapPanel` only | Deleted. |
| `GET /api/v0/activity/heatmap` (`getActivityHeatmap`, `ze_api/api/v0/activity/*`) | `api/v0/__init__.py`, `tests/api/test_activity_route.py` | Deleted with its test; codegen drops the operation. |
| WS `reset_preview` / `reset` (`ze_api/api/ws/commands.py`; the `WsCommandFrame.name` Literal in `ws/schemas.py`, generated as `Name3` in `ws.ts`) | no web caller; docs `native-interface.md:74-75`, `onboarding.md:179` | Deleted; no existing test covers these branches (new test). |
| `ResetService` | ze-api container, `scripts/reset_personal_state.py`, `tests/onboarding/test_reset.py` | Unchanged (developer script path); the WS route to it goes. |
| `settingsDataPath`, `settingsDataSectionId` | `DataOverview`, `SettingsWorkspace` | Return `/governance#data`. |
| `redirects`, `RedirectTo` | `places.ts` (+ test), `routes.tsx`, `routes.test.tsx` | Optional `hint` per entry; `RedirectTo` uses it instead of the incoming hash (`your-data` → `data`), keeps the query. |
| `Spark` (`shared/ui/hud`) | 183 shell, 186 rows | Unchanged; new `SeriesSpark` beside it. |

Parallel touch points with 186 and 189: `app/router/routes.tsx`, `app/router/RedirectTo.tsx`, `shared/config/places.ts` (+ tests), `shared/lib/query-keys.ts`, `pages/doing/ui/DoingInterim.tsx` (189 removes Procedures, 190 removes Workspace, 188 deletes the file), `shared/ui/hud/index.ts`. Each edits only its own lines.

## Design

### Backend (deletions)

- `ze_api/api/ws/commands.py`: delete the `reset_preview` and `reset` branches; remove both names from the `WsCommandFrame.name` Literal (`ws/schemas.py`).
- `ze_api/api/v0/activity/`: delete the package and its registration; delete `tests/api/test_activity_route.py`.

### Web

- `shared/ui/hud/SeriesSpark.tsx`: an SVG polyline over `values: number[]` (min–max scaled, a baseline tick optional), tokens from `ze.css`, `aria-label` with the first, last and max values; tests for scaling, empty and single-point input. DESIGN.md gains one line under Rows.
- `widgets/spend`: label "Am I spending normally?"; readouts "last 7 days $x.xx/day vs 30-day $y.yy/day" (from `by_day`), anomaly count (coral only when > 0), per-flow 30-day totals from `by_agent` and `by_plugin` (plain names, top 5 + "others"), `SeriesSpark` over `by_day`; anomaly rows (agent, run vs baseline with four decimals under $1, multiplier, when). `lib/money.ts` (pure) holds the formatting.
- `widgets/attention`: one line on pushes ("Pushes go to your ntfy topic" + "Open ntfy"), quiet hours form (port of `QuietHoursSettings` validation: HH:MM, timezone, start ≠ end) with `useQuietHoursQuery`/`useUpdateQuietHoursMutation`; no budget numbers until Phase 6.
- `widgets/data`: domain rows (plain label from `lib/domain-labels.ts`, a closed map keyed by `listDataDomains` ids; unknown → humanised id), export (draw-on rule with "preparing"), import (file input, `.zip` accept), delete with the intent step (`features/{export,import,delete}-user-data`).
- `widgets/connections`: server URL and key form + test (`features/test-api-connection`, `getConfig`/`saveConfig`, `reconnect`, `resetClient`), server version (`getVersion`), plugin settings sections from the manifest (`PluginSettingsSection` logic moved in), `ChoosePalette`, "Forget this server" (`clearConfig` after one confirmation).
- `widgets/files`: status line (available, bytes used of ceiling, busy), the file tree (path, size, modified), "Workspace is off" when `available` is false; read-only.
- `pages/governance`: `GovernancePage`, desktop order (Spend, Attention | Data, Connections | Files) and phone order (Attention → Spend → Connections → Data → Files); `RedirectHintTarget` ids `data`, `connections`, `files`.
- Router: `governance` → `GovernancePage`; other `governance/*` → not found; delete `governanceLoaders`; Doing interim drops `workspace`. Redirects (with `hint`): `/costs` → `/governance`; `/data`, `/governance/data` → `/governance` hint `data`; `/settings`, `/governance/settings` → `/governance` hint `connections` (an incoming `#your-data` maps to `data`); `/workspace`, `/doing/workspace` → `/governance` hint `files`.

### Split phases

- **After 185**: `widgets/attention` budget readout from `useAttentionBudgetQuery` (185, `entities/notification`): `Dots` used of `max_per_day`, "next slot HH:MM" when `next_slot_at`, held count; recent outcomes from `listNotifications?delivery=held&delivery=suppressed&delivery=failed&limit=10` (key `["notifications-delivery", …]`, outside `["notifications"]`, see 186); a 503 shows the module error line.
- **After 195**: `GovernancePage` publishes `place: "governance"` and `focused_module` with `useScreenPublisher`; no per-row refs (no resolver kinds; 194).

## Project Structure

### Documentation (this feature)

```
specs/phases/190-web-governance/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code

```
apps/ze-api/ze_api/api/ws/{commands,schemas}.py ; apps/ze-api/ze_api/api/v0/{__init__.py,activity/} ; apps/ze-api/tests/api/test_activity_route.py
apps/ze-web/src/pages/governance/ ; widgets/{spend,attention,data,connections,files}/ ; shared/ui/hud/SeriesSpark.tsx
apps/ze-web/src/app/router/{routes.tsx,RedirectTo.tsx} ; shared/config/places.ts ; shared/lib/query-keys.ts ; pages/doing/ui/DoingInterim.tsx
packages/ze-ui/src/charts/{heatmap-chart.tsx,heatmap-data.ts,index.tsx} ; packages/ze-client/src/generated/* ; DESIGN.md (SeriesSpark line)
```

## Docs touched ([DOCS] tasks)

- `docs/frontend.md`: Governance place and modules; deleted Usage/Data/Settings/Workspace pages; redirect table with hints; `SeriesSpark`.
- `docs/native-interface.md` (~74-75): WS `reset_preview`/`reset` removed.
- `docs/onboarding.md` (~179): reset is a developer script now (`scripts/reset_personal_state.py`).
- `docs/workspace.md` (~20): the file map lives in Governance › Files (read-only).
- `docs/architecture.md`: REST table loses `getActivityHeatmap`; web section.
- `docs/features.md`: Governance; usage heatmap removed.
- `packages/ze-ui/README.md`: heatmap chart removed.
- `AGENTS.md`: phase row 190 and the phase 92 heatmap row note; Learned User Preferences workspace line (map now in Governance › Files, still tree/info only); `specs/README.md` row 190.

## Complexity Tracking

None.
