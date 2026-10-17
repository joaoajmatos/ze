# Implementation Plan: World (W2)

**Branch**: `186-web-world` | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md (Clarifications 2026-10-17 are binding), `main` at b9e62e7b (183 shell, 185 specs), 184 floor at 9ca300d8, 185 and 195 plans. DESIGN.md sections "The field chart", "Rows", "Honesty visuals", "One Alarm Rule". Revised after Gauge's review (V-1..V-11).

## Summary

World becomes the real home at `/`. The page composes one `World` model from nine queries (priority snapshot, loops, goals, workflows and their latest executions, held writes, reminders, hypotheses, notifications since the last visit, job runs, budget) plus the pending-confirmation store. It hands that model to six widgets by props. The field chart and leader line are ported from `/jarvis` without its three faked values. Needs you answers every decision in place, through mutations that already exist and the gate `action` frame. The interim World (old Loops and Priority pages), the bell's held-write list and the Reminders plugin page are deleted.

## Technical Context

**Language/Version**: TypeScript 5, React 19, TanStack Query 5, zustand (ze-web); Python 3.12 for the ze-calendar cut.
**Primary Dependencies**: no new packages. The field is hand-written SVG (as in `/jarvis`), not a chart library.
**Storage**: none. `localStorage` only for `ze.world.lastSeenAt` (per-viewer convenience, try/catch).
**Testing**: vitest + Testing Library; pure lib functions (placement, posture mapping, band grouping, sentence) unit-tested; Playwright-free captures through the impeccable flow as in 183; pytest for ze-calendar.
**Constraints**: FSD (`pages → widgets → features → entities → shared`, no same-layer cross-slice imports, lint-enforced); DESIGN.md tokens only (`shared/styles/ze.css`); no value the API lacks; 44 px targets; `prefers-reduced-motion`.
**Scale**: single user; a few dozen concerns; the field must hold 60 fps while scrolling.

## Constitution Check

| Principle | Check |
|---|---|
| Spec first | spec.md + Clarifications; plan and tasks here. |
| Honest claims | Every mark, row and number maps to an API field (SC-001 list). No 0.5 fallback, no invented trail, no hard-coded deadline. Raw enums never render (posture table). |
| Package boundaries | All web; ze-calendar removes its own page. No backend contract added. |
| Pre-v1 hard cuts | Interim World, old Loops/Priority pages and widgets, bell held-write list, `?confirm=` bell handling, `/world/priority`, Reminders page and descriptor deleted in this phase. |
| Tests | Fail-first per task; route, mutation and lib tests. |
| Docs are part of done | [DOCS] tasks cover the docs in "Docs touched". |

## Blast radius

`graphify affected <symbol> --depth 2` on `main` b9e62e7b, plus `rtk proxy grep` where graphify had no unique node:

