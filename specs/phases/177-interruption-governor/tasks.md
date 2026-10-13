# Tasks: Interruption Governor (part 1)

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Unit tests use fakes (`AsyncMock` pools, a recording fake `AppInterface`, a fixed clock). Never call OpenRouter, System One or ntfy.

**Lanes**: `[ENG]` = Claude Sonnet lane lead (cross-package design, migration, concurrency, the governor, arbitration, catch-up, integration, gates). `[JR]` = OpenCode flash junior (exact files and behaviour given). See **Lanes** at the end.

**Tags**: `[BE]` backend Python · `[WEB]` ze-web and generated client · `[PLATFORM]` migration, config, wiring · `[DOCS]` docs, READMEs, specs.

**Normative references**: inventory and classes: spec.md "Push-site inventory". Governor API: [contracts/governor-api.md](./contracts/governor-api.md). REST: [contracts/quiet-hours-rest.md](./contracts/quiet-hours-rest.md). Catch-up: [contracts/catch-up.md](./contracts/catch-up.md). Tables and outcomes: [data-model.md](./data-model.md).

**Rules for the implementer**
- Before changing a signature listed in plan.md "Blast radius", run `graphify affected "<Symbol>" --depth 2` and also `rtk proxy grep -rn "<name>" --include='*.py' .` (graphify misses `ze_sdk` re-exports and has no unique node for `ProactiveNotifier`). Update every caller in the same change.
- Plugins import `PushKind`/`PushOutcome` from `ze_sdk.proactive`, never from `ze_proactive` in new code.
- No `print()`; `get_logger(__name__)`. No bare `Exception`/`ValueError` in domain code (`PushPolicyError`, `CatchUpError`).
- No compatibility shims: `push()`/`push_notification()` are deleted, not deprecated.
- Shared worktree: stage and commit only your lane's files with explicit paths (`git add <paths>; git commit -m … -- <paths>`); never `git add -A`, never `git stash`, never reset or check out files you do not own. Commit only when the ENG lead or Maestro asks; split commits by user story.
- If a step disagrees with the code you find, stop and report the difference to the ENG lead; do not redesign.

**Ordering**: Phases run in order inside a lane; cross-lane waits are listed in **Lanes**. `[P]` tasks touch different files and may run together.

---

## Phase 0: Gate  [ENG]

- [x] **T001** [ENG] [BE] Check whether Phase 170 has landed on `main` and on this branch: `git log --oneline main -- core/arbitration/ze-priority/ze_priority/arbitration.py core/cognition/ze-worldstate/ze_worldstate/surfacing.py core/cognition/ze-correlation/ze_correlation/push.py apps/ze-api/ze_api/compose.py`. If 170 is in, rebase first and read its diff of those four files plus `apps/ze-api/config/config.yaml`; 177 must keep 170's `eligible_candidates` arguments, grounding change and `correlation.push.enabled/dry_run` behaviour. If 170 is not in, proceed; record in the Handoffs note that 170 rebases on 177 for these files. Also confirm `ze_proactive/migrations/versions/` ends at `zpro003`.

---

## Phase 1: Setup — migration  [ENG]

- [x] **T002** [ENG] [PLATFORM] Create `core/contracts/ze-proactive/ze_proactive/migrations/versions/zpro004_interruption_governor.py` (revision `zpro004`, down `zpro003`, raw SQL) exactly per data-model.md: add `notifications.push_class, urgency, format, actions, delivery, delivered_at` (add nullable → backfill `push_class='accountability'`, `urgency='normal'`, `format='text'`, `actions='[]'`, `delivery='delivered'`, `delivered_at=created_at` → `SET NOT NULL` where specified → CHECK constraints), `notifications_held_idx`; create `interruption_settings` (single row, CHECK from data-model) and `proactive_job_runs`. Downgrade drops all of it. Verify with `make db-up && make migrate` and `psql -c '\d notifications'`.

---

## Phase 2: Foundational — the governor core  [ENG]  (blocks every user story)

