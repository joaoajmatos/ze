# Feature Specification: Push Bar and Cooldowns

**Feature Branch**: `204-push-bar-and-cooldowns`

**Created**: 2026-10-22

**Status**: Ready to implement (2026-10-26)

**Depends on**: 198 (wiring fixes B4 and B11)

**Input**: Architecture review 2026-10-22, candidate C9. Phase 198 fixes the wiring: NLI reaches the loop bar, novelty reads a key that is written, and a cooldown no longer starts after a failed push. This phase is the deepening behind those fixes. One push bar module is built once with the embedder, NLI and push history, and reads novelty from what the governor recorded. The notifier owns "at most once per key per window" (`notify(..., once_per=...)`), recorded only for `delivered` or `held`. `push_log` becomes the governor's private store. Conversational cooldowns move to `TurnSurfacing`. The workflow-failure ledger moves out of `push_log`.

## Context *(re-verified against main `5426cce1`, 2026-10-26, after 198 and 199 landed)*

Phase 198 (B4, B11) already changed the wiring this context first described. On main today:

The push bar's conditions are free functions in `ze_correlation/push.py` (280 lines): `passes_confidence` (:33), `passes_relevance` (:37), `passes_novelty` (:41) and `passes_grounding` (:69). They were extracted so that "both sources call exactly one implementation", but each caller still builds its own inputs and its own thresholds:

- **Loops.** `LoopSurfacer.passes_push_bar` (`ze_worldstate/surfacing.py:63-111`) reads novelty history with `push_log.list_recent_payloads(ATTENTION_PUSH_EVENT_KEY, 48)` (:88-90), the key the governor writes (198 B4). NLI is a constructor argument with default `None` (:52), and `passes_grounding` passes when NLI is `None` (`push.py:75`). The inline-then-push cooldown reads `push_log.was_sent_within_hours("worldstate_loop_inline:<id>", 12)` (:105-107). Thresholds come from `worldstate.push` through `LoopPushSettings` (`ze_worldstate/bootstrap.py:98-119`).
- **Hypotheses.** `CorrelationPushCandidateSource` (`push.py:142-240`) reads novelty history from `hypothesis_store.list_recently_surfaced_summaries` (:227-231), takes `embedder` and `nli_client` with default `None` (:153-154), and reads its thresholds from `_load_config(settings)` (:259) and `nli_config` (:218-220).
- `AttentionArbitrationJob` (`ze_priority/arbitration.py`) calls each source's `eligible_candidates()`, so the bar runs inside the sources, not in the job.

`push_log` (`ze_proactive/push_log_store.py`, 114 lines) mixes five unrelated uses under free-form string keys:

1. The governor's budget claims: `try_claim`, `release_claim`, `window_sent_at`, through `ze_proactive/attention_budget.py` (`ATTENTION_PUSH_EVENT_KEY`, `try_claim_shared`, `release_shared`). The claim is unique on `(event_type, idempotency_key)` with no window (`zpro003`).
2. Job cooldowns written as "was sent? notify, then log if delivered or held" (198 B11 added the outcome check):
   - `ze_automation/jobs/accountability.py:44,56-57`
   - `ze_automation/jobs/goal_narrative.py:36,93-94`
   - `plugins/ze-personal/ze_personal/jobs/briefing.py:69,124-126`
   - `ze_automation/bootstrap.py:225,246-247` (workflow-failure alert)
3. Conversational memory: inline mentions `worldstate_loop_inline:<id>` (written at `ze_priority/turn.py:215`, read at `surfacing.py:105`) and loop offers `worldstate_loop_offer:<id>` (`turn.py:129-141`).
4. The calendar reminder log `calendar_reminder:<id>` (`ze_calendar/reminders/calendar.py:193`). Nothing reads it; `calendar_reminders.mark_sent`/`mark_unsent` is already the reminder's idempotency record.
5. The workflow-failure ledger `workflow_failure:<id>`, written by the failure handler on every failure (`bootstrap.py:219`) and read through `list_workflow_failures_within_hours` (`push_log_store.py:96`) at `ze_automation/rest.py:191-192` (`/status`), `jobs/accountability.py:119` and `briefing.py:75`. Every failed run is also in `workflow_executions` (`status = 'failed'`, `completed_at`), written by `finish_execution` before the handler runs (`workflow/scheduler.py:256`).