| Symbol | Callers | Change |
|---|---|---|
| `WorldInterim` (grep) | `app/router/routes.tsx` (index and `world/*`), `routes.test.tsx` (mock + `/world/priority` row), `pages/world/index.ts`, `WorldInterim.test.tsx` | Deleted; `WorldPage` takes both routes; `world/*` keeps only `/world` → `/` (unknown subpaths 404). |
| `LoopReviewList` | `pages/loops/ui/LoopsPage.tsx` (+ test), `widgets/loop-review/index.ts` | Deleted with `pages/loops`. |
| `PrioritySnapshot` | `pages/priority/ui/PriorityPage.tsx`, `widgets/priority-snapshot/index.ts` (+ test) | Deleted with `pages/priority`. |
| `worldLoaders` (grep) | `routes.tsx` only | Deleted. |
| `redirects` `/priority` | `shared/config/places.ts`, `places.test.ts:49`, `routes.test.tsx:106` | `/priority` → `/`; new `/reminders` → `/`. |
| `NotificationBell` | `TopBar.tsx` (+ test), `AppShell.tsx`, `NotificationBell.test.tsx` | Held-write list, `useHeldWritesQuery`/`useDecideHeldWriteMutation` use and `?confirm=` param removed; the "open World" link replaces them. |
| `useHeldWritesQuery` | `NotificationBell.tsx`, `heldWrites.test.tsx`, `entities/confirmation/index.ts`; `/jarvis` `model/world.ts` | Now used by World; the bell stops using it. |
| `claimHref` (184, `features/primitive-tree/lib/claimHref.ts`) | `useCardActions` (184) | Loop, hypothesis and held-write cards use the shared focus helper (`/?focus=<kind>:<id>`), so chat cards and notifications select the same item. |
| `useLoopTransitionMutation` | `widgets/loop-review` (deleted), `/jarvis` | Invalidates all loop keys and the snapshot. |
| `refreshKeysForScreen` | `RefreshHandler` (+ tests) | Returns a list of keys. |
| `notificationHref` (grep) | `NotificationBell.tsx`, `widgets/app-shell/lib/notification-format.ts` (+ test) | `held_write`, `open_loop`, `reminder`, `hypothesis` → `/?focus=<kind>:<id>`; moves to `shared/lib/notification-href.ts` because World (a page) and the bell (a widget) both need it. |
| `RefreshHandler` | `AppShell.tsx` (+ test), `features/invalidate-on-ws-refresh/index.ts` | Adds `message` frame invalidation of the World keys; `notification` frame also invalidates budget and the per-kind keys. |
| `usePendingConfirms`, `useConfirmation` | `useChatWorkspace.ts` (187 moves), `ConfirmationFrameHandler.tsx` | Read by World (pages may import features). No change. |
| `set_world_signal` (grep: `entities/presence/model/presence.ts`, `store.ts`) | presence reducer | Dispatched by World (`attention`, `acting`, cleared on unmount). No reducer change. |
| `build_reminders_page` (ze-calendar) | `api/routes.py::get_reminders_page`, `tests/test_ui_page.py` (3) | Deleted with `ui/page.py`, the route, `PluginPageResponse` if unused, the `ui_contributions` entry and `test_api_routes.py:67` case. `listReminders` (185) stays. |
| `getRemindersPage` (generated) | `packages/ze-client` generated SDK; no web caller (plugin pages resolve by `page_operation_id` from the manifest) | Removed by codegen. |

`/jarvis` (`pages/jarvis/**`) is not touched (deleted in 193); its imports from `entities/*` keep working because no entity export is removed.

## Design

### Data: `pages/world/model`