- [x] **T003** [ENG] [BE] `core/contracts/ze-proactive/ze_proactive/types.py`: add `PushClass`, `Urgency`, `Delivery`, `PushOutcome` literals, frozen `PushKind(event_type, push_class, urgency, source)` with `__post_init__` calling `push_kinds.register(self)`, `QuietHoursSetting`, `JobRun`; add `push_class`, `urgency`, `delivery` to `NotificationRow` and wire `Notification`. New `ze_proactive/errors.py`: `PushPolicyError(ZeError)`, `CatchUpError(ZeError)` (import `ZeError` from `ze_agents.errors`).
- [x] **T004** [ENG] [BE] Fail-first `core/contracts/ze-proactive/tests/test_push_kinds.py` (identical re-registration is a no-op; conflicting class/urgency/source raises `PushPolicyError`; `registered_push_kinds()` returns a copy), then `ze_proactive/push_kinds.py` (module dict registry, `register`, `registered_push_kinds`, and `QUIET_HOURS_SUMMARY = PushKind("quiet_hours_summary", "accountability", "normal", "proactive")`). Avoid an import cycle: `types.py` imports `push_kinds.register` lazily inside `__post_init__`.
- [x] **T005** [P] [ENG] [BE] Fail-first `core/contracts/ze-proactive/tests/test_governor.py` (every row of the decide table in data-model.md, parametrised), then `ze_proactive/governor.py::decide`.
- [x] **T006** [P] [ENG] [BE] Fail-first `core/contracts/ze-proactive/tests/test_quiet_hours.py`: disabled → False; no row → False; 13:00–15:00 at 12:59/13:00/14:59/15:00; 23:00–08:00 at 22:59/23:00/02:00/07:59/08:00; `Europe/Lisbon` on 2026-03-29 (spring forward) and 2026-10-25 (fall back) at 00:30 and 07:30 local; non-Lisbon zone (`America/New_York`) offset check; `InterruptionSettingsStore.get()` maps a row and returns `QuietHoursSetting(enabled=False, …None)` when there is none; `upsert()` SQL uses `ON CONFLICT (id) DO UPDATE`; `get()` on a pool error raises and the *caller* handles it (see T010). Then `ze_proactive/quiet_hours.py`: pure `is_active(setting, now_utc)` (research R4) and `InterruptionSettingsStore(pool)` with `get()` / `upsert(enabled, start, end, timezone)`.
- [x] **T007** [P] [ENG] [BE] `ze_proactive/attention_budget.py`: delete `SourceKind`; `try_claim_shared(push_log, budget_key: str, max_per_day, *, payload=None, window_hours=24.0)` and `release_shared(push_log, budget_key)` use `budget_key` as the idempotency key verbatim. Update `core/contracts/ze-proactive/tests/test_attention_budget.py` to string keys (`"loop:<uuid>"`, `"hypothesis:<uuid>"`), keeping every existing behaviour assertion.
- [x] **T008** [P] [ENG] [BE] `ze_proactive/notification_store.py`: `create(*, event_type, source, title, body, target_type, target_id, push_class, urgency, format, actions, delivery)` (actions serialised as JSON list of `{label,payload,row}`; `delivered_at = now()` when `delivery='delivered'`); `list_held() -> list[NotificationRow]` (ordered `CASE urgency WHEN 'high' THEN 0 WHEN 'normal' THEN 1 ELSE 2 END, created_at`); `mark_released(id)`; `mark_failed(id)`; `count_held()`; `list_page` returns `push_class` and `delivery`. Extend `core/contracts/ze-proactive/tests/test_notification_store.py` for each (SQL text and argument assertions on `AsyncMock` pool).
- [x] **T009** [P] [ENG] [BE] `core/contracts/ze-agents/ze_agents/interface/types.py`: `Notification.urgency: Literal["low","normal","high"] = "normal"`, add `buzz: bool = True` (and `push_class: str | None = None`, `delivery: str | None = None` for the frame). Run `make test-agents`.
- [x] **T010** [ENG] [BE] Fail-first rewrite of `core/contracts/ze-proactive/tests/test_notifier.py` covering every row of the outcome table in data-model.md, plus: discretionary without `budget_key` raises `PushPolicyError`; held discretionary keeps its claim; delivery exception releases the claim and marks the row `failed`; settings-store exception → treated as not quiet + warning logged; `remaining_budget()` math and fail-open; `deliver_held()` delivers held rows in store order with `buzz=False`, marks each `released`, then one `QUIET_HOURS_SUMMARY` with `buzz=True`, urgency = highest held, body "While quiet hours were on, I held N update(s)."; `deliver_held()` with zero held rows sends nothing; `deliver_held()` while quiet is active does nothing. Then rewrite `ze_proactive/notifier.py` per contracts/governor-api.md (constructor, `notify`, `remaining_budget`, `deliver_held`, content splitting kept for long bodies, `push`/`push_notification` deleted).
- [x] **T011** [ENG] [BE] `apps/ze-api/ze_api/interface/native.py`: `_NTFY_PRIORITY_MAP = {"low": 2, "normal": 3, "high": 5}`; `push()` passes `buzz` through and never runs the quiet check (the governor already decided); `_send_message` and `send_confirmation` take the ntfy hop only when offline **and** `await self._quiet_now()` is False (C1, C2), where `quiet_now: Callable[[], Awaitable[bool]] | None` is a new constructor argument (None → never quiet; exceptions → not quiet); `_send_notification_frame` adds `push_class` and `delivery`; when `notification.delivery in {"held","suppressed"}`, `push()` sends **only** the notification frame (no chat message, no action frames, no ntfy). Tests in `apps/ze-api/tests/interface/test_native.py`: held/suppressed delivery sends only the frame; buzz False skips ntfy; low maps to 2; quiet true skips the reply ntfy and the confirmation ntfy; quiet does not affect `push()`; frame carries the new fields.
- [x] **T012** [P] [ENG] [BE] `packages/ze-sdk/ze_sdk/proactive.py`: re-export `PushKind`, `PushOutcome`, `PushClass`, `Urgency`; update `core/contracts/ze-proactive/tests/test_imports.py` and the ze-sdk import test if one lists names.
- [x] **T013** [ENG] [PLATFORM] Wiring: `ze_proactive/bootstrap.py` `_DEFAULT_MAX_PUSHES_PER_DAY = 5`; `apps/ze-api/config/config.yaml` `proactive.budget.max_pushes_per_day: 5` with comment "shared by every discretionary push (phase 177)" and `proactive.briefing.catch_up_max_age_hours: 6`; `apps/ze-api/ze_api/container.py`: build `InterruptionSettingsStore(pool)` before the interface, pass `quiet_now` (closure: `is_active(await store.get(), now)`) to `NativeAppInterface`, build `ProactiveNotifier(interface, notification_store, push_log=push_log_store, settings_store=…, max_discretionary_per_day=shared_push_budget(settings))` (move `push_log_store` creation above it), expose `container.interruption_settings_store`. `make test` must still collect (call sites are fixed in Phase 3; expect failures there until then).

