# Contract: Collision Log Query Surface

Per the clarification recorded in spec.md (Session 2026-08-26), this is exposed as a REST
endpoint following the codebase's existing pattern for other queryable stores (`GET
/api/v0/loops`, `/api/v0/notifications`, `/api/v0/skills`). Auth: `require_api_key`
(`HTTPBearer`), same as every other `/api/v0/` route — no new auth mechanism (single API key,
constitution Principle II).

## `GET /api/v0/collisions`

**Summary**: List logged cross-function contribution collisions (FR-009).

**Query parameters** (all optional, combine with AND):

| Param | Type | Description |
|---|---|---|
| `entity_id` | UUID | Only collisions whose `matched_entity_id` equals this |
| `source_function` | string (`SourceFunction` value) | Only collisions where either side's `source_function` matches |
| `since` | ISO 8601 datetime | Only collisions with `created_at >= since` |
| `until` | ISO 8601 datetime | Only collisions with `created_at <= until` |
| `limit` | int, default 50, max 200 | Page size |

**Response `200`**: `list[CollisionLogEntrySchema]`, each item:

```json
{
  "id": "uuid",
  "contribution_a": {
    "domain_id": "uuid",
    "producer_kind": "open_loop",
    "source_function": "perception",
    "claim_kind": "fact"
  },
  "contribution_b": {
    "domain_id": "uuid",
    "producer_kind": "hypothesis",
    "source_function": "reflection",
    "claim_kind": "inference"
  },
  "matched_entity_id": "uuid",
  "matched_target_face": "world",
  "conflict_summary": "string",
  "created_at": "2026-08-26T12:00:00Z"
}
```

Matches FR-005 and FR-009's "sufficient detail to review the collision without further lookups"
requirement (User Story 3, Acceptance Scenario 1) — no separate lookup of the original
contributions is needed to understand what collided and why.

**Response model / OpenAPI**: declares `response_model`, `summary`, and `description` per
`CLAUDE.md`'s REST conventions; request query params via annotated `Query(...)`, matching the
`/api/v0/loops` route's existing style.

## Internal contract: `submit_and_detect_collisions()`

Not an external interface, but the seam every producer call site (six today) integrates against —
documented here because it's this feature's actual point of integration, per `plan.md`'s Project
Structure.

```python
async def submit_and_detect_collisions(
    contribution: Contribution,
    write: Callable[[], Awaitable[T]],
    *,
    result_id: Callable[[T], UUID],
    producer_kind: str,
    check_fact_exists: Callable[[UUID], Awaitable[bool]] | None = None,
    check_episode_exists: Callable[[UUID], Awaitable[bool]] | None = None,
    check_signal_exists: Callable[[UUID], Awaitable[bool]] | None = None,
) -> T: ...
```

**Contract**:
- Delegates to the unmodified `ze_plugin.contribution.validate_and_submit()` for validation and
  persistence — identical rejection behavior, identical return value, identical exceptions
  (FR-001, FR-006).
- Only after `write()` succeeds does it run the collision check, using `contribution.content` /
  `contribution.entity_ids` / `contribution.target_face` / `contribution.source_function` and
  `result_id(result)` as this contribution's identity.
- The collision check itself never raises past this function's boundary and never delays the
  return of `result` beyond a hard, short timeout on the NLI call (FR-008) — implemented as
  "compute the result, schedule the collision check, return the result," with the check's own
  errors caught and logged, not propagated.
- If `contribution.content is None`, the check is skipped entirely for that contribution (it can
  still be a "past" candidate contributed to the recency window with no content, but will never
  itself trigger a comparison, nor match against later ones, since NLI needs both sides' text).
