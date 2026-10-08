# Data Model: Routing Choice After E5 (164)

No database change. All types are in-process dataclasses. The persisted shape is the existing 162 `JudgmentTrace` inside `messages.trace`.

## `RoutingSurfaceConfig` (ze-core, `routing/judge.py`)

| Field | Type | Source | Rule |
|---|---|---|---|
| `enabled` | `bool` | `system_one.surfaces.routing.enabled` | default `False` |
| `choice_trust` | `float \| None` | `…routing.choice_trust` | `None` = uncalibrated; in `[0, 1]` |
| `multi_specialist_hold` | `float \| None` | `…routing.multi_specialist_hold` | `None` = uncalibrated; independent bar |
| `complexity_lookup_max` | `float \| None` | `…routing.complexity_lookup_max` | `None` = Score not consumed; regex runs |
| `shortlist_k` | `int` | `…routing.shortlist_k` | default 4; min 2; clamped to enabled agent count |

`calibrated` is true only when `enabled` and both `choice_trust` and `multi_specialist_hold` are set. Built by `routing_surface_config(settings)` with the same dict-or-`.config` tolerance as `speech_act_surface_config`. A bad bar (non-numeric, NaN, out of range) is `None` with a warning log. `shortlist_k` not an int ≥ 2 falls back to 4.

## `RoutingDecision` (ze-core, `routing/judge.py`)

| Field | Type | Meaning |
|---|---|---|
| `kind` | `"trust" \| "decompose" \| "abstain" \| "skip"` | outcome of the decision table |
| `agent` | `str \| None` | trusted shortlist agent (kind `trust`) |
| `reason` | `str` | `trusted`, `choice_none`, `multi_specialist`, `choice_unsure`, `invalid_answer`, or the client `skip_reason` |
| `confidence` | `float \| None` | Choice peakedness when the Choice is consumed |
| `complexity` | `"simple" \| "complex" \| None` | from the Score and `complexity_lookup_max`; `None` = regex |
| `consumed` | `frozenset[str]` | question ids that decided the outcome (`agent`, `multi_specialist`, `complexity`) |

## `RoutingJudgment` (ze-core, `routing/types.py`)

Carried on the envelope so `embed_route` can turn it into trace rows.

| Field | Type | Meaning |
|---|---|---|
| `result` | `SystemOneResult` | the raw client result |
| `question_kinds` | `dict[str, str]` | id → `choice` / `noul` / `score` |
| `consumed` | `frozenset[str]` | as above |
| `skip_reason` | `str \| None` | decision-level reason (`invalid_answer`) |

## `RoutingEnvelope` additions (ze-core, `routing/types.py`)

| Field | Type | Default | Meaning |
|---|---|---|---|
| `judgment` | `RoutingJudgment \| None` | `None` | set whenever a request was attempted |
| `complexity_source` | `"regex" \| "score"` | `"regex"` | `decompose` keeps `complexity` when `score` |

`apply_conductor_rewrite` (153/155) is unchanged; it builds a new envelope and does not need either field because the rows are already in `state["judgments"]`.

## Questions (ids)

| id | type | criteria | Used for |
|---|---|---|---|
| `agent` | choice | shortlist agent names → descriptions, plus `none` | trust / none |
| `multi_specialist` | noul | — | decompose when Choice would trust a single agent |
| `complexity` | score | ordered levels `lookup`, `single_tool`, `multi_hop` | model tier |

## Config block

```yaml
system_one:
  surfaces:
    routing:
      enabled: false
      choice_trust: null            # uncalibrated — set from make calibrate-routing
      multi_specialist_hold: null   # uncalibrated — set from make calibrate-routing
      complexity_lookup_max: null   # uncalibrated — set from make calibrate-routing
      shortlist_k: 4
```
