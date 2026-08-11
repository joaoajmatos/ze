# Feature Specification: Proactive/Concurrency Hardening Sweep

**Feature Branch**: `113-hardening-sweep`

**Created**: 2026-08-11

**Status**: Implemented

**Input**: User description: "Proactive/Concurrency Hardening Sweep — fix four underdeveloped concepts identified in audit: (1) push_log idempotency gap in PushSweepJob (check-then-act TOCTOU on passes_push_bar/log_push, no unique constraint enforcing exclusivity at write time, closes overlap risk from trigger_now bypassing scheduler's max_instances=1 and potential multi-replica overlap); (2) pending_confirmations clobber bug — table keyed by PRIMARY KEY(thread_id) with ON CONFLICT DO UPDATE causes a second gate on the same thread to silently overwrite the first (orphaned checkpoint becomes unresumable, and the first gate's timeout task later deletes the second gate's row); fix by rekeying to request_id (or composite thread_id+request_id) and updating clear() to take request_id; (3) cost as a hard limit — CapabilityGate.evaluate() has no cost/budget awareness, CostTracker/CostReconciler are after-the-fact telemetry only, add a pre-call budget check in the existing capability_check graph node against a new budget config block, using token-estimated running cost (don't wait for reconciliation), returning BLOCKED/AWAIT_CONFIRMATION via the existing GateDecision enum; (4) trace-panel liveness — descoped, deferred to Phase 95, since it requires the full astream_events migration and token/typing streaming already work."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - No lost confirmation gates (Priority: P1)

Ze sometimes asks the user to confirm or deny an action (send this email, spend this much, take this irreversible step) mid-conversation. If a second such question gets triggered on the same conversation thread before the user answers the first one — for example, a fast follow-up message that itself needs approval — the first question must not silently vanish. Today it does: the newer gate overwrites the older one in storage, and when the older gate's timeout eventually fires, it deletes the newer gate's row instead, orphaning whatever action was waiting on it.

**Why this priority**: This is an active, reachable data-loss bug, not a theoretical race. A user can lose track of what they approved, or an approved action can silently fail to resume, with no error surfaced. It directly damages trust in the confirmation mechanism, which exists specifically to protect irreversible actions.

**Independent Test**: Trigger two confirmation-worthy actions on the same conversation thread in quick succession (before the first is answered). Confirm both gates remain independently addressable, both eventually resolve (approve/deny/timeout) correctly, and neither gate's resolution or timeout affects the other's stored state.

**Acceptance Scenarios**:

1. **Given** a pending confirmation gate on a thread, **When** a second, distinct confirmation gate is opened on the same thread before the first is answered, **Then** both gates are stored independently and neither overwrites the other.
2. **Given** two pending gates on the same thread, **When** the user answers the second (newer) gate, **Then** the first (older) gate remains pending and unaffected.
3. **Given** two pending gates on the same thread, **When** the first (older) gate's timeout elapses, **Then** only the first gate is cleared/expired — the second gate's pending state is untouched.
4. **Given** a resolved or expired gate, **When** its resolution is processed, **Then** the correct underlying action (and only that action) is resumed or discarded.

---

### User Story 2 - Spend cannot run away mid-session (Priority: P2)

Ze tracks how much each conversation and each day costs in LLM spend, but today that tracking is purely after-the-fact — it can tell the user what was spent, not stop spend before it happens. If a session or day is on track to exceed a spending threshold the user has set, Ze should hold off starting further costly work and let the user decide whether to continue, rather than finding out afterward that a budget was blown.

**Why this priority**: Real financial exposure with no backstop today — a runaway agentic loop (e.g., a stuck goal or workflow retry storm) could keep spending indefinitely with the only signal being a same-day or next-day anomaly alert. This is more consequential than the notification/gate issues in terms of blast radius, but is scoped as P2 because it requires new configuration surface (a budget the user must set) rather than fixing an existing broken guarantee.