Outside those modules, `push_log` is named by the ze-api wiring (`wiring/stores.py`, `container.py`, `agents.py` dependency map, `jobs.py`), the ze-core data domain `proactive.log` (`ze_core/bootstrap.py:256`), the ze-sdk re-export (`ze_sdk/proactive.py:5`) and the ze-personal and ze-calendar plugin constructors.

The notifier already has `notify(dedup_hours=...)` (`ze_proactive/notifier.py:87,128-136`), but no production caller uses it. Its check (`notification_store.exists_recent`, `notification_store.py:308-330`) matches any notification row for the event and target in the window, whatever its delivery outcome. The discretionary dedup is a separate concept, `budget_key`, required on every discretionary push and passed by twelve callers; a repeated key returns `duplicate` (`notifier.py:146-156`).

Five callers hand-roll `if outcome in ("delivered", "held")` after a push:

- `ze_correlation/push.py:196`
- `ze_priority/arbitration.py:77`
- `ze_automation/jobs/stuck_goals.py:50`
- `ze_finance/jobs/recurring.py:113`
- `ze_personal/jobs/insights.py:173`

The four cooldown jobs in item 2 repeat the same check.

**Blast radius** (`graphify affected --depth 2`, full list in [plan.md](plan.md)):

- `PushLogStore`: ze-api wiring (`container.py`, `stores.py`, `api/ws/commands.py` through `/status`), ze-automation (`bootstrap.py`, `jobs/accountability.py`, `jobs/goal_narrative.py`, `rest.py`), ze-proactive (`notifier.py`), ze-calendar and ze-personal (`plugin.py`), and 14 test modules.
- `passes_novelty` / `passes_grounding`: `ze_correlation/push.py`, `ze_worldstate/surfacing.py`, `ze-correlation/tests/test_push.py`.
- `ProactiveNotifier`: 18 source modules across ze-automation, ze-correlation, ze-proactive, ze-calendar, ze-finance, ze-messenger, ze-personal and ze-api.

**Added 2026-10-22 (phase 198 clarify, Q4):** the unique index on `push_log(event_type,
idempotency_key)` has no window, and `push_log` is never pruned. Loops claim `budget_key` as
`loop:<id>`, so a loop can be pushed at most once in its life: a revived loop that drifts again never
pushes. This phase owns `push_log`, so it fixes this. Decided 2026-10-26 (Clarifications, Q1).

## Clarifications

### Session 2026-10-26

- Q: How often may Ze re-push a loop that stays drifting? → A: At most once per 7 days, through `notify(once_per=OncePer(key, within))`. New config key `worldstate.push.repush_after_days`, default 7. The 48-hour novelty check and the daily budget still apply. No worldstate schema change.
- Q: A push held by quiet hours keeps its cooldown. If the later quiet-hours release fails, does the cooldown stay? → A: Yes. A failed release keeps its cooldown; the bell shows the failed row and the next window retries.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A push Ze already sent is not sent again, and a failed one is retried (Priority: P1)

The user gets the morning brief, the weekly goal narrative and accountability summaries at most once per window. A brief that failed, or that the budget suppressed, does not block the next attempt.

**Why this priority**: the cooldown is the user-visible behaviour. Today four jobs each re-implement it around `notify` (phase 198 B11 made them record only `delivered` or `held`), and two runs inside one window can both send, because the check and the record are separate statements.

**Independent Test**: drive each job through a real `ProactiveNotifier` whose interface fails the first push, then delivers, and assert one delivery and no cooldown after the failure.

**Acceptance Scenarios**:

1. **Given** a morning brief delivered at 07:00, **When** the job runs again at 09:00, **Then** no second brief is sent: the job skips on its cooldown, and a run racing it gets `deduped` from `notify`.
2. **Given** a morning brief whose push `failed` at 07:00, **When** the job runs at 07:15, **Then** the brief is sent.
3. **Given** a brief suppressed by the budget, **When** the next run comes, **Then** the cooldown has not started.
4. **Given** quiet hours hold a brief (`held`), **When** the job runs again inside the window, **Then** no second brief is queued.

---

### User Story 2 - Every discretionary push passes the same bar, with the same inputs (Priority: P1)

The user is not pushed about a loop or a hypothesis that is ungrounded, or that repeats something Ze just pushed.

**Why this priority**: the bar is the quality gate for unprompted interruptions. While each source assembles its own inputs, a wiring slip (B4) silently turns a check off.

**Independent Test**: build the push bar with a fake embedder, NLI and history, and drive `AttentionArbitrationJob.run` with one loop candidate and one hypothesis candidate. A missing NLI dependency fails construction instead of passing silently.

