# Ze web overhaul plan — "What does Ze understand, and what is it doing about it?"

Status: decided by the user on 2026-10-17 (section f); ready to be split into floors. Design system: `DESIGN.md` at the floor root.
Reference implementation: `apps/ze-web/src/pages/jarvis/` (routes `/jarvis`, `/jarvis/assemble`).
Current-screen inventory and critique: `.impeccable/work/inventory.md`. Product truth: `PRODUCT.md`.

Philosophy, in one line per view: a view exists only if it answers what Ze understands (claims with
kind, source and confidence), what Ze is doing about it (runs, nudges, held writes), and what it
needs from the user (decisions). Ze is not an agenda or a notes app; lists of rows are not a purpose.

---

## a) The new information architecture

Five places. Everything in today's nav maps into one of them; the sidebar of 13 routes goes away.

| Place | Route | Answers | Replaces |
|---|---|---|---|
| **World** (home) | `/` | What is the state of my life as Ze holds it, what slipped, what needs me | Chat home, `/loops`, `/priority`, the Reminders plugin page, the bell's held writes |
| **Ask / Assemble** | `/ask`, `/ask/:threadId` | Talk to Ze; every answer assembles as HUD modules; the trace sits beside the answer | Chat (`/`), the trace side panel, session history, onboarding, confirmations, retry |
| **Doing** | `/doing`, `/doing/goals/:id`, `/doing/workflows/:id` | What runs unattended, what it did, what it waits for | `/goals`, `/goals/:id`, `/workflows`, `/workflows/:id`, `/skills`, `/procedures`, `/workspace` (runs) |
| **Mind** | `/mind`, `/mind/:entityId` | What Ze believes about me and the people and projects around me, how sure, since when | `/brain-memory`, `/brain-graph`, Contacts plugin page, `/procedures` (library) |
| **Governance** | `/governance` | Is Ze behaving: spend, budget, quiet hours, data, connections, settings | `/costs`, `/data`, `/settings`, `/workspace` (files), News settings |

### Capability map

| Today | Where it goes | Note |
|---|---|---|
| Chat + trace + session history | **Ask** | Chat is one input channel. The trace is a module beside the answer, not a side panel |
| Confirmations (`confirm_request` write/budget/held/prompt) | **Everywhere** as the Needs-you module; the live card appears in Ask when a turn pauses | One component, four kinds |
| Held writes | World › Needs you; Doing › run detail | `listHeldWrites` / `decideHeldWrite` |
| Rollback / Retry | Ask (on the latest reply) | `retry` frame, `message_rollback` frame, rollback section in the trace module |
| Notifications bell | World › "While you were away"; a small bell stays in the top bar for the unread count | `listNotifications`, `notification` frame |
| Goals, goal detail, gates, learnings, traces | Doing › Goals; gates also surface in World › Needs you | `listGoals`, `getGoalDetail`, `listGoalTraces`, `reviewGoalLearning`, `startGoal`; gate answers go over the `action` frame (`goal_plan:yes:<id>`) |
| Workflows, executions, revisions, flowchart | Doing › Workflows | `listWorkflows`, `getWorkflow`, `listWorkflowExecutions`, `getWorkflowExecution`, `triggerWorkflow`, `cancelWorkflowExecution`, `listWorkflowRevisions` |
| Priority | World › the field + "Needs you" order; a "Why this order" readout per item | `getPrioritySnapshot`, `submitPriorityOverride`, `unpinPriorityOverride`; no separate page |
| Loops | World › field, loops rail, Needs you (suspicions) | `listLoops`, `confirmLoop`, `closeLoop`, `dropLoop` |
| Skills | Doing › Skills module (review queue first) | `listSkills`, `importSkill`, approve/reject/enable/disable/delete |
| Procedures | Doing › Procedures (candidates to review, active); library detail in Mind | `listProcedureCandidates`, `listActiveProcedures`, `listProcedureLibrary`, `getProcedure`, `editProcedure`, `reviewProcedureCandidate`, `disableProcedure` |
| Memory feed, timeline scrubber | Mind › Beliefs (feed with kind/confidence/decay; "as of" scrubber kept) | `getMemoryFeed`, `getMemoryTimelineBounds`, `reviewFacts` |
| Memory graph | Mind › Graph as an entity-first view (search an entity, see its neighbourhood), never the whole hairball | `getMemoryGraph`, `getEntityDetail`, `getMemoryActivity` |
| Contacts plugin | Mind › People (server-driven page rendered as HUD modules) | `getContactsPage` via the UI manifest |
| Reminders plugin | World › Doing now / field (reminders are deadlines on concerns) | `getRemindersPage`; linked through `loop.reminder_id` |
| News plugin | Ask (a query) and Governance › Connections (settings) | `getNewsPage`, `getNewsSettings` |
| Usage / costs | Governance › Spend | `getCostSummary`, `getCostAnomalies`, `getActivityHeatmap` |
| Data | Governance › Data | `listDataDomains`, `exportData`, `importData`, `createDeleteIntent`, `deleteData` |
| Workspace | Doing › Runs (live output) and Governance › Files | `getWorkspace`, `listWorkspaceFiles`, `getWorkspaceFile`, `uploadWorkspaceFile`, `deleteWorkspaceFile`, `listWorkspaceRuns`, `watchWorkspaceRunEvents`, `cancelWorkspaceRun` |
| Settings | Governance | connection, `getQuietHours` / `updateQuietHours`, reset commands |
| Onboarding | Ask (first run); the orb walks the user through it | `command: onboarding`, `component_submit`, `OnboardingMeta` on messages |

