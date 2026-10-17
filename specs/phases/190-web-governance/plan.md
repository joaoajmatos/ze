# Implementation Plan: Governance (W6)

**Branch**: `190-web-governance` | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md (Clarifications 2026-10-17 are binding), `main` at b5fdc1c1 (183 and 184 landed). Built in parallel with 186 and 189; the 185 budget readout and the 195 publishing are the last two task phases.

## Summary

Governance becomes one page at `/governance` that answers "is Ze behaving?" in six modules: Spend, Attention, Data, Connections, Files and Reset. It replaces the interim Usage, Data and Settings pages and the workspace file map. One backend addition makes Reset honest: REST preview and reset routes over the existing `ResetService` replace the two WS commands that answered with a chat message. The costs heatmap and its chart are deleted.

## Technical Context

**Language/Version**: TypeScript 5, React 19, TanStack Query 5 (ze-web, `@myguyze/ze-ui`); Python 3.12 (ze-api routes).
**Primary Dependencies**: none new.
**Storage**: no migration. `localStorage` stays only for the existing client config (server URL, key) and palette.
**Testing**: vitest + Testing Library; pytest for the reset routes (fake `ResetService`).
**Constraints**: FSD; DESIGN.md "no chart without a question" (SC-001: every chart's module label is its question); money with two decimals; 44 px targets.
**Scale**: single user.

## Constitution Check

| Principle | Check |
|---|---|
| Spec first | spec.md + Clarifications; plan and tasks here. |
| Honest claims | No budget numbers before 185; reset counts from the service, labelled in plain words; Gmail status omitted (no API). |
| Package boundaries | ze-api owns the reset routes; ze-onboarding's `ResetService` unchanged. |
| Pre-v1 hard cuts | WS `reset_preview`/`reset` deleted with their schema values; old pages, widgets, heatmap chart deleted. |
| Tests | Fail-first per task. |
| Docs are part of done | [DOCS] tasks cover "Docs touched". |

## Blast radius

`graphify affected` on `main` b5fdc1c1 plus `rtk proxy grep`:

| Symbol | Callers | Change |
|---|---|---|
| `CostsOverview` (+ `AgentHeatmap`, `ActivityHeatmapPanel`, `DayDetailPopover`, `HeatmapLegend`) | `pages/costs` | Deleted; `widgets/spend`. |
| `DataOverview` | `pages/data` | Deleted; `widgets/data`. |
| `SettingsWorkspace`, `QuietHoursSettings`, `PluginSettingsSection` | `pages/settings` | Deleted; quiet hours → `widgets/attention`, plugin settings → `widgets/connections`. 185 T005 edits `QuietHoursSettings`: if 185 lands first, its budget hook is reused in Phase 6; if 190 lands first, 185 rebases onto `widgets/attention`. |
| `WorkspaceManagement` | `pages/workspace` (Doing interim `workspace` loader) | Deleted; `widgets/files`. |
| `GovernanceInterim` (grep), `ChoosePalette` | `routes.tsx`, its test; `features/choose-palette` stays and renders in Connections | Interim deleted. |
| `HeatmapChart`, `heatmap-data` (`@myguyze/ze-ui/charts`) | `AgentHeatmap`, `CostsOverview` (grep; graphify's list here is noisy) | Deleted with their export and test. `PieChart` stays (`PrimitiveRenderer` `pie`). |
| `useOptionalCharts`, `ChartsToggle` | `widgets/memory-graph/ui/GraphToolbar.tsx` (189 deletes it) | Deleted when no user remains (grep at T016). |
| `entities/activity` (`useActivityHeatmapQuery`) | `ActivityHeatmapPanel` only | Deleted; `GET /api/v0/activity/heatmap` loses its consumer (listed for 194). |
| `settingsDataPath`, `settingsDataSectionId` (`shared/config/places.ts`) | `DataOverview`, `SettingsWorkspace` | Point at `/governance` with hint `data`. |
| redirects | `places.ts` (+ test), `routes.test.tsx` | `/costs` → `/governance`; `/data`, `/governance/data` → `/governance` (hint `data`); `/settings`, `/governance/settings` → `/governance` (hint `connections`); `/workspace`, `/doing/workspace` → `/governance` (hint `files`). |
| WS `reset_preview` / `reset` (`ze_api/api/ws/commands.py`, `ws/schemas.py` `Name3`) | no web caller; docs `native-interface.md`, `onboarding.md` | Deleted; generated `ws.ts` regenerates. |
| `ResetService` | ze-api container, `scripts/reset_personal_state.py`, tests | Unchanged; new routes call it. |

Parallel touch points with 186 and 189: `app/router/routes.tsx`, `shared/config/places.ts` (+ tests), `shared/lib/query-keys.ts`, `pages/doing/ui/DoingInterim.tsx` (189 removes Procedures, 190 removes Workspace). Each edits only its own lines.

## Design

### Backend

`apps/ze-api/ze_api/api/v0/reset/{router,schemas}.py`:
- `GET /reset/preview?scope=memory|personal_state|full_dev` (`previewReset`) → `{ scope, counts: [{ table, count }] }`.
- `POST /reset` (`resetState`), body `{ scope, confirm }` → `{ scope, deleted: [{ table, count }] }`; `confirm != "RESET"` → 422 (the service raises `OnboardingError`; map it); service failure → 503.
- Register in `api/v0/__init__.py`; `require_api_key`. Delete the two WS branches and their `Name3` values.

### Web

- `widgets/spend`: question label "Am I spending normally?"; 7-day total (two decimals), anomaly count (coral only when > 0), per-flow readouts from `by_agent` and `by_plugin` (plain names, top 5 + "others"), one `Spark` over `by_day`; anomaly rows (agent, run cost vs baseline, multiplier, when).
- `widgets/attention`: quiet hours form (port of `QuietHoursSettings` validation: HH:MM, timezone, start ≠ end) with `useQuietHoursQuery`/`useUpdateQuietHoursMutation`; Phase 6 adds the budget readout (`Dots` used of max, next slot, held count) and recent push outcomes.
- `widgets/data`: domain rows (plain label from a closed map in `lib/domain-labels.ts`, count; unknown → humanised id), export (draw-on rule with "preparing"), import, delete with the intent step (`features/{export,import,delete}-user-data`).
- `widgets/connections`: server URL and key form + test (`features/test-api-connection`, `getConfig`/`saveConfig`/`clearConfig`, `reconnect`, `resetClient`), server version (`getVersion`), plugin settings sections from the manifest (`PluginSettingsSection` logic moved in), `ChoosePalette`.
- `widgets/files`: status line (available, bytes used of ceiling, busy), file rows (path, size, modified), upload (`placeWorkspaceFile`), delete (`deleteWorkspaceFile` via a new `entities/workspace` mutation), "Workspace is off" state when `available` is false (Files only).
- `widgets/reset`: scope choice (memory, personal state) → `previewReset` → counts in plain words (`lib/table-labels.ts`, closed map; unknown tables summed as "other records") → typed "RESET" → `resetState` → result; disabled while offline.
- `pages/governance`: `GovernancePage` with modules in desktop order (Spend, Attention | Data, Connections | Files, Reset) and phone order (Attention → Spend → Connections → Data → Files → Reset); `RedirectHintTarget` ids `data`, `connections`, `files`.
- Router: `governance` → `GovernancePage`; `governance/*` other paths → not found; delete `governanceLoaders`; Doing interim drops `workspace`.

### Split phases

- **After 185**: `widgets/attention` budget readout from `useAttentionBudgetQuery` (185, `entities/notification`): `Dots` used of `max_per_day`, "next slot HH:MM" when `next_slot_at`, held count; recent outcomes from `listNotifications?delivery=held&delivery=suppressed&delivery=failed&limit=10` (key `["notifications-delivery", …]`, not under `["notifications"]`, see 186).
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
apps/ze-api/ze_api/api/v0/reset/ ; apps/ze-api/ze_api/api/ws/{commands,schemas}.py ; apps/ze-api/ze_api/api/v0/__init__.py
apps/ze-web/src/pages/governance/ ; widgets/{spend,attention,data,connections,files,reset}/
apps/ze-web/src/entities/workspace/api/useDeleteWorkspaceFileMutation.ts ; entities/reset/ (preview query, reset mutation)
apps/ze-web/src/app/router/routes.tsx ; shared/config/places.ts ; pages/doing/ui/DoingInterim.tsx
packages/ze-ui/src/charts/{heatmap-chart.tsx,heatmap-data.ts,index.tsx} ; packages/ze-client/src/generated/*
```

## Docs touched ([DOCS] tasks)

- `docs/frontend.md`: Governance place and modules; deleted Usage/Data/Settings/Workspace pages; redirects.
- `docs/native-interface.md`: WS `reset_preview`/`reset` removed; reset REST.
- `docs/onboarding.md`: reset now via REST and Governance › Reset.
- `docs/workspace.md`: the file map lives in Governance › Files (chat-first unchanged).
- `docs/architecture.md`: REST table (reset routes), web section.
- `docs/features.md`: Governance.
- `packages/ze-ui/README.md`: heatmap chart removed.
- `AGENTS.md`: phase row 190; Learned User Preferences workspace line (map moved to Governance › Files, still tree/info only); `specs/README.md` row 190.

## Complexity Tracking

None.
