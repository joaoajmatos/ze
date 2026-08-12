# Contract: Skills REST API + Trace Frame

All routes under `/api/v0/skills`, `require_api_key` dependency (`HTTPBearer`), each route
declares `response_model`, `summary`, `description` per `CLAUDE.md`'s OpenAPI conventions.
Follows the `apps/ze-api/ze_api/api/routes/loops.py` shape: thin FastAPI routes delegating to
`ze_skills.rest` functions, `HTTPException(404)` on not-found, `HTTPException(409)` on invalid
transitions (`InvalidSkillTransitionError`).

## `GET /api/v0/skills`

List every skill (bundled + imported), optionally filtered.

**Query params**: `status: SkillStatus | None`, `source: SkillSource | None`.

**Response** `SkillListResponse`:

```json
{
  "skills": [
    {
      "id": "uuid",
      "name": "string",
      "slug": "string",
      "description": "string",
      "source": "bundled" | "imported",
      "origin_url": "string | null",
      "bundling_plugin": "string | null",
      "status": "pending_review" | "active" | "disabled" | "rejected",
      "has_unsupported_scripts": "boolean",
      "created_at": "iso8601",
      "approved_at": "iso8601 | null",
      "last_checked_at": "iso8601 | null",
      "last_check_error": "string | null"
    }
  ]
}
```

Supports FR-012 (management view listing) and User Story 3's "list, filter" independent test.

## `GET /api/v0/skills/{skill_id}`

Full detail for one skill — includes `instructions`, `allowed_tools`, `reference_files`
(filename + content_type, not full content by default — see
`GET /api/v0/skills/{skill_id}/reference-files/{filename}` below for content), and — only when
`status == pending_review` and a prior approved version exists — a `previous_version` object
(from the latest `SkillReview` with `decision = approved`) for content-change comparison
(FR-016, User Story 4 scenario 2).

**404** if no skill with that id.

## `GET /api/v0/skills/{skill_id}/reference-files/{filename}`

Full content of one stored non-script supporting reference file (FR-022), so the review view
(FR-005) and management view can show exactly what would be injected into context when the
skill is used — the `GET /{skill_id}` detail response only lists `filename`/`content_type` to
keep that payload light when a skill has several reference files.

**Response** `SkillReferenceFileResponse`:

```json
{
  "filename": "string",
  "content_type": "string",
  "content": "string"
}
```

**404** if no skill with that id, or no reference file with that filename on this skill.

## `POST /api/v0/skills/import`

Submit a URL for import (FR-001).

**Request** `SkillImportRequest`: `{"url": "string"}`.

**Behavior**: fetches and parses per `research.md`; on success, creates a `Skill` row with
`status = pending_review`, `source = imported`. Never activates it (FR-004).

**Response** `201 Created`, body = the new skill (same shape as `GET /{skill_id}`), so the
caller can render the review view immediately (User Story 1 scenario 1).

**Errors**: `422 Unprocessable Entity` with a specific message on parse/fetch failure
(unreachable URL, malformed frontmatter, missing required fields) — no `Skill` row created
(FR-003).

## `POST /api/v0/skills/{skill_id}/approve`

Transition `pending_review → active` (FR-006). Records a `SkillReview` row
(`decision = approved`) with the current content snapshot. Sets `approved_at`, refreshes the
matcher's cached embedding for this skill.

**409** if not currently `pending_review`.

## `POST /api/v0/skills/{skill_id}/reject`

Transition `pending_review → rejected` (FR-006). Records a `SkillReview` row
(`decision = rejected`).

**409** if not currently `pending_review`.

## `POST /api/v0/skills/{skill_id}/disable`

Transition `active → disabled` (FR-013). Removes from the matcher's active set immediately.

**409** if not currently `active`.

## `POST /api/v0/skills/{skill_id}/enable`

Transition `disabled → active` (FR-013) — no re-review required, since content hasn't changed
since it was last approved (enforced by rejecting the transition if a recheck already moved
this skill to `pending_review` in the meantime — status must still be `disabled`, not
`pending_review`, at call time).

**409** if not currently `disabled`.

## `DELETE /api/v0/skills/{skill_id}`

Permanently remove an imported skill (FR-014). Cascades `SkillReview`/`ReferenceFile` rows.

**403** (or `422`) if `source == bundled` — bundled skills are removed by uninstalling the
owning plugin, not through this endpoint; the spec's FR-014 scopes removal to imported skills.

## `POST /api/v0/skills/{skill_id}/refresh`

User-triggered manual recheck (FR-015's manual path, distinct from the daily job in FR-021).
Re-fetches `origin_url`, compares `content_hash`; if changed, transitions to `pending_review`
and records the new content for comparison (same effect as the scheduled job's per-skill
logic). Returns the (possibly updated) skill detail.

**422** if `source == bundled` (no `origin_url` to refresh).

**200** with `last_check_error` populated (not a 4xx/5xx) if the source is unreachable —
per spec Edge Cases, an unreachable source does not deactivate the skill or fail the request;
`last_checked_at` still updates.

## Trace frame extension (no new endpoint — existing mechanism, new field)

`trace_update` WS frame and `GET /api/v0/messages/{id}/trace` (`MessageTraceResponse`) both
gain `skills_used: SkillUsageTrace[]`:

```json
{
  "type": "trace_update",
  "message_id": "uuid",
  "...": "...existing MessageTrace fields unchanged...",
  "skills_used": [
    {
      "skill_id": "uuid",
      "name": "string",
      "source": "bundled" | "imported",
      "trigger": "automatic" | "explicit",
      "similarity": "number | null"
    }
  ]
}
```

Empty array when no skill was used for that turn (User Story 2 scenario 2). Satisfies FR-010,
FR-011, and the trace-panel inspection in User Story 2 scenario 3.