- `useWorld(): WorldModel` composes the queries below and returns `{ loading, now, sourcesFailed, concerns, decisions, doing, touched, away, budget, sentenceCounts }`. Each sub-part carries its own `error` so one failing query only blanks its module.
- Queries (all from entity indexes): `usePrioritySnapshotQuery`, `useLoopsQuery()` (default states) and `useLoopsQuery("closed")` for Touched, `useGoalsQuery`, `useWorkflowsQuery` + `useLatestExecutionsQuery(ids ≤ 10)` (new in `entities/workflow`, `useQueries` over `listWorkflowExecutions(limit 5)`), `useHeldWritesQuery`, `useRemindersQuery({ status: "all", limit: 100 })` (new `entities/reminder`), `useHypothesesQuery({ state: "all", limit: 200 })` (new `entities/hypothesis`; the snapshot includes confirmed ones), `useNotificationsSinceQuery(since)` and `useAttentionBudgetQuery` (`entities/notification`, the second from 185), `useProactiveJobRunsQuery(since)` (new `entities/proactive-job`), and `usePendingConfirms` (feature store).
- `lib/concerns.ts` (pure): join snapshot items with their records by `source_kind` + `source_id`: loop → `confidence`, `confidence_prior`, `confidence_changed_at`, `claim_kind`, `provenance`, `state`, `drift_deadline`, `reminder_id`; goal (stuck goals only reach the snapshot) → progress (184), `confidence: null`, slipped; hypothesis → `confidence`, `claim_kind`; relationship → `confidence: null`, readout = title and rank (no record route). Items whose record is missing keep the title only and are flagged `partial` (the readout says "details unavailable"). Reminders become deadlines: `due = min(drift_deadline, linked reminder fire_at)`, the readout naming which; unlinked reminders become their own `reminder` concerns (no confidence).
- `lib/decisions.ts` (pure): held writes, gates (goals with `gate_id`), suspected loops, pending confirmations of kind `budget`/`write` from every thread (not `HELD_KEY`, not `prompt`: prompts are gates and suggestions already listed or not decisions World owns). Ordered by expiry, then age.
- `lib/sentence.ts` (pure, EN only like the rest of the UI): from counts: slipped promises, watched concerns, decisions waiting. Exact strings tested.
- `lib/last-seen.ts`: storage and the visit are separate. Persist: write `lastSeenAt = now` on every `visibilitychange` to hidden, on `pagehide` and on unmount (storage = last time World was in front of the user). Visit (memory): on mount `since = stored lastSeenAt ?? now − 24 h`; on hide record `hiddenAt`; on visible, if hidden ≥ 5 min, `since = hiddenAt` (new visit), else unchanged. Pure functions over `(state, event, now)` plus a thin hook.
- `lib/focus.ts`: parse `?focus=<kind>:<id>` (kinds `loop`, `held_write`, `reminder`, `hypothesis`, `goal`); unknown → ignored.

### Posture → visual (one table, shared)

