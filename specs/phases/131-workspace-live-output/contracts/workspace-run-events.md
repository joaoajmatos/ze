# Contract: `GET /api/v0/workspace/runs/{id}/events` (redaction amendment)

**Status**: Existing endpoint (Phase 129). This phase amends its behavior, not its
shape — no new route, no new operation_id, no new response field.

## Unchanged

- Method/path: `GET /api/v0/workspace/runs/{run_id}/events`
- `operation_id`: `watchWorkspaceRunEvents`
- Media type: `application/x-ndjson`
- Line shape: `{"seq": int, "type": "stdout"|"stderr"|"exit", "data": string, "exit_code"?: int, "timed_out"?: bool}`
- Behavior: streams already-produced lines then live lines, closes after `exit`.
- 404 when the handle is unknown to the sidecar.

## Amended (FR-006)

- `data` on `stdout`/`stderr` lines MUST be passed through
  `ze_workspace.sanitize.redact()` before being written to the response body. `exit`
  lines carry no free text and are unaffected.
- No change to status codes, headers, or closing behavior.

## Consumers (new, frontend only — no backend contract change)

Two UI surfaces open this same stream directly and MUST treat it as append-only,
ordered by `seq`, terminating at `exit`:

1. Chat still-running chip (`apps/ze-web/src/entities/message/ui/MessageBubble.tsx`)
   — opened for the run(s) the current `trace_update` frame reports as
   `status === "in_progress"`.
2. Workspace in-progress banner (`apps/ze-web/src/widgets/workspace-management/ui/RunningRunBanner.tsx`)
   — opened for each row `useWorkspaceRunsQuery` reports as in progress
   (`ended_at === null`).

Both MUST stop reading and MUST NOT re-open the stream once an `exit` line is
received or the run disappears from its respective in-progress source (cancelled via
`POST /runs/{id}/cancel`, which Phase 116/129 cancel rules already terminate — this
phase adds no new cancel path).

## Explicitly not introduced

- No WebSocket frame type for run output.
- No new REST endpoint (e.g. no "current preview snapshot" GET).
- No pagination/cursor parameter on `/events` — a fresh connection always replays
  from the start of the retained journal, which is bounded by the existing
  `OUTPUT_PREVIEW_CHARS` cap (research.md R2), so replay cost is bounded too.
