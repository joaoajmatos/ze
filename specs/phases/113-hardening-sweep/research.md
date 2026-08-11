# Phase 0 Research: Proactive/Concurrency Hardening Sweep

## R1 — How does the confirmation clobber actually happen end-to-end?

**Decision**: Fix both layers that are thread_id-keyed: the DB table `pending_confirmations`
(`PRIMARY KEY (thread_id)`, `ON CONFLICT (thread_id) DO UPDATE` in
`core/ze-core/ze_core/conversation/confirmations/store.py:33`) **and** the in-process
`pending_configs: dict[str, dict]` in `apps/ze-api/ze_api/api/websocket/endpoint.py:63`,
which is also keyed by `thread_id` and silently overwritten by
`pending_configs[thread_id] = result` (endpoint.py:122, 147, 215) whenever a second gate
opens on the same thread before the first is answered.

**Rationale**: The original audit found the DB-layer bug. Reading `endpoint.py` during
planning showed the in-memory dict has the identical shape of bug — a second `await_confirmation`
pause on the same thread overwrites `pending_configs[thread_id]` before the first is resolved,
so even if the DB row were fixed, `container.resume_turn(pending_config)` in
`confirmation.py:handle_confirm` would resume the *wrong* (newer) LangGraph checkpoint
config for an "approve" on the *older* gate's `request_id`. Both must be rekeyed together
or the fix is incomplete.

**Alternatives considered**:
- *Fix only the DB table.* Rejected — the in-memory dict is checked first in the WS
  handlers and is the actual object passed to `container.resume_turn`; fixing only the
  DB layer leaves the live bug in place.
- *Serialize gates per thread (only one allowed to open at a time, second one queues).*
  Rejected — more invasive (needs a new queuing/backpressure mechanism, and changes
  observable behavior — a legitimate second gate would be silently delayed rather than
  answered). Multi-key storage is simpler and matches the spec's "both remain
  independently addressable" requirement (FR-001) rather than serializing them.

## R2 — Confirmation store/dict key shape

**Decision**: Change `pending_confirmations`'s primary key from `thread_id` to
`request_id` (globally unique, already generated via `uuid4()` per gate). Add a
non-unique index on `thread_id` for `get_all_pending()`-style thread-scoped lookups
still needed elsewhere (e.g. reconnect replay). Mirror the same key change in
`pending_configs`: change to `dict[str, dict]` keyed by `request_id`, with a secondary
`dict[str, set[str]]` (`thread_id -> {request_id, ...}`) maintained alongside it so
existing thread-scoped lookups (e.g. "does this thread have any pending gate") stay
O(1) without scanning.

**Rationale**: `request_id` is already the correlation id the client sends back in
`{"type": "confirm", "id": ..., "choice": ...}` (per `confirmation.py:handle_confirm`,
`request_id = data.get("id", "")`) — the client already addresses gates by this id, the
storage layer just wasn't using it as the key. This is the minimal change that satisfies
FR-001–FR-003 without altering the WS protocol or client behavior.

**Alternatives considered**:
- *Composite key `(thread_id, request_id)`.* Considered for the DB table since it keeps
  thread-scoped queries simple (`WHERE thread_id = $1`) without a secondary index.
  Adopted for the DB migration (composite unique key is simplest in SQL); the in-memory
  dict uses the nested/secondary-index shape above since Python dicts don't support
  composite-key range scans as cleanly as SQL `WHERE`.

## R3 — Confirmation timeout task must target the right gate

**Decision**: `confirmation_timeout()` (apps/ze-api/ze_api/api/websocket/confirmation.py:111)
must be called with the specific `request_id` it was scheduled for, and must call
`confirmation_store.clear(thread_id, request_id)` (new signature) rather than
`clear(thread_id)`. The `if not cleared: return` guard already present is sufficient to
make this safe — if a different gate already resolved and cleared its own row, the
delete-by-`(thread_id, request_id)` simply finds nothing and returns.

**Rationale**: This is the direct fix for the failure mode described in the spec
(Edge Cases: "the first gate's timeout task later deletes the second gate's row").
Once `clear()` is scoped to `request_id`, this class of bug is structurally impossible
— a delete can only ever remove the row it was scheduled against.

**Alternatives considered**: Cancel the older timeout task when a newer gate opens on
the same thread. Rejected as unnecessary once deletes are `request_id`-scoped — the old
timeout firing and clearing its own (already-answered-or-not) row is harmless either way.

## R4 — How to estimate real-time spend without waiting for reconciliation

**Decision**: Add `core/ze-core/ze_core/telemetry/pricing.py`, a static
`MODEL_PRICING: dict[str, tuple[float, float]]` (prompt $/1M tokens, completion $/1M
tokens) table seeded from the same model slugs already in `MODEL_CONTEXT_WINDOWS`
(`core/ze-core/ze_core/openrouter/context_windows.py`) and `config/config.yaml`, with a
conservative default rate for unlisted models. A new `SpendBudgetChecker` in
`telemetry/budget.py` sums `prompt_tokens`/`completion_tokens` from `llm_cost_log` for
the running session/day (a plain `SUM(...) WHERE session_id = $1` / `WHERE created_at >
today` query — cheap, no new table) and multiplies by this static table to get an
estimated running $ total, compared against the configured budget.