**Checkpoint**: ENG posts "foundation landed (T002–T013)" to the JR lanes. Every later task depends on it.

---

## Phase 3: User Story 1 — every push classified, budget for discretionary only (P1)  [ENG lead; T018–T024 are [JR]]

**Goal**: all 30 inventory rows call `notify` with their `PushKind`; arbitration stops claiming; two silent bugs fixed.
**Independent test**: each package's tests with a fake notifier returning outcomes; T025 inventory test.

- [x] **T014** [ENG] [BE] Create `core/automation/ze-automation/ze_automation/push_kinds.py` with exactly these kinds (event_type, class, urgency, source): `workflow_failure` accountability high `workflows`; `goal_plan_proposed` accountability high `goals`; `goal_attention_needed` accountability high `goals`; `goal_plan_adapted` accountability normal `goals`; `goal_milestone_done` accountability normal `goals`; `goal_completed` accountability normal `goals`; `goal_gate` accountability high `goals`; `cost_anomaly` accountability high `accountability`; `accountability_narrative` accountability normal `accountability`; `goal_narrative` accountability normal `goals`; `stuck_goal` discretionary normal `goals`; `goal_suggestion` discretionary normal `goals`; `goal_overlap` discretionary normal `goals`; `goal_reuse` discretionary low `goals`. Constants named in UPPER_SNAKE of the event type.
- [x] **T015** [ENG] [BE] ze-api sites. New `apps/ze-api/ze_api/push_kinds.py`: `confirmation_request` accountability high `conversation`; `confirmation_timeout` accountability low `conversation`; `workspace_run_completed` accountability normal `workspace`. `api/websocket/confirmation.py`: `push_confirmation_ntfy` → `notify(CONFIRMATION_REQUEST, "Ze needs your approval", prompt or "Ze needs your approval.")` (rename the function `notify_confirmation_request`, update `api/websocket/__init__.py`); `confirmation_timeout` → `notify(CONFIRMATION_TIMEOUT, "Approval request expired", timeout_msg, target_type="thread", target_id=thread_id)`. `container.py` `_NotifierPushSender.send_completion` → `notify(WORKSPACE_RUN_COMPLETED, …)`. Update `apps/ze-api/tests/api/test_workspace_followthrough.py`, `tests/api/test_ws_conformance.py`, `tests/agents/test_bootstrap.py` fakes to the `notify` API.
- [x] **T016** [ENG] [BE] Arbitration path (re-read 170's diff first if landed). `core/cognition/ze-worldstate/ze_worldstate/surfacing.py`: declare `LOOP_DRIFT = PushKind("loop_drift","discretionary","normal","worldstate")` in a new `ze_worldstate/push_kinds.py`; `send(loop) -> PushOutcome | None` (None when no longer drifting) calls `notify(LOOP_DRIFT, "Open loop", format_hedged_mention(...), target_type="open_loop", target_id=str(loop.id), budget_key=f"loop:{loop.id}")`; delete `claim_push` and `release_push_claim` (graphify shows no non-test callers; delete their tests). `core/cognition/ze-correlation/ze_correlation/push.py`: `HYPOTHESIS = PushKind("hypothesis","discretionary","normal","correlation")` in new `ze_correlation/push_kinds.py`; `send(h) -> PushOutcome` with `budget_key=f"hypothesis:{h.id}"`, `target_type="hypothesis"`. `core/arbitration/ze-priority/ze_priority/arbitration.py`: constructor `(priority_view, loop_surfacer, correlation_push_source, notifier)` (plus 170's loop settings if landed); `run()` returns early when `await notifier.remaining_budget() == 0`; iterate the ranking, call `_send`, stop on `delivered`/`held`/`suppressed_budget`, continue on `duplicate`/`failed`/`None`; no `try_claim_shared`/`release_shared` imports. Update `apps/ze-api/ze_api/compose.py` construction. Rewrite `core/arbitration/ze-priority/tests/test_arbitration.py` (zero budget sends nothing; top candidate delivered stops; duplicate falls through to next; suppressed stops; held counts as sent), update `ze-worldstate/tests/test_surfacing.py` and `ze-correlation/tests/test_push.py`.
- [x] **T017** [ENG] [BE] Goals. `core/automation/ze-automation/ze_automation/goals/executor.py`: replace `self._push` and `self._notify` with one injected `notify` callable (constructor/`wire_goal_executor_push(stack, notifier)` binds `notifier.notify`); map each site per spec inventory A6–A10 and D6 (titles: "Goal paused", "Milestone failed", "Goal stopped", "Replan failed", "Direction not applied", "Plan adapted", "Applying your direction", "Adapting the plan", "Milestone done", "Goal completed", "Checkpoint", "Prior work reused"; keep the existing body text and `format="html"`; keep actions on A10); `_fire_gate` sends **one** `notify(GOAL_GATE, …, actions=…, target_type="goal_gate", target_id=str(gate.id))` instead of push + notify; `_push_reuse_notice` is `await`ed and uses `budget_key=f"goal_reuse:{milestone.id}"`. `agents/goals/tools.py`: A5 `notify(GOAL_PLAN_PROPOSED, …, actions=[Start goal, Cancel], target_type="goal", target_id=str(goal.id))`; D5 `notify(GOAL_OVERLAP, …, budget_key=f"goal_overlap:{new_goal.id}")`. `bootstrap.py` A4 `notify(WORKFLOW_FAILURE, …)` (keep the cooldown via `push_log`). Update `tests/goal_agent/{test_create_goal_convergence,test_goal_agent,test_goal_tools}.py` and executor tests; add a test that the reuse notice is awaited (fake notify records the call).
- [x] **T018** [P] [JR] [US1] [BE] `core/automation/ze-automation/ze_automation/jobs/cost_anomaly.py` → `notify(COST_ANOMALY, "Cost anomaly detected", body)`; `jobs/accountability.py` → `notify(ACCOUNTABILITY_NARRATIVE, "Weekly accountability report", narrative)`; `jobs/goal_narrative.py` → `notify(GOAL_NARRATIVE, "Goal progress this week", content, format="html")`. Import kinds from `ze_automation.push_kinds`. Keep every `push_log` dedup line. Update the matching tests under `core/automation/ze-automation/tests/` (fake notifier `notify = AsyncMock(return_value="delivered")`; assert kind and title). `make test-automation`.
- [x] **T019** [P] [JR] [US1] [BE] `core/automation/ze-automation/ze_automation/jobs/stuck_goals.py`: one `notify(STUCK_GOAL, "Goals need attention", content, format="html", actions=actions, budget_key=f"stuck_goals:{date.today().isoformat()}")` per run (delete the per-goal `notify` loop's notify call; keep `mark_stuck_alerted` for each goal, and only when the outcome is `delivered` or `held`). `jobs/goal_suggestion.py`: one `notify(GOAL_SUGGESTION, f'New goal idea: "{title}"', content, format="html", actions=…, target_type="goal_suggestion", target_id=str(suggestion.id), budget_key=f"goal_suggestion:{suggestion.id}")` (delete the second call). Update `tests/proactive_jobs/test_stuck_goals.py`, `test_goal_suggestion.py`. `make test-automation`.
- [x] **T020** [P] [JR] [US1] [BE] `core/cognition/ze-memory/ze_memory/dream/job.py`: new `ze_memory/push_kinds.py` `DREAM_REVIEW = PushKind("dream_review","discretionary","low","memory")`; replace `push(...)` with `notify(DREAM_REVIEW, "Dream insights to review", f"Ze dreamed overnight — {n} insight(s) await your review.", budget_key=f"dream:{run_id}")`. Update its test. `make test-memory`.
- [x] **T021** [P] [JR] [US1] [BE] ze-personal. New `plugins/ze-personal/ze_personal/push_kinds.py` (via `ze_sdk.proactive`): `morning_brief` accountability normal `personal`; `insight` discretionary normal `personal`; `contact_review` discretionary low `personal`. `jobs/briefing.py` → `notify(MORNING_BRIEF, "Morning Briefing", text)`; `jobs/insights.py` → `notify(INSIGHT, …, target_type="insight", target_id=str(row["id"]), budget_key=f"insight:{row['id']}")` and set `pushed=true` only when outcome is `delivered` or `held`; `jobs/contacts.py` → `notify(CONTACT_REVIEW, "Add to contacts?", text, format="html", actions=[Add, Skip], target_type="person", target_id=pid, budget_key=f"contact:{pid}")`. Update `plugins/ze-personal/tests/jobs/{test_briefing,test_insights,test_contact_review}.py`. `make test-personal`.
- [x] **T022** [P] [JR] [US1] [BE] ze-finance. New `plugins/ze-finance/ze_finance/push_kinds.py`: `finance_stale_nudge` discretionary low, `finance_recurring_new` discretionary normal, `finance_price_change` discretionary normal, source `finance`. `jobs/recurring.py` lines ~101/120/130 → `notify` with titles "Bank statement needed", "New recurring expenses", "Price change" and budget keys `finance_stale:{account.id}:{date.today()}`, `finance_new:{account_id}:{date.today()}`, `finance_price:{item.id}:{item.amount}`; `record_nudge` only on `delivered`/`held`. Update finance job tests. `make test-finance`.
- [x] **T023** [P] [JR] [US1] [BE] ze-messenger. **Fail-first**: first add `plugins/ze-messenger/tests/test_inbound_relay_push.py` with a real `InboundMessageProcessor`, a known contact and a fake notifier that has only `notify` (`AsyncMock`); run it and see it fail on the current `push(title=…)` call (`AttributeError`/`TypeError`). Then: new `plugins/ze-messenger/ze_messenger/push_kinds.py`: `INBOUND_MESSAGE = PushKind("inbound_message","discretionary","normal","messenger")`. `inbound/processor.py` line ~148: replace the broken `push(title=…, body=…, tags=…)` with `notify(INBOUND_MESSAGE, f"Message from {known.name or msg.sender}{subject_part}", msg.body[:200], budget_key=f"inbound:{msg.channel_type}:{msg.message_id}")` (`InboundMessage.message_id`, `ze_communication/types.py`). The test must then pass with exactly one `notify(INBOUND_MESSAGE, …)` call; an unknown sender produces none. `make test-messenger`.
- [x] **T024** [P] [JR] [US1] [BE] ze-calendar. New `plugins/ze-calendar/ze_calendar/push_kinds.py`: `user_reminder` requested high, `calendar_reminder` requested high, `calendar_reminders_scheduled` accountability low, source `calendar`. `reminders/store.py::fire_reminder` → `notify(USER_REMINDER, "Reminder", f"⏰ {reminder.label}", target_type="reminder", target_id=str(reminder_id))`; `reminders/calendar.py:164` → `notify(CALENDAR_REMINDER, "Calendar reminder", label, target_type="reminder", target_id=str(reminder_id))`; `:235` → `notify(CALENDAR_REMINDERS_SCHEDULED, "Reminders scheduled", text)`. Update `plugins/ze-calendar/tests/jobs/test_reminders.py`. `make test-calendar`.
- [x] **T025** [ENG] [US1] [BE] `apps/ze-api/tests/test_push_inventory.py`: (a) import every `push_kinds` module (`ze_api`, `ze_automation`, `ze_worldstate`, `ze_correlation`, `ze_memory`, `ze_proactive`, and the four plugins) and assert `registered_push_kinds()` equals an `EXPECTED` dict of `event_type → (push_class, urgency)` copied from the spec inventory (31 entries: the 30 inventory rows plus G1 `quiet_hours_summary`); (b) AST-walk `core/`, `plugins/`, `apps/ze-api/ze_api/` (skip `tests/`, `.venv`) and fail on any `Call` whose func is `Attribute(attr="push" | "push_notification")` with a receiver whose source text contains `notifier` or `interface`, except in `ze_proactive/notifier.py` and `ze_api/interface/native.py`. Confirm (b) fails when a dummy `self._notifier.push("x")` is added.

**Checkpoint**: `make test-proactive test-agents test-priority test-worldstate test-correlation test-automation test-memory test-personal test-finance test-messenger test-calendar test` green.

---

## Phase 4: User Story 2 — quiet hours hold and release (P1)  [ENG]

**Goal**: held pushes are silent until quiet hours end, then released once with one buzz.
**Independent test**: T026 job tests; T027 acceptance day.

- [x] **T026** [ENG] [US2] [BE] Fail-first `core/contracts/ze-proactive/tests/test_release_held_job.py` (inside quiet → no call; outside with held → `deliver_held` called once; store error logged, no raise), then `ze_proactive/jobs/release_held.py::QuietHoursReleaseJob(notifier)` (`job_id = "quiet_hours_release"`, `run()` calls `notifier.deliver_held()`), registered in `ze_proactive/bootstrap.py::register_notification_jobs` with cron `proactive.notifications.release_cron` default `*/5 * * * *` and `catch_up=False`. Pass the notifier into `register_notification_jobs` (update its caller in `apps/ze-api/ze_api/compose.py` or `container.py`).
- [x] **T027** [ENG] [US2] [BE] Acceptance `apps/ze-api/tests/test_governor_acceptance.py` (SC-001): real `ProactiveNotifier`, in-memory fakes for `NotificationStore`, `PushLogStore` (claims with unique `(event_type, key)` and a 24 h count), `InterruptionSettingsStore` (23:00–08:00 `Europe/Lisbon`), a recording `AppInterface` (records chat messages and `buzz`), a controllable clock. Script a day: 2 requested (06:30, 15:00), 6 accountability (01:00, 03:00, 10:00, 12:00, 18:00, 23:30), 9 discretionary (00:30, 02:00, 09:00, 10:30, 11:00, 13:00, 14:00, 16:00, 17:00, each a distinct key); run `deliver_held()` at 07:55 and 08:05 and 23:59. Assert every SC-001 number; assert no buzz between 23:00–08:00 except requested; assert exactly one summary at 08:05.

---

## Phase 5: User Story 3 — quiet hours in Settings (P1)  [JR-B; T029 is ENG]

**Goal**: the user edits quiet hours in ze-web; REST and client exist.
**Independent test**: REST tests; vitest form tests.

- [x] **T028** [JR] [US3] [BE] `apps/ze-api/ze_api/api/schemas.py`: `QuietHoursResponse`, `QuietHoursUpdate` (validators per contracts/quiet-hours-rest.md; IANA check with `zoneinfo.ZoneInfo`), add `push_class: str`, `delivery: str` to `NotificationItem`. `api/dependencies.py`: `get_interruption_settings_store` (from `container.interruption_settings_store`) and `get_notifier`. `api/routes/notifications.py`: `GET` and `PUT /quiet-hours` (declare them **before** `/{notification_id}/read`; `response_model`, `summary`, `description`, `operation_id` exactly as in the contract; `active_now` via `is_active`, `held_count` via `notification_store.count_held()`, `max_discretionary_per_day` via the notifier). Tests `apps/ze-api/tests/api/test_quiet_hours_routes.py`: empty → defaults; round trip; 422 for start==end, bad time, bad zone, enabled without fields (assert `loc`); list notifications includes `push_class`/`delivery`. `make test`.
- [x] **T029** [ENG] [US3] [PLATFORM] `apps/ze-api/ze_api/interruption_domain.py` (`DataDomain("proactive.interruption_settings", …)` modeled on `feedback_domain.py`, table `interruption_settings`) and add it to `all_domains` in `container.py`; test in `apps/ze-api/tests/test_interruption_domain.py` (export/delete/count SQL).
- [x] **T030** [JR] [US3] [WEB] After T028: `make codegen`; commit `packages/ze-client/src/generated/**`. Confirm `getQuietHours`, `updateQuietHours` and the `NotificationItem` fields exist; `make typecheck-web`.
- [x] **T031** [JR] [US3] [WEB] `apps/ze-web/src/entities/quiet-hours/api/useQuietHoursQuery.ts` (key `["quiet-hours"]`, SDK `getQuietHours`), `api/useUpdateQuietHoursMutation.ts` (SDK `updateQuietHours`; on success invalidate `["quiet-hours"]` and the notification queries' keys from `entities/notification/api`), `index.ts` exports. Follow `entities/notification/api/*` for client and error handling.
- [x] **T032** [JR] [US3] [WEB] `apps/ze-web/src/widgets/quiet-hours-settings/ui/QuietHoursSettings.tsx` + `index.ts`: switch (existing `shared/ui` toggle or checkbox), two `Input type="time"`, timezone `Input` with a `datalist` from `Intl.supportedValuesOf?.("timeZone")`, default `Intl.DateTimeFormat().resolvedOptions().timeZone` when the server value is null; read-only line "Ze sends at most {n} unprompted nudges a day. Reminders you set always come through."; status line "Quiet hours are on now · {held} held" / "Quiet hours are off now"; Save button; field errors from 422 `detail[].loc`. Mount it inside the "Notifications" block of `widgets/settings-workspace/ui/SettingsWorkspace.tsx` above the ntfy button. Test `QuietHoursSettings.test.tsx` (vitest + Testing Library, mocked hooks): empty state shows browser zone; save calls mutation with values; 422 shows message under the field. `make test-web && make typecheck-web`.

---

## Phase 6: User Story 4 — catch-up for missed runs (P2)  [ENG; T036, T038 are [JR]]

**Goal**: scheduled work missed while the host was down or asleep runs once.
**Independent test**: pure catch-up tests; scheduler tests with fake run store and clock.

- [x] **T033** [ENG] [US4] [BE] Fail-first `core/contracts/ze-proactive/tests/test_catchup.py` (daily `0 8 * * *`: last yesterday 08:00, now 10:00 → today 08:00; now 07:00 → None; three days down → only the latest; `*/5 * * * *` with a week down hits the cap and returns a time ≤ now; naive datetime → `CatchUpError`), then `ze_proactive/catchup.py::missed_fire_time` per contracts/catch-up.md.
- [x] **T034** [P] [ENG] [US4] [BE] `ze_proactive/job_run_store.py::JobRunStore(pool)` (`record_start`, `record_finish`, `get_all`; errors logged and swallowed) + `tests/test_job_run_store.py`.
- [x] **T035** [ENG] [US4] [BE] `ze_proactive/scheduler.py` per contracts/catch-up.md: constructor `(run_store=None, clock=…)`; `register`/`add_cron_job` gain `catch_up`, `catch_up_max_age_hours`; wrapper records runs; `misfire_grace_time=None`; `start()` schedules catch-ups. Tests `tests/test_scheduler.py` with a fake run store and a fake APScheduler (or the real `AsyncIOScheduler` not started, inspecting `get_jobs()`): missed → one `":catchup"` job; no row → none; age limit honoured; staggering 5 s; wrapper records ok/error and re-raises. In `apps/ze-api/ze_api/container.py` construct `ProactiveScheduler(run_store=JobRunStore(pool))`.
- [x] **T036** [JR] [US4] [BE] `plugins/ze-personal/ze_personal/plugin.py`: register the briefing with `catch_up_max_age_hours=float(cfg.get("catch_up_max_age_hours", 6))` from `proactive.briefing`. Test in `plugins/ze-personal/tests/` that the scheduler receives it. (Config key added by T013.)
- [x] **T037** [ENG] [US4] [BE] `core/automation/ze-automation/ze_automation/workflow/scheduler.py`: `misfire_grace_time=None` in `schedule_job`, `schedule_at`, `_add_job`; in `start()` after `recover_stale`, catch up each enabled scheduled workflow per contracts/catch-up.md using the latest `list_executions(workflow.id, limit=1)` `started_at`. Tests in `core/automation/ze-automation/tests/` with a fake store: missed → `trigger_now` once; no executions → none; not missed → none.
- [x] **T038** [JR] [US4] [BE] `plugins/ze-calendar/ze_calendar/reminders/calendar.py`: `replay_unsent()` fires overdue reminders via `asyncio.create_task(self.fire_reminder(r.id, late_from=r.fire_at))` and schedules future ones as today; `fire_reminder(reminder_id, late_from: datetime | None = None)` appends `f" (late, was due {local:%H:%M})"` using the user timezone already available to the service (if none, `Settings.timezone` passed in by `plugin.py`; ask ENG before touching `plugin.py` lines outside the service construction). Test: one past + one future reminder → one immediate `notify` with the late suffix, one `schedule_at`. `make test-calendar`.

---

## Phase 7: User Story 5 — bell shows held and suppressed (P3)  [JR-B]

- [x] **T039** [JR] [US5] [WEB] `apps/ze-web/src/widgets/notification-bell/ui/NotificationBell.tsx`: show a small muted label under the title: `held` → "Held for quiet hours", `suppressed` → "Not pushed: daily limit"; nothing for other values. Extend `NotificationBell.test.tsx` with one case per value. `make test-web`.

---

## Phase 8: Docs and polish  [DOCS: JR-B or Docs Steward; T048–T049 ENG]

Each docs task follows the `doc-style` skill (`.claude/skills/doc-style/SKILL.md`) for `docs/*.md` and root `README.md`.

- [x] **T040** [P] [JR] [DOCS] `core/contracts/ze-proactive/README.md`: governor (classes, urgency, budget, quiet hours, release job, catch-up), new modules table rows, `zpro004` tables; delete any mention of `push()`.
- [x] **T041** [P] [JR] [DOCS] `docs/scheduled-jobs.md`: new section "Interruption governor" (the three classes with the inventory as a table of kinds, budget 5 and what it covers, quiet hours and hold/release, `quiet_hours_release` job, catch-up rules and `catch_up_max_age_hours`); update the attention-arbitration section (~line 441: arbitration no longer claims; budget covers every discretionary push) and each job paragraph that says "pushed via `ProactiveNotifier`" to name its class.
- [x] **T042** [P] [JR] [DOCS] `docs/native-interface.md`: ntfy priorities (low 2 / normal 3 / high 5), `buzz`, quiet-hours rule for reply and confirmation ntfy, `notification` frame fields `push_class`/`delivery`, the two quiet-hours REST routes.
- [x] **T043** [P] [JR] [DOCS] `docs/configuration.md`: `proactive.budget.max_pushes_per_day` (default 5, scope), `proactive.briefing.catch_up_max_age_hours`, `proactive.notifications.release_cron`; note quiet hours are a Settings value, not YAML.
- [x] **T044** [P] [JR] [DOCS] `docs/sdk.md` (import line ~16, table ~425: `PushKind`, `notify` only), `docs/extending-ze.md` (~341–360 example rewritten with a `PushKind` and `notify(..., budget_key=…)`, plus one sentence on choosing a class), `packages/ze-sdk/README.md` (`proactive.py` row).
- [x] **T045** [P] [JR] [DOCS] `docs/goals.md` (~124, ~134, ~174), `docs/workflows.md` (~106 plus workflow catch-up), `docs/finance.md` (finance nudges are discretionary), `docs/frontend.md` (Settings › Notifications quiet hours; bell labels), `docs/deployment.md` (laptop hosts: catch-up and misfire behaviour).
- [x] **T046** [P] [JR] [DOCS] Root `README.md` (~62: loop pushes share the discretionary budget; ~104: classes, quiet hours, catch-up), `docs/cognitive-architecture.md` and `docs/architecture.md` (executive "decide when to interrupt" and governance "inhibit" now cover every push), `docs/package-architecture.md` (ze-proactive description), `core/cognition/ze-worldstate/README.md`, `core/cognition/ze-correlation/README.md`, `core/arbitration/ze-priority/README.md` (budget lines).
- [x] **T047** [JR] [DOCS] `AGENTS.md`: ze-proactive tree line (governor, quiet hours, catch-up), migration ownership row for `zpro` (+ `interruption_settings`, `proactive_job_runs`), phase table row 177; `specs/README.md` index row; `specs/arch/executive-function.md` §7 table row 177 → "Implemented (spec `phases/177-interruption-governor`)" and §8 D4 "user's hours: set in Settings"; `specs/arch/attention-arbitration.md` status note (budget now covers every discretionary push; arbitration no longer claims); spec.md status → Implemented.
- [x] **T048** [ENG] [DOCS] Coverage check: `git diff --stat main...HEAD` and confirm every changed public behaviour has its doc from T040–T047 and every file in those tasks changed; list any gap in the floor report.
- [x] **T049** [ENG] [PLATFORM] Gates: `make lint`, `make test-py`, `make test-web`, `make typecheck-web`; run quickstart.md manual steps 1–8 (or ask Tally); post results in the Handoffs note; run the speckit after-implement hook.

---

## Dependencies

- T001 → T002 → T003 → T004 → (T005, T006, T007, T008, T009 in parallel) → T010 → T011 → T012 → T013 → **checkpoint**.
- Phase 3: T014 before T017–T019 (they import `ze_automation.push_kinds`). T015, T016, T017 (ENG) and T018–T024 (JR) in parallel after the checkpoint. T025 last in Phase 3.
- Phase 4: T026 after T010 and T013; T027 after Phase 3 and T026.
- Phase 5: T028 after T013; T029 after T013; T030 after T028; T031 after T030; T032 after T031.
- Phase 6: T033 → T035; T034 → T035; T036 after T035; T037 after T033; T038 after T024.
- Phase 7: T039 after T030.
- Phase 8: each doc task after the code it describes; T048 → T049 last.

## Parallel examples

- After the checkpoint: ENG on T016 while JR-A runs T018, T020, T021, T022 and JR-B runs T028.
- Phase 6: T033 and T034 together; T036/T038 (JR) while ENG does T037.

## Implementation strategy

MVP = Phases 0–4 (governor, every site classified, quiet-hours hold/release with the setting writable through REST by T028). Then Phase 5 web form, Phase 6 catch-up, Phase 7 bell labels, Phase 8 docs. Each phase leaves all touched package suites green.

---

## Lanes

### Lane ENG (Claude Sonnet, lane lead)

Tasks: T001–T017, T025–T027, T029, T033–T035, T037, T048, T049.

Owns:
- `core/contracts/ze-proactive/**` (code, migration, tests, except `README.md`)
- `core/contracts/ze-agents/ze_agents/interface/types.py`
- `packages/ze-sdk/ze_sdk/proactive.py`
- `apps/ze-api/ze_api/{container.py,compose.py,push_kinds.py,interruption_domain.py,interface/native.py,api/websocket/confirmation.py,api/websocket/__init__.py}`, `apps/ze-api/config/config.yaml`, ze-api tests `tests/{test_push_inventory.py,test_governor_acceptance.py,test_interruption_domain.py,interface/test_native.py,api/test_workspace_followthrough.py,api/test_ws_conformance.py,agents/test_bootstrap.py}`
- `core/arbitration/ze-priority/ze_priority/arbitration.py` + tests; `core/cognition/ze-worldstate/ze_worldstate/{surfacing.py,push_kinds.py}` + tests; `core/cognition/ze-correlation/ze_correlation/{push.py,push_kinds.py}` + tests
- `core/automation/ze-automation/ze_automation/{push_kinds.py,bootstrap.py,agents/goals/tools.py,goals/executor.py,workflow/scheduler.py}` + their tests

Integrates the JR lanes, runs the full gates, asks Tally (QA) for the quickstart run, sets the floor to review and reports to the Maestro.

### Lane JR-A (OpenCode flash): call sites in jobs and plugins

Tasks: T018–T024, T036, T038.

Owns:
- `core/automation/ze-automation/ze_automation/jobs/{cost_anomaly,accountability,goal_narrative,stuck_goals,goal_suggestion}.py` and `core/automation/ze-automation/tests/proactive_jobs/**`
- `core/cognition/ze-memory/ze_memory/{dream/job.py,push_kinds.py}` and the dream job test
- `plugins/ze-personal/ze_personal/{push_kinds.py,jobs/briefing.py,jobs/insights.py,jobs/contacts.py,plugin.py}` and `plugins/ze-personal/tests/jobs/**`
- `plugins/ze-finance/ze_finance/{push_kinds.py,jobs/recurring.py}` and its tests
- `plugins/ze-messenger/ze_messenger/{push_kinds.py,inbound/processor.py}` and its tests
- `plugins/ze-calendar/ze_calendar/{push_kinds.py,reminders/store.py,reminders/calendar.py}` and `plugins/ze-calendar/tests/**`

Order: starts on ENG's "foundation landed" message; T018/T019 also wait for T014. T036 waits for T035; T038 after T024.

### Lane JR-B (OpenCode flash): REST, web, docs

Tasks: T028, T030–T032, T039, then T040–T047 (unless a Docs Steward is staffed, who then takes T040–T047).

Owns:
- `apps/ze-api/ze_api/api/{schemas.py,dependencies.py,routes/notifications.py}`, `apps/ze-api/tests/api/test_quiet_hours_routes.py`
- `packages/ze-client/src/generated/**`
- `apps/ze-web/src/entities/quiet-hours/**`, `apps/ze-web/src/widgets/quiet-hours-settings/**`, `apps/ze-web/src/widgets/settings-workspace/ui/SettingsWorkspace.tsx`, `apps/ze-web/src/widgets/notification-bell/**`
- Docs: `docs/**`, `README.md`, package READMEs listed in T040–T046, `AGENTS.md`, `specs/README.md`, `specs/arch/{executive-function,attention-arbitration}.md`, this phase's `spec.md` status line

Order: T028 starts on "foundation landed"; T030 after T028; T039 after T030. Docs after the code they describe (T041 after Phase 6; T042 after T011 and T028; T044 after T012).

### Cross-lane files

A lane that needs a change in another lane's file asks the ENG lead. Known touch points: `ze_automation/push_kinds.py` (ENG, T014) is imported by JR-A's job files; `container.py` (ENG) provides `interruption_settings_store` and `notifier` used by JR-B's dependencies (T013 provides both); `config.yaml` (ENG, T013) carries the briefing key JR-A reads in T036.
