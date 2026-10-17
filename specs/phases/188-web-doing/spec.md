# Feature Specification: Doing (W4)

**Feature Branch**: `188-web-doing`

**Created**: 2026-10-17

**Status**: Ready to implement on `main` with 183 and 184 (plan and tasks written 2026-10-17 against `main` b5fdc1c1); no dependency on 187. Linked reminders wait for 185 and screen-context publishing for 195 (split task phases).

**Input**: Maestro brief 2026-10-17, phase W4; overhaul plan sections a (Doing), b.3, e (Phase W4).

**Governed by**: `DESIGN.md`, `PRODUCT.md` principle 4 ("Unattended work is accountable"), phases 102–108 (workflows: branching, flowchart, failure policy, revisions), 23/91 (goal detail, traces), 114 (skills), 138–139 (procedures), 115/116/129/131 (workspace runs, live output), 181 (held writes).

**Depends on**: 183 (shell) and 184 (goal progress fields, `failure_summary`), both on `main`. Split tasks: linked reminders on the goal page need 185 (`listReminders`); screen context needs 195. Uses 194 (action ledger) when available.

**Doctrine functions served**: action (what runs unattended and what it did), executive function (goals and gates), governance (held writes, skill and procedure review).

---

## Clarifications

### Session 2026-10-17 (planning against the code, parallel build)

