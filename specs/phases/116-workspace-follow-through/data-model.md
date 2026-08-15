# Phase 1 Data Model: Workspace Follow-Through

This spec attaches to Phase 115's `workspace_runs` table
(`core/ze-workspace/ze_workspace/migrations/versions/zws001_workspace.py`) and adds
no new Postgres table (FR-012). It does not touch `workspace_state`, `skill_scripts`,
or any Phase 115 enum's stored values.

## Reused from Phase 115 (unchanged shape)

- `WorkspaceRunStatus` — `succeeded | failed | timed_out | cancelled | refused`.
  Follow-through does not add a status; "still running" is a UI/turn-reply framing
  of a row where `ended_at IS NULL`, not a stored value.
- `WorkspaceRunOrigin` — `conversation | user | unattended`. Follow-through applies
  only to `origin = conversation` rows (FR-015); `unattended` rows keep using
  existing unattended-notification behavior, never this spec's follow-up path.
- `WorkspaceRun` columns: `id`, `started_at`, `ended_at`, `command`, `origin`,
  `thread_id`, `message_id`, `skill_id`, `skill_script_path`, `status`, `exit_code`,
  `output_preview`, `output_file_path`, `files_touched`, `error_summary` — all
  reused as-is. Phase 115 already left `ended_at` nullable and documented it as
  "column exists so 116 can detach" and `id` as "stable identity for a later
  follow-through spec." No column rename or type change.

## New in this phase

### `WorkspaceRun.follow_through_notified` (column, `zws002`)

| Field | Type | Notes |
|---|---|---|
| `follow_through_notified` | `BOOLEAN NOT NULL DEFAULT false` | Set true the moment the watcher has dispatched (or begun dispatching) the follow-up turn / push for this run's terminal status. |

**Why a column, not just in-memory state**: D5's startup reconciliation must be able
to tell "terminal but never followed through" (needs re-dispatch) apart from
"terminal and already handled, `ze-api` just restarted afterward" (must not re-notify
— a restart must not double-send a follow-up turn or push for a run the user already
saw finish). Purely in-memory tracking cannot survive the exact restart D5 exists to
handle; this is the one durable bit follow-through needs beyond what Phase 115
already persists.

**Set**: by the `RunWatcher` itself, in the same store call that would otherwise just
read the row — set *before* calling `TurnStarter.invoke`/`PushSender.send_completion`
so a crash mid-dispatch is a missed notification (acceptable per the spec's Edge
Cases: "Ze does not retry forever; missing a push is not treated as a failed run"),
never a duplicate one.

**Not retried**: if `follow_through_notified` is already true, reconciliation (D5)
skips the row. No FR requires at-least-once delivery of the follow-up beyond the one
dispatch attempt.

### In-memory only (no table)

| State | Owner | Notes |
|---|---|---|
| `RunWatcher` background tasks | `core/ze-workspace` `ze_workspace/followthrough.py` | One `asyncio.Task` per detached run, keyed by `run.id`. Rebuilt at startup by D5 reconciliation, not persisted. |
| `ThreadTurnLock` | `core/ze-workspace` `ze_workspace/turn_lock.py` | `dict[str, asyncio.Lock]` keyed by `thread_id`. Process-local; a lock held at the moment of a crash is simply gone on restart along with the in-flight turn it guarded — no durable state to reconcile (LangGraph's own checkpoint is the durability layer for turn content, not this lock). |

These two are deliberately not modeled as Postgres rows: they exist only to
coordinate this single `ze-api` process (D3's alternatives-considered explains why
no cross-process locking is needed), and persisting them would imply a durability
guarantee (surviving a crash mid-lock) the spec does not ask for.

## Key Entities (from spec) → implementation mapping

- **Workspace run** (spec) → existing `WorkspaceRun` row + new
  `follow_through_notified` flag.
- **Follow-up turn** (spec) → not a stored entity; a `TurnResult` produced by
  `invoke_raw_turn`, persisted the same way any conversation turn already is
  (checkpoint + `messages` + `MessageTrace`). No new table.
- **Completion push** (spec) → not a stored entity; a `Notification` delivered via
  the existing `ProactiveNotifier`/`AppInterface.push` path. If Ze's notification
  center (`notifications` table, Phase 105) is used for the push, it reuses that
  existing table with `event_type = "workspace_run_completed"` — no new column
  there either (the existing `target_type`/`target_id` pair already carries an
  arbitrary reference id).

## Validation

- `follow_through_notified` transitions `false → true` exactly once per row; the
  store update is a single `UPDATE ... WHERE id = $1 AND follow_through_notified =
  false` (idempotent under a concurrent double-dispatch attempt, though D3's lock
  already prevents that in practice).
- A row with `origin != 'conversation'` MUST never have `follow_through_notified`
  set by this spec's watcher (FR-015) — the unattended path's own notification
  mechanism is untouched and does not read or write this column.

## Migration

`core/ze-workspace/ze_workspace/migrations/versions/zws002_run_followthrough.py` —
adds `follow_through_notified BOOLEAN NOT NULL DEFAULT false` to `workspace_runs`,
`depends_on` Phase 115's `zws001`. Raw SQL, no ORM, continues the `zws` chain
(`apps/ze-api/ze_api/migrate.py`'s `_ZE_WORKSPACE_VERSIONS` constant already lists
that chain — this just adds a revision to it).
