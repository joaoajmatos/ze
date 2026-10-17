# Tasks: Governance (W6)

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), DESIGN.md.

**Build gate**: starts now on `main` (183 and 184 landed), in parallel with 186 and 189. Phase 6 waits for 185 on `main`; Phase 7 waits for 195 on `main`. If either has not landed when the rest is done, the floor goes to review without it and the split phase lands as a follow-up commit. The Spec Architect (Lintel) stays on call.

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Vitest + Testing Library with a mocked `@myguyze/ze-client`; pytest with a fake `ResetService`.

**Lanes**: `[ENG]` Claude Sonnet lane lead (reset routes, page, router, attention, connections, gates). `[JR]` OpenCode junior (exact files given). Floor Reviewer reviews per user story. `[DOCS]` Docs Steward.

**Tags**: `[BACKEND]` Python · `[WEB]` ze-web, `@myguyze/ze-ui`, generated client · `[DOCS]` docs and specs.

**Rules for the implementer**
- FSD: `pages → widgets → features → entities → shared`; widgets get callbacks by props.
- Every chart's module label is the question it answers (SC-001). No budget number before 185.
- Shared with the 186 and 189 floors: `app/router/routes.tsx`, `shared/config/places.ts` (+ tests), `shared/lib/query-keys.ts`, `pages/doing/ui/DoingInterim.tsx`. Edit only Governance's lines; rebase if they landed first.
- Generated client (`packages/ze-client/src/generated/*`) belongs to ENG: commit `make codegen` output with each task that changes the OpenAPI or WS schema.
- Before changing a shared export, run `graphify affected "<Symbol>" --depth 2` and `rtk proxy grep`; update every caller in the same change.
- Shared worktree: `git add <paths>`; `git commit -m ... -- <paths>`; never `git add -A` or `git stash`. Commit only when the ENG lead or Maestro asks; split commits by user story.

---

## Phase 0: Gate [ENG]

- [ ] T001 [ENG] [WEB] Branch from current `main`. `make web-install`; `graphify update .`; `graphify affected` on `CostsOverview`, `DataOverview`, `SettingsWorkspace`, `QuietHoursSettings`, `PluginSettingsSection`, `WorkspaceManagement`, `ResetService`; grep `GovernanceInterim`, `governanceLoaders`, `HeatmapChart`, `heatmap-data`, `useOptionalCharts`, `ChartsToggle`, `reset_preview`, `settingsDataPath`. Record in the Handoffs note: (a) differences from plan.md "Blast radius"; (b) whether 185 and 195 are on `main` and whether 185 changed `QuietHoursSettings`; (c) whether 189 already removed `GraphToolbar` (last `useOptionalCharts` user); (d) the impeccable baseline critique of the interim Governance. Stop and report differences to the Spec Architect.

## Phase 1: Reset backend [US4]

- [ ] T002 [ENG] [BACKEND] Tests first `apps/ze-api/tests/api/test_reset_routes.py` (fake `ResetService`): `GET /api/v0/reset/preview?scope=memory` returns `{scope, counts:[{table,count}]}`; unknown scope → 422; `POST /api/v0/reset` with `confirm: "RESET"` returns `deleted`; any other confirm → 422; service failure → 503; no key → 401. Implement `apps/ze-api/ze_api/api/v0/reset/{__init__,router,schemas}.py` (`previewReset`, `resetState`, response_model, summary, description); register.
- [ ] T003 [ENG] [BACKEND] Tests first in the WS command tests (`apps/ze-api/tests/api/` file covering `commands.py`): `reset_preview` and `reset` are no longer accepted commands (schema rejects the name). Delete both branches in `ze_api/api/ws/commands.py` and their `Name3` values in `ws/schemas.py`. `make codegen`; commit the generated client and WS types with T002–T003.

## Phase 2: Entities [US1–US5]

- [ ] T004 [P] [JR] [WEB] Tests first: `entities/reset/{api/useResetPreviewQuery.ts,api/useResetMutation.ts,index.ts}` (preview disabled until a scope is chosen; mutation sends `confirm`); `entities/workspace/api/useDeleteWorkspaceFileMutation.ts` (invalidates the files query). Implement.
- [ ] T005 [P] [JR] [WEB] Tests first `widgets/data/lib/domain-labels.test.ts` and `widgets/reset/lib/table-labels.test.ts`: closed maps to plain words; unknown domain → humanised id; unknown tables summed as "other records"; no raw table name in output. Implement both.

## Phase 3: Spend, Data, Files [US1, US3]

- [ ] T006 [ENG] [WEB] Tests first `widgets/spend/ui/Spend.test.tsx` (fixtures incl. one anomaly): label "Am I spending normally?"; total with two decimals; anomaly count coral only when > 0; per-flow readouts top 5 + others; one `Spark` over `by_day`; anomaly rows. Implement `widgets/spend`.
- [ ] T007 [P] [JR] [WEB] Tests first `widgets/data/ui/Data.test.tsx`: domain rows with plain labels and counts (no mono table names, no "IMPORTABLE" badge); export shows "preparing" then done; import result; delete runs `createDeleteIntent` then `deleteData` behind a confirmation. Implement `widgets/data` with the three features.
- [ ] T008 [P] [JR] [WEB] Tests first `widgets/files/ui/Files.test.tsx`: status line; rows (path, size, modified); upload calls `placeWorkspaceFile` and refreshes; delete asks once then calls the mutation; `available: false` → "Workspace is off" in Files only. Implement `widgets/files`.

