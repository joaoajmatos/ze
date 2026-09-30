# Data Model: System One Client

**Feature**: `162-system-one-client`

No new Postgres tables. Types below are in-process dataclasses (ze-agents / ze-core `types.py` style). Pydantic copies live only in `ze_api/api/schemas.py`.

## SystemOneQuestion

One named judgment in a request map. Discriminated by `type`.

| Field | Type | Rules |
|---|---|---|
| `type` | `"noul"` \| `"choice"` \| `"score"` | Required; wire name, not `yes_no` |
| `instructions` | `str` | Required; non-empty |
| `criteria` | `dict[str, str]` \| `list[str]` \| omitted | **choice**: non-empty `dict` of option → description. **score**: non-empty `list` of ordered level descriptions (2–10 typical). **noul**: optional `{true, false}` descriptions |

Unknown `type`, empty `instructions`, empty question map, or empty `state` → do not send HTTP; `SystemOneResult` skip `invalid_request`.

## SystemOneResult

Return of `evaluate`. Never a parsed chat string.

| Field | Type | Rules |
|---|---|---|
| `outcome` | `"ok"` \| `"skip"` | Required |
| `skip_reason` | `str \| None` | Closed set when skip: `disabled`, `missing_key`, `timeout`, `overload`, `error`, `invalid_request` |
| `model` | `str \| None` | **Reported** id from the response (may be dated, e.g. `typesafe/jev-1.13-20260917`). Null on skip |
| `provider` | `str \| None` | OpenRouter `provider` when present |
| `id` | `str \| None` | OpenRouter generation id (`gen-dec-…`) |
| `answers` | `dict[str, SystemOneAnswer]` | Empty on skip |
| `input_tokens` | `int \| None` | From `usage.input_tokens` |
| `output_tokens` | `int \| None` | From `usage.output_tokens` |
| `latency_ms` | `int` | Wall time of the attempt (including failed HTTP) |

## SystemOneAnswer

Per question id. Fields present depend on `type` (same as OpenRouter):

| `type` | Present |
|---|---|
| `noul` | `noul: float` in `[0, 1]`. No separate confidence |
| `choice` | `choice: str`, `probabilities: dict[str, float]`, `confidence: float` (peakedness) |
| `score` | `score: float`, `probabilities: dict[str, float]`, `confidence: float` |

Do not treat `confidence` here as doctrine `Confidence` or as E5 cosine.

## JudgmentTrace

One row on `MessageTrace.judgments`. JSON-safe for `asdict` → JSONB.

| Field | Type | Rules |
|---|---|---|
| `question_id` | `str` | Name in the questions map |
| `kind` | `"noul"` \| `"choice"` \| `"score"` | Primitive |
| `answer` | `str \| float \| None` | Label, noul, or score; null on skip |
| `probabilities` | `dict[str, float] \| None` | Choice/score; null for noul and skip |
| `peakedness` | `float \| None` | Wire `confidence` for choice/score; **null for noul** (0.5 is undecided, not medium) |
| `model` | `str \| None` | Reported model |
| `input_tokens` | `int \| None` | |
| `latency_ms` | `int` | |
| `consumed` | `bool` | True only if **code used** the answer to branch. Speculative unused answers stay false |
| `skip_reason` | `str \| None` | Set when this row is a skip, not a fake high-confidence answer |

## MessageTrace (existing)

Add `judgments: list[JudgmentTrace] = field(default_factory=list)`.

Old JSONB rows without the key deserialize as `[]`.

## AgentState (existing)

Add `judgments: list` (list of `JudgmentTrace`). `make_graph_input` sets `[]` every turn. `record_trace` copies into `MessageTrace.judgments`. 162 production path never appends.

## system_one config (YAML)

| Field | Type | Default |
|---|---|---|
| `enabled` | `bool` | `false` |
| `model` | `str` | `typesafe/jev-1.13` |
| `timeout_ms` | `int` | `2000` |
| `surfaces` | `dict` | `{}` — reserved; 162 ignores |

## Relationships

```text
SystemOneClient.evaluate
    → SystemOneResult (ok | skip)
    → (optional) CostTracker.record on ok
    → (later phases) append JudgmentTrace onto AgentState.judgments
        → record_trace → MessageTrace.judgments → messages.trace JSONB
            → REST / WS / trace panel
```

Disabled or missing key: skip result; no cost row; 162 does not write skip rows onto the trace unless a caller recorded them (no caller yet).
