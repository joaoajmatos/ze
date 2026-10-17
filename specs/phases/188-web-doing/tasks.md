# Tasks: Doing (W4)

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), DESIGN.md.

**Build gate**: starts now on `main` (183 and 184 landed), in parallel with 186, 189 and 190. It has no dependency on 187. **Merge order**: 188 merges after 189 and 190, because T017 deletes the Doing interim that holds their Procedures and Workspace sections until they land (spec Clarification D-3). Phase 6 waits for 185 on `main`; Phase 7 waits for 195 on `main`. If either has not landed when the rest is done, the floor goes to review without it and the split phase lands as a follow-up commit. The Spec Architect (Lintel) stays on call.

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Vitest + Testing Library with a mocked `@myguyze/ze-client`; the run event stream is mocked at `useWorkspaceRunEventsQuery`.

**Lanes**: `[ENG]` Claude Sonnet lane lead (entities, gate feature, needs-you, boards, runs, pages, router, gates). `[JR]` OpenCode junior (exact files given). Floor Reviewer reviews per user story. `[DOCS]` Docs Steward.

**Tags**: `[WEB]` ze-web · `[DOCS]` docs and specs. No backend, no migration.

**Rules for the implementer**
- FSD: `pages → widgets → features → entities → shared`; widgets get callbacks by props and never import another widget.
- One Alarm Rule: coral only for stuck goals, failed workflow executions, and unattended workspace runs that `failed` or `timed_out`. Planning goals, gates and held writes are cream; `cancelled` and `refused` runs are never coral.
- SC-001: no raw enum, status code or traceback in app text (statuses, origins, `error_summary`, `failure_summary`). Command output renders verbatim in a mono output box. Workflow failures show `failure_summary`, never `error`.
- Shared with other floors: `app/router/routes.tsx`, `app/router/RedirectTo.tsx`, `shared/config/places.ts` (+ tests), `shared/lib/query-keys.ts` (186, 189, 190); `features/answer-gate`, `HeldWriteCard` in `features/respond-to-confirmation`, and `entities/workflow/api/useLatestExecutionsQuery.ts` (186: whichever floor lands first creates them, the other reuses them and adds only what it lacks); `pages/doing-goal` and `pages/doing-workflow` (195: if 195 landed first, keep its publisher calls). Edit only Doing's lines.
- 44 px targets: assert the min-size class in tests (jsdom has no layout); check sizes in the T021 captures.
- Before changing a shared export, run `graphify affected "<Symbol>" --depth 2` and `rtk proxy grep`; update every caller in the same change.
- Shared worktree: `git add <paths>`; `git commit -m ... -- <paths>`; never `git add -A` or `git stash`. Commit only when the ENG lead or Maestro asks; split commits by user story.

---

## Phase 0: Gate [ENG]

- [ ] T001 [ENG] [WEB] Branch from current `main`. `make web-install`; `graphify update .`; `graphify affected` on `GoalsOverview`, `WorkflowsOverview`, `SkillManagementList`, `GateStatusCard`, `GoalLearningsList`, `MilestoneTimeline`, `WorkflowExecutionsList`, `WorkflowDefinitionNotice`, `GoalDetailPage`, `WorkflowDetailPage`, `formatCronExpression`, `goalsPath`, `workflowsPath`, `useWorkspaceRunEventsQuery`, `GoalCard`; grep `DoingInterim`, `doingLoaders`, `answer-gate`, `useLatestExecutionsQuery`, `hintMap`, `format-cron`, `HeldWriteCard`, `HELD_ACTIONS`, `startGoal`. Record in the Handoffs note: (a) differences from plan.md "Blast radius"; (b) which of 185, 186, 189, 190 and 195 are on `main`, and so whether `features/answer-gate` (and which actions it sends), `HeldWriteCard`, `useLatestExecutionsQuery` and the redirect `hint` field exist; (c) whether 189 and 190 already removed their `DoingInterim` sections; (d) the impeccable baseline critique of the interim Doing. Stop and report differences to the Spec Architect.

## Phase 1: Entities and the gate feature [US1–US4]

