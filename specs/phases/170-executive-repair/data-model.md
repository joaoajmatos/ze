# Data Model: Executive Repair

No migration. No change to `OpenLoop`, `StuckGoal`, `Goal` or table shapes.

## Store API changes

`LoopStore` (Protocol and `PostgresLoopStore`, `ze_worldstate/store.py`):

| Method | Change |
|---|---|
| `list_drift_candidates()` | SQL predicate becomes `state = 'active' AND drift_deadline IS NOT NULL AND drift_deadline <= now()` |
| `record_corroboration(loop_id, *, window_days=DEFAULT_DRIFT_WINDOW_DAYS)` | **new.** Active only: `drift_deadline = GREATEST(COALESCE(drift_deadline, now()), now() + make_interval(days => $2))`, `updated_at = now()`. Other states: no-op |

`GoalStore.list_stuck` (Protocol unchanged, `PostgresGoalStore` query changes): one `awaiting_gate` row per goal.

`MemoryStore.write_episode` (Protocol in `ze_memory/store.py`, impl in `retriever.py`): return type `None` → `UUID | None`.

## Worldstate types

`LoopAdmission.commit`: `Callable[[], Awaitable[list[OpenLoop]]] | None` → `Callable[[Sequence[EvidenceRef]], Awaitable[list[OpenLoop]]] | None`.

`LoopInflow.extract(text, provenance)` → `extract(text, provenance, evidence: Sequence[EvidenceRef] = ())`.

Removed: `DriftingLoopMention`.

## Priority

`ze_priority.types` gains:

```python
@dataclass
class PrioritySnapshotResult:
    items: list[MergedPriorityItem]
    sources_failed: tuple[SourceKind, ...]   # sorted, stable
```

`ze_priority.rest.get_snapshot` returns `PrioritySnapshotResult`.

REST (`apps/ze-api/ze_api/api/schemas.py`):

```python
SourceKindLiteral = Literal["loop", "goal", "hypothesis", "relationship"]

class PrioritySnapshotResponse(BaseModel):
    items: list[PrioritySnapshotItem]
    sources_failed: list[SourceKindLiteral]
```

`PrioritySnapshotItem.source_kind`, `PriorityOverrideSchema.anchor_source_kind` and `PriorityOverrideRequestSchema` kinds use `SourceKindLiteral`.

## Config (`apps/ze-api/config/config.yaml`)

```yaml
worldstate:
  drift:
    enabled: true
    cron: "0 5 * * *"          # window_days removed
  push:
    enabled: true              # now read
    inline_cooldown_hours: 12  # now read
    thresholds:                # now read
      tau_confidence: 0.5
      tau_relevance: 0.5
      novelty_similarity_max: 0.85
      grounding_threshold: 0.3   # was 0.5 and unread; 0.3 is what the code ran with
correlation:
  push:
    enabled: false             # now honored by the arbitration path
    dry_run: true              # now honored by the arbitration path
```

## Harness

| Name | Where | Meaning |
|---|---|---|
| marker `pg` | `apps/ze-api/pyproject.toml` | needs a real Postgres |
| env `ZE_TEST_PG` | process | `1` enables `pg` tests |
| env `ZE_TEST_PG_URL` | process | optional asyncpg URL; skips container start |
| fixture `pg_dsn` (session) | `tests/pg/conftest.py` | async DSN of the migrated database |
| fixture `pg_pool` (function) | same | asyncpg pool, tables truncated before use |
| make target `test-pg` | `Makefile` | runs `-m pg` with `ZE_TEST_PG=1` |
