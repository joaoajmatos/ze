# Feature Specification: Push Bar and Cooldowns

**Feature Branch**: `204-push-bar-and-cooldowns`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 198 (wiring fixes B4 and B11)

**Input**: Architecture review 2026-10-22, candidate C9. Phase 198 fixes the wiring: NLI reaches the loop bar, novelty reads a key that is written, and a cooldown no longer starts after a failed push. This phase is the deepening behind those fixes. One push bar module is built once with the embedder, NLI and push history, and reads novelty from what the governor recorded. The notifier owns "at most once per key per window" (`notify(..., once_per=...)`), recorded only for `delivered` or `held`. `push_log` becomes the governor's private store. Conversational cooldowns move to `TurnSurfacing`. The workflow-failure ledger moves out of `push_log`.

## Context *(verified against the code, 2026-10-22)*

The push bar's conditions are free functions in `ze_correlation/push.py` (280 lines): `passes_confidence` (:33), `passes_relevance` (:37), `passes_novelty` (:41) and `passes_grounding` (:69). They were extracted so that "both sources call exactly one implementation", but each caller builds its own inputs:

- **Loops.** `LoopSurfacer.passes_push_bar` (`ze_worldstate/surfacing.py:80-106`) reads novelty history from `push_log.list_recent_payloads(PUSH_EVENT_KEY = "worldstate_loop_push")` (:23, :87). No production code writes that key, because the governor claims under `attention_push` (`ze_proactive/attention_budget.py:10`). It takes `nli_client` as a call argument with default `None` (:114), and `passes_grounding` passes when NLI is `None` (`push.py:75`).
- **Hypotheses.** `CorrelationPushCandidateSource` (`push.py:142`) reads novelty history from `hypothesis_store.list_recently_surfaced_summaries` (:228) and its thresholds from `_load_config(settings)` (:259).

`push_log` (`ze_proactive/push_log_store.py`, 114 lines; 21 non-test modules reference `push_log`/`PushLogStore`) mixes five unrelated uses under free-form string keys:

1. The governor's budget claims (`try_claim`, `release_claim`, `window_sent_at`).
2. Job cooldowns written as "was sent? notify, then log", whatever the outcome:
   - `jobs/accountability.py:44,56`
   - `jobs/goal_narrative.py:36,93`
   - `plugins/ze-personal/ze_personal/jobs/briefing.py:69,125`
   - `ze_automation/bootstrap.py:225,248` (workflow failure)
3. Conversational memory: inline mentions `worldstate_loop_inline:<id>` (`ze_priority/turn.py:238`, read at `surfacing.py:101`) and loop offers (`turn.py:139,149`).
4. The calendar reminder log (`ze_calendar/reminders/calendar.py:189`).
5. The workflow-failure ledger read by `/status` and the briefing:
   - `list_workflow_failures_within_hours` (`push_log_store.py:96`)
   - read at `ze_automation/rest.py:192`, `jobs/accountability.py:118` and `briefing.py:75`

The notifier already has `notify(dedup_hours=...)` (`ze_proactive/notifier.py:87,128-136`), but no production caller uses it. Its check (`notification_store.exists_recent`, `notification_store.py:308-330`) matches any notification row for the event and target in the window, whatever its delivery outcome.

Five callers hand-roll `if outcome in ("delivered", "held")`:

- `push.py:196`
- `ze_priority/arbitration.py:77`
- `jobs/stuck_goals.py:50`
- `ze_finance/jobs/recurring.py:113`
- `ze_personal/jobs/insights.py:173`

**Blast radius** (`graphify affected`):

- `PushLogStore`: ze-api wiring (`agents.py`, `container.py`, `jobs.py`, `stores.py`), `ze_automation/bootstrap.py` (`make_workflow_failure_handler`, `register_proactive_jobs`), automation jobs, and the pg tests `test_acceptance.py`, `test_loop_confirmation_pg.py` and `test_push_log_window_pg.py`.
- `passes_novelty`: `ze_correlation/push.py`, `ze_worldstate/surfacing.py`, `ze_priority/turn.py`, `ze_worldstate/bootstrap.py` and three test modules.
- `ProactiveNotifier`: every proactive job and the ze-api wiring.

**Added 2026-10-22 (phase 198 clarify, Q4):** the unique index on `push_log(event_type,
idempotency_key)` has no window, and `push_log` is never pruned. Loops claim `budget_key` as
`loop:<id>`, so a loop can be pushed at most once in its life: a revived loop that drifts again never
pushes. This phase owns `push_log`, so it fixes this, for example by keying the claim per drift
episode or by adding a window.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A push Ze already sent is not sent again, and a failed one is retried (Priority: P1)

The user gets the morning brief, the weekly goal narrative and accountability summaries at most once per window. A brief that failed, or that the budget suppressed, does not block the next attempt.

**Why this priority**: the cooldown is the user-visible behaviour. Today six callers each re-implement it, and record it even after a failure.

**Independent Test**: drive each job through `notify` with a fake governor that returns `failed`, then `delivered`, and assert one delivery and no cooldown after the failure.

**Acceptance Scenarios**:

1. **Given** a morning brief delivered at 07:00, **When** the job runs again at 09:00, **Then** no second brief is sent and the outcome is `deduped`.
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
4. **Given** the bar is built without an NLI client, **When** the application starts, **Then** startup fails with a clear configuration error, or the bar runs explicitly without grounding and says so in the log once. See FR-004.

---

### User Story 3 - The workflow-failure history survives without the push log (Priority: P2)