### What merges, moves, or is cut

- **Merge:** Loops + Priority + Reminders → World. Goals + Workflows + Skills + Procedures (review) + Workspace runs → Doing. Memory feed + Graph + Contacts + Procedure library → Mind. Costs + Data + Settings + Workspace files → Governance.
- **Move into Ask/Assemble:** the chat, its trace, session history, onboarding, confirmation cards, retry/rollback. "What's slipping?", "How is X going?", "What should I decide today?" become presets; any question answers as modules.
- **Cut (pre-v1 hard cut, nothing kept behind a flag):** the left nav with organ groups, the floating Ze launcher, `/priority` as a page, `/loops` as a page, the memory-growth and usage heatmap charts, the storage and plugin pie charts, the whole-graph hairball, the "Current definition" banner, the trace side panel and "Ze's Mind" wording, the dark-glass card system, the Calm/Cinematic register.

---

## b) Screen by screen

Shared chrome (all screens): top bar (dot-matrix ZE, five tabs, unread bell, connection dot), a one-line strip (legend · date · session clock), the sticky Ask bar (44px, `/` focuses it; mic button when voice input lands in W8), and the Presence module (orb) at the top of the left rail on every screen. Modules carry no instrument ids outside the Assemble canvas (decision 9). Phone: one column, rails `display: contents`, Ask bar stays sticky above a bottom bar with five icons (decision 8).

Shared states: **loading** = module frames draw on with dim labels and no numbers (never skeleton bars); **empty** = one sentence in Ze's voice naming what would appear ("Nothing is slipping. I am watching 11 concerns."); **error** = a cream module "That didn't load" with the failing source and a Retry chip; **offline** (WS closed) = the presence module goes `error` (dim orb, coral limb, "Offline") and every write control is disabled with "Ze is offline" in the label; **sources failed** = the World hero head prints "N sources down: priority, hypothesis" from `sources_failed` and the modules that depend on them show their error state while the rest render.

### 1. World (`/`)
Purpose: the state of the user's life as Ze holds it, in one look; what slipped and what needs a decision come first.
Modules: Presence (orb, state phrase); Needs you (gates, held writes, suspicions, budget pauses, with Yes/Drop/Open); Doing now (running goal, next workflow, runs this week); the Field (time left × how sure; marks by claim kind; readout on select); the Sentence + "What's slipping?" CTA; Loops · confidence (ticks, glyphs, sparklines, mono readouts); Touched · 7 d; While you were away (notifications with one action each).
Data: `getPrioritySnapshot` (items + `sources_failed`), `listLoops`, `listGoals`, `listWorkflows` (+ executions for "runs ok"), `listHeldWrites`, `listNotifications`, `getQuietHours`, `getRemindersPage`; WS `notification`, `confirm_request`, `refresh`. Writes: `confirmLoop`, `dropLoop`, `decideHeldWrite`, `submitPriorityOverride`, `action` frame for gates.
States: as shared; the Field's empty state is a bare grid with "Nothing tracked yet. Tell me what you are working on."
Phone: Presence → Sentence + CTA → ranked list grouped by band (no plot) → Needs you → Doing now → Loops → the rest.

