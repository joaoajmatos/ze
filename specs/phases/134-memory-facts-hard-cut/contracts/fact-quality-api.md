# Contract: `GET /api/v0/memory/facts/quality` provenance buckets

Existing route `getFactQuality` (`apps/ze-api/ze_api/api/routes/memory.py`).

## Breaking change (pre-v1)

`MemoryFactQualityResponse.by_provenance` MUST NOT include key `"raw"`.

Counts are grouped by stored doctrine values. Minimum keys after cut:

- `prompt_supplied` — former `raw` + new prompt-supplied writes
- `synthesized` — unchanged meaning

Include `graph_recall` and `live_search` when implementing via a single `GROUP BY provenance`
(preferred) rather than four FILTER clauses that omit empty keys.

`synthesized_unreviewed` / `synthesized_uncorroborated` / `synthesized_expired` still filter
`provenance = 'synthesized'`.

Pydantic schema stays `dict[str, int]` for `by_provenance`. Tests that assert `"raw"` update
to `"prompt_supplied"`.
