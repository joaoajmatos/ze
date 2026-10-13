# Contract: priority snapshot response

## Python

```python
# ze_priority/types.py
@dataclass
class PrioritySnapshotResult:
    items: list[MergedPriorityItem]
    sources_failed: tuple[SourceKind, ...]

# ze_priority/rest.py
async def get_snapshot(priority_view, override_store) -> PrioritySnapshotResult:
    ranking = await priority_view.rank()
    overrides = await override_store.get_active()
    return PrioritySnapshotResult(
        items=merge(ranking, overrides, datetime.now(UTC)),
        sources_failed=tuple(sorted(ranking.sources_failed)),
    )
```
`_snapshot_row_for` uses `.items`. `PriorityView.rank` is unchanged (still raises `ZePriorityError` only when every configured source fails).

## REST

`GET /api/v0/priority/snapshot` → `PrioritySnapshotResponse`:

```json
{ "items": [ { "source_kind": "relationship", "source_id": "…", "title": "Ana",
               "displayed_rank": 3, "computed_rank": 3,
               "overridden_from_computed": false, "override": null } ],
  "sources_failed": ["goal"] }
```

`operation_id` stays `getPrioritySnapshot`. Summary and description updated to mention `sources_failed`. `POST /override` and `POST /override/{id}/unpin` still return one `PrioritySnapshotItem`.

`SourceKindLiteral = Literal["loop","goal","hypothesis","relationship"]` in `schemas.py` replaces the inline Literals on `PrioritySnapshotItem.source_kind`, `PriorityOverrideSchema.anchor_source_kind` and the kinds in `PriorityOverrideRequestSchema`.

## Client and web

- `make codegen` regenerates `packages/ze-client/src/generated/*`. Commit the result.
- `usePrioritySnapshotQuery` returns `{ items: PrioritySnapshotItem[]; sourcesFailed: string[] }` (`data?.items ?? []`).
- `PrioritySnapshot` shows, above the list when `sourcesFailed.length > 0`, a notice: "Couldn't load: {labels}. The ranking may be incomplete." Labels from the same map as `SOURCE_LABEL` with `relationship: "Relationship"` added (plural-neutral wording).
- Query-key and optimistic update code that reads the cached array (`useReprioritizeMutation`, `useUnpinPriorityOverrideMutation`) updates to the new shape.

## Tests

- `apps/ze-api/tests/api/test_priority_routes.py` (create if absent): relationship item → 200; `sources_failed` reported; response keys.
- `core/arbitration/ze-priority/tests/test_rest.py` (create if absent): `get_snapshot` returns the failed sources sorted.
- `apps/ze-web/src/widgets/priority-snapshot/ui/PrioritySnapshot.test.tsx` (create if absent): notice present/absent; relationship label.
