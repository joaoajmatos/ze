# Data Model: Complexity Routing (182)

## Config

```yaml
system_one:
  surfaces:
    routing:
      enabled: true
      choice_trust: 0.5
      multi_specialist_hold: 0.5
      shortlist_k: 9            # complexity_lookup_max: deleted (hard cut)
    complexity:                 # new surface
      enabled: false
      simple_max: null          # Noul needs_deep_reasoning at or below → model_simple
```

`ComplexitySurfaceConfig(enabled: bool = False, simple_max: float | None = None)`; `calibrated = enabled and simple_max is not None`. An invalid bar (bool, non-number, NaN, outside [0, 1]) parses to `None` with a warning.

## Engine types (`ze_core`)

| Type | Fields | Notes |
|---|---|---|
| `TierDecision` (`routing/tier.py`, frozen) | `tier: Literal["simple","full"]`, `decided_by: DecidedBy`, `consumed: bool` | Output of pure `decide_tier`. |
| `DecidedBy` | `"system_one" \| "off" \| "uncalibrated" \| "skip" \| "invalid_answer" \| "no_simple_model" \| "compound"` | `skip` carries the client's `skip_reason` on the judgment row. |
| `TierOutcome` (`routing/tier.py`, frozen) | `decision: TierDecision`, `model: str`, `judgment: RoutingJudgment \| None` | Returned by `TierJudge.choose`; `judgment` is `None` when no request was made. |
| `TierTrace` (`conversation/messages/types.py`) | `agent: str`, `tier: str`, `decided_by: str`, `model: str` | On `MessageTrace.tier: TierTrace \| None` and `AgentState["tier"]`. |
| `RoutingEnvelope` | **removed** `complexity`, `complexity_source` | Subtask `model` is always the full model at route time. |
| `RoutingSurfaceConfig` | **removed** `complexity_lookup_max` | |
| `RoutingDecision` | **removed** `complexity` | |
| `EngineStack` (`bootstrap.py`) | **removed** `estimator` | |

## Judgment row

Appended to `state["judgments"]` and `MessageTrace.judgments` via `judgments_from_result`: `question_id="needs_deep_reasoning"`, `kind="noul"`, `answer=<P(yes)>`, `consumed=True` only when `decided_by == "system_one"`, `skip_reason` on skip.

## API

`TierTraceResponse` (Pydantic, `ze_api/api/schemas.py`): `agent: str`, `tier: Literal["simple","full"]`, `decided_by: str`, `model: str`. Optional `tier: TierTraceResponse | None = None` on `MessageTraceResponse` and `MessageTraceEntry`; the same object in the `trace_update` WS frame.

## Storage

Migration `zc0NN_drop_routing_log_tier` (ze-core `zc` chain): `routing_log` drops `complexity TEXT` and `model_selected TEXT`. Downgrade re-adds both, nullable. No other table changes.

## Calibration row (`eval/calibration/complexity*.jsonl`)

| Field | Type | Rule |
|---|---|---|
| `id` | str | unique per file; prefix `cx-` (tuned) or `cxh-` (held-out) |
| `lang` | `"en" \| "pt"` | |
| `agent` | `"companion" \| "research" \| "goals"` | the routed agent |
| `conversation` | list of `{role: "user"\|"assistant", content: str}` | prior turns, oldest first; may be empty |
| `recap` | str \| null | resume recap text when the session resumed (then `conversation` is empty) |
| `memory` | list[str] | retrieved memory snippets, ≤ 5 |
| `focus` | str \| null | workflow/goal/procedure in focus |
| `skill` | `{name, description}` \| null | matched skill |
| `prompt` | str | the user's message this turn |
| `gold_tier` | `"simple" \| "full"` | research R2 label rule; unsure → `full` |
| `kind` | list of `single`, `multi_turn`, `anaphoric`, `resumed`, `with_memory`, `with_focus`, `with_skill` | coverage tags |
| `why` | str | one line |