**Independent Test**: Configure a low per-session or per-day spend threshold, drive a conversation past that threshold, and confirm Ze holds further costly execution and surfaces the budget state to the user instead of proceeding silently.

**Acceptance Scenarios**:

1. **Given** a configured session or daily budget, **When** running spend (estimated in real time, not waiting for after-the-fact reconciliation) is within budget, **Then** execution proceeds normally with no interruption.
2. **Given** a configured session or daily budget, **When** running spend reaches or would exceed the budget, **Then** Ze blocks or holds further costly execution for that session/day rather than proceeding silently.
3. **Given** execution has been held for exceeding budget, **When** the user is notified, **Then** the notification clearly states the current spend, the configured limit, and what the user can do next (e.g., approve continuing, wait until the period resets).
4. **Given** no budget is configured, **When** Ze operates as before, **Then** behavior is unchanged (spend is tracked as telemetry only) — the feature is opt-in.

---

### User Story 3 - No duplicate proactive nudges for the same open loop (Priority: P3)

Ze periodically sweeps open loops (things it's tracking that might need the user's attention) and decides whether to push a notification about one. If the same sweep job somehow runs twice at once — for example, a manual "run now" trigger overlapping with its own in-flight run — the user should never receive two notifications about the same open loop from that double-run.

**Why this priority**: Lowest severity of the three — worst case is a duplicate, mildly annoying notification, not lost data or runaway spend, and existing safeguards (single-instance cron scheduling, per-loop cooldown checks) already prevent this in the common case. This closes the remaining edge case (manual trigger bypassing the scheduler's overlap guard, or a future multi-instance deployment) rather than fixing a currently-common failure.

**Independent Test**: Force two concurrent runs of the same proactive push sweep (e.g., via back-to-back manual triggers) against a shared open loop that qualifies for a push, and confirm only one notification is ever sent for that loop from that sweep.

**Acceptance Scenarios**:

1. **Given** a sweep job about to notify on a specific open loop, **When** a second concurrent run of the same sweep job independently reaches the same decision for the same loop, **Then** only one notification is actually sent.
2. **Given** a notification has just been logged for a loop, **When** any concurrent or subsequent sweep re-evaluates that same loop within its cooldown window, **Then** it recognizes the notification was already sent and does not send another.
3. **Given** a manually triggered sweep run, **When** it overlaps with another run of the same job (manual or scheduled), **Then** the overlap does not produce duplicate notifications for any loop.

---

### Edge Cases

- What happens when a confirmation gate's underlying action (goal step, workflow step, draft response) is no longer valid by the time the gate resolves (e.g., the goal was cancelled while the gate was pending)? Resolution should fail gracefully and inform the user, not resume a stale action.
- What happens when a third (or more) confirmation gate is opened on a thread while two are already pending? The independence guarantee from User Story 1 must hold for any number of concurrent gates, not just two.
- What happens when running spend is already over budget the moment a new turn starts (budget was exceeded by a previous session)? Ze must hold before starting new costly work, not just mid-turn.
- What happens when the token-estimated running cost used for the pre-call check later turns out to have under- or over-estimated true cost once reconciliation completes? The estimate is a gate for stopping *future* spend; it does not need to retroactively correct a decision already made.
- What happens to a budget hold if the user never responds (analogous to confirmation gate timeout)? Define what "resetting" a session/day budget hold means so the user isn't stuck indefinitely.
- What happens when the push-sweep idempotency safeguard itself experiences a transient failure (e.g., the write enforcing exclusivity fails for a reason unrelated to a duplicate)? The sweep should treat this as "notification not confirmed sent" and fail safe (skip, log, retry later) rather than either double-sending or crashing the sweep.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow multiple confirmation gates to be pending simultaneously on the same conversation thread without one overwriting another.
- **FR-002**: System MUST resolve (approve/deny/timeout/clear) each confirmation gate independently of any other pending gate on the same thread.
- **FR-003**: System MUST ensure a confirmation gate's timeout only ever affects that specific gate, never a different, newer gate that happens to share the same thread.
- **FR-004**: System MUST allow the user to configure a spend budget scoped to a session and/or to a day.
- **FR-005**: System MUST evaluate running spend against the configured budget before starting new costly execution within a session/day, using a real-time estimate rather than waiting for after-the-fact cost reconciliation.
- **FR-006**: System MUST hold or block further costly execution once the configured budget is reached or would be exceeded, and MUST surface this state to the user with the current spend and limit.
- **FR-007**: System MUST leave current behavior unchanged (telemetry-only, no blocking) for sessions/days with no configured budget.
- **FR-008**: System MUST ensure that when a proactive push-sweep job evaluates whether to notify about a given open loop, at most one notification is actually sent for that loop per qualifying sweep decision, even if the sweep runs concurrently with itself.
- **FR-009**: System MUST make the "has this loop already been notified about" check and the "record that a notification was sent" write atomic (or otherwise race-safe) with respect to concurrent invocations of the same sweep job.
- **FR-010**: System MUST NOT regress the existing per-loop cooldown and daily push-budget behavior already in place for proactive notifications.

### Key Entities

- **Pending Confirmation**: A gate awaiting user approval/denial for an in-progress action, associated with a conversation thread and an underlying action/checkpoint to resume. Must be individually addressable and resolvable even when other gates exist on the same thread.
- **Spend Budget**: A user-configured spend ceiling scoped to a session or a day, compared against a running (real-time-estimated) cost total to decide whether new costly execution may proceed.
- **Push Notification Record**: A record that a proactive notification about a specific open loop was sent, used to prevent the same loop from being notified about twice by concurrent or overlapping sweep runs.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero confirmation gates are lost or silently overwritten when multiple gates occur on the same thread, verified across repeated concurrent-gate test runs.
- **SC-002**: 100% of resolved or expired confirmation gates resume or discard the correct underlying action — no cross-gate mix-ups.
- **SC-003**: When a session or day budget is configured and reached, 100% of further costly execution attempts in that scope are held/blocked before incurring additional spend, rather than after.
- **SC-004**: Users are informed of a budget hold with enough detail (current spend, limit, next steps) to decide how to proceed without needing to check logs.
- **SC-005**: Zero duplicate notifications are sent for the same open loop from concurrent or overlapping runs of the same proactive sweep, verified across repeated concurrent-sweep test runs.
- **SC-006**: No regression in existing single-run proactive notification behavior (cooldowns, daily push budgets) after the idempotency fix.

## Assumptions

- This sweep covers items 1–3 from the audit (confirmation clobbering, cost hard-limit, push-sweep idempotency). Item 4 (trace-panel liveness) is explicitly out of scope here and remains tracked under Phase 95, since closing it meaningfully requires the broader `astream_events` migration rather than a standalone fix.
- Goal-engine gates (keyed separately by `gate_id`/`goal_id`) already support concurrent pending gates correctly and are not in scope for User Story 1 — only the conversational (thread-keyed) confirmation gate path is affected.
- "Real-time-estimated" spend for the budget check means a token-based estimate available immediately at call time, not the fully reconciled dollar cost, which is only available minutes later. The estimate is accepted as good enough to gate on.
- Spend budgets are a new opt-in configuration surface; no default budget is assumed for existing users, so this feature does not change behavior for anyone who doesn't configure one.
- The push-sweep idempotency fix only needs to guarantee at-most-once notification delivery per loop per sweep decision; it does not need to guarantee exactly-once in the face of arbitrary infrastructure failure (fail-safe skip is acceptable over duplicate send).
- Multi-replica deployment of the proactive scheduler is not confirmed to exist today, but the idempotency fix should not rely on single-process assumptions (e.g., in-memory locks) so that it also holds if that changes.
