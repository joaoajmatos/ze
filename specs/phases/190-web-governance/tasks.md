# Tasks: Governance (W6)

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), DESIGN.md.

**Build gate**: starts now on `main` (183 and 184 landed), in parallel with 186 and 189. Phase 6 waits for 185 on `main`; Phase 7 waits for 195 on `main`. If either has not landed when the rest is done, the floor goes to review without it and the split phase lands as a follow-up commit. The Spec Architect (Lintel) stays on call.

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Vitest + Testing Library with a mocked `@myguyze/ze-client`; pytest for the backend deletions.

**Lanes**: `[ENG]` Claude Sonnet lane lead (backend cuts, redirects, page, router, spend, attention, connections, gates). `[JR]` OpenCode junior (exact files given). Floor Reviewer reviews per user story. `[DOCS]` Docs Steward.

**Tags**: `[BACKEND]` Python · `[WEB]` ze-web, `@myguyze/ze-ui`, generated client · `[DOCS]` docs and specs.

**Rules for the implementer**
- FSD: `pages → widgets → features → entities → shared`; widgets get callbacks by props.
- Every chart's module label is the question it answers (SC-001). No budget number before 185. Files are read-only (user decision). No Reset module (user decision).
- Shared with the 186, 188 and 189 floors: `app/router/routes.tsx`, `app/router/RedirectTo.tsx`, `shared/config/places.ts` (+ tests), `shared/lib/query-keys.ts`, `pages/doing/ui/DoingInterim.tsx`, `shared/ui/hud/index.ts`. Edit only Governance's lines; rebase if they landed first.
- 44 px targets: assert the min-size class in tests (jsdom has no layout); check sizes in the T019 captures.
- Generated client (`packages/ze-client/src/generated/*`) belongs to ENG: commit `make codegen` output with each task that changes the OpenAPI or WS schema.
- Before changing a shared export, run `graphify affected "<Symbol>" --depth 2` and `rtk proxy grep`; update every caller in the same change.
- Shared worktree: `git add <paths>`; `git commit -m ... -- <paths>`; never `git add -A` or `git stash`. Commit only when the ENG lead or Maestro asks; split commits by user story.

---

## Phase 0: Gate [ENG]

- [ ] T001 [ENG] [WEB] Branch from current `main`. `make web-install`; `graphify update .`; `graphify affected` on `CostsOverview`, `DataOverview`, `SettingsWorkspace`, `QuietHoursSettings`, `PluginSettingsSection`, `WorkspaceManagement`, `RedirectTo`; grep `GovernanceInterim`, `governanceLoaders`, `HeatmapChart`, `heatmap-data`, `activityHeatmap`, `useOptionalCharts`, `ChartsToggle`, `reset_preview`, `settingsDataPath`, `getActivityHeatmap`. Record in the Handoffs note: (a) differences from plan.md "Blast radius"; (b) whether 185 and 195 are on `main` and whether 185 changed `QuietHoursSettings`; (c) whether 189 already removed `GraphToolbar` (last `useOptionalCharts` user); (d) the impeccable baseline critique of the interim Governance. Stop and report differences to the Spec Architect.

## Phase 1: Backend cuts [US1]

- [ ] T002 [ENG] [BACKEND] Tests first, new `apps/ze-api/tests/api/test_ws_commands_reset_removed.py` (no test covers these branches today): a `command` frame named `reset_preview` or `reset` fails schema validation. Delete both branches in `ze_api/api/ws/commands.py` and both names from the `WsCommandFrame.name` Literal in `ws/schemas.py`.
- [ ] T003 [ENG] [BACKEND] Delete `ze_api/api/v0/activity/` and its registration in `api/v0/__init__.py`, and `tests/api/test_activity_route.py`; the OpenAPI export test no longer lists `getActivityHeatmap`. `make codegen`; commit the generated client and WS types with T002–T003.

## Phase 2: Shared [US1, US6]

- [ ] T004 [ENG] [WEB] Tests first `shared/ui/hud/SeriesSpark.test.tsx`: min–max scaling, empty and single-point input, `aria-label` with first, last and max. Implement `SeriesSpark.tsx`, export from `shared/ui/hud`; add one line to DESIGN.md (Rows: "SeriesSpark draws a series; Spark draws a two-point change").
- [ ] T005 [ENG] [WEB] Tests first `app/router/RedirectTo.test.tsx` and `shared/config/places.test.ts`: an entry with `hint` replaces the incoming hash and keeps the query (`/settings?x=1#your-data` → `/governance?x=1#data`; `/settings` → `/governance#connections`; `/workspace` → `/governance#files`); entries without `hint` keep today's behaviour. Add `hint?: string` to the redirect table and implement it in `RedirectTo`.
- [ ] T006 [P] [JR] [WEB] Tests first `widgets/data/lib/domain-labels.test.ts` and `widgets/spend/lib/money.test.ts`: closed domain map from `listDataDomains` ids to plain words, unknown → humanised id, no raw table name; money: totals two decimals, amounts under $1 four decimals for run and baseline. Implement both.

## Phase 3: Spend, Data, Files [US1, US3]

- [ ] T007 [ENG] [WEB] Tests first `widgets/spend/ui/Spend.test.tsx` (fixtures incl. one anomaly): label "Am I spending normally?"; "last 7 days $x/day vs 30-day $y/day" from `by_day`; anomaly count coral only when > 0; per-flow 30-day totals top 5 + others; `SeriesSpark` over `by_day`; anomaly rows with run vs baseline. Implement `widgets/spend`.
- [ ] T008 [P] [JR] [WEB] Tests first `widgets/data/ui/Data.test.tsx`: domain rows with plain labels and counts (no mono table names, no "IMPORTABLE" badge); export shows "preparing" then done; import uses a `.zip` file input and shows the result; delete runs `createDeleteIntent` then `deleteData` behind a typed DELETE confirmation. Implement `widgets/data` with the three features.
- [ ] T009 [P] [JR] [WEB] Tests first `widgets/files/ui/Files.test.tsx`: status line; tree rows (path, size, modified); no upload or delete control; `available: false` → "Workspace is off" in Files only. Implement `widgets/files`.

