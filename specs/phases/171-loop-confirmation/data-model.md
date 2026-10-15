# Data Model: Loop Confirmation Path (171)

No migration. No new table or column.

## `LoopOffer` (new, `ze_priority/types.py`)

| Field | Type | Notes |
|---|---|---|
| `loop_id` | `UUID` | the suspected loop |
| `title` | `str` | as stored |
| `provenance` | `str` | e.g. `email`, `conversation`, `calendar`, `ingestion` |

Frozen dataclass. Built only by `TurnSurfacing.resume_loop_offers`.

## Offer record (existing `push_log`)

| Column | Value |
|---|---|
| `event_type` | `worldstate_loop_offer:<loop_id>` |
| `payload` | `None` |
| `sent_at` | now (default) |

Cooldown query: `was_sent_within_hours(event_type, 168)`.

## `ResumeRecap` (changed, `ze_core/orchestration/nodes/context.py`)

| Field | Change |
|---|---|
| `loop_offers: list[Any]` | **new**, default `[]`; items expose `.title` (duck-typed; `ze_core` does not import `LoopOffer`) |
| `has_content()` | also true when `loop_offers` is non-empty |
| `render()` | appends, after workflows: `"Not yet tracked (Ze noticed these; the user has not confirmed them):"`, one `- <title>` line each, then the instruction line (see contract) |

## `AgentState` (changed, `ze_core/orchestration/state.py`)

| Key | Type | Set by | Read by |
|---|---|---|---|
| `open_items_query` | `bool` | `fetch_context`, every turn | `surface_loops` |
| `loop_offer_ids` | `list[str]` | `fetch_context`, every turn (`[]` off the gap branch) | `record_trace` |

## `MessageTrace` / `MessageTraceResponse` (changed)

`loop_offer_ids: list[str] = []` added beside `resume_recap_applied` in `ze_core/conversation/messages/types.py`, the store parser (`store.py`, default `[]` for old rows), `ze_api/api/schemas.py`, `ze_api/api/messages.py`, and the generated `@myguyze/ze-client` types.

## Open loop lifecycle (unchanged edges, new write on one edge)

```
suspected --confirm (page | REST | confirm_loop | track_loop match)--> active
          stamp: confidence 0.9, confirmed_at = updated_at = now(), drift_deadline = now + 7d, drift_rationale NULL
suspected --drop (page | REST | drop_loop)--> dropped (+ dismissal fingerprint, 109)
suspected --14 days, StaleSuspicionJob--> dropped
```

Provenance and claim kind never change on confirm.

## Constants

| Name | Value | Where |
|---|---|---|
| `OFFER_LIMIT` | 3 | `ze_priority/turn.py` |
| `OFFER_COOLDOWN_HOURS` | 168 | `ze_priority/turn.py` |
| `RECAP_LIMIT` | 5 | `ze_priority/turn.py` |
| `OPEN_QUERY_LIMIT` | 10 | `ze_priority/turn.py` |
| `OPEN_QUERY_THRESHOLD` | from calibration | `ze_priority/open_query.py` |
| `OPEN_QUERY_EXAMPLES` | ~15 EN + ~15 PT | `ze_priority/open_query.py` |