### 2. Ask / Assemble (`/ask`, `/ask/:threadId`)
Purpose: talk to Ze and get an answer that assembles as modules; every claim in the answer carries its posture; the trace is one module away.
Modules: Presence + Try chips (presets, keys 1–3) + Sessions (history, search) in the left rail; the canvas (sentence, decision, loop, goal, workflow, person, timeline, chart, facts, and server-driven `render_*` modules); the Trace module (routing, memory used with relevance, tools, skills, judgments, tier, effects, rollback); the live Confirmation card when a turn pauses; the Retry control on the latest reply with its undo plan.
Data: WS `message`, `token`, `typing` (progress text), `trace_update` (partial, progressive), `edit`, `confirm_request`/`confirm_cancel`, `message_superseded`, `message_rollback`, `error` (busy); REST `listSessions`, `searchSessions`, `listMessages`, `getMessageTrace(s)`, `setMessageFeedback`, `getMessageFeedback`; outbound `message` (with `context.screen`), `ack`, `confirm`, `action`, `command`, `component_submit`, `retry`, `ping`.
States: listening/thinking/speaking phases on the orb; busy error → "Ze is still working on the last one" with Cancel; empty session → the three presets; history unavailable → the Retry control disabled with its reason.
Phone: Presence compact → Try chips → canvas (spans collapse to 12, timeline omitted) → Trace collapsed behind one chip.

### 3. Doing (`/doing`, `/doing/goals/:id`, `/doing/workflows/:id`)
Purpose: what runs without the user, what it did, what it waits for.
Modules on the index: Needs you (gates and held writes only); Goals (one row per goal: milestones done/total, next milestone, gate due, age; stuck goals coral); Workflows (schedule in words, next run, last result, failures coral, Run now); Runs (workspace runs with live output, busy rule); Skills (review queue first, then on/off); Procedure candidates (review).
Goal detail: milestone timeline as a field (x = time, marks by state), gate module (cream, the one action), learnings with evidence, traces as a readout list, linked loops and reminders.
Workflow detail: flowchart kept (`@xyflow/react`), executions with outputs and a human failure line, revisions with the diff summary and "View conversation".
Data: `listGoals`, `getGoalDetail`, `listGoalTraces`, `reviewGoalLearning`, `startGoal`, `listWorkflows`, `getWorkflow`, `listWorkflowExecutions`, `getWorkflowExecution`, `triggerWorkflow`, `cancelWorkflowExecution`, `listWorkflowRevisions`, `listHeldWrites`, `decideHeldWrite`, `listWorkspaceRuns`, `watchWorkspaceRunEvents`, `cancelWorkspaceRun`, `listSkills` + review calls, `listProcedureCandidates`, `reviewProcedureCandidate`; WS `confirm_request` (kind held/prompt), `notification`.
States: a workflow with no executions says "Never run"; a failed execution row carries Retry (Run now) and Open; workspace sidecar down → Runs module error state with "Workspace is off", nothing else affected.
Phone: Needs you → Goals → Workflows → Runs → Skills; detail pages single column with the gate first.

### 4. Mind (`/mind`, `/mind/:entityId`)
Purpose: what Ze believes about the user and the people and projects around them, with kind, confidence and age, and the way to correct it.
Modules: Beliefs (the memory feed as rows: glyph by kind, sparkline of confidence decay, source, "since"; keep/drop review inline; an "as of" scrubber as a readout, not a bar chart); People (contacts as rows with last contact, projects, stale follow-ups; the server-driven Contacts page rendered as modules); Entity (search → neighbourhood: one-hop relationships as a small field, activity over time as a sparkline, facts about it); Procedures (library, versions, invocations).
Data: `getMemoryFeed`, `getMemoryTimelineBounds`, `reviewFacts`, `getMemoryGraph`, `getEntityDetail`, `getMemoryActivity`, `getContactsPage` (manifest), `listProcedureLibrary`, `getProcedure`, `editProcedure`, `disableProcedure`.
States: empty beliefs → "I have not learned anything yet. Tell me about yourself or connect Gmail."; graph entity not found → the search stays with "No entity named X".
Phone: Beliefs → People → Entity search; the neighbourhood field becomes a grouped list.

