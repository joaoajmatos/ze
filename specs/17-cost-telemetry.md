# Cost Telemetry — Spec

## Purpose

Persist every LLM call's token usage and attributed cost to Postgres so Ze's
spending can be analysed by flow type, agent, model, and time period. The
instrumentation layer must be invisible to callers — adding a new agent or
proactive feature requires zero extra work for basic attribution, and at most
one line for new flow types.

## Design Principle

`OpenRouterClient` is the single chokepoint for every LLM call. Injecting a
`CostTracker` there is sufficient to capture all usage. Attribution context
(which flow triggered the call, which agent is running) propagates through the
async call chain via a Python `ContextVar` — set once at the flow entry point,
read automatically inside the tracker.

## New Module: `ze/telemetry/`

### `ze/telemetry/types.py`

```python
from dataclasses import dataclass

@dataclass
class CostRecord:
    agent: str
    flow_type: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    duration_ms: int
    session_id: str | None
    cost_usd: float | None   # None when model not in pricing table
```

### `ze/telemetry/context.py`

```python
from contextvars import ContextVar
from dataclasses import dataclass, replace

@dataclass(frozen=True)
class CostContext:
    flow_type: str
    agent: str
    session_id: str | None = None

_CTX: ContextVar[CostContext | None] = ContextVar("ze_cost_ctx", default=None)

def set_flow_context(flow_type: str, session_id: str | None = None) -> None:
    current = _CTX.get()
    if current is not None:
        _CTX.set(replace(current, flow_type=flow_type, session_id=session_id))
    else:
        _CTX.set(CostContext(flow_type=flow_type, agent="unknown", session_id=session_id))

def set_agent_context(agent: str) -> None:
    current = _CTX.get()
    if current is not None:
        _CTX.set(replace(current, agent=agent))

def get_cost_context() -> CostContext:
    return _CTX.get() or CostContext(flow_type="unknown", agent="unknown")
```

### `ze/telemetry/tracker.py`

```python
import asyncio
import decimal
from ze.telemetry.context import get_cost_context
from ze.telemetry.types import CostRecord
from ze.logging import get_logger

log = get_logger(__name__)

class CostTracker:
    def __init__(self, pool, settings) -> None:
        self._pool = pool
        self._settings = settings

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        total_tokens: int,
        duration_ms: int,
    ) -> None:
        """Fire-and-forget: schedules a DB write without blocking the caller."""
        ctx = get_cost_context()
        cost_usd = _compute_cost(model, prompt_tokens, completion_tokens, self._settings)
        rec = CostRecord(
            agent=ctx.agent,
            flow_type=ctx.flow_type,
            session_id=ctx.session_id,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            duration_ms=duration_ms,
            cost_usd=cost_usd,
        )
        asyncio.create_task(_write(self._pool, rec))

async def _write(pool, rec: CostRecord) -> None:
    try:
        async with pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO llm_cost_log
                    (session_id, agent, flow_type, model,
                     prompt_tokens, completion_tokens, total_tokens,
                     cost_usd, duration_ms)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
                """,
                rec.session_id, rec.agent, rec.flow_type, rec.model,
                rec.prompt_tokens, rec.completion_tokens, rec.total_tokens,
                rec.cost_usd, rec.duration_ms,
            )
    except Exception as exc:
        log.warning("cost_write_failed", error=str(exc))

def _compute_cost(model: str, prompt: int, completion: int, settings) -> float | None:
    pricing = settings.model_pricing.get(model)
    if not pricing:
        return None
    return (
        prompt    / 1_000_000 * pricing["prompt_per_1m"]
        + completion / 1_000_000 * pricing["completion_per_1m"]
    )
```

## DB Table: `llm_cost_log` (Migration 003)

```sql
CREATE TABLE llm_cost_log (
    id                UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id        TEXT,
    agent             TEXT        NOT NULL,
    flow_type         TEXT        NOT NULL,
    model             TEXT        NOT NULL,
    prompt_tokens     INT         NOT NULL,
    completion_tokens INT         NOT NULL,
    total_tokens      INT         NOT NULL,
    cost_usd          NUMERIC(12,8),
    duration_ms       INT         NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX llm_cost_log_created_idx  ON llm_cost_log (created_at DESC);
CREATE INDEX llm_cost_log_flow_idx     ON llm_cost_log (flow_type, created_at DESC);
CREATE INDEX llm_cost_log_agent_idx    ON llm_cost_log (agent, created_at DESC);
CREATE INDEX llm_cost_log_session_idx  ON llm_cost_log (session_id) WHERE session_id IS NOT NULL;
```

