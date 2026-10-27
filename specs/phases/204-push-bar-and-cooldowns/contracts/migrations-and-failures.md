# Contract: migrations and the workflow-failure read

## Migrations

Two migrations, each on its owner's chain. Both are raw SQL Alembic files; `ze_api/cli/migrate.py` already lists both chains (`_ZE_PROACTIVE_VERSIONS`, `_ZE_PRIORITY_VERSIONS`), so the runner needs no change.

### `zpro006_push_claims` (ze-proactive, lane `lead`)

- File: `core/contracts/ze-proactive/ze_proactive/migrations/versions/zpro006_push_claims.py`
- `revision = "zpro006"`, `down_revision = "zpro005"` (the head of the `zpro` chain on main).
- Upgrade, in order:
  1. `DELETE FROM push_log WHERE event_type <> 'attention_push' OR idempotency_key IS NULL`
  2. `DROP INDEX IF EXISTS ux_push_log_event_idempotency`; `DROP INDEX IF EXISTS push_log_event_type_sent_at_idx`
  3. `ALTER TABLE push_log RENAME COLUMN idempotency_key TO claim_key`; `ALTER COLUMN claim_key SET NOT NULL`
  4. `ADD COLUMN discretionary BOOLEAN NOT NULL DEFAULT TRUE`; `ALTER COLUMN discretionary DROP DEFAULT`
  5. `CREATE INDEX push_log_claim_key_sent_at_idx ON push_log (claim_key, sent_at DESC)`; `CREATE INDEX push_log_discretionary_sent_at_idx ON push_log (sent_at) WHERE discretionary`
- Downgrade: drop the two new indexes and `discretionary`, rename `claim_key` back, drop `NOT NULL`, recreate the two old indexes. Older repeat claims of one key are deleted first (the newest stays), because the old unique index allows one row per `(event_type, key)`. Deleted rows stay deleted.
- test-pg: `apps/ze-api/tests/pg/test_push_claims_pg.py` (replaces `test_push_log_window_pg.py`) checks the claim rules (research R2); the upgrade over old rows is checked on a scratch database (tasks T041): a second claim of the same key inside the window is `cooling`; outside it, `won`; `within=None` cools forever; the budget count reaches `over_budget`; `release` frees the key; two concurrent `claim` calls on one key give one `won`.

### `zpri002_surfacing_memory` (ze-priority, lane `conv`)

- File: `core/arbitration/ze-priority/ze_priority/migrations/versions/zpri002_surfacing_memory.py`
- `revision = "zpri002"`, `down_revision = "zpri001"`.
- Upgrade: create `surfacing_memory` and `surfacing_memory_lookup_idx` as in data-model.md. No data is copied from `push_log` (the inline and offer rows are dropped by `zpro006`; dev data is disposable).
- Downgrade: drop the table.
- test-pg: `apps/ze-api/tests/pg/test_loop_confirmation_pg.py` (offers cool for a week) moves onto the new table.

Migration order between chains does not matter: neither reads the other's table.

AGENTS.md "Migration ownership" rows change: ze-proactive (`push_log` claims, `zpro006`), ze-priority (`surfacing_memory`, `zpri002`).

## Workflow failures (lane `jobs`)

```python
# ze_automation/workflow/types.py
@dataclass(frozen=True)
class WorkflowFailure:
    workflow_id: UUID | None
    workflow_name: str
    execution_id: UUID
    failed_at: datetime
    error: str | None

# ze_automation/workflow/store.py (Protocol) and postgres.py (PostgresWorkflowStore)
async def list_failed_executions(self, since_hours: float) -> list[WorkflowFailure]: ...
```

SQL: `workflow_executions e LEFT JOIN workflows w ON w.id = e.workflow_id WHERE e.status = 'failed' AND e.completed_at > now() - ($1 * interval '1 hour') ORDER BY e.completed_at DESC`. `workflow_name` is `COALESCE(w.name, 'unknown')`.

Readers:

| Reader | Today | After |
|---|---|---|
| `build_status_summary` (`ze_automation/rest.py`) | `PushLogStore(pool).list_workflow_failures_within_hours(days*24)`, names from `payload` | `container.workflow_store.list_failed_executions(days*24)`, `workflow_name` |
| `AccountabilityJob._build_summary` | `self._push_log.list_workflow_failures_within_hours(...)` | `self._workflow_store.list_failed_executions(...)`; constructor takes `workflow_store` instead of `push_log_store` |
| `MorningBriefing.run` (ze-personal) | `self._push_log.list_workflow_failures_within_hours(24)`, `entry.payload`, `entry.sent_at` | `self._workflows.list_failed_executions(24)`, `workflow_name`, `failed_at` |

The line in the brief keeps its text: `⚠️  Recent failure: {name} at {HH:MM UTC}`.

The failure handler (`make_workflow_failure_handler`) loses `push_log_store` and the ledger write; it keeps the alert, with `once_per=OncePer(f"workflow_failure_alert:{workflow.id}", within=timedelta(hours=cooldown))`.