- [ ] T002 [P] [JR] [WEB] Tests first `entities/workflow/lib/schedule.test.ts` and `entities/workflow/lib/result.test.ts`. Schedule: the cases from `shared/lib/format-cron` tests move here; an invalid cron returns the raw expression in mono, never throws. Result (pure): from the latest execution, return `ok`, `failed` (with `failure_summary`; a null summary gives "Failed" with no `error` text), `running` or `never` (no executions). Implement `lib/schedule.ts` (the one `cronstrue` call) and `lib/result.ts`; point `entities/workflow/lib/format.ts` at `schedule.ts`; delete `shared/lib/format-cron.ts` (+ test).
- [ ] T003 [P] [JR] [WEB] Tests first `entities/goal/lib/progress.test.ts` (extend): from one `GoalListItem` (184 fields only, no detail fetch), derive done/total, next milestone title, "gate open since" (from `gate_open_since`), "stuck since" (from `stuck_since`), age (from `created_at`), and a status word for every status (no raw enum); `boardOrder` covers all six `GoalStatus` values: active, `awaiting_gate` and planning goals first (stuck, then gate open, which includes `awaiting_gate`, then by `last_progress_at` descending), then `paused` goals, then completed and abandoned goals as a separate "finished" group. Implement in `lib/progress.ts`.
- [ ] T004 [ENG] [WEB] Tests first `entities/workspace/api/useWorkspaceRunsQuery.test.tsx` and `entities/workspace/lib/run-status.test.ts`: `useWorkspaceRunsQuery({ limit: 20 })` calls `listWorkspaceRuns` under the existing `queryKeys.workspaceRuns()` and refetches every 5 s while any run is `in_progress`, not otherwise (fake timers); `useWorkspaceQuery` takes the same interval from the runs data; `useCancelWorkspaceRunMutation` calls `cancelWorkspaceRun` and invalidates the runs and workspace keys, and on a 409 or 404 refetches and resolves with a plain outcome ("already finished", "no longer exists") instead of throwing; the status map gives words for every status (`succeeded`, `failed`, `timed_out`, `cancelled`, `refused`, `in_progress`) and origin (unknown → humanised); `isAlarm` is true only for `origin == "unattended"` with `failed` or `timed_out`. Implement and export from `entities/workspace/index.ts`.
- [ ] T005 [ENG] [WEB] If `entities/workflow/api/useLatestExecutionsQuery.ts` is absent (186 not on `main`): tests first, then implement it as 186's plan states (latest execution for at most 10 workflows, one `listWorkflowExecutions({ limit: 1 })` each). If present, reuse it unchanged.
- [ ] T006 [ENG] [WEB] `features/answer-gate`, one goal-action sender. If absent: tests first `features/answer-gate/model/useAnswerGate.test.ts`, then implement it as 186's plan states: Proceed and Stop send `goal:approve|stop:<gate_id>` as an `action` frame on the goal's session thread and stay in flight until the goals refetch drops the gate or an error frame arrives, with a 15 s timeout line; Redirect stays in flight until the first message or error frame, then opens the overlay on that thread with the gate as subject. The goals and World queries invalidate on success. Whether or not it existed, add (tests first) the stuck variant: `goal_stuck:redirect|pause|abandon:<goal_id>`; Pause and Abandon stay in flight until the goals refetch shows the new status or an error frame arrives (15 s timeout line); the test asserts the signal is the backend's `{"type":"refresh","screen":"goals"}` frame through `invalidate-on-ws-refresh`; Abandon asks once first; Redirect opens the overlay with the goal as subject. A test asserts no path in the feature calls `startGoal`.

## Phase 2: Needs you, Goals, Workflows [US1, US2, US3]

- [ ] T007a [ENG] [WEB] If `HeldWriteCard` is absent: tests first `features/respond-to-confirmation/ui/HeldWriteCard.test.tsx` (approve, deny, edits call `useDecideHeldWriteMutation` with the request id; disabled while that request is pending; highlighted prop passes through), then implement it from the bell's `HELD_ACTIONS` and `answerHeldWrite` and move `NotificationBell` onto it (its tests stay green). If present, reuse it.
- [ ] T007 [ENG] [WEB] Tests first `widgets/doing-needs-you/ui/DoingNeedsYou.test.tsx`: planning-goal rows (title, "plan ready") with Start calling `useStartGoalMutation`; gate rows from goals with `gate_id` (goal title, gate title, open since) with Proceed / Stop / Redirect through props wired to `features/answer-gate`; held-write rows render `HeldWriteCard` from `useHeldWritesQuery`; cream only (no coral class); empty → "Nothing needs you". Implement. Answering a gate or starting a goal invalidates the key World's Needs you reads (US1).
- [ ] T008 [ENG] [WEB] Tests first `widgets/goals-board/ui/GoalsBoard.test.tsx`: rows in `boardOrder` with `Meter` done/total, next milestone, "gate open since …", age; a stuck goal is coral with "stuck since …" and Redirect / Pause / Abandon passed by props to the T006 sender, and no other row is coral; a paused goal sits after the active ones with the word "Paused" and a Resume that opens the overlay with the goal as subject (same path as Redirect; the backend has no resume action and `startGoal` accepts only planning); completed and abandoned goals sit under a collapsed "Finished (n)"; the row opens `/doing/goals/:id` (`goalPath`); no raw status. Implement with T003.
- [ ] T009 [ENG] [WEB] Tests first `widgets/workflows-board/ui/WorkflowsBoard.test.tsx`: schedule in words, next run, last result from `lib/result.ts` (failed → coral with `failure_summary`; no executions → "Never run"; running → "Running"); Run now calls `useTriggerWorkflowMutation` and shows in flight; Open goes to `/doing/workflows/:id`. Implement with T002, T005.