### 5. Governance (`/governance`)
Purpose: is Ze behaving. Spend, budget, quiet hours, data, connections, settings, files.
Modules: Spend (7-day total, per-flow readouts, anomalies coral, one trend sparkline); Attention budget (pushes used today of max, quiet hours form, held pushes); Data (domains as rows with counts; export, import, delete with the intent step); Connections (server URL, API key test, Gmail and plugin connections, news sources); Files (workspace files, upload, delete); Reset (scoped reset with preview and the typed confirmation).
Data: `getCostSummary`, `getCostAnomalies`, `getQuietHours`, `updateQuietHours`, `listNotifications` (held), `listDataDomains`, `exportData`, `importData`, `createDeleteIntent`, `deleteData`, `getWorkspace`, `listWorkspaceFiles`, `uploadWorkspaceFile`, `deleteWorkspaceFile`, `getNewsSettings`, `getUiManifest` (plugin settings operations), `healthCheck`, `getVersion`; WS `command: reset_preview` / `reset`.
States: budget remaining is not exposed (gap 3) → show used of max; export in progress → a draw-on rule with the readout "preparing"; delete requires the intent token.
Phone: Attention budget → Spend → Connections → Data → Files → Reset.

---

## c) How the conversation works in this UI

- **Streaming:** the Ask bar sends `message` with `context.screen` (and `goal_id` / `workflow_id` when asked from a detail page). The orb goes listening → thinking on `typing`, speaking on the first `token`; tokens stream into the Sentence module; `typing.text` shows as the presence phrase. `trace_update` frames with `partial: true` fill the Trace module progressively (routing → memory → tools → final). `message` closes the turn: the orb goes done → idle; the client sends `ack`.
- **Assembly:** every reply's `components` (server-driven descriptors from `@myguyze/ze-ui`: text, badge, table, chart, progress, steps, connections, form, button, card_notice, choice_group, confirm, metric, timeline, list, review, consent, connect_account, progress_steps) render as HUD modules through one `PrimitiveRenderer` restyled to the system: a module frame per top-level primitive, labels as `h2.lbl`, meters and sparklines for progress and metrics, chips for badges, command chips for buttons, the field-style timeline for `timeline`. The three presets are answered by backend-emitted components (B1, decision 7); the prototype's client-side `compose.ts` is not ported.
- **Trace:** one module beside the answer, collapsed by default on phones. Sections: routing (agent, method, confidence, tier), memory used (chunks with relevance), tools (calls with gate and effect), skills, judgments, sources, effects known, write confirmations, rollback. The feedback thumbs live in its head. "Why?" on any module in the answer scrolls to the trace section that produced it.
- **Confirmations:** `confirm_request` renders the Needs-you card in place (kind `write`: one row per item with the effect phrase in the imperative and an editable body when `editable_field` is set; `budget`: one row; `held`: the source run named; `prompt`: the title as the question and `actions` as command chips). Approve/Deny send `confirm`; prompt buttons send `action`. `confirm_cancel` closes it everywhere. The same card appears in World and Doing when the user is not in Ask, with a bell ring and no chat message (phase 181).
- **Retry and rollback:** the latest reply carries Retry; `retry_eligibility` from the trace builds the undo plan the user confirms (two steps); the `retry` frame carries `confirmed_plan`; `message_rollback` updates the rollback section; `message_superseded` swaps the reply.
- **Voice:** the mic chip records, the client sends the audio as a message attachment (phase 10 preprocess handles voice → transcript; the exact transport is gap 5), the orb shows listening with the input level, the transcript appears in the Ask bar before sending so the user can correct it. Spoken replies are out of scope for v1 of the overhaul.
- **Onboarding:** `command: onboarding` starts it; `OnboardingMeta` on messages drives a stepper in the Presence module; forms and choices arrive as server-driven primitives and submit with `component_submit`.

---

## d) Backend gaps (numbered)

1. **Composed answers for the presets.** "What's slipping?", "How is X going?", "What should I decide today?" need the backend to emit the modules (loop, goal, decision, person, timeline, sentence) as `render_*` components with claim posture on each; today the prototype composes them client-side from six REST calls.
2. **Claim posture on every descriptor.** `render_*` primitives need optional `kind`, `provenance`, `confidence`, `updated_at` fields so a module can draw glyph, chip and sparkline without a second lookup.
3. **Interruption budget remaining today** and the push log (`push_log`, `proactive_job_runs`) over REST, for the Attention budget module and "While you were away".
4. **Drift fields on loops over REST** are present; add `confidence_at_last_evidence` (or the evidence timestamp used by decay) so the sparkline "from" value is real, not derived.
5. **Voice transport over the WebSocket** (an `attachment` on the `message` frame, or an upload endpoint returning an id) and a `transcript` field on the reply, so the Ask bar can show what Ze heard.
6. **Correlation hypotheses as a list** (`GET /api/v0/hypotheses`) with confidence and evidence, for the Mind entity view and the "I suspect …" sentence.
7. **Action-record ledger over REST** ("what Ze did unattended") for Doing › Runs and goal/workflow detail.
8. **Contribution collisions over REST** for Governance (observability of user-vs-executive disagreements).
9. **Human failure line on workflow executions** (`failure_summary`) instead of the client parsing tracebacks.
10. **Goal rows need progress fields** (`milestones_done`, `milestones_total`, `next_milestone`, `gate_due_at`, `stuck_since`) on `listGoals`, not only on detail.
11. **Model tier on the trace** is there; expose the configured default tier on `getVersion` or settings so Governance can print it honestly.
12. **Reminders as first-class REST** (list with `loop_id` links) rather than only the plugin page descriptor, so World can place them on the field.
13. **Screen context echo:** the trace should record `screen_context` so "asked from goal X" is visible.
14. **Notification actions:** a notification row should carry a deep link target (`goal_id`, `workflow_id`, `execution_id`) so "While you were away" rows have one action.