## Phase 4: Attention, Connections, Reset [US2, US4, US5]

- [ ] T009 [ENG] [WEB] Tests first `widgets/attention/ui/Attention.test.tsx`: quiet-hours round trip with validation (HH:MM, timezone, start ≠ end; disabled clears the times); no budget number or maximum rendered (until Phase 6). Implement `widgets/attention` (port the `QuietHoursSettings` logic).
- [ ] T010 [ENG] [WEB] Tests first `widgets/connections/ui/Connections.test.tsx`: save URL and key, test reports the server version or the failing reason; plugin settings sections from the manifest render (port of `PluginSettingsSection`); `ChoosePalette` renders. Implement `widgets/connections`.
- [ ] T011 [P] [JR] [WEB] Tests first `widgets/reset/ui/Reset.test.tsx`: choose memory or personal state → preview counts in plain words → the Reset button stays disabled until "RESET" is typed → result shown; offline disables it; `full_dev` is not offered. Implement `widgets/reset`.

## Phase 5: Page, router, cuts [US1–US6]

- [ ] T012 [ENG] [WEB] Tests first `pages/governance/ui/GovernancePage.test.tsx`: desktop module order; phone order Attention → Spend → Connections → Data → Files → Reset; hint targets `data`, `connections`, `files`. Implement `GovernancePage`, `pages/governance/index.ts`.
- [ ] T013 [ENG] [WEB] Tests first `app/router/routes.test.tsx` and `shared/config/places.test.ts`: `/governance` → `GovernancePage`; `/governance/data` and `/data` → `/governance` (hint `data`); `/governance/settings` and `/settings` → `/governance` (hint `connections`); `/costs` → `/governance`; `/workspace` and `/doing/workspace` → `/governance` (hint `files`); `settingsDataPath()` points at the new hint. Update `routes.tsx` (delete `governanceLoaders`, remove the Doing `workspace` loader), `places.ts`, `pages/doing/ui/DoingInterim.tsx` (drop Workspace).
- [ ] T014 [ENG] [WEB] Delete `pages/{costs,data,settings,workspace}`, `widgets/{costs-overview,data-overview,settings-workspace,workspace-management}`, `entities/activity`, `pages/governance/ui/GovernanceInterim.tsx` (+ tests). `rtk proxy grep -rn "costs-overview\|data-overview\|settings-workspace\|workspace-management\|GovernanceInterim\|useActivityHeatmapQuery" apps/ze-web/src` returns only `/jarvis` hits if any.
- [ ] T015 [JR] [WEB] Delete `packages/ze-ui/src/charts/heatmap-chart.tsx`, `heatmap-data.ts`, `heatmap-data.test.ts` and their export in `charts/index.tsx`; `PieChart` stays. `make test-web`.
- [ ] T016 [JR] [WEB] If grep finds no other user (189 removed `GraphToolbar`): delete `shared/lib/optional-charts.ts`, `shared/ui/primitives/ChartsToggle.tsx` and their exports. Otherwise leave them and note it in the Handoffs note for the 189 floor.

## Phase 6: Budget readout (needs 185 on main) [US2]

- [ ] T017 [ENG] [WEB] Tests first in `widgets/attention/ui/Attention.test.tsx`: `Dots` show `used` of `max_per_day`; "next slot HH:MM" only when `next_slot_at`; held count; recent outcomes list from `listNotifications` with `delivery` held/suppressed/failed (key outside `["notifications"]`); a 503 from the budget route shows the module error line, never a number. Implement with 185's `useAttentionBudgetQuery`.

## Phase 7: Screen context (needs 195 on main)

- [ ] T018 [JR] [WEB] Tests first: `GovernancePage` publishes `place: "governance"` and `focused_module` via `useScreenPublisher`; no per-row refs. Implement.

## Phase 8: Acceptance and docs

- [ ] T019 [ENG] [WEB] Gates: `make test-web`, `make typecheck-web`, `make web-build`, `make lint`, `make test-py`. Impeccable critique of Governance ≥ 29/40 and ≥ the T001 baseline; detector 0; captures at 1440 and 390 with no console errors; SC-001 check (every chart labelled by its question). Record in the Handoffs note.
- [ ] T020 [DOCS] Update every doc in plan.md "Docs touched".
- [ ] T021 [DOCS] `AGENTS.md` phase row 190 and the workspace preference line; `specs/README.md` row 190 → Implemented; spec status.
- [ ] T022 [DOCS] Coverage check: `git diff main...HEAD --stat` against "Docs touched"; record in the Handoffs note.

---

## Dependencies

- T001 first. T002 → T003. T004 after T003 (codegen). T005 independent.
- T006 independent. T007 after T005. T008 after T004. T009, T010 independent. T011 after T004, T005.
- T012 after T006–T011. T013 after T012. T014 after T013. T015 after T014. T016 after T014.
- T017 after 185 on `main` and T009. T018 after 195 on `main` and T012.
- T019 after all landed code; T020–T022 last.

## Lanes

### Lane ENG (Claude Sonnet, lane lead)

T001–T003, T006, T009, T010, T012–T014, T017, T019. Owns `packages/ze-client/src/generated/*`, `app/router/*`, `shared/config/places.ts`.

### Lane JR (OpenCode junior)

T004, T005, T007, T008, T011, T015, T016, T018.

### Docs (Docs Steward)

T020–T022.
