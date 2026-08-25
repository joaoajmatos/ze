# Contract: `FactDigestItem.created_at`

The only server-facing contract change in this feature — everything else is client-side derivation from data already returned.

## Before

```json
{ "id": "...", "key": "favorite_color", "value": "teal", "agent": "companion" }
```

## After

```json
{ "id": "...", "key": "favorite_color", "value": "teal", "agent": "companion", "created_at": "2026-07-02T14:03:00Z" }
```

**Backward compatibility**: Purely additive field on an existing response (`GET /api/v0/entities/{id}`, `EntityDetailResponse.facts[]`). No existing consumer breaks — `apps/ze-web`'s current `EntityDetailPanel` only reads `f.key`/`f.value`. `packages/ze-client`'s generated `FactDigestItem` type gains the field on the next codegen run (`bun run scripts/codegen.ts`), matching how spec 118 wired new fields through the same pipeline.

**Source**: `core/ze-memory/ze_memory/admin.py`'s `get_entity_detail` (~line 384) already runs `SELECT f.id, f.predicate AS key, f.value, ... FROM memory_facts f ... ORDER BY f.created_at DESC` — it already sorts by `created_at`, it just doesn't select or return it. The fix is two one-line changes: add `f.created_at` to the `SELECT` list, and add `"created_at": r["created_at"]` to the dict comprehension that builds each fact entry (~line 396). No new query, no new column, no migration.