## Phase 3: Runs and Skills [US4, US5]

- [ ] T010 [ENG] [WEB] Tests first `widgets/runs/ui/Runs.test.tsx`: recent runs (command summary, origin and status in words, started or "not started" when `started_at` is null, exit code only when finished); `error_summary` in plain words; output (`output_preview`, or the live `lines` from `useWorkspaceRunEventsQuery`, mocked, returning `lines`, `status`, `exitCode`, `looksBinary`) verbatim in a mono output box, "binary output" when `looksBinary`; the running row has Cancel (`useCancelWorkspaceRunMutation`), none when `id` is null, and a 409/404 outcome shows as a plain line; when the stream reaches `closed` the runs and workspace queries are invalidated; `useWorkspaceQuery().busy` shows "busy · one run at a time"; `available: false` → "Workspace is off" in Runs only, the other modules render; coral only for an unattended `failed` or `timed_out` run (a failed conversation run and a cancelled unattended run are not coral). Implement with T004.
- [ ] T011 [P] [JR] [WEB] Tests first `widgets/skills-queue/ui/SkillsQueue.test.tsx`: pending-review skills first with approve and reject; then installed skills with on/off and remove (`useSkillTransitionMutation`); import by URL (`useSkillImportMutation`) with the error line on failure; executable approval stays a separate step as today. Implement.

## Phase 4: Detail pages [US1, US2, US6]

- [ ] T012 [P] [JR] [WEB] Tests first `widgets/milestone-field/ui/MilestoneField.test.tsx`: marks placed by time (completed time for done, created time otherwise), done filled, active ring, pending hollow; an `aria-label` per mark with title and state words; phone (`useMediaQuery` mocked) renders an ordered list. Implement as SVG with `ze.css` tokens.
- [ ] T013 [ENG] [WEB] Restyle `widgets/workflow-graph` with tokens and nodes sized to their label; delete `WorkflowDefinitionNotice` and its export. Keep the graph tests green; add one asserting no banner renders.
- [ ] T014 [ENG] [WEB] Tests first `pages/doing-goal/ui/DoingGoalPage.test.tsx`: an open gate renders first with the T006 actions (no `startGoal` call); a planning goal shows Start; status, type and time-horizon in words; then `MilestoneField`; `retrospective_text` and `learnings_summary` when present; learnings with evidence and review (`features/review-goal-learning`); traces as a readout list with no "Show tool calls" toggle; linked loops from `useLoopsQuery()` filtered client-side by `goal_id` (the hook takes only a state; the test is named "loads all loops and filters by goal (single user, no per-goal route)"); not found → the place's empty line. Implement from `useGoalDetailQuery` + `useGoalTracesQuery`.
- [ ] T015 [ENG] [WEB] Tests first `pages/doing-workflow/ui/DoingWorkflowPage.test.tsx` (port the cases of `WorkflowDetailPage.test.tsx` that still apply): flowchart; the live execution from `useLiveExecutionQuery`; "Chat about this run" calls `askAbout` with `workflow_id` and `execution_id` (kept until 195 T020 replaces it); executions with outputs and `failure_summary` (never `error`); revisions with diff summary and "View conversation" (`askPath(thread)`); Run now and Cancel (`useCancelExecutionMutation`) on a running execution. Implement.

## Phase 5: Index page, router, cuts [US1–US6]

