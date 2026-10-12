# ze-collision

Contribution collision detection — logs when two parts of Ze make conflicting claims.

## Role in Ze

Many parts of Ze write claims to the world-state through the contribution seam. Two of them can disagree. For example, a user states a priority and Ze's own reasoning synthesizes another. This package notices the conflict and records it. It never blocks, delays, or resolves either write.

### Key features

- `submit_and_detect_collisions()` wraps `validate_and_submit()` from `ze-plugin` without changing it
- Compares a new contribution with recent ones from a different `(source_function, provenance)` pair on the same world-state face
- Uses the NLI model to find real contradictions, not mere co-occurrence
- Fails open: a detection error never affects the write
- Append-only `contribution_collisions` log with a query function

### Integration

`ze-api` builds a `PostgresCollisionLogStore` and passes it to the packages that submit contributions (`ze-memory`, `ze-correlation`, `ze-worldstate`, `ze-priority`). `GET /api/v0/collisions` lists the log. The package keeps a 24-hour in-memory window of recent contributions. The window lives in one process and is not shared.

## Responsibilities

| Module | What it provides |
|---|---|
| `detect.py` | `submit_and_detect_collisions()` and the recency window |
| `store.py` | `CollisionLogStore` Protocol and `PostgresCollisionLogStore` |
| `rest.py` | `list_collisions()` — filter by entity, source function, and time |
| `types.py` | `CollisionCandidate` and `CollisionLogEntry` dataclasses |
| `migrations/` | `zcol001` — creates `contribution_collisions` |

## Dependencies

`ze-agents`, `ze-plugin`, `ze-logging`, `asyncpg`.

## Usage

```python
from ze_collision.detect import submit_and_detect_collisions
```

Call it where code would call `validate_and_submit()`. Plugin code reaches it through `ze_sdk.contribution`.

## Testing

From the repo root:

```bash
make test-collision
```

See [docs/testing.md](../../../docs/testing.md).
