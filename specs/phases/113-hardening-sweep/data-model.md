# Phase 1 Data Model: Proactive/Concurrency Hardening Sweep

## Entity: Pending Confirmation

Represents an in-flight confirm/deny gate awaiting user response, correlated to a
LangGraph checkpoint that resumes on approval.

| Field | Type | Notes |
|---|---|---|
| `request_id` | `TEXT` | **New primary key.** Globally unique per gate (`uuid4()`), already generated at gate-open time and already round-tripped by the client in `{"type": "confirm", "id": ...}`. |
| `thread_id` | `TEXT NOT NULL` | Conversation thread the gate belongs to. Indexed (non-unique) for thread-scoped queries (reconnect replay via `get_all_pending()`-style lookups). No longer unique — multiple rows may share a `thread_id`. |
| `prompt` | `TEXT NOT NULL` | Unchanged. |
| `actions` | `JSONB NOT NULL` | Unchanged. |
| `expires_at` | `TIMESTAMPTZ NOT NULL` | Unchanged — drives the existing timeout-task expiry. |
| `created_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Unchanged. |

**Relationships**: One thread MAY have zero or more Pending Confirmations open at once
(previously implicitly capped at one by the schema; this migration removes that implicit
cap, matching FR-001).

**State transitions**: `open` → `approved` (row deleted, checkpoint resumed) |
`denied` (row deleted, checkpoint aborted) | `expired` (row deleted by its own
timeout task, checkpoint aborted). All three transitions are now scoped to exactly the
row matching `(request_id)`, never to "whatever row currently exists for this
`thread_id`."

**In-memory mirror**: `apps/ze-api/ze_api/api/websocket/endpoint.py`'s
`pending_configs` moves from `dict[str, dict]` (`thread_id -> graph_config`) to
`dict[str, dict]` (`request_id -> graph_config`) plus a derived
`dict[str, set[str]]` (`thread_id -> {request_id, ...}`) maintained in lockstep for
thread-scoped existence checks. This is process-local state, not persisted — rebuilt
from the DB store's `get_all_pending()` on reconnect, same as today.

## Entity: Spend Budget (configuration, not a DB table)

A user-configured spend ceiling read from `config/config.yaml`, not persisted as its
own row — it's compared against existing `llm_cost_log` data.

| Field | Type | Notes |
|---|---|---|
| `session_limit_usd` | `float \| None` | Optional. `None` = no session-scoped limit (current behavior). |
| `daily_limit_usd` | `float \| None` | Optional. `None` = no day-scoped limit (current behavior). |

**Relationships**: Compared against a derived, computed value — running estimated spend
— not stored itself:

- **Running Session Spend (derived)**: `SUM(prompt_tokens * rate_in + completion_tokens
  * rate_out)` over `llm_cost_log` rows for the current `session_id`, using the static
  `MODEL_PRICING` table for `rate_in`/`rate_out` per row's `model`. Computed on read,
  every `capability_check` invocation — no caching, since the table is small and the
  query is indexed on `session_id`.
- **Running Daily Spend (derived)**: Same computation, scoped to `created_at >=
  today_start` instead of `session_id`.

**State transitions**: N/A — this is a threshold comparison, not a stateful entity.
"Budget hold" is not a persisted state; it's re-evaluated fresh on every
`capability_check` call, so it naturally clears once the day rolls over or a new session
starts (no explicit reset mechanic needed, per spec Edge Cases).

## Entity: Model Pricing Table (static, code-owned)

| Field | Type | Notes |
|---|---|---|
| `model` (key) | `str` | OpenRouter model slug, e.g. `"anthropic/claude-sonnet-4-6"`. |
| `prompt_rate_per_million` | `float` | USD per 1,000,000 prompt tokens. |
| `completion_rate_per_million` | `float` | USD per 1,000,000 completion tokens. |

Seeded from the same model slugs already present in `MODEL_CONTEXT_WINDOWS`
(`core/ze-core/ze_core/openrouter/context_windows.py`) and `config/config.yaml`.
Unlisted models fall back to a conservative default rate (documented in the module,
mirroring `DEFAULT_CONTEXT_WINDOW_TOKENS`). Not a DB table — a static in-code dict,
consistent with the `context_windows.py` precedent (Phase 112) and the "no new external
API calls" constraint.

## Entity: Push Log Entry (extended)

| Field | Type | Notes |
|---|---|---|
| `id` | existing PK | Unchanged. |
| `event_type` | `TEXT NOT NULL` | Unchanged. |
| `payload` | `TEXT` | Unchanged — free-text rationale, used for novelty checks. |
| `sent_at` | `TIMESTAMPTZ NOT NULL DEFAULT now()` | Unchanged. |
| `idempotency_key` | `TEXT` | **New, nullable.** For `worldstate_loop_push` events, set to `str(loop_id)`. `NULL` for every other existing event type (workflow failures, correlation pushes, etc.) — those are unaffected by this migration. |

**Constraint**: `UNIQUE (event_type, idempotency_key)` — Postgres unique indexes treat
each `NULL` as distinct, so rows with `idempotency_key IS NULL` (all pre-existing event
types) are never subject to this constraint; only `worldstate_loop_push` rows, which
always populate the key, are deduplicated by it.

**Relationships**: One Open Loop maps to at most one successful `worldstate_loop_push`
push-log write system-wide at any point in time in the sense that a second concurrent
attempt to write the same `(event_type, idempotency_key)` pair fails at the DB level and
is treated by the caller as "already claimed," not retried.

**State transitions**: `unclaimed` (no row exists for this loop+event_type) →
`claimed` (row inserted — first writer wins). No update or delete path for this
entity; a new drift cycle on the same loop later produces a new `drift_rationale` and
is a semantically new push decision (existing `passes_novelty`/cooldown logic already
governs whether that's allowed — orthogonal to this fix).