- **No dependency on 187.** Held writes use the existing `ConfirmationCard` (`features/respond-to-confirmation`, already used by the bell) with `useHeldWritesQuery`/`useDecideHeldWriteMutation`; 187 only places that card in Ask. Gates use the WS `action` frame through `features/answer-gate` (186's plan: Proceed/Stop/Redirect on the session thread, in flight until the goals refetch drops the gate, Redirect then opens the overlay). Whichever of 186 and 188 lands first creates `features/answer-gate`; the other reuses it.
- **Doing does not own procedures or the workspace file map** (189 and 190 own them; see their specs).
- **Runs are new in the web app.** `listWorkspaceRuns`, `watchWorkspaceRunEvents` and `cancelWorkspaceRun` exist but only the chat bubble streams a run today (`useWorkspaceRunEventsQuery`). The Runs module lists recent runs, streams the running one and cancels it; the busy state comes from `getWorkspace().busy` (runs start from chat, so Doing shows "busy", not a refusal).
- **One page with anchors.** `/doing` holds the index modules; `/doing/goals/:goalId` and `/doing/workflows/:workflowId` stay. `/doing/goals`, `/doing/workflows` and `/doing/skills` redirect to `/doing` with hints `goals`, `workflows`, `skills`; `goalsPath()` and `workflowsPath()` return those.
### Session 2026-10-18 (Gauge review D-1..D-10)

- **Planned goals are a needs-you item (D-1).** A goal in `planning` shows in Needs you (cream) with "Start" through REST `startGoal` (`useStartGoalMutation`). No gate path calls `startGoal`: gates use `goal:approve:<gate_id>` only (today's `GateStatusCard` "Approve & continue" calls the wrong route; it is deleted).
- **A stuck goal carries its next action (D-2).** The coral stuck row has Redirect, Pause and Abandon, sent as the existing WS `action` payloads `goal_stuck:redirect|pause|abandon:<goal_id>` (`goal_actions.py`) through the same sender as the gate actions in `features/answer-gate`. Redirect opens the overlay with the goal as subject, like the gate Redirect; Abandon asks once first. Whichever floor lands `features/answer-gate` second adds the variant it lacks.
- **188 merges after 189 and 190 (D-3).** Doing is the only floor whose deletions remove other floors' interim sections. Its router task keeps the Procedures and Workspace interim loaders while 189 or 190 is not on `main`, and deletes `DoingInterim` only when both have landed; the Maestro merges 188 last of the three.
- **Runs stay fresh (D-4).** While any listed run is `in_progress`, the runs list and workspace status refetch every 5 s; both are invalidated when a run's stream reaches `closed` (the backend sends no `refresh` frame for the workspace, so polling covers runs started from chat). `WorkspaceRunResponse.id` and `started_at` can be null (no Cancel and "not started" then). Cancel on a 409 (already finished) or 404 (unknown) refetches and shows a plain line, not an error toast.
- **Coral for unattended failures only (D-5, DESIGN.md "Failed unattended runs may be coral").** A workspace run is coral only when `origin == "unattended"` and its status is `failed` or `timed_out`; `cancelled` and `refused` are never coral, and conversation or user runs show their failure in plain words (they already appear in chat). Workflow executions carry no trigger field, and every workflow execution runs unattended, so a failed execution is coral whether it was scheduled or started with Run now.
- **SC-001 covers app text, not program output (D-6).** Statuses, origins, `error_summary` and `failure_summary` render in plain words. Command output (`output_preview`, the live stream) renders verbatim in a mono output box and may contain anything the program printed.
- **Nothing the old pages showed is lost silently (D-7).** The goal page keeps `retrospective_text` (phase 24) and `learnings_summary` and the status, type and time-horizon words. The Goals board orders active and planning goals first: stuck ones first, then those with an open gate, then the rest by last progress. Completed and abandoned goals collapse under "Finished (n)". The old search and filters are dropped: a single user has few goals and the board's order covers them. The workflow page keeps the live execution (`useLiveExecutionQuery`) and the "Chat about this run" button (`askAbout` with `workflow_id` and `execution_id`) until 195's chip replaces it.
- **One held-write card (D-8).** `HeldWriteCard` in `features/respond-to-confirmation` owns the held-write actions, disabled state and decide mutation; the bell, World (186) and Doing all use it. Whichever floor lands it first moves the bell onto it.
- **195 touches the two detail pages** (it publishes their subject and moves the workflow page's old `askAbout` context). If 195 lands first, the rebuilt pages keep its publisher calls; if 188 lands first, 195 rebases onto the new pages.

## Overview

Doing answers what runs without the user, what it did, and what it waits for, at `/doing`, `/doing/goals/:id`, `/doing/workflows/:id`. It replaces the interim Doing sections from 183 (Goals, Workflows, Skills). Procedures (candidates and library) move to Mind (189) and the workspace file map to Governance › Files (190), decided 2026-10-17 so the floors build in parallel.

## Modules

- **Index**: Needs you (planning goals to start, open gates and held writes, with `HeldWriteCard`); Goals (one row per goal from `listGoals` progress fields: done/total meter, next milestone, gate open since, age; stuck goals coral per the One Alarm Rule with Redirect, Pause, Abandon; finished goals collapsed); Workflows (schedule in words, next run, last result with `failure_summary`, failures coral, Run now); Runs (workspace runs with live output via `watchWorkspaceRunEvents`, "busy" shown when a run holds the workspace, cancel, unattended failures coral; "Workspace is off" error state when the sidecar is down, nothing else affected); Skills (review queue first, then on/off).
- **Goal detail**: gate module first (cream, the one action), milestone timeline as a field (x = time, marks by state), learnings with evidence and review (`reviewGoalLearning`), retrospective and learnings summary, traces as a readout list (no "Show tool calls" toggle), linked loops (`listLoops`, `goal_id`) and, after 185, their reminders.
- **Workflow detail**: flowchart kept (`widgets/workflow-graph`, `@xyflow/react`, restyled, nodes sized to fit), the live execution, executions with outputs and the human failure line, "Chat about this run" (until 195), revisions with diff summary and "View conversation", Run now / Cancel. The "Current definition" banner is deleted.

## User Scenarios & Testing *(mandatory)*

1. **A gate is answered from Doing (P1)** and the same gate disappears from World's Needs you (shared query invalidation).
2. **A workflow can be run and cancelled (P1)**; a failed execution row shows `failure_summary`, Run now, Open.
3. **A workflow with no executions says "Never run" (P1).**
4. **A live workspace run streams and can be cancelled (P2)**; while a run holds the workspace, Runs shows "busy" (runs start from chat, so Doing has no refusal to show).
5. **Skills can be reviewed (P2)** with their existing calls.
6. **Phone (P1)**: Needs you → Goals → Workflows → Runs → Skills; detail pages single column with the gate first.
7. **A planned goal can be started, and a stuck goal redirected, paused or abandoned, from Doing (P1).**

## Requirements *(mandatory)*

- **FR-001**: `pages/doing`, `pages/doing-goal`, `pages/doing-workflow`; widgets `doing-needs-you` (gates and held writes), `goals-board`, `workflows-board`, `runs`, `skills-queue`, `milestone-field`, `workflow-graph` (restyled, kept); `features/answer-gate` (shared with 186).
- **FR-002**: Goal row derivations from `listGoals` only (no per-row detail fetch); detail from `getGoalDetail` + `listGoalTraces`.
- **FR-003**: Gate actions use the `action` frame (`goal:approve:<gate_id>` and the existing stop/redirect payloads); held writes use `decideHeldWrite`.
- **FR-004**: Hard cuts: `pages/{goals,goal-detail,workflows,workflow-detail,skills}`, `widgets/{goals-overview,workflows-overview,gate-status,goal-learnings,milestone-timeline,workflow-executions,skill-management}` as they are (`pages/procedures` and `widgets/procedure-candidates` are deleted by 189; `pages/workspace` by 190), `pages/doing/ui/DoingInterim.tsx`, the "Current definition" banner, `shared/lib/format-cron.ts` if replaced by a schedule-in-words helper in the workflow slice (keep `cronstrue` usage in one place).
- **FR-004a**: Screen context (phase 195): the index publishes visible goals, workflows and runs; detail pages publish their subject (`goal`, `workflow`, `workflow_execution`); every module and row (goal, workflow, run, skill, gate, held write) wires "Chat about this" (callbacks passed down by props from widgets, 195 FR-024), with a test per kind.
- **FR-005**: Acceptance: critique ≥ 29/40 on index and both details; detector 0; captures at 1440 and 390.

## Success Criteria *(mandatory)*

- **SC-001**: No raw enum or traceback renders in app-generated text in Doing (statuses, origins, summaries); command output renders verbatim in a mono output box.
- **SC-002**: `make test-web`, `make typecheck-web`, `make web-build`, lint pass.

## Out of Scope

- "What Ze did unattended" ledger view (needs 194 gap 7; added to Runs when 194 lands).

## Owning packages

ze-web only; no backend, no migration. (The goal screen note this phase carried moved to phase 195, which resolves every kind.)