**Acceptance Scenarios**:

1. **Given** a drifting loop whose title its evidence does not support, **When** arbitration runs, **Then** the loop is not pushed and the reason is `ungrounded`.
2. **Given** a loop pushed 3 hours ago, **When** a near-duplicate rationale comes up, **Then** novelty blocks it, reading the push the governor actually recorded.
3. **Given** a hypothesis and a loop with the same rationale, **When** both are candidates, **Then** novelty treats them against one shared history.
4. **Given** the bar is built with `nli=None`, **When** the application starts, **Then** the bar runs without grounding and logs `push_bar_grounding_off` once. There is no default value: leaving NLI out fails construction. See FR-004.

---

### User Story 3 - The workflow-failure history survives without the push log (Priority: P2)

`/status` and the morning brief list recent workflow failures from a record of the failures themselves, not from push bookkeeping.

**Why this priority**: today the failure list is push bookkeeping: the alert handler writes a `workflow_failure:<id>` row into `push_log` and `/status`, the weekly accountability report and the brief read it back. The run record (`workflow_executions`) already holds every failure, so the copy goes and the readers read the runs.

**Independent Test**: fail a workflow twice inside its alert cooldown, and assert that `/status` lists two failures while only one alert was pushed.

**Acceptance Scenarios**:

1. **Given** two failures of one workflow within an hour, **When** the user opens `/status`, **Then** both failures are listed, and only one alert was pushed.

---

### User Story 4 - Conversation cooldowns belong to the conversation (Priority: P3)

Inline loop mentions and loop offers keep their cooldowns (12 hours inline, a week for offers) through `TurnSurfacing`'s own record, not through push keys.

**Independent Test**: mention a loop inline, then run arbitration 1 hour later, and assert the loop is not pushed (reason `mentioned_recently`). Offer a suspected loop at resume, and assert it is not offered again within 7 days. Do both without a push log.

**Acceptance Scenarios**:

1. **Given** a loop was mentioned inline 1 hour ago, **When** it becomes a push candidate, **Then** the inline-then-push cooldown still holds. The push bar reads the mention through `TurnSurfacing`'s interface.
2. **Given** a suspected loop was offered at resume 3 days ago, **When** the next session resumes, **Then** it is not offered again.

---

### User Story 5 - A loop that keeps drifting is pushed again, at most weekly (Priority: P2)

A loop that drifts, is pushed, and stays drifting can be pushed again after 7 days. Today it is pushed once in its whole life.

**Independent Test**: push a drifting loop, advance the clock 6 days, and assert arbitration does not push it (outcome `deduped`); advance to day 8 and assert it is pushed, if the bar and the budget allow.

**Acceptance Scenarios**:

1. **Given** a loop pushed 8 days ago that is still drifting, **When** arbitration runs and the bar and budget pass, **Then** the loop is pushed again.
2. **Given** a loop pushed 2 days ago, **When** arbitration runs, **Then** it is not pushed, and arbitration moves on to the next candidate.

### Edge Cases