---

## e) Build phases

Each phase is one floor for one Sonnet engineer plus a Floor Reviewer; a Docs Steward joins where marked. Pre-v1: delete, do not shim. Every phase ends with `make test-web`, `make typecheck-web`, `make web-build`, the impeccable detector at 0 on the touched slices, Playwright captures at 1440 and 390 with no console errors and 44px targets, and an impeccable critique of the touched surface at or above the previous score.

**Phase W1 — Shell and tokens** (depends on: nothing; decisions 1, 2, 5, 8, 9 apply: World at `/`, five tabs, palette setting in Governance, phone bottom bar, no instrument ids outside the Assemble canvas). Move `jarvis.css` tokens into `src/shared/styles/ze.css` as the app stylesheet; `shared/ui` gets Module, Corners, Meter, Dots, Spark, Glyph, Decode, CountUp, DotMatrix, Control/CommandChip, Chip; `widgets/app-shell` becomes the HUD chrome (top bar with five tabs, strip, sticky Ask bar, phone bottom bar); `widgets/presence` holds the orb (`Orb.tsx`, `Presence.tsx`, `LeaderLine.tsx`); the palette switcher moves to Governance; router gets the five routes with redirects from the old ones. Delete: the old nav groups, `ChatNavGroup`, the floating launcher, the proto pages (`pages/proto`, `pages/jarvis` once the real pages land), Tailwind utility styling of the shell. Tests: shell renders five tabs, Ask focus on `/`, orb state machine unit tests (spring stagger, reduced motion still frame), DotMatrix glyph coverage. Acceptance: every old route redirects; phone shows the bottom bar; reduced motion verified.

**Phase W2 — World** (depends on W1). `pages/world` with `widgets/field-chart`, `widgets/needs-you`, `widgets/doing-now`, `widgets/loops-rail`, `widgets/away`; entities `loop`, `priority`, `goal`, `workflow`, `held-write`, `notification` reused and extended (`useWorldQuery` composing them with `sources_failed`). Delete: `pages/loops`, `pages/priority`, `widgets/loop-review`, `widgets/priority-snapshot`, the reminders plugin page route. Tests: field placement (bands, lanes, collision), honesty mapping (posture → glyph/chip/meter), Needs-you mutations, sources-failed rendering, phone grouped list. Acceptance: critique ≥ 29/40; attention line anchors on the mark; 60fps scroll probe.