## Phase 4: Attention, Connections [US2, US4, US5]

- [ ] T010 [ENG] [WEB] Tests first `widgets/attention/ui/Attention.test.tsx`: the ntfy line with "Open ntfy"; quiet-hours round trip with validation (HH:MM, timezone, start ≠ end; disabled clears the times); no budget number or maximum rendered (until Phase 6). Implement `widgets/attention` (port the `QuietHoursSettings` logic).
- [ ] T011 [ENG] [WEB] Tests first `widgets/connections/ui/Connections.test.tsx`: save URL and key, test reports the server version or the failing reason; plugin settings sections from the manifest render (port of `PluginSettingsSection`); `ChoosePalette` renders; "Forget this server" asks once, then clears the saved config. Implement `widgets/connections`.

## Phase 5: Page, router, cuts [US1–US6]

- [ ] T012 [ENG] [WEB] Tests first `pages/governance/ui/GovernancePage.test.tsx`: desktop module order; phone order Attention → Spend → Connections → Data → Files; hint targets `data`, `connections`, `files`; no Reset module. Implement `GovernancePage`, `pages/governance/index.ts`.
- [ ] T013 [ENG] [WEB] Tests first `app/router/routes.test.tsx`: `/governance` → `GovernancePage`; other `/governance/*` → not found; `/costs` → `/governance`; `/data`, `/governance/data` → `/governance#data`; `/settings`, `/governance/settings` → `/governance#connections`; `/workspace`, `/doing/workspace` → `/governance#files`; `settingsDataPath()` → `/governance#data`. Update `routes.tsx` (delete `governanceLoaders`, remove the Doing `workspace` loader), `places.ts`, `pages/doing/ui/DoingInterim.tsx` (drop Workspace; a no-op if 188 deleted the file).
- [ ] T014 [ENG] [WEB] Delete `pages/{costs,data,settings,workspace}`, `widgets/{costs-overview,data-overview,settings-workspace,workspace-management}`, `entities/activity`, `queryKeys.activityHeatmap` (+ its `query-keys.test.ts` case), the heatmap comment in `shared/config/agents.ts`, `pages/governance/ui/GovernanceInterim.tsx` (+ tests). `rtk proxy grep -rn "costs-overview\|data-overview\|settings-workspace\|workspace-management\|GovernanceInterim\|activityHeatmap\|ActivityHeatmap" apps/ze-web/src` returns only `/jarvis` hits if any.
- [ ] T015 [JR] [WEB] Delete `packages/ze-ui/src/charts/heatmap-chart.tsx`, `heatmap-data.ts`, `heatmap-data.test.ts` and their export in `charts/index.tsx`; `PieChart` stays. `make test-web`.
- [ ] T016 [JR] [WEB] If grep finds no other user (189 removed `GraphToolbar`): delete `shared/lib/optional-charts.ts`, `shared/ui/primitives/ChartsToggle.tsx` and their exports. Otherwise leave them: 189's T016 carries the same conditional, so whichever floor lands second deletes them.

## Phase 6: Budget readout (needs 185 on main) [US2]

- [ ] T017 [ENG] [WEB] Tests first in `widgets/attention/ui/Attention.test.tsx`: `Dots` show `used` of `max_per_day`; "next slot HH:MM" only when `next_slot_at`; held count; recent outcomes from `listNotifications` with `delivery` held/suppressed/failed (key `["notifications-delivery", …]`, outside `["notifications"]`); a 503 from the budget route shows the module error line, never a number. Implement with 185's `useAttentionBudgetQuery`.

## Phase 7: Screen context (needs 195 on main)

- [ ] T018 [JR] [WEB] Tests first: `GovernancePage` publishes `place: "governance"` and `focused_module` via `useScreenPublisher`; no per-row refs. Implement.

## Phase 8: Acceptance and docs

- [ ] T019 [ENG] [WEB] Gates: `make test-web`, `make typecheck-web`, `make web-build`, `make lint`, `make test-py`. Impeccable critique of Governance ≥ 29/40 and ≥ the T001 baseline; detector 0; captures at 1440 and 390 with no console errors and 44 px targets; SC-001 check (every chart labelled by its question). Record in the Handoffs note.
- [ ] T020 [DOCS] Update every doc in plan.md "Docs touched".
- [ ] T021 [DOCS] `AGENTS.md` phase row 190, the phase 92 heatmap note and the workspace preference line; `specs/README.md` row 190 → Implemented; spec status.
- [ ] T022 [DOCS] Coverage check: `git diff main...HEAD --stat` against "Docs touched"; record in the Handoffs note.

---

## Dependencies

- T001 first. T002 → T003. T004, T005, T006 independent.
- T007 after T004, T006. T008 after T006. T009 independent. T010, T011 independent.
- T012 after T007–T011. T013 after T005, T012. T014 after T013. T015 after T014. T016 after T014.
- T017 after 185 on `main` and T010. T018 after 195 on `main` and T012.
- T019 after all landed code; T020–T022 last.

## Lanes

### Lane ENG (Claude Sonnet, lane lead)

T001–T005, T007, T010–T014, T017, T019. Owns `packages/ze-client/src/generated/*`, `app/router/*`, `shared/config/places.ts`.

### Lane JR (OpenCode junior)

T006, T008, T009, T015, T016, T018.

### Docs (Docs Steward)

T020–T022.
