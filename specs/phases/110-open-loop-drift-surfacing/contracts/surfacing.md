# Contracts: Open-Loop Drift Detection & Surfacing

This feature adds no new REST endpoints (Phase A's `GET/POST /api/v0/loops...` surface already
covers review). Its "interfaces" are: one additive REST field, one new orchestration-graph
`config["configurable"]` key, and one new inter-package function surface
(`ze-worldstate → ze-correlation`). Each is documented below as the stable contract other code
depends on.

## 1. REST — additive field on existing loop payloads

`GET /api/v0/loops` and `GET /api/v0/loops/{id}` (`ze_worldstate/rest.py`,
`apps/ze-api/ze_api/api/routes/loops.py`) responses gain one additive, nullable field:

```jsonc
{
  "id": "...",
  "title": "...",
  "state": "drifting",
  "claim_kind": "inference",
  "provenance": "conversation",
  "confidence": 0.42,
  "drift_rationale": "No corroborating evidence (email, calendar, or conversational update) since confirmation on 2026-07-10; implied window elapsed 2026-07-17.",
  "created_at": "...",
  "updated_at": "..."
}
```

- `drift_rationale` is `null` for any loop not in (and never having passed through) `drifting`.
- No existing field changes shape or meaning. No client-breaking change; `ze-web`'s loop-review
  widget renders the field only if present (progressive enhancement, per Assumptions: "No new
  UI paradigm").

## 2. `config["configurable"]["loop_surfacer"]` — orchestration-graph injection contract

Mirrors the existing `config["configurable"]["correlation_engine"]` contract in shape and
lifecycle (constructed once at container build time in `ze_api/container.py`, passed at
`graph.ainvoke(..., config)` time, read once per turn by the new `surface_loops` node).

```python
class LoopSurfacer(Protocol):
    async def inline_candidates(self, entity_ids: list[UUID]) -> list[DriftingLoopMention]: ...
```

- Called by `ze_core/orchestration/nodes/loop_surfacing.py` with the turn's resolved entity ids
  (same `state["memory_context"].entities` source `nodes/correlation.py` already reads via
  `_extract_seeds`).
- Returns zero or more `DriftingLoopMention` values (loop id, title, **hedged `mention_text`**
  built via `format_hedged_mention`, evidence refs) — entity-link-overlap matches only, no
  confidence/relevance/novelty/budget gating (FR-006: inline has no such gate).
- If the key is absent from `config["configurable"]` (e.g. a test harness that doesn't wire it),
  the node returns `{}` immediately — identical fallback behavior to `nodes/correlation.py`'s
  `engine is None` branch, so `ze-core`'s test suite needs no new fixture to keep passing.
- The node never raises; any `LoopSurfacer` exception is caught and logged
  (`inline_loop_surfacing_error`), matching `correlate`'s own `except Exception` fallback.

## 3. `ze_correlation.push` — extracted bar functions (new inter-package surface)

These five functions become the actual, minimal contract of the new `ze-worldstate →
ze-correlation` dependency edge (research.md §4). Signatures are stable and intentionally
`Hypothesis`-agnostic:

```python
def passes_confidence(confidence: float, tau: float) -> bool: ...

def passes_relevance(relevance: float, tau: float) -> bool: ...

async def passes_novelty(
    summary: str,
    recent_summaries: list[str],
    embedder: Any,
    max_similarity: float,
) -> bool: ...

async def passes_grounding(
    summary: str,
    evidence_labels: list[str],
    nli_client: NLIClient | None,
    threshold: float,
) -> bool: ...

async def within_budget(
    push_log: Any,
    event_key: str,
    max_per_day: int,
    window_hours: float = 24.0,
) -> bool: ...
```

- `CorrelationPushConsumer._passes_push_bar` is refactored to call these same functions with its
  existing `hypothesis.confidence`/`hypothesis.summary`/evidence — behavior-preserving, verified
  by the existing `core/ze-correlation/tests/test_push.py` suite continuing to pass unmodified.
- `ze_worldstate.surfacing.LoopSurfacer.passes_push_bar` calls all five functions with the
  loop's own `confidence`, a `relevance` score computed via the injected `RelevanceModel` against
  the loop's linked entity names (`topics=[]`, research.md §7), `drift_rationale` as `summary`,
  resolved evidence labels, and the distinct `event_key="worldstate_loop_push"` — plus one
  loop-specific gate, the inline-cooldown check (research.md §6), that has no correlation-engine
  equivalent and lives entirely in `ze-worldstate`.
- `ze-worldstate`'s `pyproject.toml` gains `"ze-correlation"` as a direct dependency; `CLAUDE.md`'s
  package dependency graph table is updated in the same commit (constitution Governance
  principle + Clarification).
