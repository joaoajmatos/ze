# Feature Specification: Interruption Governor (part 1)

**Feature Branch**: `177-interruption-governor`

**Created**: 2026-10-12

**Status**: Implemented

**Input**: User description: "Phase 177, governor part 1 (findings F5 and F11; decision D4 of `specs/arch/executive-function.md`). Today only loop and hypothesis pushes share the daily push budget (Phase 123); about fifteen other push sites are ungoverned; there are no quiet hours and no urgency tiers; cron jobs have no catch-up. Decided by the user: (a) user-requested timed alerts (reminders, calendar prep) are exempt from the discretionary budget and always fire; (b) every discretionary push goes through one governor with an urgency tier and the shared budget; (c) quiet hours are a user setting editable in the ze-web Settings UI (persisted, REST under `/api/v0`, typed client via codegen, a settings form), with discretionary pushes held during quiet hours; (d) cron catch-up for missed runs. Inventory every push site and classify each as exempt or discretionary. No calibrated interrupt Score yet (Phases 178–179); tiers are rule-based."

**Governed by**: [`specs/arch/executive-function.md`](../../arch/executive-function.md) (F5, F8 boundary, F11, Option 3, §8 D4, D7), [`specs/arch/attention-arbitration.md`](../../arch/attention-arbitration.md), [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md) (executive and governance functions), [`specs/arch/ntfy-push-notifications.md`](../../arch/ntfy-push-notifications.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md). Phases [105](../105-notification-center/spec.md), [113](../113-hardening-sweep/spec.md), [116](../116-workspace-follow-through/spec.md), [123](../123-attention-arbitration/spec.md).

**Depends on**: nothing hard. Phase 170 (executive repair) edits three of the same files (`ze_priority/arbitration.py`, `ze_worldstate/surfacing.py`, `ze_correlation/push.py`) in different functions. Whichever phase lands second rebases and re-reads the other's diff of those files (see Assumptions).

**Does not change**: push *ranking* across sources (still `PriorityView` for loops and hypotheses; ranking every discretionary source is 178–179), the loop and hypothesis push bars (relevance, novelty, grounding), any System One question or bar, the loop store and its transitions (169–172), the briefing content (F7, Phase 176), outcome capture on pushes (F8, Phase 178), calendar- or activity-aware availability (Option 3 scope (b), later), and the WebSocket single-connection rule.

**Doctrine functions served**: *executive* (decide when to interrupt or initiate) and *governance* (inhibit what Ze says unprompted). The governor produces no claim. A push class is a rule-based routing label, not a `Priority` claim, and never licenses a stronger claim kind.

---

## Overview

Ze interrupts the user through one transport (`ProactiveNotifier` → `NativeAppInterface.push` → chat message + `notification` frame + ntfy when the client is offline). Phase 123 put two of the callers, loop drift and hypothesis pushes, under a shared daily budget of 3. Everything else calls the notifier directly: 30 inventory rows in 9 packages (inventory below; some rows cover several call lines). There is no notion of which pushes the user asked for and which Ze chose to send, no quiet time, and urgency is `"normal"` almost everywhere. `ProactiveScheduler` keeps jobs in memory with APScheduler defaults, so a cron minute that passes while the host is down or asleep is lost. Calendar event reminders that come due while the server is down are re-added on startup as past-dated jobs, and APScheduler drops them.

The inventory also found two silent defects:

- **Messenger relay never sends.** `InboundMessageProcessor` calls `ProactiveNotifier.push(title=…, body=…, tags=…)`. `push` takes `(content, *, format, urgency)`, so the call raises `TypeError`. "Message from a known contact" has never been delivered.
- **Goal reuse notice never sends.** `GoalExecutor._push_reuse_notice` calls `self._push(...)` without `await`. The coroutine is created and dropped.

This phase adds one **interruption governor** in `ze-proactive`. Every proactive push declares a **push kind**: a class (`requested`, `accountability`, `discretionary`) and an urgency (`low`, `normal`, `high`). The governor applies one rule set: requested alerts always fire; during the user's quiet hours everything else is held and released as a batch when quiet hours end; only discretionary pushes claim the shared daily budget. Quiet hours are a user setting with a REST surface and a form on the Settings page. Cron jobs record their runs and catch up once after downtime.

## Clarifications

### Session 2026-10-12

