# Contract: Sidecar Run API (`sidecar/workspace/main.py`)

Internal control API between `ze-api` and the always-on `ze-workspace`
sidecar. Bearer-token authenticated (`WORKSPACE_API_TOKEN`), unchanged from
Phase 115. This document covers only the run-lifecycle routes this phase adds
or changes; `/health`, `/stat`, `/fs*`, `/reset` are unchanged (see spec
115/116 for those).

## `POST /run`

Starts a command as a background task and returns immediately — does **not**
wait for the process to exit (FR-001).

**Request**

```json
{
  "command": ["bash", "-lc", "make test"],
  "cwd": "",
  "timeout_seconds": 120,
  "stdin_b64": null,
  "env": {}
}
```

`id` is an **optional** field (UUID string). When present, the sidecar uses it
as the journal key (Decision 1 — the mind always supplies its own
`workspace_runs.id`). When absent, the sidecar generates one.

**Response — 200**

```json
{ "id": "5b1e...-uuid" }
```

**Response — 409** (one-slot invariant already occupied, `JournalEntry` retention model)

```json
{ "error": "busy", "id": "<running-id>", "command": ["bash", "-lc", "..."] }
```

**Response — 400** `{"error": "empty_command"}` or `{"error": "outside_workspace"}` — unchanged from Phase 115's validation.

## `GET /runs/{id}`

Point-in-time status readback. Works for a running, terminal, or (per
retention) recently-terminal handle.

**Response — 200**

```json
{
  "id": "5b1e...-uuid",
  "status": "running",
  "exit_code": null,
  "timed_out": false,
  "stdout_preview": "...",
  "stderr_preview": "",
  "output_file_path": null,
  "files_touched": [{"path": "out.txt", "op": "created"}]
}
```

`files_touched` reflects a diff taken at call time against the pre-run
snapshot while `status == "running"`, and the final diff once terminal.

**Response — 404** `{"error": "not_found"}` — unknown, disposed-by-retention,
or never-existed id. The caller (mind) treats this identically to "computer
restarted and lost it" (Edge Case: "How does the system handle a handle the
computer has already disposed? Treated as unknown: not running, no fabricated
output.").

## `GET /runs/{id}/events`

Streams `application/x-ndjson` (Decision 4): one JSON object per line.
Already-buffered events replay first, then live events follow as produced.
The stream ends after the `exit` event. Multiple concurrent callers on the
same `id` are all allowed (Edge Case: "What happens if two clients try to
watch the same handle? Both MAY read it.") — each gets its own replay-then-live
view from its own connection time.

**Stream body** (one line per event)

```
{"seq": 0, "type": "stdout", "data": "Running tests...\n"}
{"seq": 1, "type": "stdout", "data": "5 passed\n"}
{"seq": 2, "type": "exit", "data": "", "exit_code": 0, "timed_out": false}
```

**Response — 404** if `id` is unknown (same semantics as `GET /runs/{id}`);
returned as a normal JSON error body (not a stream) since nothing has been
buffered for an id that never existed.

Redaction (FR-012): every `data` chunk passes the same `sanitize.redact()`
pass Phase 115 already applies to previews before being appended to the
buffer — never after, so a replay can never emit an unredacted chunk that was
briefly live.

## `POST /runs/{id}/cancel`

Cancels a specific handle. Never kills a different run (FR-006).

**Response — 200** `{"ok": true}` — handle was running, is now `cancelled`.

**Response — 404** `{"error": "not_found"}` — handle unknown, or already
disposed by retention.

**Response — 409** `{"error": "already_terminal", "status": "succeeded"}` —
handle exists but already reached a terminal status before this call landed
(Edge Case: "a run that already finished, cancel does nothing, told it
already finished").

## Removed

The bare `POST /cancel` (no id, implicitly "whatever is running") from Phase
115/116 is replaced by `POST /runs/{id}/cancel`. There is exactly one caller
in this codebase (`WorkspaceClient.cancel()`/`rest.execute_reset`), both
updated in the same change (see `mind-workspace-api.md`) — no external
consumer of the sidecar API exists to break.