`/status` and the morning brief list recent workflow failures from a record of the failures themselves, not from push bookkeeping.

**Why this priority**: today a failure that was never pushed, because of its cooldown or the budget, is missing from `/status`.

**Independent Test**: fail a workflow twice inside its alert cooldown, and assert that `/status` lists two failures while only one alert was pushed.

**Acceptance Scenarios**:

1. **Given** two failures of one workflow within an hour, **When** the user opens `/status`, **Then** both failures are listed, and only one alert was pushed.

---

### User Story 4 - Conversation cooldowns belong to the conversation (Priority: P3)

Inline loop mentions and loop offers keep their cooldowns (12 hours inline, a week for offers) through `TurnSurfacing`'s own record, not through push keys.

**Independent Test**: run two turns that mention the same loop 1 hour apart, and assert one inline mention. Do this without a push log.

**Acceptance Scenarios**:

1. **Given** a loop was mentioned inline 1 hour ago, **When** it becomes a push candidate, **Then** the inline-then-push cooldown still holds. The push bar reads the mention through `TurnSurfacing`'s interface.

### Edge Cases

- A job's cooldown key covers a target (`goal:<id>`) and not only an event type. `once_per` takes the key the caller names, and two different targets never block each other.
- Two runs of the same job race inside one window. The cooldown claim and the budget claim are atomic together, so only one delivery happens.
- The governor holds a push during quiet hours, then `QuietHoursReleaseJob` releases it. The release does not start a second cooldown.
- Calendar reminders are `requested` pushes. They never take a cooldown from this module (FR-009).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST provide one push-bar module that is built once at startup with its embedder, NLI client, history source and thresholds. It takes a candidate (text, confidence, relevance, evidence labels, source kind) and returns pass, or fail with a named reason.
- **FR-002**: The push bar's novelty check MUST read the history of discretionary pushes that the governor recorded as `delivered` or `held`. It MUST NOT read a per-source key.
- **FR-003**: Loop and hypothesis push sources MUST supply only candidates. Neither may call a bar condition directly, or read push history directly.
- **FR-004**: Constructing the push bar without an NLI client MUST be an explicit, logged choice ("grounding off"), not a default parameter value.
- **FR-005**: `notify` MUST accept a cooldown (`once_per`: key and window). It returns `deduped` when a push with that key was `delivered` or `held` inside the window, and records the key only for those two outcomes.
- **FR-006**: The cooldown check, the cooldown record and the discretionary budget claim MUST happen in one atomic step per push.
- **FR-007**: Every job that today calls `was_sent_within_hours` and then `log` around `notify` MUST move to `once_per` and lose its push-log dependency. That covers accountability, goal narrative, morning brief and workflow failure.
- **FR-008**: The push log MUST become private to the governor. No module outside ze-proactive's governor and notifier may read or write it.
- **FR-009**: Requested pushes, such as reminders, MUST be unaffected. They keep their own idempotency and never spend the discretionary budget.
- **FR-010**: Inline-mention and loop-offer cooldowns MUST be held by a record that `TurnSurfacing` owns, with the current windows (12 h inline; 7 days for offers, per phase 171). The push bar reads "mentioned inline recently" through `TurnSurfacing`'s interface.
- **FR-011**: Workflow failures MUST be recorded where workflow runs live, so `/status` and the briefing list every failure, whether or not it was pushed.
- **FR-012**: The calendar reminder log (`calendar_reminder:<id>`) MUST move to the calendar's own reminder record. It is a requested-push idempotency record, not push history.
- **FR-013**: Pre-v1 hard cut. `was_sent_within_hours`, `log`, `list_recent_payloads`, `list_workflow_failures_within_hours` and the free bar functions are deleted, not wrapped. Existing `push_log` rows that are not governor claims are dropped by a migration.
- **FR-014**: The five hand-rolled `outcome in ("delivered", "held")` checks MUST use one named predicate exported by ze-proactive.

### Key Entities

- **Push bar**: the gate a discretionary candidate passes before it may claim the attention budget. It checks confidence, relevance, novelty against recorded pushes, and grounding.
- **Push cooldown**: "at most once per key per window", owned by the notifier and keyed by the caller.
- **Push history**: the governor's record of discretionary pushes and their outcomes. It is private to the governor.
- **Surfacing memory**: `TurnSurfacing`'s record of loops mentioned inline or offered in conversation.
- **Workflow failure record**: one row per failed workflow run, kept with workflow runs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No module outside ze-proactive's governor and notifier references the push log. A grep finds zero matches in non-test code.
- **SC-002**: A push that `failed` or was `suppressed_budget` never starts a cooldown, for every job in FR-007. One parametrized test proves it.
- **SC-003**: One test through `AttentionArbitrationJob.run` shows grounding and novelty rejecting a loop candidate, with no direct call to a bar condition.
- **SC-004**: `/status` lists 100% of workflow failures in its window, including failures that were not pushed.
- **SC-005**: Adding a new discretionary push source needs a candidate adapter only, with no edit to bar code.

## Assumptions

- Phase 198 has landed: NLI is injected into the loop source, and outcome-gated cooldowns exist for the jobs it touched. This phase replaces those fixes with the module that makes them structural.
- Thresholds keep their current values and config keys. Only their owner changes.
- `notifications` stays the per-push delivery record that the bell reads. The cooldown may be answered from it, or from the governor's history, as long as FR-005's outcome rule holds. The plan decides which.
- Dev data is disposable (`pre-v1-hard-cuts.md`).
