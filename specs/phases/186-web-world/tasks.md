# Tasks: World (W2)

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), DESIGN.md.

**Build gate**: start when 184, 185 and 195 are on `main`. The Spec Architect (Lintel) stays on call for design questions.

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Vitest + Testing Library with mocked `@myguyze/ze-client` calls; pure `lib/` functions get table tests; pytest for ze-calendar.

**Lanes**: `[ENG]` Claude Sonnet lane lead (page model, field chart, Needs you, presence, router, invalidation, gates). `[JR]` OpenCode junior (exact files given). Floor Reviewer reviews per user story. `[DOCS]` Docs Steward.

**Tags**: `[WEB]` ze-web, generated client · `[BACKEND]` ze-calendar · `[DOCS]` docs and specs.

**Rules for the implementer**
- FSD: `pages → widgets → features → entities → shared`; no same-layer cross-slice imports (lint). Widgets get data and callbacks by props from `pages/world`; `chatAbout` comes from `features/ask-bar` in the page.
- Every value maps to an API field. Never port `/jarvis`'s `?? 0.5`, staleness trail or hard-coded deadlines/reminders. No raw enum renders.
- DESIGN.md tokens and classes from `shared/styles/ze.css` only; One Alarm Rule (coral only for slipped); Needs you is cream.
- Before changing a shared export, run `graphify affected "<Symbol>" --depth 2` and `rtk proxy grep -rn "<symbol>" apps/ze-web/src`; update every caller in the same change.
- `/jarvis` is not touched (193 deletes it).
- Generated client (`packages/ze-client/src/generated/*`) belongs to ENG; JR never edits it.
- Shared worktree: `git add <paths>`; `git commit -m ... -- <paths>`; never `git add -A` or `git stash`. Commit only when the ENG lead or Maestro asks; split commits by user story.

---

## Phase 0: Gate [ENG]

- [ ] T001 [ENG] [WEB] Branch from `main` with 184, 185, 195 merged. `make web-install`, `make codegen` (no diff expected). `graphify update .`, then `graphify affected` on `NotificationBell`, `RefreshHandler`, `LoopReviewList`, `PrioritySnapshot`, `useHeldWritesQuery`, `usePendingConfirms`, `build_reminders_page`, and grep `WorldInterim`, `notificationHref`, `set_world_signal`, `worldLoaders`. Record in the Handoffs note: (a) differences from plan.md "Blast radius"; (b) the generated client has `listReminders`, `listHypotheses`, `getAttentionBudget`, `listProactiveJobRuns`, the `listNotifications` `since` param, `LoopListItem.confidence_prior`/`drift_deadline`, `GoalListItem` progress fields, `failure_summary`; (c) 195's exported names (`useScreenPublisher`, `chatAbout`, `Module.onChatAbout`, `ChatAboutChip`) and 184's preset send for "What's slipping?"; (d) the gate action handler (`ze_api/api/ws/goal_actions.py`) on a session thread with no open turn: Proceed/Stop post the assistant message and `refresh` (screen `goals`) to that thread; Redirect arms `pending_gate_redirect` for that thread and the next message there is consumed (`turns.py`); a bad id sends an `error` frame to that thread; (e) the 184 `claimHref` on `main`. Run the `/jarvis` World critique baseline (impeccable) and record the score. Stop and report differences to the Spec Architect.

## Phase 1: Entities and shared [US1–US6]

