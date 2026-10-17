# ze-web screen inventory + critique (Phase A, steps 2-3)

Captures: `apps/ze-web/.impeccable/work/shots/current/*.png` (1440x900, dark, DB ze_e2e_web + enrich.sql, news off, workspace sidecar down).
Functions: PER perception · MEM memory · EXE executive · SOC social cognition · REF reflection · ACT action · GOV governance.

## Routes

| Route | Widgets → data | Function | Job it should do | What it lacks / critique |
|---|---|---|---|---|
| `/` Chat (index) | chat-workspace → sessions, messages, trace, feedback, retry, confirm, onboarding | PER/ACT; GOV via confirm card; REF via trace | Talk; approve what Ze is waiting on | Landing = empty chat with starfield + "Your personal AI assistant": the world-state is invisible on arrival. Confirm card says "From workflow:" with an empty name. Trace panel empty-state takes 1/4 of the screen. |
| `/goals` | goals-overview → listGoals | EXE | Which goals move, which wait on me | Rows show only title + status pill. No progress, next milestone, gate due, age. "Awaiting gate" is a grey pill, not a call to act. ALL-CAPS outline button. |
| `/goals/:id` | milestone-timeline, goal-learnings, gate-status → getGoalDetail, listGoalTraces | EXE/REF/GOV | Where the goal is, what Ze learned, what needs my OK | Raw token `awaiting_gate`. Learnings squeezed into a 280px column with three caps buttons each. Gate (the one action) sits at the bottom right. Traces hidden behind "Show tool calls". No linked loops/reminders. |
| `/priority` | priority-snapshot → getPrioritySnapshot | EXE (arbitration) | Why this order; reorder | Bare numbered list of titles + kind chip. No reason, confidence, due, source; no visible drag affordance. Failure shows as orange sentence ("Couldn't load: Hypothesis") — hypotheses failed on this DB. Duplicates loops+goals with less info. |
| `/loops` | loop-review → listLoops, confirm/close/drop | EXE (active concerns) | Confirm suspicions; see what drifts | Best screen today (Needs your OK vs Tracking). But "Drifting" is green (wrong semantic: drift is the alarm). No drift deadline, rationale, age, evidence. Raw provenance tokens (`user_declared`). Confidence is text only. CAPS buttons ×2 per row. |
| `/workflows` | workflows-overview → listWorkflows | ACT/EXE | What runs unattended, did it work | Schedule + next run + status, but no last result, failure, or run history. Card-per-row, equal weight. |
| `/workflows/:id` | workflow-graph, workflow-executions → getWorkflow, executions, revisions | ACT/REF | What it does, what happened each run | Flowchart nodes oversized and overflow the card. Run history = "Completed 120.0s" ×N, no outputs. "Current definition" info banner is noise. |
| `/skills` | skill-management → listSkills, import | ACT/GOV | Review/approve skills | Import field flush against the top bar with no page padding (layout bug). Empty state only. |
| `/brain-memory` | memory-feed, timeline-scrubber, procedure-candidates → getMemoryFeed, timeline-bounds | MEM | What Ze believes about me, how sure, since when | Raw fact keys leak (`exercise_habit:`). Confidence pill, no kind/decay. Timeline bar chart is decoration (counts per day, no question). Episodes and facts look the same. |
| `/brain-graph` | memory-graph → getMemoryGraph, getEntityDetail, memory activity | MEM/SOC | Who/what is connected to what | Hairball in the middle third of an empty canvas; labels unreadable at default zoom. Answers no question. |
| `/procedures` | procedure-management → listProcedureLibrary | MEM (procedural)/REF | What Ze learned how to do | Empty state on seeded data. |
| `/costs` Usage | costs-overview → getCostSummary, anomalies, activity heatmap | GOV | Am I spending normally | Plugin pie overflows the viewport (layout bug) and has 2 slices. `$3.158` (3 decimals). Spend heatmap grey-on-grey; agent heatmap 12 months mostly empty. |
| `/data` | data-overview → listDataDomains | GOV | What Ze stores; export/delete | 20-slice pie unreadable. Mono raw table names. "IMPORTABLE" badge on every row = noise. |
| `/workspace` | workspace-management → getWorkspace, files | ACT | Ze's computer: files, runs | Sidecar down → only an error. Status text unpadded at top-left (layout bug). Runs not shown at all. |
| `/settings` | settings-workspace → connection, quiet hours, export/import/delete | GOV | Configure | Quiet hours + daily budget ("at most 5 nudges a day") buried in a form; budget remaining today not shown. CAPS full-width buttons. |
| plugin Contacts | plugin-screen (server-driven) → getContactsPage | SOC | Who matters, who's gone quiet | Top bar title "3 people" (count as title). No last contact, projects, stale follow-ups (phase 128 data exists in graph). |
| plugin Reminders | plugin-screen → getRemindersPage | EXE (commitments) | What's coming | Title "Upcoming"; dd/mm/yy 00:02; no link to loops. |
| plugin News | (disabled in this run) | PER | — | not captured |

Shell: left nav with 4 collapsible groups (Automation / Knowledge / System / Plugins) — groups by organ, not function; floating purple "Ze" launcher overlaps content bottom-right on every page; bell with held writes + notifications; trace + history in chat only.

## Backend data no screen shows
- Exposed but unused by ze-web: `listActiveProcedures`, workspace runs (`listWorkspaceRuns`, `watchWorkspaceRunEvents`, `getWorkspaceFile`), priority override/unpin (no visible control), goal traces only behind a toggle.
- Shown poorly: loop drift_deadline / drift_rationale / sources, priority reasons, held writes (only in bell), quiet hours + budget, memory activity.
- NOT exposed over REST (backend ask if a screen needs them): correlation hypotheses as a list (only inside priority snapshot), action-record ledger ("what Ze did unattended"), contribution collisions, routing log, push log / proactive job runs, interruption budget remaining today.

## Global critique (impeccable critique + audit + emil)
1. Generic AI-dark: purple accent on near-black, Space Grotesk headings (impeccable detect: overused font), Inter body, purple glow pills. Nothing is Ze's own.
2. No hierarchy: every page is a stack of equal rounded cards; the one action (gate approve, confirm a suspicion) weighs the same as browsing.
3. Wrong semantics: drifting = green; orange = errors and "suspected"; purple = active nav, buttons, chips, charts and the Ze bubble at once.
4. Raw enums leak: `awaiting_gate`, `user_declared`, `exercise_habit:`, mono table names.
5. Charts are decoration: pies with 2 or 20 slices, empty-year heatmaps, count bars. None answers a question.
6. Layout bugs: skills + workspace content flush to the top bar; usage pie overflows; workflow graph overflows; Ze bubble covers rows.
7. Buttons: ALL-CAPS tracked outline pills everywhere (KEEP/DROP/CLOSE/RUN NOW/APPROVE), two or three per row.
8. IA by organ (Automation/Knowledge/System) not by the question the user has; the home is chat, so the world-state never greets the user.
9. Motion: none purposeful (starfield is ambient decoration).