## OpenRouterClient Changes

- Accept `cost_tracker: CostTracker | None = None` in `__init__`.
- In `complete()`: after extracting `usage`, call `self._cost_tracker.record(...)`.
- In `stream()`: capture the usage field from the final SSE chunk (currently
  discarded). OpenRouter sends a `usage` object on the last non-`[DONE]` chunk
  when `include_usage: true` is set (or on the `[DONE]` chunk itself). Add
  `"stream_options": {"include_usage": true}` to streaming requests. Accumulate
  tokens across chunks; call `tracker.record()` after the stream closes.

## BaseAgent Changes

Add to the top of `run()`:

```python
from ze.telemetry.context import set_agent_context
...
async def run(self, ctx: AgentContext) -> AgentResult:
    set_agent_context(self.name)
    ...
```

All existing and future agents inherit this automatically.

## Flow Entry Points

| Module | Call to add |
|--------|-------------|
| `ze/telegram/bot.py` — message handler | `set_flow_context("user_message", str(chat_id))` |
| `ze/proactive/briefing.py` — `run()` | `set_flow_context("morning_briefing")` |
| `ze/proactive/insights.py` — `run()` | `set_flow_context("insight_generation")` |
| `ze/proactive/reminders.py` — `sync()` | `set_flow_context("calendar_sync")` |
| `ze/memory/consolidator.py` — `run()` | `set_flow_context("memory_consolidation")` |
| `ze/routing/router.py` — `_haiku_fallback()` | `set_agent_context("router")` |

## Pricing Config

Add to `config/models.yaml`:

```yaml
pricing:
  anthropic/claude-haiku-4-5:
    prompt_per_1m: 0.80
    completion_per_1m: 4.00
  anthropic/claude-sonnet-4-5:
    prompt_per_1m: 3.00
    completion_per_1m: 15.00
  anthropic/claude-opus-4-5:
    prompt_per_1m: 15.00
    completion_per_1m: 75.00
```

These mirror OpenRouter's pass-through pricing for Anthropic models. Update
manually when prices change.

## Settings Change

Add `model_pricing: dict[str, dict]` to `Settings`, loaded from the `pricing`
key in `config/models.yaml`.

## REST Endpoint: `GET /admin/costs`

Route in `ze/api/admin.py` (new file, mounted at `/admin`).

### Query params

| Param | Default | Description |
|-------|---------|-------------|
| `days` | 30 | Lookback window |
| `group_by` | `flow_type` | `flow_type` \| `agent` \| `model` \| `session_id` |

### Response schema

```python
@dataclass
class CostBucket:
    group: str
    calls: int
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    cost_usd: float | None   # None if any call had no pricing

@dataclass
class CostSummaryResponse:
    period_days: int
    group_by: str
    total_cost_usd: float | None
    total_calls: int
    buckets: list[CostBucket]
```

### SQL pattern

```sql
SELECT
    <group_by_col>           AS group_key,
    COUNT(*)                 AS calls,
    SUM(prompt_tokens)       AS prompt_tokens,
    SUM(completion_tokens)   AS completion_tokens,
    SUM(total_tokens)        AS total_tokens,
    SUM(cost_usd)            AS cost_usd
FROM llm_cost_log
WHERE created_at >= NOW() - INTERVAL '<days> days'
GROUP BY group_key
ORDER BY total_tokens DESC
```

### Auth

Protected by the existing `ZE_API_KEY` header check (same as other admin-style
routes).

## Container Changes

`CostTracker` is constructed in `build_container()` and injected into
`OpenRouterClient`. No other components need a reference to it.

## Testing

- `CostTracker.record()`: mock `asyncio.create_task`; assert `_write` is
  scheduled with the correct `CostRecord` fields.
- `_compute_cost()`: unit test with known pricing values.
- Context propagation: verify that `set_flow_context` + `set_agent_context` are
  visible inside a spawned coroutine.
- `OpenRouterClient.complete()` with a mock tracker: assert `tracker.record()`
  is called with the right token counts.
- `GET /admin/costs`: mock DB, assert grouping logic.

## Out of Scope

- Real-time cost alerting / budget enforcement.
- Per-user or per-conversation cost attribution (single-user system).
- Retroactive backfill of historical calls (start tracking from deploy date).
- Automatic pricing refresh from OpenRouter's `/models` endpoint.