**Rationale**: This exactly mirrors the precedent Phase 112 already established for
context-window sizing (`context_windows.py`'s own docstring: "No live lookup — a
chars/4 estimate against this table's value is precise enough"). `CostReconciler`
explicitly can't be used for a pre-call gate — it skips rows younger than 2 minutes by
design (`reconciler.py:_MIN_AGE_SECONDS = 120`) and needs a live OpenRouter call per
row, which is the wrong shape for something that must run before every costly turn.

**Alternatives considered**:
- *Wait for `cost_usd` reconciliation and gate on that.* Rejected — reconciliation lags
  by design (2+ minutes, batched, network-dependent); a runaway loop could blow the
  budget many times over before its own spend is even priced.
- *Call OpenRouter's pricing/generation endpoint live before every turn.* Rejected —
  violates the "no new external API calls for the budget check" constraint in Technical
  Context, and adds latency + a new failure mode (network call) to every gated turn.
- *Gate on token count directly, no $ conversion.* Considered and rejected as the
  primary mechanism — the spec's acceptance criteria (FR-006, SC-004) require surfacing
  "current spend" and "the limit" in dollar terms the user actually configured, since
  `CostTracker`/`CostReconciler` and existing cost UI already speak in `$`. A token-based
  budget would need its own separate mental model for the user. (Token counts remain the
  *input* to the estimate — just not the unit the budget is expressed or communicated in.)

## R5 — Where the budget check plugs into the graph

**Decision**: Extend the existing `capability_check` node
(`core/ze-core/ze_core/orchestration/nodes/execution.py:27`) to also call
`SpendBudgetChecker`, and take the stricter of the two `GateDecision`s (existing
`_GATE_RANK` ordering already used for compound-subtask strictness at line 43). When the
budget checker signals "over budget," it returns `GateDecision.AWAIT_CONFIRMATION` (not
`BLOCKED`) — this reuses the existing DRAFT/EXECUTE boundary already wired end-to-end
(draft_response → await_confirmation → resume), and satisfies the spec's requirement
that the user can "approve continuing" (Edge Cases, Acceptance Scenario 3), which a hard
`BLOCKED` (→ `end_blocked`, no resume path) cannot offer.

**Rationale**: No new graph node, no new edge — `after_capability_check` already
switches on `GateDecision` and routes `AWAIT_CONFIRMATION` correctly. `CapabilityGate`
itself stays budget-agnostic (single responsibility: mode/override resolution); the node
composes the two independent decisions, matching how it already composes per-subtask
decisions today.

**Alternatives considered**:
- *Put the budget check inside `CapabilityGate.evaluate()`.* Rejected — `evaluate()` is
  synchronous and per-(agent, intent); a budget check needs an async DB read and is
  session/day-scoped, not agent/intent-scoped. Mixing the concerns would force
  `evaluate()` to become async everywhere, a much larger blast radius than necessary.
- *New dedicated `budget_check` graph node before `capability_check`.* Rejected per the
  Technical Context constraint (no new graph nodes) — the existing node is a correct,
  cheaper extension point.

## R6 — Closing the push_log TOCTOU

**Decision**: Add a unique index on `push_log` scoped to `(event_type, idempotency_key)`
where `idempotency_key` is a new nullable column, populated by `LoopSurfacer.log_push()`
with the loop's id (`str(loop_id)`) for the `worldstate_loop_push` event type only
(existing event types that don't pass a key are unaffected — column stays `NULL` for
them, and Postgres unique indexes ignore rows with `NULL` in the indexed column by
default, preserving current behavior for every other caller of `push_log_store.log()`).
`PushLogStore` gets a new `try_claim(event_type, idempotency_key, payload)` method that
performs the insert and swallows a unique-violation by returning `False` (already
claimed) instead of raising — `LoopSurfacer`/`PushSweepJob` then treat `False` as "someone
else already sent this, skip the actual notification."

**Rationale**: Converts the existing check-then-act (`passes_push_bar()` then
`log_push()`) into an act-then-check: the *write* is the arbiter of exclusivity, not the
pre-check. This is the standard fix for this class of race and requires no new table,
no distributed lock, and holds regardless of process topology (single or multi-replica),
per the spec's Assumptions. FR-008/FR-009 map directly onto this: "at most one
notification... even if the sweep runs concurrently with itself" is exactly what a
unique index enforces at the database level, which no application-level check can
guarantee under concurrency.

**Alternatives considered**:
- *In-memory lock/mutex around `passes_push_bar`+`log_push`.* Rejected — doesn't survive
  multiple processes/replicas (spec explicitly wants a solution that doesn't rely on
  single-process assumptions), and doesn't fix `trigger_now()`'s bypass of the
  scheduler's `max_instances=1` guard within a single process either, since that guard
  only governs the *scheduler's own* concurrent invocation, not manual triggers.
- *Postgres-native `SELECT ... FOR UPDATE` row lock spanning `passes_push_bar` through
  `log_push`.* Rejected — would require a much larger refactor (currently these are two
  separate, independently-callable methods on `LoopSurfacer`), and still has the same
  TOCTOU shape unless the lock is held across both calls, which reintroduces the
  in-memory-lock problem in different clothes if not done via an actual DB transaction
  spanning both.
- *Move the exclusivity check into `passes_push_bar()`'s `within_budget()` call.*
  Rejected — `within_budget()` in `ze_correlation/push.py` is a shared function used by
  both the correlation pusher and the loop surfacer for a *different* purpose (daily
  push-count budget, not per-loop exclusivity); overloading it would couple two
  unrelated concerns.
