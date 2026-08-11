# Contract: Spend Budget Gate

New internal interface — `core/ze-core/ze_core/telemetry/budget.py`, consumed by the
existing `capability_check` graph node (`core/ze-core/ze_core/orchestration/nodes/execution.py`).

## New module: `ze_core/telemetry/pricing.py`

```python
MODEL_PRICING: dict[str, tuple[float, float]] = {
    # model_slug -> (prompt_usd_per_million, completion_usd_per_million)
    "anthropic/claude-sonnet-4-5": (3.00, 15.00),
    "anthropic/claude-sonnet-4-6": (3.00, 15.00),
    "anthropic/claude-haiku-4-5": (1.00, 5.00),
    "openai/gpt-4o-mini": (0.15, 0.60),
    "google/gemini-flash-1.5": (0.075, 0.30),
}
DEFAULT_PRICING: tuple[float, float] = (5.00, 15.00)  # conservative fallback

def estimate_cost_usd(model: str, prompt_tokens: int, completion_tokens: int) -> float: ...
```

Actual rates to be filled in from current published OpenRouter pricing at
implementation time (values above are illustrative placeholders for planning — this is
exactly the kind of static table that goes stale and should carry a comment noting the
source/date it was seeded from, per `context_windows.py`'s own precedent).

## New module: `ze_core/telemetry/budget.py`

```python
@dataclass
class SpendBudgetConfig:
    session_limit_usd: float | None
    daily_limit_usd: float | None

@dataclass
class BudgetStatus:
    within_budget: bool
    scope: Literal["session", "daily"] | None  # which limit was hit, if any
    current_spend_usd: float
    limit_usd: float | None

class SpendBudgetChecker:
    def __init__(self, cost_store: CostStore, config: SpendBudgetConfig) -> None: ...

    async def check(self, session_id: str) -> BudgetStatus:
        """Sum estimated cost for the session and for today; compare against config.
        No config set on either scope => always within_budget=True (opt-in, FR-007)."""
```

`check()` performs two aggregate queries against `llm_cost_log`
(`SELECT model, prompt_tokens, completion_tokens FROM llm_cost_log WHERE session_id =
$1` and `... WHERE created_at >= $1::date`), applies `estimate_cost_usd` per row, sums,
and compares to configured limits. If both limits are `None`, short-circuits without a
query (avoids overhead for the common case of no budget configured, matching FR-007).

## Call-site change: `capability_check` node

```python
# core/ze-core/ze_core/orchestration/nodes/execution.py

async def capability_check(state: AgentState, config: RunnableConfig) -> dict:
    gate: CapabilityGate = config["configurable"]["capability_gate"]
    budget_checker: SpendBudgetChecker | None = config["configurable"].get("budget_checker")
    ...
    decisions = [gate.evaluate(...) for st in subtasks]

    if budget_checker is not None:
        status = await budget_checker.check(session_id=state["session_id"])
        if not status.within_budget:
            decisions.append(GateDecision.AWAIT_CONFIRMATION)
            state_updates["budget_status"] = status  # surfaced to draft_response/confirmation prompt text

    decision = min(decisions, key=lambda d: _GATE_RANK.get(d, 0))
    return {"gate_decision": decision, **state_updates}
```

`budget_checker` is `None` when no budget config is present (constructed conditionally
in the container, same pattern as other optional `configurable` deps already in this
node) — zero behavior change for users who never configure a budget (FR-007).

## Config surface: `apps/ze-api/config/config.yaml`

```yaml
# New, opt-in top-level block. Absent = current (telemetry-only) behavior.
budget:
  session_limit_usd: null    # e.g. 2.00
  daily_limit_usd: null      # e.g. 10.00
```

Hot-reloaded on SIGHUP, consistent with existing `config.yaml` behavior documented in
`CLAUDE.md`.

## Confirmation prompt content

When `gate_decision == AWAIT_CONFIRMATION` due to budget (not mode), the
`draft_response` node's prompt to the user must include `budget_status.current_spend_usd`
and `budget_status.limit_usd` (per spec Acceptance Scenario 3 / SC-004) — implementation
detail deferred to tasks.md, but the `BudgetStatus` dataclass above already carries the
fields needed to render that message without a second query.