- [ ] T002 [P] [JR] [WEB] `entities/reminder/{api/useRemindersQuery.ts,index.ts}` (+ test with mocked `listReminders`; `status` param; key `["reminders", status]` in `shared/lib/query-keys.ts`).
- [ ] T003 [P] [JR] [WEB] `entities/hypothesis/{api/useHypothesesQuery.ts,index.ts}` (+ test; `state`, `entity_id`, `limit` params; key `["hypotheses", state, entityId]`).
- [ ] T004 [P] [JR] [WEB] `entities/proactive-job/{api/useProactiveJobRunsQuery.ts,lib/job-labels.ts,index.ts}` (+ tests: `since` param; key `["proactive-job-runs", since]`; only `visible: true` jobs are returned by the selector; unknown ids are hidden; every registered job id has an entry: the fixture list comes from T001 grepping both `job_id = "…"` class attributes and keyword registrations (`job_id="…"`, e.g. `goal_advance_sweep`, `dream_inactivity_watcher`, `memory_consolidation`, `cost_reconciliation`, `checkpoint_pruning` in the `bootstrap.py` files); housekeeping jobs are `visible: false`).
- [ ] T005 [P] [JR] [WEB] `entities/notification/api/useNotificationsSinceQuery.ts` (non-paged, `since`, limit 50, key `["notifications-since", since]`, never under `["notifications"]`) and `entities/workflow/api/useLatestExecutionsQuery.ts` (`useQueries` over at most 10 workflow ids, `limit: 5`), exported from the entity indexes (+ tests).
- [ ] T006 [ENG] [WEB] Tests first `shared/lib/claim-posture.test.ts` (shared with 189 Mind; if 189 landed it first, extend it instead): the posture table (told, evidenced, inferred, suspected, goal, plain) → glyph, chip label, state words for every loop/goal/hypothesis/relationship state; no output equals a raw enum (`awaiting_gate`, `user_declared`, `causal_guess`, …). Implement `shared/lib/claim-posture.ts`, export it from `shared/lib`; export `useReprioritizeMutation`, `useUnpinPriorityOverrideMutation` from `entities/priority-item/index.ts`. In `entities/loop/api/useLoopTransitionMutation.ts` (+ test) invalidate the `["loops"]` prefix and `["priority-snapshot"]`.
- [ ] T007 [ENG] [WEB] Tests first `shared/lib/notification-href.test.ts` (moved from `widgets/app-shell/lib`): `held_write`, `open_loop`, `reminder`, `hypothesis` → `/?focus=<kind>:<id>` (`open_loop` uses kind `loop`); the rest unchanged (184 targets); a `focusHref(kind, id)` helper is exported and used by both. Move `notificationHref` to `shared/lib/notification-href.ts`, export from `shared/lib`, update the bell import; delete the old file and test. Update 184's `features/primitive-tree/lib/claimHref.ts` (+ test) so loop, hypothesis and held-write cards use `focusHref`.

## Phase 2: Page model [US1, US3, US4]

- [ ] T008 [ENG] [WEB] Tests first `pages/world/lib/concerns.test.ts`: snapshot × records join per source kind; a stuck goal joins its progress and is slipped (healthy goals never appear: they are not in the snapshot); a confirmed hypothesis joins its record from the `state=all` list; a relationship item has title and rank only; a missing record gives a `partial` concern with the title only; goal and relationship concerns have `confidence: null` (never 0.5); `due` = earliest of `drift_deadline` and linked reminder `fire_at`, labelled; an unlinked reminder becomes its own concern; an `overdue` reminder is slipped; trail present only when `confidence_prior` is non-null. Implement `lib/concerns.ts`.
- [ ] T009 [ENG] [WEB] Tests first `pages/world/lib/decisions.test.ts`: held writes, gates (goals with `gate_id`), suspected loops, pending `budget`/`write` confirmations from every thread (not `HELD_KEY`, not `prompt`); ordering by expiry then age; an empty pending store (fresh reload before replay) yields no chat-confirmation rows and the replayed frames bring them back. Implement `lib/decisions.ts`.
- [ ] T010 [P] [JR] [WEB] Tests first `pages/world/lib/{sentence,last-seen,focus}.test.ts`: exact sentence strings for 0/1/many slipped, watched, waiting; `last-seen`: survives a throwing `localStorage` (falls back to now − 24 h); every hide, `pagehide` and unmount write `lastSeenAt = now`; a 5-second hide writes storage but leaves the in-memory `since` unchanged; a hide of 5 minutes or more moves `since` to the hide time; a fresh mount after a closed tab uses the stored time; `focus` parses `loop:<id>` etc. and ignores unknown kinds. Implement the three files.
- [ ] T011 [ENG] [WEB] Tests first `pages/world/model/useWorld.test.tsx` (mocked client): the model carries `sourcesFailed` from the snapshot; one failing query sets only its part's `error`; `since` for Away is the stored last-seen. Implement `model/useWorld.ts`.

## Phase 3: The field [US1, US3, US5]

- [ ] T012 [ENG] [WEB] Tests first `widgets/world-field/lib/placement.test.ts`: band x-ranges and `xOfDays` (ported values), no-deadline lanes by rank, label collision never overlaps two boxes, null-confidence concerns sit in the "not a claim" lane at the top of their band, px-true `k`. Port into `lib/placement.ts` and `lib/trail.ts`.
- [ ] T013 [ENG] [WEB] Tests first `widgets/world-field/ui/FieldChart.test.tsx`: marks render by posture (filled, half, dashed, hollow goal), slipped marks carry the hot class, NOW line, hover/focus callout, select → readout; every mark is a focusable button with an accessible name ("Reply to Ana, drifting, slipped 3 days ago, 62% sure"). Implement `FieldChart.tsx`, `FieldReadout.tsx` (computed vs displayed rank, override, pin; Close and Drop for active and drifting loops call the loop transition mutation; not shown for suspected loops, which Needs you handles).
- [ ] T014 [ENG] [WEB] Tests first `widgets/world-field/ui/reorder.test.tsx`: drag and keyboard (Space lift, arrows, Space drop, Escape) produce the `submitPriorityOverride` payload (anchor neighbour, relation, pinned); unpin calls `useUnpinPriorityOverrideMutation` with `item.override.id`. Implement.
- [ ] T015 [JR] [WEB] Tests first `widgets/world-field/ui/FieldList.test.tsx`: ranked list grouped Slipped / This week / Later / No deadline, same posture vocabulary, slipped row carries the pulse class (not under reduced motion). Implement `FieldList.tsx`.