**Phase W3 — Ask / Assemble** (depends on W1, B1 and W2 for the loop/goal modules; decision 7: B1 lands first, so the canvas renders backend-emitted components and the prototype's `compose.ts` is deleted, not ported). `pages/ask` with the canvas, Trace module, Sessions rail, confirmation card, Retry. `PrimitiveRenderer` in `@myguyze/ze-ui/react` restyled to the system (module per primitive), new `timeline` and `metric` renderers. Delete: `widgets/chat-workspace` (ChatSidePanel, ContextOverlay, MessageBubble as they are), `features/chat-side-panel`, `features/open-context-overlay`, the trace panel. Keep and move: `features/respond-to-confirmation`, `features/retry-reply`, `features/reply-feedback`, `features/load-chat-history`, `features/trace-state`. Tests: WS frame reducer (token/typing/trace_update/confirm/cancel/superseded/rollback), cascade order and pin/dismiss, confirmation kinds, retry plan confirmation, primitive renderer snapshots. Acceptance: a full turn streams with progressive trace; a `write` confirmation round-trips; busy error handled.

**Phase W4 — Doing** (depends on W1; W3 for the held-write card). `pages/doing`, `pages/doing-goal`, `pages/doing-workflow`; widgets goals-board, workflows-board, runs (with `watchWorkspaceRunEvents`), skills-queue, procedure-candidates; keep `widgets/workflow-graph` restyled. Delete: `pages/goals`, `pages/goal-detail`, `pages/workflows`, `pages/workflow-detail`, `pages/skills`, `pages/procedures` (candidates part), `pages/workspace` (runs part), `widgets/goals-overview`, `widgets/workflows-overview`, `widgets/gate-status`, `widgets/goal-learnings`, `widgets/milestone-timeline`, `widgets/workflow-executions`, `widgets/skill-management`, `widgets/procedure-candidates`. Tests: goal row derivations, gate action frame, execution failure line, run stream reducer, skill review flows. Acceptance: a gate can be answered from Doing and World; a workflow can be run and cancelled.

**Phase W5 — Mind** (depends on W1). `pages/mind`, widgets beliefs-feed (with the as-of readout), people, entity-neighbourhood (small field), procedure-library. Delete: `pages/brain-memory`, `pages/brain-graph`, `widgets/memory-feed`, `widgets/memory-graph`, `widgets/timeline-scrubber`, `widgets/procedure-management`, the plugin contacts page route (rendered inside People). Tests: feed row posture mapping, review mutations, entity search and one-hop neighbourhood layout, as-of query. Acceptance: no whole-graph render; every belief shows kind, confidence, source, since.

**Phase W6 — Governance** (depends on W1). `pages/governance`, widgets spend, attention-budget (quiet hours form), data, connections (incl. palette and plugin settings via manifest), files, reset. Delete: `pages/costs`, `pages/data`, `pages/settings`, `pages/workspace` (files part), `widgets/costs-overview`, `widgets/data-overview`, `widgets/settings-workspace`, `widgets/workspace-management`, the pie and heatmap charts in `@myguyze/ze-ui/charts` that no screen uses. Tests: quiet hours form, export/import/delete intent flow, reset preview + typed confirm, connection test. Acceptance: Governance answers "am I spending normally" in one look; no chart without a question.

**Phase W7 — Plugins and server-driven pages** (depends on W3, W5). The UI manifest's nav entries map into the five places (Contacts → Mind, Reminders → World, News → Ask preset + Governance settings); `widgets/plugin-screen` renders manifest pages as modules. Docs Steward: `docs/frontend.md`, `docs/native-interface.md`, README screenshots. Tests: manifest mapping, plugin settings operation dispatch. Acceptance: no plugin page renders outside the five places.

**Phase W8 — Voice and polish** (depends on W3 and backend gap 5). Mic chip, level-driven listening orb, transcript correction, ambience toggle in Governance; final impeccable critique of every page, `document` refresh of `DESIGN.md`, and deletion of `pages/jarvis` and `.impeccable/work/cap` prototypes. Acceptance: critique ≥ 30/40 on each page; reduced motion and keyboard paths verified on all five.

Backend floors to schedule alongside (owned by the Backend Engineer, from section d): **B1** gaps 1, 2, 9, 10, 14, scheduled before W3 (decision 7) and in parallel with W1–W2; **B2** gaps 3, 4, 6, 12 (W2, W5, W6); **B3** gap 5 (W8, voice input only, decision 6); **B4** gaps 7, 8, 11, 13 (nice to have).

Order: W1 ‖ B1 → W2 → W3 → W4 ‖ W5 ‖ W6 → W7 → W8 (after B3).

---

## f) Decisions (user, 2026-10-17)

The user answered "go with the recommendations" to all nine questions. Recorded as decided:

1. **Home:** World is the home at `/`; Ask lives at `/ask`. The Ask bar is on every screen.
2. **Five places:** World · Ask · Doing · Mind · Governance. "Open loops", "goals", "workflows" stay as module names inside them.
3. **Priority:** folded into World (order + "Why this order" readout, drag to pin). `/priority` is deleted.
4. **Graph:** entity-first neighbourhood in Mind; the whole-graph hairball is deleted.
5. **Palette:** kept as a user setting in Governance; Orchid is the default; Ultraviolet and Amethyst remain.
6. **Voice:** input only in this overhaul (W8); spoken output later.
7. **Backend sequencing:** B1 (composed answers + posture on descriptors, gaps 1, 2, 9, 10, 14) runs before W3; W3 does not ship client-side compositions.
8. **Phone:** bottom tab bar with five icons; the Ask bar sits above it.
9. **Instrument ids (A·02, G·01):** dropped everywhere except the Assemble canvas, where the index is the component's position in the answer.
