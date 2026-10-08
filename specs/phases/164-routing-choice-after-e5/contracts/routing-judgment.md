# Contract: Routing judgment

Home: `core/engine/ze-core/ze_core/routing/judge.py`. Imports `ze_agents.system_one` types only.

## Request

One `SystemOneClient.evaluate(state, questions, max_attempts=1)` call per multi-agent turn.

State (named fields, no `AgentState`):

```json
{"user": "<raw user text, <=2000 chars>", "history": "<existing hint, optional>", "context": "<routing_hints, <=600 chars, optional>"}
```

Questions:

```
agent             choice  criteria = { <shortlist agent name>: <@agent.description>, ..., "none": "No listed agent can handle this request on its own." }
multi_specialist  noul    "Does this request need more than one of these specialists, for example look something up and then act on the result?"
complexity        score   criteria = ["lookup: ...", "single_tool: ...", "multi_hop: ..."]  (ordered)
```

Instructions end with `Judge the user's words; history and context are background only.` Production option order is E5 rank order; eval shuffles.

## Decision table

See research R2. `decide(result, cfg, shortlist) -> RoutingDecision` is pure and owns every bar. It never raises.

| Input | Outcome |
|---|---|
| surface off, or `choice_trust`/`multi_specialist_hold` null | no call (160 path) |
| client skip | `skip` (160 path) |
| Choice invalid/unknown/no confidence | `skip` `invalid_answer` |
| Choice `none` | `decompose` `choice_none` |
| Choice agent, peakedness < `choice_trust` | `abstain` `choice_unsure` (160 bars) |
| Choice agent ≥ `choice_trust`, Noul ≥ `multi_specialist_hold` | `decompose` `multi_specialist` |
| Choice agent ≥ `choice_trust`, Noul below bar or missing | `trust` |

Complexity: Score valid and `complexity_lookup_max` set → `simple` if `score <= bar`, else `complex`; otherwise `None` (regex).

## Config

`system_one.surfaces.routing`: `enabled`, `choice_trust`, `multi_specialist_hold`, `complexity_lookup_max`, `shortlist_k`. See [data-model.md](../data-model.md).

## Fail-open

Timeout, missing key, overload, error, invalid request, uncalibrated bar → the 160 path (pin 5, FR-006). The 162 client already returns skip rather than raising; the router wraps the call defensively and treats an exception as `error`.
