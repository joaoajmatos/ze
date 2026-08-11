# Quickstart: Validating the Hardening Sweep

Prerequisites: `make db-up`, `make migrate`, `make dev` (ze-api running), a WebSocket
client able to send/receive frames (e.g. the ze-web app via `make web`, or a raw WS
tool against `/ws`).

## 1. Confirmation gates don't clobber each other (User Story 1)

1. Start a conversation turn that is known to hit a confirmation gate (an agent/intent
   configured `Mode.CONFIRM` — see `config/config.yaml` or an agent's `intents`).
2. Before responding to the resulting `{"type": "confirmation", "id": "<A>", ...}`
   frame, immediately send a second message on the **same thread** that also triggers a
   confirmation gate.
3. Expect a second `{"type": "confirmation", "id": "<B>", ...}` frame, with `A != B`.
4. Query `pending_confirmations` directly: `SELECT request_id, thread_id FROM
   pending_confirmations WHERE thread_id = '<thread>'` — expect **two** rows, not one.
5. Send `{"type": "confirm", "id": "<A>", "choice": "approve"}`. Expect the action tied
   to gate A to execute/resume, and gate B to remain pending (`SELECT` still shows one
   row for `request_id = <B>`).
6. Send `{"type": "confirm", "id": "<B>", "choice": "deny"}`. Expect gate B's underlying
   action to be aborted, with no effect on gate A's already-completed resolution.

**Pass criteria**: SC-001, SC-002 — no cross-gate data loss or mix-up at any step.

## 2. Spend budget holds execution (User Story 2)

1. In `config/config.yaml`, set a low session budget:
   ```yaml
   budget:
     session_limit_usd: 0.01
     daily_limit_usd: null
   ```
   Reload config (SIGHUP or restart `make dev`).
2. Send a message that triggers an `EXECUTE`-mode agent turn costly enough to exceed
   $0.01 in one or two turns (any normal LLM-backed turn on a non-trivial model should
   do it).
3. On the turn where running session spend would exceed the configured limit, expect a
   `{"type": "confirmation", ...}` frame (not silent execution, not a hard `blocked`
   dead-end) whose prompt text states the current estimated spend and the configured
   limit.
4. Approve the confirmation. Expect the turn to proceed (the budget hold is advisory —
   user can always choose to continue).
5. Remove/null the budget config, reload, and confirm turns proceed with no
   confirmation prompts related to spend (regression check for FR-007).

**Pass criteria**: SC-003, SC-004 — hold happens before further spend is incurred for
that scope, and the surfaced message is self-sufficient (no log-digging required).

## 3. No duplicate push notifications from a concurrent sweep (User Story 3)

1. Get an open loop into `LoopState.DRIFTING` with a `drift_rationale` set, such that it
   would pass `LoopSurfacer.passes_push_bar()` today (see
   `core/ze-worldstate/tests/jobs/test_push_sweep.py` for how existing tests construct
   this fixture state).
2. Trigger `PushSweepJob.run()` twice concurrently against the same DB state — e.g. via
   two near-simultaneous manual job triggers, or in a test, `asyncio.gather(job.run(),
   job.run())`.
3. Expect exactly one call to `notifier.push(...)` across both runs (assert on a mock
   notifier in a test, or check ntfy/notification history in a manual run).
4. Query `push_log`: `SELECT COUNT(*) FROM push_log WHERE event_type =
   'worldstate_loop_push' AND idempotency_key = '<loop_id>'` — expect exactly `1`.

**Pass criteria**: SC-005 — zero duplicates across concurrent runs; SC-006 — a
single, non-concurrent run still behaves exactly as before (cooldown/budget checks
still apply, only one notification either way).

## Automated coverage

Each scenario above should also exist as a package test using mocked stores
(`AsyncMock`, per constitution V):

- `core/ze-core/tests/conversation/confirmations/test_store.py` — key-collision cases
  for `save`/`get_pending`/`clear` with multiple `request_id`s sharing a `thread_id`.
- `apps/ze-api/tests/websocket/test_confirmation_concurrency.py` — end-to-end
  two-gates-same-thread flow through the WS handlers, asserting `pending_configs`
  dict-shape correctness.
- `core/ze-core/tests/telemetry/test_budget.py` — `SpendBudgetChecker.check()` against
  mocked `CostStore` rows, session vs. daily scope, no-config-set short-circuit.
- `core/ze-core/tests/orchestration/test_capability_check_budget.py` — node-level
  composition of `CapabilityGate` decision + budget decision, strictest-wins.
- `core/ze-proactive/tests/test_push_log_store.py` — `try_claim` unique-violation
  returns `False` rather than raising; unaffected behavior for `NULL`-key rows.
- `core/ze-worldstate/tests/jobs/test_push_sweep.py` — extend existing suite with a
  concurrent-claim race test (two `PushSweepJob.run()` calls, one notifier call).

`make test-core`, `make test-proactive`, `make test-worldstate`, `make test-api`, and
`make lint` must all pass before this phase is considered done (constitution V).
