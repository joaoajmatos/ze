# Implementation Plan: Doing (W4)

**Branch**: `188-web-doing` | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md (Clarifications 2026-10-17 and 2026-10-18 are binding; revised 2026-10-18 after Gauge's review D-1..D-10), `main` at b5fdc1c1 (183 and 184 landed). Planned to build now, in parallel with 186, 189 and 190, with no dependency on 187. Linked reminders (185) and screen context (195) are the last two task phases.

## Summary

Doing becomes one index page at `/doing` and two detail pages, answering what runs without the user, what it did, and what it waits for. The index holds five modules: Needs you (planning goals, gates and held writes), Goals, Workflows, Runs and Skills. All of them read existing endpoints: 184's goal progress fields and `failure_summary`, the workspace runs API (new to the web app), and skills. Gates, stuck-goal actions and held writes reuse pieces that exist or that 186 also plans (`features/answer-gate`, a shared `HeldWriteCard`), so nothing waits for 187. Doing merges after 189 and 190, because it deletes the Doing interim that still holds their sections. The old Goals, Workflows and Skills pages, their widgets and the "Current definition" banner are deleted.

## Technical Context

**Language/Version**: TypeScript 5, React 19, TanStack Query 5, `@xyflow/react` + dagre (kept).
**Primary Dependencies**: none new.
**Storage**: none.
**Testing**: vitest + Testing Library with a mocked `@myguyze/ze-client`; the run event stream is mocked at `useWorkspaceRunEventsQuery`.
**Constraints**: FSD; DESIGN.md tokens and One Alarm Rule (coral only for stuck goals, failed workflow executions, and unattended workspace runs that `failed` or `timed_out`); no raw enum or traceback in app text, command output verbatim in a mono box (SC-001); 44 px targets by class, measured in captures.
**Scale**: single user; at most 10 workflows get their latest executions (as 186).

## Constitution Check

| Principle | Check |
|---|---|
| Spec first | spec.md + Clarifications; plan and tasks here. |
| Honest claims | Workflow results from executions, never invented; "Never run" when there are none; failures show `failure_summary`, never `error`; runs show `output_preview` and the live stream, never a guessed status. |
| Package boundaries | ze-web only; no backend. |
| Pre-v1 hard cuts | Old Doing pages, widgets, the banner and the Doing interim go in this phase. |
| Tests | Fail-first per task. |
| Docs are part of done | [DOCS] tasks cover "Docs touched". |

## Blast radius

`graphify affected` on `main` b5fdc1c1 plus `rtk proxy grep`:

| Symbol | Callers | Change |
|---|---|---|
| `GoalsOverview` | `pages/goals` | Deleted; `widgets/goals-board`. |
| `WorkflowsOverview` | `pages/workflows` | Deleted; `widgets/workflows-board`. |
| `SkillManagementList` | `pages/skills` | Deleted; `widgets/skills-queue`. |
| `GoalCard` ("Start goal" via `startGoal` for `planning`) | `GoalsOverview` | Deleted with it; planning goals move to Needs you with `useStartGoalMutation`. |
| `GateStatusCard` ("Approve & continue" calls `startGoal`, the wrong route), `GoalLearningsList`, `MilestoneTimeline` (+ `ExecutionTraceLog`, `TraceRow`, `MilestoneRow`) | `pages/goal-detail` | Deleted; `widgets/milestone-field`, learnings and traces rebuilt inside `pages/doing-goal`. |
| `WorkflowExecutionsList` | `pages/workflow-detail` | Deleted; executions rebuilt in `pages/doing-workflow` with `failure_summary`. |
| `WorkflowGraph`, `StepNode`, `StepDetailPanel`, `WorkflowGraphToolbar`, `lib/layout.ts` | `pages/workflow-detail` | Kept, restyled (tokens, nodes sized to their label). |
| `WorkflowDefinitionNotice` | `pages/workflow-detail`, `widgets/workflow-graph/index.ts` | Deleted (the banner). |
| `GoalDetailPage`, `WorkflowDetailPage` | `routes.tsx` (`doing/goals/:goalId`, `doing/workflows/:workflowId`) | Replaced by `pages/doing-goal`, `pages/doing-workflow`. 195 edits these two pages; if 195 landed first, keep its publisher calls in the rebuilt pages. |
| `formatCronExpression` (`shared/lib/format-cron.ts`) | `entities/workflow/lib/format.ts` only | Moves into `entities/workflow/lib/schedule.ts` (the one `cronstrue` call); `shared/lib/format-cron.ts` deleted. |
| `goalsPath()`, `workflowsPath()` | `GoalDetailPage`, `WorkflowDetailPage`, `notification-format.ts` (186 moves it to `shared/lib/notification-href.ts`) | Return `/doing#goals`, `/doing#workflows`. |
| `DoingInterim`, `doingLoaders` | `routes.tsx`, its test | Deleted only once 189 and 190 are on `main`; until then their two loaders stay. 188 merges last of the three. |
| `useWorkspaceRunEventsQuery` (returns `lines`, `status`, `exitCode`, `looksBinary`) | chat `MessageBubble` (187 moves it) | Reused by Runs; its `closed` status invalidates the runs and workspace queries. |
| `HELD_ACTIONS`, `answerHeldWrite` | `widgets/app-shell/ui/NotificationBell.tsx` | Move into `HeldWriteCard` (`features/respond-to-confirmation`); the bell, World (186) and Doing use it. Created by whichever floor lands first. |
| `ChatAboutRunButton`, `useLiveExecutionQuery` | `pages/workflow-detail` | Kept in `pages/doing-workflow` (the button until 195 replaces it). |
| `features/answer-gate` (186 plan) | World Needs you | Created by whichever of 186 and 188 lands first. |
| `entities/workflow/api/useLatestExecutionsQuery.ts` (186 plan) | World Doing now | Created by whichever of 186 and 188 lands first. |

Parallel touch points: with 186, `features/answer-gate`, `useLatestExecutionsQuery`, `shared/config/places.ts`, `routes.tsx`, `query-keys.ts`; with 189 and 190, `DoingInterim`/`doingLoaders` and the redirect table; with 195, the two detail pages. Each edits only its own lines; the second to land rebases.

## Design

### Entities and features

- `entities/workspace`: `useWorkspaceRunsQuery({ limit: 20 })` (`listWorkspaceRuns`; `refetchInterval` 5 s while any run is `in_progress`, off otherwise), the same interval on `useWorkspaceQuery`; `useCancelWorkspaceRunMutation` (`cancelWorkspaceRun`; 409 and 404 refetch and return a plain outcome, not an error); `lib/run-status.ts` (status and origin words; `isAlarm(run)` true only for `origin == "unattended"` with `failed` or `timed_out`). `queryKeys.workspaceRuns` exists; no backend `refresh` frame covers the workspace, so polling covers runs started from chat.
- `entities/workflow`: `lib/schedule.ts` (cron → words, moved from `shared/lib/format-cron.ts`); `useLatestExecutionsQuery` (186 plan; create if absent); `lib/result.ts` (pure): last result from the latest execution: ok / failed with `failure_summary` / running / never run.
- `entities/goal`: `lib/progress.ts` extended: goal row derivations from `GoalListItem` (184) only: done/total, next milestone, gate open since, stuck since, age (from `created_at`); status words; `boardOrder` (active, `awaiting_gate` and planning first: stuck, then gate open, then by `last_progress_at`; then paused, with Resume opening the overlay; completed and abandoned in a "Finished" group).
- `features/answer-gate`: one goal-action sender. Gate actions `goal:approve|stop|redirect:<gate_id>` and stuck actions `goal_stuck:redirect|pause|abandon:<goal_id>`; Abandon asks once first; Redirect (both kinds) opens the overlay with the goal as subject. Otherwise per 186 plan (Proceed/Stop/Redirect via `action` frames on the session thread; Proceed/Stop in flight until the goals refetch drops the gate or an error frame within 15 s; Redirect in flight until the first message or error frame, then the overlay opens on that thread with the gate as subject).
- Held writes: `HeldWriteCard` in `features/respond-to-confirmation` wraps `ConfirmationCard` with the held actions, disabled state and `useDecideHeldWriteMutation`; lists come from `useHeldWritesQuery` (`entities/confirmation`).

### Widgets (props only)

- `widgets/doing-needs-you`: planning-goal rows with Start (`useStartGoalMutation`), gate rows (from goals with `gate_id`) with Proceed / Stop / Redirect, and held-write rows rendered with `HeldWriteCard`. Cream, never coral.
- `widgets/goals-board`: one row per goal: `Meter` done/total, next milestone, "gate open since …", age; stuck goals coral with "stuck since …" and Redirect / Pause / Abandon; rows in `boardOrder`, finished goals under "Finished (n)" collapsed; row opens `/doing/goals/:id`.
- `widgets/workflows-board`: schedule in words, next run, last result (`lib/result.ts`; failures coral with `failure_summary`; every execution runs unattended), Run now (`useTriggerWorkflowMutation`), Open.
- `widgets/runs`: recent runs (command summary, origin in words, status in words, started or "not started", exit); `error_summary` in plain words; output (`output_preview` or the live `lines`) verbatim in a mono box; the running one streams with `useWorkspaceRunEventsQuery` and has Cancel (none when `id` is null); coral only when `isAlarm`; "busy" from `useWorkspaceQuery().busy`; "Workspace is off" when `available` is false (Runs only).
- `widgets/skills-queue`: pending review first (approve, reject), then installed skills with on/off and remove (`useSkillTransitionMutation`), import (`useSkillImportMutation`).
- `widgets/milestone-field`: milestones on a time axis (x = created/completed time, marks by status: done filled, active ring, pending hollow), with a phone list fallback.
- `widgets/workflow-graph`: restyle only; `WorkflowDefinitionNotice` deleted.

### Pages

- `pages/doing`: `DoingPage`, desktop: Needs you and Goals left, Workflows and Runs centre, Skills right; phone: Needs you → Goals → Workflows → Runs → Skills; hint ids `goals`, `workflows`, `skills`, `runs`.
- `pages/doing-goal`: gate module first (when a gate is open), status, type and time-horizon words, `milestone-field`, `retrospective_text` and `learnings_summary` when present, learnings with evidence and review (`features/review-goal-learning`), traces as a readout list (no "Show tool calls" toggle), linked loops (`useLoopsQuery`, filter `goal_id`); after 185: each linked loop's reminder (`useRemindersQuery` joined by `reminder_id`).
- `pages/doing-workflow`: flowchart, the live execution (`useLiveExecutionQuery`), "Chat about this run" (`askAbout` with `workflow_id`, `execution_id`; until 195 T020 replaces it), executions with outputs and `failure_summary`, revisions with diff summary and "View conversation" (`askPath(thread)`), Run now / Cancel (`useCancelExecutionMutation`).
- Router: `doing` → `DoingPage`; `doing/goals/:goalId` → `DoingGoalPage`; `doing/workflows/:workflowId` → `DoingWorkflowPage`; `/doing/goals`, `/doing/workflows`, `/doing/skills` → `/doing` with hints (190's `hint` field: if 190 has not landed, 188 adds it as planned in 190 T005); `/goals`, `/workflows`, `/skills` old redirects point straight to the hinted `/doing` (one hop).

### Split phases

- **After 185**: linked loops' reminders on the goal page.
- **After 195**: the index publishes `visible` goals, workflows and runs and the focused module; detail pages publish `subject` (`goal`, `workflow`, `workflow_execution` with `parent_id`); `ChatAboutChip` on goal, workflow, run (`workspace_run`), skill, gate (`goal_gate` with `parent_id`) and held-write rows; `Module.onChatAbout` by props.

## Project Structure

### Documentation (this feature)

```
specs/phases/188-web-doing/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code

```
apps/ze-web/src/pages/{doing,doing-goal,doing-workflow}/
apps/ze-web/src/widgets/{doing-needs-you,goals-board,workflows-board,runs,skills-queue,milestone-field,workflow-graph}/
apps/ze-web/src/features/answer-gate/ ; entities/{workspace,workflow,goal}/
apps/ze-web/src/app/router/routes.tsx ; shared/config/places.ts ; shared/lib/format-cron.ts (deleted)
```

## Docs touched ([DOCS] tasks)

- `docs/frontend.md`: Doing place, widgets, deleted Goals/Workflows/Skills pages, redirects.
- `docs/goals.md`: goal page (gate first, milestone field, learnings, traces, linked loops).
- `docs/workflows.md`: workflow page (flowchart, executions with failure line, revisions); banner removed.
- `docs/skills.md`: skills review in Doing.
- `docs/workspace.md`: runs in Doing › Runs (stream and cancel); files in Governance.
- `docs/features.md`: Doing.
- `AGENTS.md`: phase row 188; the places fact; `specs/README.md` row 188.

## Complexity Tracking

None.
