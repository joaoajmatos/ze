# Data Model: Workspace Live Output

This phase adds no tables, no columns, and no new persisted entity. It reuses Phase
129's `workspace_runs` row and sidecar run journal as-is (FR-007). The only "model"
changes are in-memory/transport shapes on the existing contract.

## Existing entities reused (no schema change)

- **`WorkspaceRun`** (`ze_workspace.types`, table `workspace_runs`) — unchanged.
  `id`, `command`, `status`, `started_at`, `ended_at`, `output_preview`,
  `files_touched`. This phase reads it, never writes new columns to it.
- **Run journal** (sidecar-side, in-memory + `JournalEventDTO`) — unchanged shape:
  `seq: int`, `type: "stdout" | "stderr" | "exit"`, `data: str`,
  `exit_code: int | None`, `timed_out: bool | None`. Already capped at
  `OUTPUT_PREVIEW_CHARS` total emitted bytes (see research.md R2).

## Transport-level additions (not persisted)

### Redacted journal event line (backend change)

The existing NDJSON line shape emitted by `GET /runs/{id}/events`
(`apps/ze-api/ze_api/api/routes/workspace.py:277-293`) is unchanged in field names;
the only change is that `data` MUST be passed through `ze_workspace.sanitize.redact()`
before being written to the wire for `stdout`/`stderr` event types (FR-006, research.md
R3). `exit` events carry no free text and are not redacted.

```json
{"seq": 12, "type": "stdout", "data": "fetching 40 files..."}
{"seq": 13, "type": "stderr", "data": "warning: retrying (1/3)"}
{"seq": 14, "type": "exit", "data": "", "exit_code": 0, "timed_out": false}
```

### Client-side accumulated preview state (frontend, in-memory only)

Both consumers (chat chip, workspace banner) hold the same shape, keyed by run id.
Not persisted anywhere — rebuilt from the replay on every mount, matching FR-002's
"replay then continue" and the edge case that a reconnect must not stack a duplicate
prefix.

| Field | Type | Notes |
|---|---|---|
| `runId` | `string` (UUID) | The Phase 129 handle. Does not mint a new identity (per spec Key Entities). |
| `lines` | `string` | Accumulated `stdout` + `stderr` `data`, in `seq` order. Bounded by the server-side cap (research.md R2) — no separate client cap needed. |
| `lastSeq` | `number \| null` | Highest `seq` applied, used only to drop a duplicate/out-of-order event if the stream is ever re-consumed (defensive; the endpoint is a single ordered stream per open connection, not a resumable cursor). |
| `status` | `"streaming" \| "closed" \| "unavailable"` | `"streaming"` while the connection is open and no `exit` seen; `"closed"` once an `exit` event arrives; `"unavailable"` if the stream could not be opened or dropped without an `exit` (FR-010 — still-running stays honest, no invented output). |
| `exitCode` | `number \| null` | From the `exit` event, if seen. Informational only — the terminal outcome text still comes from follow-through, not from this state (this phase does not duplicate that channel, FR-004/FR-008). |
| `looksBinary` | `boolean` | Heuristic flag (research.md R4) driving the "output is not printable" note instead of rendering `lines` raw. |

No new database migration, no new Alembic revision, no new package dependency.