Questions sent to the user through the Maestro on 2026-10-12 (logged in the floor's Handoffs note). **The user accepted every recommendation (Q1–Q6 = A) on 2026-10-13.**

- Q1: What happens to a push during quiet hours? → A (**user, 2026-10-13**): **Defer.** The push is recorded at once in the notification bell, silently (no chat message, no ntfy). When quiet hours end, Ze posts the held items to chat without a buzz, then sends one summary that buzzes: "While quiet hours were on, I held N updates." Rejected alternatives: drop (bell row only); queue into the morning briefing (couples to a plugin job, lost when the briefing is off, once a day).
- Q2: What breaks through quiet hours? → A (**user, 2026-10-13**): **Only `requested`** (user reminders and calendar event reminders). Everything else waits, including approval requests, failures, cost anomalies, and the offline ntfy buzz for a chat reply (the reply is still saved and replayed on connect).
- Q3: Quiet-hours default and the user's hours? → A (**user, 2026-10-13**): **No default.** Quiet hours are off until the user sets them in Settings › Notifications. The timezone field is prefilled from the browser. The user's own hours, 23:00–08:00 `Europe/Lisbon`, are used only in the docs example and the acceptance fixture; nothing ships enabled.
- Q4: How are the contested sites classified? → A (**user, 2026-10-13**): the morning briefing, the weekly accountability report and the weekly goal narrative are **accountability** (scheduled reports the user switched on in config: never budgeted, held in quiet hours). The messenger inbound relay, stuck goals, insights, goal suggestions, contact review, finance nudges, dream review, goal overlap and reuse notices, loop pushes and hypothesis pushes are **discretionary**.
- Q5: Budget size? → A (**user, 2026-10-13**): `proactive.budget.max_pushes_per_day` default **5** (was 3), still in `config.yaml`, shown read-only in the Settings form. Discretionary sources other than loops and hypotheses claim first come, first served; cross-source ranking is 178–179.
- Q6: Catch-up scope? → A (**user, 2026-10-13**): (1) every `ProactiveScheduler` cron job; (2) scheduled user workflows; (3) overdue calendar event reminders fire on startup, marked late. Catch-up output still goes through the governor.

---

## Push-site inventory *(mandatory for this phase)*

Every call site that reaches `AppInterface.push` or ntfy, at `main` 0b9845b1. "Kind" is the new `PushKind.event_type`. Paths are relative to the package root. After this phase each row is a module-level `PushKind` and a call to `ProactiveNotifier.notify`.

### Requested: exempt from the budget and from quiet hours

| # | Site | What it sends | Kind | Urgency |
|---|---|---|---|---|
| R1 | `plugins/ze-calendar/ze_calendar/reminders/store.py:101` `fire_reminder` | A reminder the user set ("⏰ call mum") | `user_reminder` | high |
| R2 | `plugins/ze-calendar/ze_calendar/reminders/calendar.py:164` `CalendarReminderService.fire_reminder` | Prep alert before a calendar event | `calendar_reminder` | high |

### Accountability: not budgeted; held during quiet hours

| # | Site | What it sends | Kind | Urgency |
|---|---|---|---|---|
| A1 | `apps/ze-api/ze_api/api/websocket/confirmation.py:181` `push_confirmation_ntfy` | "Ze needs your approval" for an action in a turn | `confirmation_request` | high |
| A2 | `apps/ze-api/ze_api/api/websocket/confirmation.py:221` `confirmation_timeout` | The approval request expired | `confirmation_timeout` | low |
| A3 | `apps/ze-api/ze_api/container.py:175` `_NotifierPushSender.send_completion` | A detached workspace run finished | `workspace_run_completed` | normal |
| A4 | `core/automation/ze-automation/ze_automation/bootstrap.py:268` workflow failure handler | A scheduled workflow failed | `workflow_failure` | high |
| A5 | `core/automation/ze-automation/ze_automation/agents/goals/tools.py:211` | Proposed plan for a goal the user just asked for, with Start/Cancel | `goal_plan_proposed` | high |
| A6 | `core/automation/ze-automation/ze_automation/goals/executor.py` 282, 292, 378, 429, 683, 796 | Goal paused, milestone failed, goal stopped, replan or steer failed | `goal_attention_needed` | high |
| A7 | `…/goals/executor.py` 660, 774, 817 | Applying the user's direction; adapting the plan; the adapted plan | `goal_plan_adapted` | normal |
| A8 | `…/goals/executor.py:322` | Milestone done (n/total) | `goal_milestone_done` | normal |
| A9 | `…/goals/executor.py:474` `_push_retrospective` | Goal completed, with retrospective | `goal_completed` | normal |
| A10 | `…/goals/executor.py:866` + `:886` `_fire_gate` (a push with actions plus a separate `notify`) | Checkpoint needs approval | `goal_gate` | high |
| A11 | `core/automation/ze-automation/ze_automation/jobs/cost_anomaly.py:116` | One agent run cost far above its baseline | `cost_anomaly` | high |
| A12 | `core/automation/ze-automation/ze_automation/jobs/accountability.py:50` | Weekly accountability report | `accountability_narrative` | normal |
| A13 | `core/automation/ze-automation/ze_automation/jobs/goal_narrative.py:88` | Weekly goal progress narrative | `goal_narrative` | normal |
| A14 | `plugins/ze-personal/ze_personal/jobs/briefing.py:121` | Morning briefing | `morning_brief` | normal |
| A15 | `plugins/ze-calendar/ze_calendar/reminders/calendar.py:235` | "I scheduled these reminders for event X" (after calendar sync) | `calendar_reminders_scheduled` | low |

### Discretionary: claims the shared budget; held during quiet hours

| # | Site | What it sends | Kind | Budget key | Urgency |
|---|---|---|---|---|---|
| D1 | `core/cognition/ze-worldstate/ze_worldstate/surfacing.py:203` `LoopSurfacer.send` | A drifting loop ("you mentioned X…") | `loop_drift` | `loop:<loop_id>` | normal |
| D2 | `core/cognition/ze-correlation/ze_correlation/push.py:176` `CorrelationPushCandidateSource.send` | A cross-domain connection | `hypothesis` | `hypothesis:<id>` | normal |
| D3 | `core/automation/ze-automation/ze_automation/jobs/stuck_goals.py:39` + `:50` (one push with actions plus one `notify` per goal) | Goals idle or blocked at a gate | `stuck_goal` | `stuck_goals:<run date>` | normal |
| D4 | `core/automation/ze-automation/ze_automation/jobs/goal_suggestion.py:101` + `:125` (push with actions plus `notify`) | A new goal idea | `goal_suggestion` | `goal_suggestion:<id>` | normal |
| D5 | `core/automation/ze-automation/ze_automation/agents/goals/tools.py:126` | Two goals overlap | `goal_overlap` | `goal_overlap:<new_goal_id>` | normal |
| D6 | `…/goals/executor.py:631` `_push_reuse_notice` (**never awaited today**) | Prior work from another goal was reused | `goal_reuse` | `goal_reuse:<milestone_id>` | low |
| D7 | `core/cognition/ze-memory/ze_memory/dream/job.py:172` (only when `review_notifications_enabled`) | Dream insights await review | `dream_review` | `dream:<run_id>` | low |
| D8 | `plugins/ze-personal/ze_personal/jobs/insights.py:163` | A weekly insight | `insight` | `insight:<insight_id>` | normal |
| D9 | `plugins/ze-personal/ze_personal/jobs/contacts.py:43` | "Add this person to your contacts?" | `contact_review` | `contact:<person_id>` | low |
| D10 | `plugins/ze-finance/ze_finance/jobs/recurring.py:101` | No new transactions; upload a statement | `finance_stale_nudge` | `finance_stale:<account_id>:<date>` | low |
| D11 | `plugins/ze-finance/ze_finance/jobs/recurring.py:120` | New recurring expenses found | `finance_recurring_new` | `finance_new:<account_id>:<date>` | normal |
| D12 | `plugins/ze-finance/ze_finance/jobs/recurring.py:130` | A recurring charge changed price | `finance_price_change` | `finance_price:<recurring_id>:<amount>` | normal |
| D13 | `plugins/ze-messenger/ze_messenger/inbound/processor.py:148` (**raises `TypeError` today**; fixed with a fail-first regression test) | Message from a known contact | `inbound_message` | `inbound:<channel_type>:<message_id>` | normal |

### Governor-owned

| # | Site | What it sends | Kind | Urgency |
|---|---|---|---|---|
| G1 | `core/contracts/ze-proactive/ze_proactive/notifier.py` `deliver_held` (new) | "While quiet hours were on, I held N updates." | `quiet_hours_summary` (accountability) | highest held urgency at send time; declared `normal` |

### Not proactive pushes (conversation delivery); only the quiet-hours buzz rule applies

| # | Site | Behaviour after this phase |
|---|---|---|
| C1 | `apps/ze-api/ze_api/interface/native.py:166` `_send_message` ntfy hop when the client is offline (chat replies, retry replies, workspace follow-up turn replies from `container.py:148`, goal action replies from `goal_actions.py:260`) | Message is saved and replayed as today. The ntfy buzz is skipped during quiet hours. |
| C2 | `apps/ze-api/ze_api/interface/native.py:218` `send_confirmation` ntfy hop | Frame is sent as today. The ntfy buzz is skipped during quiet hours. |

No other module calls `AppInterface.push`, `ProactiveNotifier.push`, `ProactiveNotifier.push_notification` or `ze_notifications.Notifier.push`. A test enforces this (FR-004).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every push is classified and only discretionary ones share the budget (Priority: P1)

Ze has several things to say today: a reminder the user set for 15:00, a workflow failure, a drifting loop, two goal ideas, three weekly insights and a contact to review. The reminder and the workflow failure arrive when they happen. The discretionary items share one daily budget; once it is spent, the rest go to the notification bell without a push.

**Why this priority**: This is the core of D4: one policy for every push, so a reminder never competes with a nudge and the nudges cannot flood the user.

**Independent Test**: With a fake interface, fake push log and fake stores, call `ProactiveNotifier.notify` with one kind of each class; exhaust the budget; assert outcomes, interface calls and stored rows.

**Acceptance Scenarios**:

1. **Given** a `requested` kind, **When** it is sent with the budget already spent, **Then** it is delivered with a buzz and claims no budget.
2. **Given** an `accountability` kind, **When** it is sent with the budget spent, **Then** it is delivered and claims no budget.
3. **Given** `max_pushes_per_day: 5` and five discretionary pushes delivered in the last 24 h, **When** a sixth discretionary push is sent, **Then** the outcome is `suppressed_budget`, a bell row is stored with delivery `suppressed`, and there is no chat message and no ntfy.
4. **Given** a discretionary push whose budget key was already claimed, **When** it is sent again, **Then** the outcome is `duplicate` and nothing is stored or sent.
5. **Given** the interface raises during delivery of a discretionary push, **Then** the budget claim is released and the row's delivery is `failed`.
6. **Given** a discretionary kind and no budget key, **Then** `notify` raises `PushPolicyError` (a `ZeError`).
7. **Given** a known contact emails the user, **When** the messenger processor handles it, **Then** an `inbound_message` push goes through the governor (the `TypeError` path is gone).
8. **Given** a goal milestone reuses earlier work, **Then** the `goal_reuse` push is awaited and governed.
9. **Given** the loop and hypothesis arbitration job, **When** it runs, **Then** it ranks as today, checks that budget remains, and sends the top candidate through the governor; it no longer claims the budget itself.

---

### User Story 2 - Quiet hours hold pushes and release them when quiet hours end (Priority: P1)

The user sets quiet hours 23:00–08:00 in Europe/Lisbon. At 02:00 a drifting loop and a workflow failure come up; at 06:30 a reminder the user set fires. The reminder buzzes at 06:30. The other two appear in the bell silently. At 08:00 Ze posts them to chat and sends one buzz: "While quiet hours were on, I held 2 updates."

**Why this priority**: "Nothing at night" is the most visible promise of the governor (Option 3: "User notices").

**Independent Test**: Pure-function tests for the quiet-hours window (same-day window, window across midnight, DST change days); governor tests with a fixed clock; release-job test with held rows.

**Acceptance Scenarios**:

1. **Given** quiet hours 23:00–08:00 and the local time 02:00, **When** an accountability or discretionary push is sent, **Then** the outcome is `held`, a bell row with delivery `held` is stored, a silent `notification` frame is sent, and there is no chat message and no ntfy.
2. **Given** the same window, **When** a `requested` push is sent at 06:30, **Then** it is delivered with a buzz.
3. **Given** a held discretionary push, **Then** it claimed a budget slot at hold time (the daily cap bounds what is released).
4. **Given** held rows and the local time 08:00 or later, **When** the release job runs, **Then** each held item is delivered to chat in order of urgency (high first) then age, without ntfy and with its actions; the rows become `released`; then one summary message is delivered with one ntfy at the highest urgency among the held items.
5. **Given** quiet hours are disabled, **Then** nothing is held.
6. **Given** the client is offline at 02:00 inside quiet hours, **When** a chat reply or a confirmation frame is delivered, **Then** it is saved and sent as today but no ntfy buzz is sent.
7. **Given** a release job run while still inside quiet hours, **Then** it releases nothing.
8. **Given** the server was down at 08:00, **When** it starts at 09:30, **Then** the next release run (within 5 minutes) releases the held items.

---

### User Story 3 - The user sets quiet hours in Settings (Priority: P1)

On the Settings page, under Notifications, the user sees a quiet-hours form: an on/off switch, a start time, an end time and a timezone (prefilled from the browser), plus a read-only line with today's discretionary budget ("Ze sends at most 5 unprompted nudges a day"). Saving persists the setting; reloading shows it; a status line says whether quiet hours are active now and how many updates are held.

**Why this priority**: Decision (c): the setting is the user's, not config.

**Independent Test**: REST tests for `GET`/`PUT /api/v0/notifications/quiet-hours` (validation, round trip); vitest for the form (renders, validates, calls the mutation, shows errors).

**Acceptance Scenarios**:

1. **Given** no saved setting, **When** the user opens Settings, **Then** the switch is off, the time fields are empty, and the timezone shows the browser's IANA zone.
2. **Given** the user enables quiet hours with 23:00, 08:00 and `Europe/Lisbon`, **When** they save, **Then** `PUT` returns the stored values plus `active_now` and `held_count`, and a reload shows the same values.
3. **Given** start equals end, or an unknown timezone, or enabled without times, **When** they save, **Then** the API returns 422 and the form shows the message next to the field.
4. **Given** the user disables quiet hours while items are held, **Then** the next release run releases them.

---

### User Story 4 - Missed scheduled runs catch up once (Priority: P2)

The host is a laptop. It is shut at 07:30 and opened at 10:00. The 08:00 morning briefing and the 09:00 weekly accountability report did not run. When the server starts, each job whose scheduled time passed since its last recorded run runs once. A calendar event reminder that came due while the server was down fires on startup, marked late. A scheduled user workflow that missed its run runs once.

**Why this priority**: F11 (Low/Medium). Lower than the governor, but it makes cron-only checks trustworthy on a laptop.

**Independent Test**: Pure tests for "missed fire time since last run" over cron expressions; scheduler tests with a fake run store and a fixed clock; calendar replay test with an overdue reminder; workflow scheduler test with a fake store.

**Acceptance Scenarios**:

1. **Given** a cron job `0 8 * * *` with last run yesterday 08:00 and now 10:00, **When** the scheduler starts, **Then** the job runs exactly once (not once per missed day).
2. **Given** a job with no recorded run (first start), **Then** it does not run at startup; its first scheduled run is recorded.
3. **Given** a job registered with `catch_up_max_age_hours=6` and a missed fire 7 hours ago, **Then** it does not catch up.
4. **Given** the process is suspended over a fire time and resumes, **Then** the job runs once on resume (misfire grace, coalesced).
5. **Given** an unsent calendar event reminder whose time passed while the server was down, **When** the calendar plugin starts, **Then** the reminder fires once through the governor as `calendar_reminder`, with "(late, was due HH:MM)" in the body.
6. **Given** an enabled scheduled workflow whose last execution started before its most recent scheduled time, **When** the workflow scheduler starts, **Then** it starts one execution.
7. **Given** a caught-up job that pushes during quiet hours, **Then** its push is held like any other.

---

### User Story 5 - The bell shows what was held or not pushed (Priority: P3)

In the notification bell, items that were held or suppressed by the budget carry a small label ("Held for quiet hours", "Not pushed: daily limit"), so the user can see what Ze kept back.

**Why this priority**: Honesty about inhibition (doctrine governance), and it makes the D7 weekly check ("any alert the user would have wanted but did not get") possible by eye.

**Independent Test**: vitest renders a list with each delivery value; REST test that `delivery` and `push_class` are present on list items.

**Acceptance Scenarios**:

1. **Given** a notification with delivery `suppressed`, **Then** the bell item shows "Not pushed: daily limit".
2. **Given** delivery `held`, **Then** it shows "Held for quiet hours"; after release it shows no label.

---

### Edge Cases

- **Window across midnight.** 23:00–08:00 is inside when local time ≥ 23:00 or < 08:00. A same-day window (13:00–15:00) is inside when 13:00 ≤ t < 15:00. Start equals end is rejected.
- **DST.** The window is evaluated in the stored IANA zone with `zoneinfo` on local wall-clock times. On the spring-forward day a window ending in the skipped hour ends at the first valid local time after it.
- **Timezone change.** The stored zone is authoritative. It is not changed by the server `TIMEZONE`.
- **Held items with actions** (goal suggestion, contact review, plan approval) keep their actions; they are delivered with actions at release.
- **Held confirmation requests** may expire before release (`CONFIRM_TIMEOUT_SECONDS`). The timeout notice is itself held, and both are released together. This is accepted: Q2 recommends nothing but `requested` breaks through.
- **Dedup window.** The existing `hours` dedup (same `event_type` and target within N hours) still runs first. A deduped push returns `deduped` and stores nothing.
- **Notifier without a store** (tests or early boot). `notify` logs `proactive_notify_no_store` and returns `failed`, as today.
- **Budget check failure.** If the push log is unreadable, the budget check allows the push (as today, `within_budget` fails open) and logs a warning.
- **Quiet-hours store failure.** If the setting cannot be read, the governor treats quiet hours as off and logs a warning. It never drops a push because of a settings error.
- **Release while the client is connected.** Release still posts to chat; the summary still buzzes only if the client is offline (the existing ntfy rule).
- **Very long held bodies.** Release uses the existing content splitting.
- **First-ever start** records no catch-up runs; it only records runs from then on.

---

## Requirements *(mandatory)*

### Functional Requirements

**Push kinds and the governor (`core/contracts/ze-proactive`)**

- **FR-001**: `ze_proactive` MUST define `PushClass = Literal["requested", "accountability", "discretionary"]`, `Urgency = Literal["low", "normal", "high"]`, and a frozen dataclass `PushKind(event_type, push_class, urgency, source)`. Creating a `PushKind` registers it; registering the same `event_type` twice with a different class, urgency or source MUST raise `PushPolicyError`. `registered_push_kinds()` returns the registry.
- **FR-002**: `ProactiveNotifier.notify` MUST be the only proactive send path, with the signature `notify(kind: PushKind, title: str, body: str, *, target_type=None, target_id=None, budget_key=None, actions=(), format="text", dedup_hours=None) -> PushOutcome`. `PushOutcome` is one of `delivered`, `held`, `suppressed_budget`, `duplicate`, `deduped`, `failed`.
- **FR-003**: `ProactiveNotifier.push` and `ProactiveNotifier.push_notification` MUST be deleted (hard cut). Every inventory row (R1–R2, A1–A15, D1–D13) MUST call `notify` with a module-level `PushKind` matching the inventory. Sites that today send twice (A10, D3, D4: one push with actions plus one `notify`) MUST send once, with the actions.
- **FR-004**: A test MUST fail if any module outside `ze_proactive/notifier.py` and `ze_api/interface/native.py` calls `.push(` on an `AppInterface`, a `ProactiveNotifier`, or a `ze_notifications` notifier, and MUST assert that `registered_push_kinds()` after importing every package equals the inventory's kinds and classes.
- **FR-005**: The decision MUST be a pure function `decide(kind, *, quiet_now: bool, budget_won: bool | None) -> Decision` in `ze_proactive/governor.py`, applying in order: `requested` → deliver; quiet hours active → hold; `accountability` → deliver; `discretionary` → deliver if the budget claim was won, else `suppressed_budget`. For discretionary pushes the claim is attempted before the quiet-hours check, so held discretionary pushes consume budget.
- **FR-006**: The budget MUST be the existing shared key (`ATTENTION_PUSH_EVENT_KEY`) in `push_log`, generalised: `try_claim_shared(push_log, budget_key: str, max_per_day)` and `release_shared(push_log, budget_key)` take a free-form key; `SourceKind` is deleted. A discretionary `notify` without `budget_key` MUST raise `PushPolicyError`. The claim MUST be released when delivery fails.
- **FR-007**: `notify` MUST store a `notifications` row for every outcome except `duplicate` and `deduped`, with `push_class`, `urgency`, `format`, `actions`, and `delivery` (`delivered`, `held`, `released`, `suppressed`, `failed`). `delivered` rows go through the interface as today (chat message, action frames, `notification` frame, ntfy when offline). `held` and `suppressed` rows send only a silent `notification` frame: the notifier calls `AppInterface.push` with `Notification.delivery` set to `held` or `suppressed`, and `NativeAppInterface.push` then sends the frame alone (no chat message, no action frames, no ntfy).
- **FR-008**: Urgency MUST map to ntfy priority `low` → 2, `normal` → 3, `high` → 5. `Notification.urgency` in `ze_agents.interface.types` becomes `Urgency`, and `Notification` gains `buzz: bool = True`; `NativeAppInterface.push` MUST skip ntfy when `buzz` is false.
- **FR-009**: `proactive.budget.max_pushes_per_day` default MUST be 5 (Q5), read once by `shared_push_budget`. The config comment MUST say it covers every discretionary push.
- **FR-010**: `AttentionArbitrationJob` MUST NOT claim or release budget. It MUST call `ProactiveNotifier.remaining_budget()` before ranking and return when it is 0, then send ranked candidates through `LoopSurfacer.send` / `CorrelationPushCandidateSource.send` (which call `notify` with their kinds and keys) until one returns `delivered` or `held`; it continues on `duplicate`, `failed` or no outcome (loop no longer drifting) and stops on `suppressed_budget`.

**Quiet hours (`core/contracts/ze-proactive`, `apps/ze-api`, `apps/ze-web`)**

- **FR-011**: Quiet hours MUST be persisted in a single-row table `interruption_settings` (`zpro004`) with `quiet_hours_enabled`, `quiet_start` (time), `quiet_end` (time), `timezone` (IANA text), `updated_at`. No row means disabled. There is no shipped default window (Q3).
- **FR-012**: `QuietHours.is_active(now_utc) -> bool` MUST be a pure function over the stored window and zone, handling windows across midnight and DST as in Edge Cases.
- **FR-013**: During quiet hours, `NativeAppInterface` MUST skip the ntfy hop for chat replies and confirmation frames (C1, C2). It reads quiet hours through an injected async callable; a read failure counts as not quiet.
- **FR-014**: A `QuietHoursReleaseJob` (`job_id = "quiet_hours_release"`, cron `*/5 * * * *`, registered by `register_notification_jobs`) MUST, when quiet hours are not active and held rows exist, deliver each held row to the interface with `buzz=False` ordered by urgency (high, normal, low) then `created_at`, mark it `released` with `delivered_at`, then deliver one summary notification (`quiet_hours_summary`, class `accountability`, urgency = highest held urgency) with `buzz=True`. A second run with no held rows does nothing.
- **FR-015**: `GET /api/v0/notifications/quiet-hours` (`operation_id="getQuietHours"`) MUST return `QuietHoursResponse {enabled, start, end, timezone, active_now, held_count, max_discretionary_per_day}`; `start`/`end` are `"HH:MM"` or null.
- **FR-016**: `PUT /api/v0/notifications/quiet-hours` (`operation_id="updateQuietHours"`) MUST accept `QuietHoursUpdate {enabled, start, end, timezone}` and return `QuietHoursResponse`. It MUST return 422 when enabled without start, end or timezone; when start equals end; when a time is not `HH:MM` 24-hour; or when the timezone is not a valid IANA key. Both routes declare `response_model`, `summary`, `description`, require the API key, and live in `ze_api/api/routes/notifications.py`.
- **FR-017**: `NotificationItem` MUST gain `push_class` and `delivery`. `@myguyze/ze-client` MUST be regenerated (`make codegen`) and committed.
- **FR-018**: ze-web MUST add `entities/quiet-hours` (`api/useQuietHoursQuery.ts`, `api/useUpdateQuietHoursMutation.ts`, `index.ts`) and `widgets/quiet-hours-settings` (`ui/QuietHoursSettings.tsx`, `index.ts`), mounted in the Notifications section of `widgets/settings-workspace/ui/SettingsWorkspace.tsx`, using existing `shared/ui` components. The timezone defaults to `Intl.DateTimeFormat().resolvedOptions().timeZone` when the server returns null.
- **FR-019**: The notification bell item MUST show "Held for quiet hours" for `held` and "Not pushed: daily limit" for `suppressed`.

**Catch-up (`ze-proactive`, `ze-automation`, `ze-calendar`)**

- **FR-020**: `ze_proactive.catchup.missed_fire_time(cron: str, last_run_at: datetime, now: datetime, tz) -> datetime | None` MUST return the most recent scheduled fire time in `(last_run_at, now]`, or None. It uses APScheduler's `CronTrigger` in the scheduler's timezone.
- **FR-021**: Job runs MUST be recorded in `proactive_job_runs` (`zpro004`: `job_id` PK, `last_started_at`, `last_finished_at`, `last_status`). `ProactiveScheduler` MUST take an optional `JobRunStore`, wrap every cron job to record start and finish (status `ok` or `error`), and set `misfire_grace_time=None` with `coalesce=True`.
- **FR-022**: `ProactiveScheduler.add_cron_job` and `register` MUST accept `catch_up: bool = True` and `catch_up_max_age_hours: float | None = None`. On `start()`, for each catch-up job with a recorded run and a missed fire time within the age limit, it MUST schedule one run, staggered 5 seconds apart in registration order. Jobs with no recorded run MUST NOT run at start.
- **FR-023**: The morning briefing MUST register with `catch_up_max_age_hours` from `proactive.briefing.catch_up_max_age_hours` (default 6).
- **FR-024**: `WorkflowScheduler.start()` MUST, for each enabled scheduled workflow, compute `missed_fire_time(workflow.schedule, last execution start, now)` and start one execution when it is not None and a last execution exists. `WorkflowScheduler.schedule_at` and its cron jobs MUST set `misfire_grace_time=None`.
- **FR-025**: `CalendarReminderService.replay_unsent` MUST fire overdue reminders immediately (as user reminders already do), with "(late, was due HH:MM)" appended in the user's configured timezone, and schedule future ones as today.

**Migrations, docs and tests**

- **FR-026**: One migration `zpro004_interruption_governor.py` in `core/contracts/ze-proactive/ze_proactive/migrations/versions/` MUST add the `notifications` columns (`push_class`, `urgency`, `format`, `actions JSONB`, `delivery`, `delivered_at`, with CHECK constraints and an index on `delivery` where `delivery = 'held'`), create `interruption_settings` and `proactive_job_runs`. Existing rows are backfilled `push_class='accountability'`, `urgency='normal'`, `delivery='delivered'` (pre-v1; no shim).
- **FR-027**: No test MAY call OpenRouter, System One or ntfy. The governor, quiet hours, release job and catch-up MUST have unit tests with fakes; the acceptance test (SC-001) runs the whole day scenario with a fixed clock.
- **FR-028**: Public docs MUST describe push classes, quiet hours, the budget, catch-up and the settings form (see `[DOCS]` tasks).

### Key Entities

- **PushKind**: a declared kind of proactive push: `event_type`, `push_class`, `urgency`, `source`. One per inventory row.
- **PushOutcome**: what the governor did with one push.
- **Delivery**: the stored state of a bell row: `delivered`, `held`, `released`, `suppressed`, `failed`.
- **Quiet hours**: a user setting: enabled, start, end, IANA timezone.
- **Budget key**: the idempotency key a discretionary push claims in the shared daily budget.
- **Job run**: the last start and finish of a scheduled job, used for catch-up.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001** (acceptance run): In a simulated day with quiet hours 23:00–08:00 Europe/Lisbon, budget 5, and 2 requested, 6 accountability and 9 discretionary pushes spread over 24 hours: 100% of requested pushes deliver with a buzz at their time; 0 ntfy buzzes happen between 23:00 and 08:00 except requested; at most 5 discretionary pushes are delivered or held; every held item is in chat within 5 minutes after 08:00, followed by exactly one summary buzz.
- **SC-002**: 30 of 30 inventory rows go through the governor (31 registered kinds with G1); the inventory test (FR-004) passes, and it fails when a new direct `.push(` call is added.
- **SC-003**: The messenger relay (D13) and the goal reuse notice (D6) each produce a governed push in a test; both failed silently before.
- **SC-004**: The user can set, change and turn off quiet hours in Settings in under a minute; the saved value survives a reload and a server restart.
- **SC-005**: After a simulated 3-hour downtime spanning one daily job's time, that job runs exactly once at startup; with no prior run recorded it does not run.
- **SC-006**: An overdue calendar event reminder fires at startup in 100% of test cases (today 0%).
- **SC-007**: `make test-py`, `make test-web`, `make typecheck-web`, `make lint` and `make test-proactive`, `test-automation`, `test-priority`, `test-worldstate`, `test-correlation`, `test-memory`, `test-calendar`, `test-personal`, `test-finance`, `test-messenger`, `test` all pass.

---

## Assumptions

- **Merge order with Phase 170.** 170 changes `AttentionArbitrationJob.__init__`/`run` (loop push settings), `LoopSurfacer.passes_push_bar`/`inline_candidates`, and `CorrelationPushCandidateSource.eligible_candidates`. 177 changes `AttentionArbitrationJob.run` (no budget claim), `LoopSurfacer.send` and `CorrelationPushCandidateSource.send`. Whichever lands second rebases and re-reads the other's diff of these three files before editing. No 177 task touches 170's functions.
- **Phases 169, 171 and 172** touch the loop store and loop review UI, not push sites. No overlap.
- **Single user.** One settings row, one budget.
- **Server timezone.** APScheduler crons keep running in the server's local timezone, as today. Quiet hours use their own stored zone.
- **Requested pushes are always delivered**, including at 03:00 if the user set a 03:00 reminder.
- **Ranking across all discretionary sources** (not just loops and hypotheses) is out of scope; other discretionary sources claim first come, first served. 178–179 add outcome capture and a calibrated Score.
- **No new graph node, no System One call, no LLM call.**
- **Eval.** The governor runs in background jobs, not in a chat turn, so the YAML chat eval harness cannot exercise it. The acceptance check is the SC-001 pytest scenario plus the manual `quickstart.md` run against `make dev`.
