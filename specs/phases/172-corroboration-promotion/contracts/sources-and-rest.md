# Contract: Source keys through the inflows, and the REST surface

## Extractor callable (plugins see only this)

Before (after 170): `extract(text: str, provenance: str, evidence: Sequence[EvidenceRef] = ()) -> None`
After: `extract(text, provenance, evidence=(), source_ref: str | None = None) -> None`

`LoopInflow.extract` builds `SourceKey(provenance, source_ref)` when `source_ref` is truthy.
`LoopInflow.admit(configurable, *, prompt)` builds `SourceKey("conversation", configurable.get("thread_id"))` and stores it on the `LoopAdmission` so the later `commit` uses it.
`propose_loop_candidates(..., source: SourceKey | None = None)` threads it to every create and match path.

| Caller | Change |
|---|---|
| `ze_messenger/inbound/processor.py` | `self.loop_extractor(msg.body, "email", <170 evidence>, source_ref=msg.thread_id or msg.message_id)`; annotate the attribute type to accept the keyword |
| `ze_calendar/jobs/calendar_reminder.py` | pass `source_ref=signal.external_ref` |
| `ze_ingestion/sink.py` | pass `source_ref=ingestion_id` |
| `ze_worldstate/inflow.py` | factories unchanged in arguments; the returned `.extract` gains the keyword |

Plugins keep importing nothing from `ze_worldstate`.

## REST

### `GET /api/v0/loops` → `list[LoopListItem]`

Adds `promoted: bool` and `source_inflows: list[str]` (distinct inflows of the loop's source rows, in first-seen order). `ze_worldstate.rest.list_loops` fetches sources for the listed loops in one query (`WHERE loop_id = ANY($1)`), not one per loop.

### `GET /api/v0/loops/{id}` → `LoopDetail`

Adds `sources: list[LoopSourceItem]`:

```json
{"role": "origin", "inflow": "conversation", "evidence_kind": "episode",
 "same_concern": null, "promoted": false, "created_at": "2026-10-13T09:12:00Z"}
{"role": "corroboration", "inflow": "email", "evidence_kind": "episode",
 "same_concern": 0.93, "promoted": true, "created_at": "2026-10-15T08:01:00Z"}
```

Route `summary`/`description` updated to mention sources. `response_model` unchanged by name.

### Codegen

`make codegen` regenerates `packages/ze-client/src/generated/*`; committed with the change.

## Web

On the loop row of the `/loops` page added by 171: when `promoted` is true, a muted line "Promoted · seen in: {labels}" with labels from `source_inflows` (conversation → chat, email → email, calendar → calendar, ingestion → a document). The label helper lives in the loop entity slice (`entities/loop/lib/format.ts`). No new query hook: `useLoopsQuery` already returns the list.
