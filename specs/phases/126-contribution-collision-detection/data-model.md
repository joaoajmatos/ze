# Phase 1 Data Model: Contribution Collision Detection

## Modified: `Contribution` (`core/ze-plugin/ze_plugin/contribution.py`)

Two new optional fields — additive, does not change existing construction call sites that don't
set them:

| Field | Type | Default | Purpose |
|---|---|---|---|
| `content` | `str \| None` | `None` | Short text representation of the claim, used for the NLI contradiction check and for the collision log's conflict summary. `None` means "this contribution can never be a collision candidate" (fail-open by construction — no content, no comparison). |
| `entity_ids` | `list[UUID]` | `[]` | Canonical `memory_entities.id` values this contribution links, as already resolved by the producer (R2). Empty means matching falls back to `target_face` per FR-002. |

`validate_and_submit`'s own signature and behavior are unchanged — these fields are simply unused
by it, exactly as `evidence` was already an optional-in-practice field some callers leave empty.

## New: `CollisionCandidate` (internal, `ze_collision/detect.py`)

Not persisted — an in-memory record of a recently-submitted contribution kept for the recency
window, used to find candidate pairs for a newly-submitted one.

| Field | Type | Notes |
|---|---|---|
| `domain_id` | `UUID` | The producer's own ID for the domain object (loop ID, signal ID, hypothesis ID, dream artifact ID, contact ID) |
| `producer_kind` | `str` | A short tag identifying the domain object's kind (`"open_loop"`, `"signal"`, `"dream_artifact"`, `"hypothesis"`, `"contact"`) — plugin/producer-domain vocabulary, never a core enum (constitution Principle III) |
| `source_function` | `SourceFunction` | From the originating `Contribution` |
| `claim_kind` | `ClaimKind` | From the originating `Contribution` |
| `target_face` | `TargetFace` | From the originating `Contribution` |
| `content` | `str` | From `Contribution.content` |
| `entity_ids` | `list[UUID]` | From `Contribution.entity_ids` |
| `submitted_at` | `datetime` | When this contribution passed through the seam |

Held in a small in-process bounded structure (recency-window-scoped, single-process — consistent
with the single-user model, no cross-process coordination needed) keyed for lookup by entity ID
and by `target_face`.

## New: `CollisionLogEntry` (`ze_collision/types.py`) — persisted

Append-only; not itself a claim on the world-state (per spec's Key Entities section).

| Field | Type | Notes |
|---|---|---|
| `id` | `UUID` | Primary key, server-generated |
| `contribution_a_domain_id` | `UUID` | First contribution's domain object ID |
| `contribution_a_producer_kind` | `str` | e.g. `"open_loop"` |
| `contribution_a_source_function` | `SourceFunction` | |
| `contribution_a_claim_kind` | `ClaimKind` | |
| `contribution_b_domain_id` | `UUID` | Second contribution's domain object ID |
| `contribution_b_producer_kind` | `str` | |
| `contribution_b_source_function` | `SourceFunction` | |
| `contribution_b_claim_kind` | `ClaimKind` | |
| `matched_entity_id` | `UUID \| None` | The shared entity that triggered the candidate match, if any (FR-005) |
| `matched_target_face` | `TargetFace` | The shared `target_face` (always present — both contributions target the same face by construction) |
| `conflict_summary` | `str` | Short description of the detected conflict (derived from the NLI check + both `content` values) |
| `created_at` | `datetime` | Server-generated, when the collision was logged |

**Validation rules**: `contribution_a_source_function != contribution_b_source_function` always
holds by construction (FR-002/FR-007) — enforced in `detect.py`, not re-validated at the DB layer
(append-only log, no update path, no reason for a CHECK constraint to reject a well-formed insert
from trusted internal code).

**Lifecycle**: Write-once. No update, no delete path (append-only, per spec's Key Entities
section). Read via the `list_collisions()` query surface (FR-009) and, transitively, the REST
route.

**Indexes** (for FR-009's filters): `(matched_entity_id, created_at)`,
`(contribution_a_source_function, contribution_b_source_function, created_at)`, `(created_at)` for
plain date-range queries.

## Store: `CollisionLogStore` Protocol + `PostgresCollisionLogStore` (`ze_collision/store.py`)

```python
class CollisionLogStore(Protocol):
    async def log(self, entry: CollisionLogEntry) -> CollisionLogEntry: ...
    async def list(
        self,
        *,
        entity_id: UUID | None = None,
        source_function: SourceFunction | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[CollisionLogEntry]: ...
```

Modeled on `PushLogStore`'s shape (`core/ze-proactive/ze_proactive/push_log_store.py`) — a thin
asyncpg-backed Protocol implementation, no ORM (constitution Principle VI).

## Migration: `zcol001_contribution_collisions.py`

New chain, owned by `ze-collision`, registered in `ze_api/migrate.py`'s
`_ZE_COLLISION_VERSIONS`. Single table `contribution_collisions` mirroring `CollisionLogEntry`
above, plus the three indexes listed.
