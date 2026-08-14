# Contract: Workspace REST API + WS / trace / confirm

All workspace routes under `/api/v0/workspace`, `require_api_key` (`HTTPBearer`), each
route declares `response_model`, `summary`, `description`, explicit camelCase
`operation_id`. Thin FastAPI routes in `apps/ze-api/ze_api/api/routes/workspace.py`
delegating to `ze_workspace.rest`.

Identifiers below match the spec's mode labels (Off · Plan · Ask · Auto-edit · Auto) and
the stored enum in [data-model.md](../data-model.md). Do not rename or recase them in
code beyond the stored snake_case values `off` | `plan` | `ask` | `auto_edit` | `auto`.

Error mapping: `WorkspaceUnavailableError` → 503; `WorkspaceBusyError` → 409;
`WorkspaceFullError` → 409; `WorkspacePathError` → 400; `WorkspaceNotFoundError` → 404;
invalid mode → 422.

## `GET /api/v0/workspace`

**operation_id**: `getWorkspace`

Live status for the workspace view header.

**Response** `WorkspaceStatusResponse`:

```json
{
  "available": true,
  "mode": "ask",
  "bytes_used": 0,
  "bytes_ceiling": 1073741824,
  "busy": false,
  "last_reset_at": null,
  "last_used_at": null
}
```

`available: false` when the sidecar health check fails — other fields may still show last
known mode from Postgres.

## `GET /api/v0/workspace/mode`

**operation_id**: `getWorkspaceMode`

**Response** `WorkspaceModeResponse`: `{ "mode": "off"|"plan"|"ask"|"auto_edit"|"auto" }`

## `PATCH /api/v0/workspace/mode`

**operation_id**: `updateWorkspaceMode`

**Request** `WorkspaceModeUpdate`: `{ "mode": "off"|"plan"|"ask"|"auto_edit"|"auto" }`

Persists until the user changes it again (FR-029). Does not confirm. Returns the new
`WorkspaceModeResponse`.

## `GET /api/v0/workspace/files`

**operation_id**: `listWorkspaceFiles`

Optional query `path` (default `""` = root).

**Response** `WorkspaceFileListResponse`:

```json
{
  "files": [
    {
      "path": "report.md",
      "size": 120,
      "modified_at": "iso8601",
      "is_dir": false
    }
  ]
}
```

**503** if unavailable.

## `GET /api/v0/workspace/files/{path}`

**operation_id**: `getWorkspaceFile`

Retrieve file bytes (`application/octet-stream`, `Content-Disposition: attachment`).
Directories → 400. Missing → 404. Path traversal → 400.

## `POST /api/v0/workspace/files`

**operation_id**: `uploadWorkspaceFile`

Multipart: `file` (required), `path` (optional relative destination; default the upload
filename). Place only — does **not** ingest (FR-027).

If the name exists, store under a distinct name and return both:

```json
{
  "path": "notes-1.txt",
  "requested_path": "notes.txt",
  "size": 42,
  "deduplicated": true
}
```

**409** `full` when the place would exceed the ceiling (workspace unchanged).
**400** on escape paths.

Used by the workspace-view uploader **and** the chat composer paperclip.

## `DELETE /api/v0/workspace/files/{path}`

**operation_id**: `deleteWorkspaceFile`

User-initiated delete (no confirm). 404 if missing.

## `POST /api/v0/workspace/files/{path}/ingest`

**operation_id**: `ingestWorkspaceFile`

Opt-in (FR-028). Reads sidecar bytes, calls `IngestionPipeline.ingest` with
`file_bytes` + mime + `label=path`. Does not remove the workspace file.

**Response**: existing ingest result shape (`IngestionResponse` as used by
`POST /api/v0/ingest`). **404** if the file is missing.

## `POST /api/v0/workspace/reset`

**operation_id**: `resetWorkspace`

Does **not** reset immediately. Creates a `confirm_request` (`editable: false`, prompt
explains that all files will be removed). On approve, cancel any in-flight run then wipe.
On deny, no change.

**Response** `202`: `{ "confirmation_id": "uuid" }` when a confirm was issued.
Idempotent with an already-empty workspace still confirms (reset always confirms).

## `GET /api/v0/workspace/runs`

**operation_id**: `listWorkspaceRuns`

Query: `limit` (default 50), `origin` optional.

**Response** `WorkspaceRunListResponse`: `{ "runs": [ WorkspaceRunResponse, ... ] }`

`WorkspaceRunResponse`: `id`, `started_at`, `ended_at`, `command`, `origin`,
`thread_id`, `message_id`, `skill_id`, `skill_script_path`, `status`, `exit_code`,
`output_preview`, `output_file_path`, `files_touched`, `error_summary`.

## Skill executable approval (extends `/api/v0/skills`)

### `POST /api/v0/skills/{skill_id}/approve-executables`

**operation_id**: `approveSkillExecutables`

Sets `executable_approved = true`. Does not replace `POST .../approve` (instructions).
**409** if `has_scripts` is false or skill is not `active`/`pending_review` in a state
that allows this action (pending review may approve executables together with
instructions only after instructions are approved — implement as: require `status ==
active` so instructions-only review stays a separate click).

Skill list/detail responses add:

```json
{
  "has_scripts": true,
  "executable_approved": false,
  "script_filenames": ["scripts/helper.py"]
}
```

Remove `has_unsupported_scripts` from the schema (replaced by `has_scripts`; regenerate
`@ze/client`).

## WebSocket

### Send message `context`

`WsSendMessageFrame.context` may include:

```json
{
  "workspace_placed": [{ "path": "notes.txt", "size": 42 }]
}
```

Set after a successful `uploadWorkspaceFile` from the composer. Bytes are never on the
frame.

### `confirm_request` / `confirm`

Existing frame. When the pending action is a workspace command or file write:

- `editable: true`
- `prompt` describes the command or file
- actions remain `approve` / `deny`
- inbound `WsConfirmFrame` gains optional `edited_content: string | null` — on approve
  with a non-null value, Ze runs the edited command or writes the edited contents

Reset confirms set `editable: false`.

### `trace_update` / `MessageTraceResponse`

Add `workspace: WorkspaceUsageTrace | null` (fields as in data-model).
Extend `skills_used[]` with `script_ran: boolean` (default false).

### Visible turn annotation

Not a WS frame of its own. The assistant message's `components` (or a dedicated
`workspace` field on the message payload) MUST include enough to render a chip: workspace
used, file names, whether a skill script ran (FR-007, SC-002). Trace-only UI is not
sufficient.

## Platform tools (agent contract)

Exact tool names (intersected by skills, never granted *by* skills):

- `workspace_list`
- `workspace_read`
- `workspace_write`
- `workspace_delete`
- `workspace_run`
- `workspace_run_skill_script`
- `ingest_workspace_file`