- A job's cooldown key covers a target (`goal:<id>`) and not only an event type. `once_per` takes the key the caller names, and two different targets never block each other.
- Two runs of the same job race inside one window. The cooldown claim and the budget claim are atomic together, so only one delivery happens.
- The governor holds a push during quiet hours, then `QuietHoursReleaseJob` releases it. The release does not start a second cooldown. If the release fails, the cooldown stays (Clarifications, Q2).
- The claim store fails. The push goes ahead unclaimed and the failure is logged, as the budget claim does today: a rare second send is better than a missed one.
- Calendar reminders are `requested` pushes. They never take a cooldown from this module (FR-009).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide one push-bar module that is built once at startup with its embedder, NLI client, push history and conversation recency. It takes a candidate (push body, claim to ground, confidence, relevance, evidence labels, source kind and id) and the thresholds its source declares, and returns pass, or fail with a named reason.
- **FR-002**: The push bar's novelty check MUST read the history of discretionary pushes that the governor recorded as `delivered` or `held`. It MUST NOT read a per-source key.
- **FR-003**: Loop and hypothesis push sources MUST supply only candidates. Neither may call a bar condition directly, or read push history directly.
- **FR-004**: Constructing the push bar without an NLI client MUST be an explicit, logged choice ("grounding off"), not a default parameter value.
- **FR-005**: `notify` MUST accept a cooldown (`once_per`: key and window; no window means once ever). It returns `deduped` when a push with that key was `delivered` or `held` inside the window, and records the key only for those two outcomes. The discretionary `budget_key` folds into it: every discretionary push declares `once_per`, and the `duplicate` outcome becomes `deduped`.
- **FR-006**: The cooldown check, the cooldown record and the discretionary budget claim MUST happen in one atomic step per push.
- **FR-007**: Every job that today calls `was_sent_within_hours` and then `log` around `notify` MUST move to `once_per` and lose its push-log dependency. That covers accountability, goal narrative, morning brief and workflow failure.
- **FR-008**: The push log MUST become private to the governor. No module outside ze-proactive may read or write it; other packages reach push history only through the notifier.
- **FR-009**: Requested pushes, such as reminders, MUST be unaffected. They keep their own idempotency and never spend the discretionary budget.
- **FR-010**: Inline-mention and loop-offer cooldowns MUST be held by a record that `TurnSurfacing` owns, with the current windows (12 h inline; 7 days for offers, per phase 171). The push bar reads "mentioned inline recently" through `TurnSurfacing`'s interface.
- **FR-011**: `/status`, the weekly accountability report and the briefing MUST read workflow failures from the workflow run record (`workflow_executions`), so they list every failed run, whether or not it was pushed. The `workflow_failure:<id>` push-log rows go.
- **FR-012**: The calendar reminder log (`calendar_reminder:<id>`) MUST be deleted. The calendar's own reminder record (`mark_sent` / `mark_unsent`) is already its requested-push idempotency record.
- **FR-013**: Pre-v1 hard cut. `was_sent_within_hours`, `log`, `list_recent_payloads`, `list_workflow_failures_within_hours`, `PushLogEntry`, `try_claim_shared`/`release_shared`/`within_budget`, `ATTENTION_PUSH_EVENT_KEY`, `notify(budget_key=..., dedup_hours=...)`, `NotificationStore.exists_recent`, `list_recently_surfaced_summaries` and the free bar functions are deleted, not wrapped. Existing `push_log` rows that are not governor claims are dropped by a migration.
- **FR-014**: The five hand-rolled `outcome in ("delivered", "held")` checks MUST use one named predicate exported by ze-proactive (and `ze_sdk.proactive` for plugins).
- **FR-015**: A drifting loop MUST be pushed at most once per `worldstate.push.repush_after_days` (default 7) while it stays drifting. The novelty check and the daily budget still apply (Clarifications, Q1).
- **FR-016**: A push held by quiet hours MUST keep its cooldown even if its later release fails (Clarifications, Q2).

### Key Entities

- **Push bar**: the gate a discretionary candidate passes before it may claim the attention budget. It checks confidence, relevance, novelty against recorded pushes, and grounding.
- **Push cooldown**: "at most once per key per window", owned by the notifier and keyed by the caller.
- **Push history**: the governor's record of discretionary pushes and their outcomes. It is private to the governor.
- **Surfacing memory**: `TurnSurfacing`'s record of loops mentioned inline or offered in conversation.
- **Workflow failure record**: one row per failed workflow run, kept with workflow runs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No module outside ze-proactive references the push log. A grep for `push_log` and `PushLogStore` in non-test, non-migration code outside `core/contracts/ze-proactive/` finds zero matches.
- **SC-002**: A push that `failed` or was `suppressed_budget` never starts a cooldown, for every job in FR-007. One parametrized test proves it.
- **SC-003**: One test through `AttentionArbitrationJob.run` shows grounding and novelty rejecting a loop candidate, with no direct call to a bar condition.
- **SC-004**: `/status` lists 100% of workflow failures in its window, including failures that were not pushed.
- **SC-005**: Adding a new discretionary push source needs a candidate adapter only, with no edit to bar code.
- **SC-006**: A drifting loop is pushed again on day 8 and not on day 6 (US5).

## Assumptions

- Phase 198 has landed: NLI is injected into the loop source, and outcome-gated cooldowns exist for the jobs it touched. This phase replaces those fixes with the module that makes them structural.
- Thresholds keep their current values and config keys (`worldstate.push.*`, `correlation.salience.surfacing.*`, the NLI grounding threshold). Only their owner changes. The one new key is `worldstate.push.repush_after_days`.
- `notifications` stays the per-push delivery record that the bell reads. The cooldown is answered from the governor's history, not from `notifications`, because only a claim taken in the same transaction can make FR-006 atomic (research R2).
- Dev data is disposable (`pre-v1-hard-cuts.md`).