The posture vocabulary lives in `entities/priority-item/lib/posture.ts` (World's concerns are priority items) and is exported, so every widget reads the same table. `postureOf(claim_kind, kind, state) → told | evidenced | inferred | suspected | goal | plain`, `glyphOf`, `chipLabelOf`, `stateWords` (no raw enum: `awaiting_gate` → "waiting on you", `user_declared` → "you told me"). One table test covers field marks, rows and cards.

### Widgets (props only; each wraps a `Module`)

- `widgets/world-field` (concerns = the snapshot set plus reminders; healthy active goals are not on the field): `FieldChart` + `lib/placement.ts` (ported `xOfDays`, bands, lanes, label collision `place`, px-true scale `k`), `lib/trail.ts` (prior → current, null-safe), `ui/FieldReadout.tsx` ("Why this order": computed vs displayed rank, override, pin; reorder controls; Close and Drop for active and drifting loops via `useLoopTransitionMutation`), `ui/FieldList.tsx` (the phone and reduced-plot fallback: ranked list grouped by band). Hit radius 26 units desktop, 60 coarse pointer. Reorder: pointer drag and keyboard (Space lift, arrows, Space drop, Escape cancel) build a `submitPriorityOverride` payload (`anchor` = neighbour, `relation` above/below, `pinned` from the toggle); unpin calls `unpinPriorityOverride` with `item.override.id` (existing `useReprioritizeMutation` and `useUnpinPriorityOverrideMutation`, exported from `entities/priority-item/index.ts` in T006, which today exports only `usePrioritySnapshotQuery`).
- `widgets/needs-you`: rows per decision kind with one or two actions: held write → Approve / Deny (`useDecideHeldWriteMutation`; editable items open the existing `ConfirmationCard` inline); gate → Proceed / Stop / Redirect (`features/answer-gate`, new: sends `{type:"action", payload:"goal:approve|stop|redirect:<gate_id>", thread_id: useSession().threadId}` through `shared/api` `send`; tracks Proceed/Stop as in flight until the goals query no longer lists the gate, or until an `error` frame on that thread within 15 s, which it reports; one send per gate while in flight. Redirect is in flight only until the first `message` or `error` frame on that thread; then the gate is marked "waiting for your instructions" and Proceed/Stop stay enabled). Redirect then calls `onChatAbout({kind:"goal_gate", id, parent_id})`, which opens the overlay on the same session thread so the next message is the instruction; suspected loop → Yes, track it / Drop (`useLoopTransitionMutation`); chat confirmation → Approve / Deny and Open (`askPath(thread)`), one `PendingConfirmRow` component per item calling `useConfirmation(false, pending.threadId)` (the hook is per thread). Cream tone, never coral. Row removed on success; failure shows the module error line.
- `widgets/doing-now`: active goals (progress, next milestone, `stuck_since` → "stuck since …"), next workflow run, runs this week ok/failed (from latest executions), the running execution (if any) with `failure_summary` for failed ones (184).
- `widgets/loops-rail`: rows (glyph, state tick, `Spark` from prior → current or none, mono readout, dim line "Drifting · email · 3 d ago"; Close and Drop on active and drifting rows).
- `widgets/touched`: loops (including closed), goals and workflows with `updated_at`/`last_progress_at`/`last_run_at` in the last seven days. `listLoops(state=closed)` has no `since` filter, so Touched filters client-side; known debt (a `since` param) noted for 194.
- `widgets/away`: notifications since last visit (title, time, one action via `notificationHref`), job runs since (only jobs marked `visible` in `entities/proactive-job/lib/job-labels.ts`, a closed map of user-meaningful jobs such as briefing, insights, workflow and goal sweeps; housekeeping jobs such as `checkpoint_pruning`, `prune_notifications`, `cost_reconciliation`, `memory_consolidation` are listed with `visible: false` and never shown; an unknown id is not shown), budget readout "3 of 5 discretionary pushes used · next slot 14:20" (`next_slot_at` only when present).

### Page: `pages/world`

`WorldPage` lays out the three columns (desktop) and the phone order (390 px: Presence → Sentence + CTA → `FieldList` → Needs you → Doing now → Loops → Touched → Away). Hero head: Sentence, "N sources down: …" when `sourcesFailed` is non-empty (only the field and readout show their error state for a failed source), and the "What's slipping?" `CommandChip`, which sends the 184 preset (`context.compose = "slipping"`) through 195's single send path and opens Ask. States: loading frames with dim labels and no numbers; empty field ("Nothing tracked yet. Tell me what you are working on."); offline (WS store `connected === false`) disables every write control with "Ze is offline".

Presence: an effect dispatches `set_world_signal` `attention` when any concern slipped (drifting loop, stuck goal, failed latest execution, overdue reminder), else `acting` when an execution is running, else `null`; cleared on unmount. The `LeaderLine` (from `shared/ui/hud/presence`) goes from `.presence-orb canvas` to the most overdue slipped mark's centre, desktop only, hidden under reduced motion; on phone the slipped row pulses (CSS, reduced-motion off).

Screen context (195): `WorldPage` publishes `{ place: "world", focused_module }`; `world-field` publishes `selection` (selected marks) and `subject` (readout item); every widget publishes its visible rows as `visible`. `chatAbout` comes from `features/ask-bar` in the page and is passed down; `Module` gets `onChatAbout` per module, and marks and rows render `ChatAboutChip` with their ref (`loop`, `goal`, `goal_gate`, `held_write`, `hypothesis`, `reminder`, `notification`, `workflow_execution`).

### WS invalidation (`features/invalidate-on-ws-refresh`)

Keys (pinned, `shared/lib/query-keys.ts`): `["loops"]` prefix (all states), `["priority-snapshot"]`, `["reminders", status]`, `["hypotheses", state, entityId]`, `["goals"]`, `["held-writes"]`, `["attention-budget"]`, `["notifications-since", since]` (must not start with `"notifications"`: the `notification` branch rewrites every `["notifications"]` query as `InfiniteData`), `["proactive-job-runs", since]`, `["workflow-executions"]` prefix.

`message` frame → invalidate loops, priority-snapshot, reminders, hypotheses, goals, held-writes, attention-budget. `notification` frame → as today, plus attention-budget, notifications-since, and its `target_type` key (`open_loop` → loops, `goal_gate`/`goal` → goals + priority-snapshot, `workflow_execution` → workflow-executions, `reminder` → reminders, `hypothesis` → hypotheses). `refreshKeysForScreen` returns a list of keys: `goals` → goals, priority-snapshot, workflow-executions. `useLoopTransitionMutation` (entities/loop) invalidates the `["loops"]` prefix and priority-snapshot instead of `["loops", ""]` only.

### Hard cuts

Web: `pages/loops`, `pages/priority`, `widgets/loop-review`, `widgets/priority-snapshot`, `pages/world/ui/WorldInterim.tsx` (+ tests), `worldLoaders`, the `/world/priority` route and test rows, the bell's held-write section and `?confirm=` handling (+ test cases), `widgets/app-shell/lib/notification-format.ts::notificationHref` (moved). Backend: `plugins/ze-calendar/ze_calendar/ui/page.py`, `tests/test_ui_page.py`, `GET /api/v0/reminders/page` and its test case, `PluginPageResponse` (if unused after), the `ui_contributions` override in `CalendarPlugin` (its only entry is the reminders page; `ZePlugin.ui_contributions` defaults to `[]`), and its `UiContribution` import if unused. Generated `getRemindersPage` disappears with codegen.

## Project Structure

### Documentation (this feature)

```
specs/phases/186-web-world/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code

```
apps/ze-web/src/pages/world/{index.ts,ui/WorldPage.tsx,model/useWorld.ts,lib/{concerns,decisions,sentence,last-seen,focus}.ts}
apps/ze-web/src/widgets/{world-field,needs-you,doing-now,loops-rail,touched,away}/
apps/ze-web/src/features/answer-gate/
apps/ze-web/src/entities/{reminder,hypothesis,proactive-job}/ ; entities/workflow/api/useLatestExecutionsQuery.ts ; entities/notification/api/useNotificationsSinceQuery.ts ; entities/priority-item/lib/posture.ts
apps/ze-web/src/shared/lib/{notification-href.ts,query-keys.ts} ; shared/config/places.ts
apps/ze-web/src/features/invalidate-on-ws-refresh/ui/RefreshHandler.tsx
apps/ze-web/src/widgets/app-shell/ui/NotificationBell.tsx
apps/ze-web/src/app/router/routes.tsx
plugins/ze-calendar/ze_calendar/{plugin.py,api/routes.py,api/schemas.py,ui/} ; packages/ze-client/src/generated/*
```

## Docs touched ([DOCS] tasks)

- `docs/frontend.md`: World place, widgets, entities, data composition, WS invalidation, deleted pages; the redirect table and `WorldInterim` line (~62–70).
- `core/cognition/ze-worldstate/README.md` (~18) and `docs/architecture.md` (~449): "Open loops page" → World; `docs/cognitive-architecture.md` if it uses the phrase.
- `docs/native-interface.md`: notification deep links (`/?focus=`), bell behaviour.
- `docs/features.md`: World as home (what it shows, decisions in place).
- `docs/architecture.md`: REST table loses `getRemindersPage`; web section names World.
- `plugins/ze-calendar/README.md`: no UI page; `listReminders` feeds World.
- `docs/extending-ze.md` only if it uses the Reminders page as the plugin-page example.
- `AGENTS.md`: phase row 186; Learned Workspace Facts nav line (World replaces Loops/Priority); `specs/README.md` row 186.

## Complexity Tracking

| Item | Why |
|---|---|
| Nine queries on one page | World is the join of the user's state; each query is small and cached. A backend aggregate would duplicate PriorityView and is not needed at single-user scale. |
| Latest executions via `useQueries` (≤ 10 workflows) | No workflow list field carries the last result; adding one is a backend change this phase does not need. |