## Phase 4: Decisions [US2]

- [ ] T016 [ENG] [WEB] Tests first `features/answer-gate/api/useAnswerGate.test.ts`: Proceed, Stop and Redirect send `{type:"action", payload:"goal:approve|stop|redirect:<id>", thread_id}` with `thread_id` = `useSession().threadId`; a second Proceed/Stop for the same gate while in flight is refused; Proceed/Stop stay in flight until the goals data drops the gate; an `error` frame on that thread within 15 s clears it and returns the error; Redirect is in flight only until the first `message` or `error` frame on that thread, then the gate is `awaitingInstructions` and Proceed still sends (test: Redirect, server reply, then Proceed); returns false when offline. Implement `features/answer-gate`.
- [ ] T017 [ENG] [WEB] Tests first `widgets/needs-you/ui/NeedsYou.test.tsx`, one per kind: held write Approve/Deny calls `useDecideHeldWriteMutation` (editable item opens `ConfirmationCard`); gate Proceed/Stop calls `useAnswerGate` and the row is disabled until it leaves; Redirect sends the redirect frame and then calls `onChatAbout({kind:"goal_gate", id, parent_id})` (same thread as the frame: test asserts both use the session thread), after which the row reads "Waiting for your instructions" with Proceed and Stop enabled; an error frame shows the module error line and re-enables the row; suspected loop calls the loop transition mutation; chat confirmation rows are one `PendingConfirmRow` each calling `useConfirmation(false, pending.threadId)`; Approve/Deny respond and Open navigates to `askPath(thread)`; success removes the row; failure shows the module error line; offline disables every action; the row named by `?focus=held_write:<id>` is highlighted. Implement `widgets/needs-you`.

## Phase 5: Rails [US1, US3]

- [ ] T018 [P] [JR] [WEB] Tests first `widgets/loops-rail/ui/LoopsRail.test.tsx`: glyph, state tick, `Spark` only with a prior, mono readout, dim line from the posture table; Close and Drop on active and drifting rows call `onTransition`, none on suspected rows. Implement.
- [ ] T019 [P] [JR] [WEB] Tests first `widgets/doing-now/ui/DoingNow.test.tsx`: active goals with progress and "stuck since"; next run; week ok/failed counts; running execution; failed run shows `failure_summary`, never raw `error`. Implement.
- [ ] T020 [P] [JR] [WEB] Tests first `widgets/touched/ui/Touched.test.tsx` (seven-day window applied client-side, closed loops included, older closed loops dropped) and `widgets/away/ui/Away.test.tsx` (notifications with one action via `notificationHref`, only visible job runs with labels, budget readout with `next_slot_at` only when present). Implement both.

## Phase 6: Page, presence, router [US1–US6]

- [ ] T021 [ENG] [WEB] Tests first `pages/world/ui/WorldPage.test.tsx`: desktop column order and the phone order at 390 px; Sentence; "N sources down: hypothesis" only when `sourcesFailed`; only the field shows the error state for a failed source; loading frames show no numbers; empty field text; offline banner; "What's slipping?" sends the 184 preset through the 195 send path and opens Ask; `?focus=loop:<id>` selects that mark. Implement `WorldPage.tsx`, `pages/world/index.ts`.
- [ ] T022 [ENG] [WEB] Tests first in `pages/world/ui/WorldPage.test.tsx`: `set_world_signal` `attention` with any slipped concern, `acting` with a running execution and nothing slipped, `null` otherwise and on unmount; `LeaderLine` rendered on desktop with a slipped mark, not on phone, not under reduced motion. Implement.
- [ ] T023 [ENG] [WEB] Tests first `app/router/routes.test.tsx` and `shared/config/places.test.ts`: `/` renders `WorldPage`; `/world` → `/`; `/world/priority` is not found; `/priority` → `/`; `/reminders` → `/`; `/loops` → `/`. Update `routes.tsx` (delete `worldLoaders`), `places.ts` redirects.
- [ ] T024 [ENG] [WEB] Tests first `features/invalidate-on-ws-refresh/ui/RefreshHandler.test.tsx`: a `message` frame invalidates the World keys; a `notification` frame also invalidates attention-budget, notifications-since and its target kind's key, and leaves `["notifications-since", …]` data untouched by the InfiniteData rewrite; a `refresh` frame with screen `goals` invalidates goals, priority-snapshot and workflow-executions. Change `refreshKeysForScreen` (+ `query-keys.test.ts`) to return a list of keys. Implement.