- [ ] T016 [ENG] [WEB] Tests first `pages/doing/ui/DoingPage.test.tsx`: desktop columns (Needs you and Goals left, Workflows and Runs centre, Skills right); phone order Needs you → Goals → Workflows → Runs → Skills; hint targets `goals`, `workflows`, `runs`, `skills`. Implement `DoingPage`, `pages/doing/index.ts`.
- [ ] T017 [ENG] [WEB] Tests first `app/router/routes.test.tsx` and `shared/config/places.test.ts`: `/doing` → `DoingPage`; `/doing/goals/:goalId` → `DoingGoalPage`; `/doing/workflows/:workflowId` → `DoingWorkflowPage`; `/doing/goals`, `/doing/workflows`, `/doing/skills` → `/doing` with hints `goals`, `workflows`, `skills`; the old `/goals`, `/workflows`, `/skills` (and their detail paths) redirect in one hop; `goalsPath()` → `/doing#goals`, `workflowsPath()` → `/doing#workflows`. Use 190's `hint` field; if 190 has not landed, add `hint` exactly as 190 T005 states (the second floor rebases). If 189 and 190 are both on `main`, delete `doingLoaders` and `pages/doing/ui/DoingInterim.tsx` (+ tests). Otherwise keep `DoingInterim` with only the sections of the floor(s) not yet landed (Procedures, Workspace), drop Goals, Workflows and Skills from it, and record in the Handoffs note that the deletion is pending; the floor does not go to review until both have landed and the file is deleted (merge order above).
- [ ] T018 [ENG] [WEB] Delete `pages/{goals,goal-detail,workflows,workflow-detail,skills}`, `widgets/{goals-overview,workflows-overview,gate-status,goal-learnings,milestone-timeline,workflow-executions,skill-management}`, and `entities/goal/ui/GoalCard` (+ test, export; its only caller is `GoalsOverview`). `rtk proxy grep -rn "goals-overview\|workflows-overview\|gate-status\|goal-learnings\|milestone-timeline\|workflow-executions\|skill-management\|GoalCard\|GoalDetailPage\|WorkflowDetailPage\|format-cron" apps/ze-web/src` returns only `/jarvis` hits if any.

## Phase 6: Linked reminders (needs 185 on main) [US1]

- [ ] T019 [ENG] [WEB] Tests first in `pages/doing-goal/ui/DoingGoalPage.test.tsx`: each linked loop with a `reminder_id` shows its reminder (due time and status word: upcoming, overdue, fired) from 185's `useRemindersQuery`, joined by `reminder_id`; a missing reminder shows nothing. Implement.

## Phase 7: Screen context (needs 195 on main) [FR-004a]

- [ ] T020 [ENG] [WEB] Tests first, one per kind: `DoingPage` publishes `place: "doing"`, visible goals, workflows and runs, and the focused module via `useScreenPublisher`; `DoingGoalPage` publishes subject `goal`; `DoingWorkflowPage` publishes subject `workflow` and the selected execution as `workflow_execution` with `parent_id`; `ChatAboutChip` on goal, workflow, run (`workspace_run`), skill, gate (`goal_gate` with `parent_id`) and held-write rows, passed to widgets by props (195 FR-024); `Module.onChatAbout` by props. Implement.

## Phase 8: Acceptance and docs

- [ ] T021 [ENG] [WEB] Gates: `make test-web`, `make typecheck-web`, `make web-build`, `make lint`. Impeccable critique ≥ 29/40 on the index and both detail pages and ≥ the T001 baseline; detector 0; captures at 1440 and 390 with no console errors and 44 px targets; SC-001 check (no raw enum or traceback). Record in the Handoffs note.
- [ ] T022 [DOCS] Update every doc in plan.md "Docs touched".
- [ ] T023 [DOCS] `AGENTS.md` phase row 188 and the places fact; `specs/README.md` row 188 → Implemented; spec status.
- [ ] T024 [DOCS] Coverage check: `git diff main...HEAD --stat` against "Docs touched"; record in the Handoffs note.

---

## Dependencies

- T001 first. T002, T003, T004, T005, T006 independent.
- T007a independent. T007 after T006, T007a. T008 after T003. T009 after T002, T005. T010 after T004. T011 independent.
- T012 independent. T013 independent. T014 after T006, T012. T015 after T013.
- T016 after T007–T011. T017 after T014–T016. T018 after T017.
- T019 after 185 on `main` and T014. T020 after 195 on `main`, T016 and T018.
- T021 after all landed code; T022–T024 last.

## Lanes

### Lane ENG (Claude Sonnet, lane lead)

T001, T004–T010 (incl. T007a), T013–T017, T018, T019, T020, T021. Owns `app/router/*`, `shared/config/places.ts`, `shared/lib/query-keys.ts`.

### Lane JR (OpenCode junior)

T002, T003, T011, T012.

### Docs (Docs Steward)

T022–T024.
