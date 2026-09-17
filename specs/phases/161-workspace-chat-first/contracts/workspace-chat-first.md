# Contract: Workspace Chat-First

Verbatim from spec: `/workspace` remains the map route.

## REST (`/api/v0/workspace`)

**Removed**

- `GET /api/v0/workspace/mode`
- `PATCH /api/v0/workspace/mode`

**`GET /api/v0/workspace`** (status) — no `mode` field:

```json
{
  "available": true,
  "bytes_used": 0,
  "bytes_ceiling": 1073741824,
  "busy": false,
  "last_reset_at": null,
  "last_used_at": null
}
```

**Kept** (not the map console): `GET /files`, `POST /files` (chat attach), retrieve/download, ingest, reset (conversation/API, not the map UI), runs list/events/cancel.

## Gate

```
decide(action: WorkspaceAction, origin: WorkspaceRunOrigin) -> allow | confirm | deny
decide_named(action: str, origin: str) -> same
```

No `mode` parameter.

## UI `/workspace`

Shows: file/directory tree (path, size, mtime), available, bytes used/ceiling, busy.
Does not show: mode switcher, upload, reset, retrieve, run list, live output, stop.

## Trace workspace object

No `mode` property. Keep runs/files/script_ran/unavailable.
