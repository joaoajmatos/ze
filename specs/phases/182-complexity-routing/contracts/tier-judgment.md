# Contract: Tier judgment (182)

Normative for `ze_core/routing/tier.py` and `ze_core/orchestration/nodes/tier.py`.

## When `choose_tier` asks

Evaluated in order; the first matching row wins. No request is made unless the last row is reached. Implementation note: a missing `tier_judge` is checked first among rows 3-5 (row 3 needs the judge's app config to compare the two models), so with no judge the label is `off`, not `no_simple_model`. Any exception while building the state or asking (rows 6) fails safe to the full model with `decided_by` `skip` and no judgment row.

| # | Condition | Tier | `decided_by` | Request |
|---|---|---|---|---|
| 1 | no envelope or no subtasks | — (node returns `{}`) | — | no |
| 2 | `len(subtasks) != 1`, or `envelope.is_compound`, or `state["conductor_hint"]` non-empty | full | `compound` | no |
| 3 | `resolve_agent_model(agent, "simple") == resolve_agent_model(agent, "full")` (no `model_simple`, or an override makes them equal) | full | `no_simple_model` | no |
| 4 | no `tier_judge` injected, or `system_one.enabled` false, or the surface `enabled` false | full | `off` | no |
| 5 | surface enabled and `simple_max` null | full | `uncalibrated` | no (warning once per process) |
| 6 | otherwise | per `decide_tier` | per `decide_tier` | **yes**, one request, `max_attempts=1` |

## `decide_tier(result, cfg)` (pure, never raises)

| Result | Tier | `decided_by` | `consumed` |
|---|---|---|---|
| `outcome == "skip"` (timeout, error, 429/529, disabled client) | full | `skip` | false |
| client raised (caught in `TierJudge`) | full | `skip` (`skip_reason="error"`) | false |
| answer missing, not `type="noul"`, not a number, NaN, or outside [0, 1] | full | `invalid_answer` | false |
| `noul <= simple_max` | simple | `system_one` | true |
| `noul > simple_max` | full | `system_one` | true |

## Question

```python
{"needs_deep_reasoning": SystemOneQuestion(type="noul", instructions=TIER_INSTRUCTIONS)}
```

`TIER_INSTRUCTIONS`: research R2 draft; tuned on the tuned set only, frozen before the held-out run. It MUST ask about the task the user is trying to get done and tell the model to resolve references from the conversation and context. It MUST NOT include the routing suffix "history and context are background only".

## State (`build_tier_state`)

Named fields, each capped, omitted when empty (research R3): `task`, `conversation`, `recap`, `memory`, `focus`, `skill`, `agent`. Nothing else. Total under ~8 kB.

## Effects

- `simple` → `envelope.subtasks[0].model = resolve_agent_model(agent, "simple", app_config)`.
- Always → `state["tier"] = TierTrace(agent, tier, decided_by, model)`; judgment rows appended (never replacing routing or skill rows).
- Telemetry agent context is `router` during the request.
- Log event `tier_decided` with `agent`, `tier`, `decided_by`, `noul` (rounded), `latency_ms`.

## Trace values shown in the web Routing section

| `tier` / `decided_by` | Text |
|---|---|
| simple / system_one | "Light model · System One" |
| full / system_one | "Full model · System One" |
| full / off | "Full model · tiering off" |
| full / uncalibrated | "Full model · tiering not calibrated" |
| full / skip, invalid_answer | "Full model · System One unavailable" |
| full / compound | "Full model · multi-agent turn" |
| full / no_simple_model | nothing shown (agent has one model) |
