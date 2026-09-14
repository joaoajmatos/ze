# Phase 1 Data Model: Workspace Run Journal

## Entities

### JournalEntry (sidecar-side, in-memory only — not persisted)

The sidecar's record for one execution, keyed by `id` in the process-local
`RunJournal` dict (Decision 1/2 in `research.md`). Never serialized to disk or
Postgres; lost if the sidecar process restarts (Edge Case 3, an accepted
failure mode).

| Field | Type | Notes |
|---|---|---|
| `id` | `UUID` | Mind-supplied (or sidecar-generated if absent). Journal key. |
| `command` | `list[str]` | As given to `POST /run`. |
| `cwd` | `str` | Relative to `WORKSPACE_ROOT`, as today. |
| `status` | `"running" \| "succeeded" \| "failed" \| "timed_out" \| "cancelled"` | `"running"` until the process exits or is cancelled. |
| `started_at` | `datetime` | UTC. |
| `ended_at` | `datetime \| None` | Set once terminal. |
| `exit_code` | `int \| None` | `None` while running; `-1` convention preserved for timed-out (matches current `supervisor.run_command`). |
| `timed_out` | `bool` | |
| `events` | `list[JournalEvent]` | Append-only buffer; bounded by the same `OUTPUT_PREVIEW_CHARS` truncation the sidecar already applies, plus spill-to-file for anything beyond it (unchanged from Phase 115). |
| `stdout_preview` / `stderr_preview` | `str` | Truncated, as today. |
| `output_file_path` | `str \| None` | Unchanged from Phase 115 (spill file under `/workspace`). |
| `files_touched` | `list[{path, op}]` | Computed via the existing `snapshot_tree`/`diff_snapshots` pair, now taken once at spawn and once at terminal (not at HTTP-return time, since there is no longer a single HTTP call spanning the run). |
| `_proc` | `asyncio.subprocess.Process \| None` | Internal only, not exposed via any route. Cleared once terminal. |

**Lifecycle**: `running` → exactly one of `succeeded | failed | timed_out |
cancelled`. Terminal is a one-way transition — once set, `complete`/`cancel`
calls are no-ops (mirrors the mind-side `WHERE ended_at IS NULL` guard in
`WorkspaceStore.complete_run`/`cancel_run`).

**One-slot invariant**: At most one `JournalEntry` may be `status == "running"`
at a time (FR-007's hard rule, enforced here as the backstop behind Decision
5's mind-side check). `POST /run` while one is running returns 409 `busy` with
the running entry's `id` and `command` in the body, so even a direct/manual
caller gets a nameable refusal.

**Retention**: bounded to the running entry (if any) plus the 5 most recent
terminal entries (Decision 3). Oldest terminal entry is evicted (not
persisted anywhere) once a 6th is added.

### JournalEvent (sidecar-side, part of `JournalEntry.events`)

| Field | Type | Notes |
|---|---|---|
| `seq` | `int` | Monotonic per entry, starts at 0. Lets a client resume a stream mid-way without re-reading everything (not required by this phase's callers, but a natural corollary of a numbered buffer). |
| `type` | `"stdout" \| "stderr" \| "exit"` | |
| `data` | `str` | Chunk of decoded output for `stdout`/`stderr`; empty for `exit`. |
| `exit_code` / `timed_out` | present only on the `exit` event | Mirrors the terminal `JournalEntry` fields at the moment of exit. |

### WorkspaceRun (mind-side, `ze_workspace/types.py` — existing dataclass, extended)

No new *conceptual* entity — `WorkspaceRun` already models "the mind's durable
record... now keyed to the computer's handle" per the spec's Key Entities. One
field is confirmed as already sufficient and one is added:

| Field | Change |
|---|---|
| `id` | **Unchanged in meaning**, but now doubles as the sidecar journal key end-to-end (Decision 1) — no separate handle field needed. |
| `sidecar_dispatched` | **New** `bool`, default `False`. Set `True` once `POST /run` has actually been called with this row's `id` (vs. the row existing but the sidecar call not yet made/acknowledged — a narrow window at start). Lets `reattach()` distinguish "never reached the sidecar, safe to mark failed outright" from "reached the sidecar, must query `GET /runs/{id}` before concluding anything." |

No other existing field changes meaning: `status`, `exit_code`,
`output_preview`, `output_file_path`, `files_touched`, `error_summary`,
`follow_through_notified` all keep their Phase 115/116 semantics — this phase
changes *how* they get populated (from a real `GET /runs/{id}`/`/events`
readback instead of a blind poll-and-guess), not *what* they mean.

## Schema Change

Migration `zws003` on the existing `ze-workspace` (`zws`) Alembic chain:

```sql
ALTER TABLE workspace_runs
  ADD COLUMN IF NOT EXISTS sidecar_dispatched BOOLEAN NOT NULL DEFAULT false;
```

No index needed — `sidecar_dispatched` is only read for the single in-progress
row(s) already selected by `list_in_progress()`'s existing `ended_at IS NULL`
predicate, not queried independently.

## State Transitions

### JournalEntry (sidecar)

```
running --(process exits 0)--> succeeded
running --(process exits non-zero)--> failed
running --(timeout elapses)--> timed_out
running --(POST /runs/{id}/cancel)--> cancelled
```

### WorkspaceRun (mind) — unchanged from Phase 116, reconfirmed here

```
(insert_in_progress_run) ended_at=NULL, status=NULL, sidecar_dispatched=False
  --(POST /run succeeds)--> sidecar_dispatched=True
  --(short wait elapses)--> RunWatcher.detach() begins watching /runs/{id}/events
  --(terminal event observed, or reattach's GET /runs/{id} is already terminal)-->
      complete_run(...) with REAL exit_code/output_preview/files_touched
      --(origin == conversation)--> follow-through dispatched exactly once
```

The only new branch: if a mind restart finds a row with
`sidecar_dispatched=False` and `ended_at IS NULL` (crashed between insert and
the `POST /run` call landing), `reattach()` marks it `failed` directly with a
plain-language `error_summary` — no sidecar call needed, since the sidecar
never received this id.