## Phase 7: Screen context [US1, US2] (needs 195)

- [ ] T025 [ENG] [WEB] Tests first: `WorldPage` publishes `place: "world"` and `focused_module`; the field publishes `selection` and `subject`; each widget publishes its visible rows (`useScreenPublisher` mock assertions). Implement.
- [ ] T026 [JR] [WEB] Tests first, one per kind (195 FR-025): `ChatAboutChip` on field marks (`loop`, `goal`, `hypothesis`, `reminder`), loop rows, Needs-you rows (`held_write`, `goal_gate`, `loop`), Away rows (`notification`, `workflow_execution`) calls the passed `onChatAbout` with the right ref; each `Module` gets `onChatAbout`. Implement in the widgets (callbacks by props only).

## Phase 8: Hard cuts [US1]

- [ ] T027 [ENG] [WEB] Delete `pages/loops`, `pages/priority`, `widgets/loop-review`, `widgets/priority-snapshot`, `pages/world/ui/WorldInterim.tsx` (+ tests). In `NotificationBell.tsx` remove the held-write section, `useHeldWritesQuery`/`useDecideHeldWriteMutation` use and the `?confirm=` handling; a `held_write` notification click navigates via `notificationHref`; the bell footer links to World › While you were away. Update `NotificationBell.test.tsx`. `rtk proxy grep -rn "loop-review\|priority-snapshot\|WorldInterim\|pages/loops\|pages/priority" apps/ze-web/src` returns nothing outside `/jarvis`.
- [ ] T028 [JR] [BACKEND] Tests first in `plugins/ze-calendar/tests/test_api_routes.py`: `GET /api/v0/reminders/page` → 404; `listReminders` still works; `CalendarPlugin().ui_contributions() == []`. Delete `ze_calendar/ui/page.py`, `tests/test_ui_page.py`, the route, `PluginPageResponse` if unused, the `ui_contributions` override and unused imports. `make test-calendar`.
- [ ] T029 [ENG] [WEB] After T028: `make codegen`; commit the generated files (no `getRemindersPage`).

## Phase 9: Acceptance [ENG]

- [ ] T030 [ENG] [WEB] Gates: `make test-web`, `make typecheck-web`, `make web-build`, `make lint`, `make test-py`. Impeccable critique of World ≥ 29/40 and ≥ the T001 `/jarvis` baseline; detector 0 on touched slices; captures at 1440 and 390 with no console errors; 44 px targets; 60 fps scroll probe on the field. SC-001: list every World value with its API field in the Handoffs note. SC-002: one decision of each kind made from World against `make dev` seed data.

## Phase 10: Docs [DOCS]

- [ ] T031 [DOCS] Update every doc in plan.md "Docs touched".
- [ ] T032 [DOCS] `AGENTS.md` phase row 186 and the nav facts line; `specs/README.md` row 186 → Implemented; spec status.
- [ ] T033 [DOCS] Coverage check: `git diff main...HEAD --stat` against "Docs touched"; record in the Handoffs note.

---

## Dependencies

- T001 before everything.
- Entities T002–T005 and T006, T007 in parallel; T008–T011 need T002–T007.
- Field T012 → T013 → T014; T015 after T012. Decisions T016 → T017 (needs T009).
- Rails T018–T020 after T006 and T011.
- T021 after T011, T013, T017, T018–T020; T022 after T021; T023 after T021; T024 independent after T002–T005.
- T025, T026 after T021 (and 195 on `main`).
- T027 after T021 and T023. T028 independent; T029 after T028.
- T030 after all code; T031–T033 last.

## Parallel examples

- After T001: JR takes T002–T005 and T010; ENG takes T006, T007, then T008.
- After T011: JR takes T018–T020 and T015; ENG takes T012–T014, then T016–T017.

## Lanes

### Lane ENG (Claude Sonnet, lane lead)

T001, T006–T009, T011–T014, T016, T017, T021–T025, T027, T029, T030. Owns `packages/ze-client/src/generated/*`, `app/router/*`, `shared/config/places.ts`.

### Lane JR (OpenCode junior)

T002–T005, T010, T015, T018–T020, T026, T028.

### Docs (Docs Steward)

T031–T033.

### Cross-lane touch points

- `shared/lib/query-keys.ts`: T002–T005 (JR) add keys; T024 (ENG) reads them. Land JR keys first.
- `entities/*/index.ts`: one export line per task.
- Widget files: T026 (JR) edits widgets ENG wrote in T013/T017 and JR wrote in T018–T020; it starts after those merge.
