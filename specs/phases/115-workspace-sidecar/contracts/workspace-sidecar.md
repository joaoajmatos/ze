# Contract: Workspace sidecar control API

Internal HTTP API implemented by `sidecar/workspace/` and consumed only by
`ze_workspace.client.WorkspaceClient`. Not mounted on `ze-api`, not in public OpenAPI.
Auth: `Authorization: Bearer $WORKSPACE_API_TOKEN` on every route except `GET /health`.
The token is supervisor-env only; child processes must not see it.

Base URL from `WORKSPACE_SERVICE_URL` (Compose `http://workspace:8080`, Fly
`http://ze-workspace.internal:8080`).

All paths in bodies are relative workspace paths. The sidecar rejects any path that
normalizes outside `/workspace` with `400` `{"error": "outside_workspace"}`.

## `GET /health`

**Response** `200` `{ "ok": true }` when the process can exec and the volume is mounted.
Used by Compose healthcheck and `WorkspaceClient.health()`.

## `GET /stat`

```json
{
  "bytes_used": 0,
  "bytes_ceiling": 1073741824,
  "busy": false,
  "workspace_root": "/workspace"
}
```

`bytes_ceiling` is configured on the sidecar (mirrors `workspace.storage_ceiling_bytes`).

## `GET /fs`

Query `path` (default `""`). List directory.

**Response**: `{ "files": [ { "path", "size", "modified_at", "is_dir" } ] }`

## `GET /fs/download`

Query `path`. Raw bytes. `404` missing, `400` if directory or outside.

## `PUT /fs`

JSON `{ "path": "a.txt", "content_b64": "...", "overwrite": false }`.

If `overwrite` is false (default) and the path exists → `409`
`{ "error": "exists", "suggested_path": "a-1.txt" }`. The client then retries with
`suggested_path` or surfaces both names.

`413` `{ "error": "full" }` if the write would exceed the ceiling — no partial file.

## `POST /fs/upload`

Multipart `file` + `path`. Same overwrite / full semantics as `PUT /fs`. Used for binary
place from `ze-api`.

## `DELETE /fs`

Query `path`. `404` missing.

## `POST /run`

JSON:

```json
{
  "command": ["python3", "script.py"],
  "cwd": "",
  "timeout_seconds": 120,
  "stdin_b64": null,
  "env": {}
}
```

`env` is **merged last and cannot set** `DATABASE_URL`, `OPENROUTER_API_KEY`,
`ZE_API_KEY`, `WORKSPACE_API_TOKEN`, or any key matching `*_SECRET` / `*_TOKEN` /
`*_PASSWORD`. Child env starts from the clean allowlist in research.md.

**Behavior**: acquire mutex (wait `run_lock_wait_seconds`); if still busy → `409`
`{ "error": "busy" }`. Exec as user `workspace`, cwd `/workspace/<cwd>`. Kill on
timeout. Collect stdout/stderr; if longer than `output_preview_chars`, spill full
output to a unique file under `/workspace` and return its path.

**Response** `200`:

```json
{
  "exit_code": 0,
  "timed_out": false,
  "stdout_preview": "",
  "stderr_preview": "",
  "output_file_path": null,
  "files_touched": [{ "path": "out.txt", "op": "created" }]
}
```

`files_touched` is a best-effort diff of `/workspace` mtimes/sizes around the run (not
a perfect FS journal).

Network: child uid cannot reach private ranges (research.md). Public internet allowed.
A failed public fetch is a non-zero exit, not a 5xx from this endpoint.

## `POST /cancel`

Kill the in-flight run (SIGTERM, then SIGKILL). `404` if none. Used by reset.

## `POST /reset`

If busy, cancel first, then delete all files under `/workspace` (recreate empty root).
**Response** `{ "ok": true }`. The sidecar does not confirm — confirmation is Ze's job.

## Isolation invariants the client/tests assert

1. `/run` process env does not contain the bearer token or Ze secrets.
2. A command `curl -s http://172.16.0.0/` (or equivalent) does not reach compose/Fly
   private services; the test may stub the firewall in unit tests and cover the real
   rules in a marked sidecar integration test (`@pytest.mark.slow` or compose smoke).
3. `GET /fs?path=../` → 400.
