# Phase 1 Data Model: Workspace Environment

Owning package for workspace entities: `core/ze-workspace/ze_workspace/types.py` +
`core/ze-workspace/ze_workspace/migrations/versions/zws001_workspace.py`.

Owning package for executable approval / skill scripts: `core/ze-skills/` +
`zsk002_skill_scripts.py`.

Turn annotation fields: `core/ze-core/ze_core/conversation/messages/types.py`
(`MessageTrace`, `SkillUsageTrace`).

## Enums

### `WorkspaceMode` (StrEnum)

User-visible labels from the spec (Off · Plan · Ask · Auto-edit · Auto). Stored values:

| Value | Label | Meaning |
|---|---|---|
| `off` | Off | No workspace actions; workspace unchanged. |
| `plan` | Plan | Show what would be run or written; do not execute. |
| `ask` | Ask | Default until the user first changes it. Confirm Ze's commands/scripts and file changes. |
| `auto_edit` | Auto-edit | File writes/edits execute; commands and skill scripts still confirm. |
| `auto` | Auto | Commands, skill scripts, and file changes execute without asking. |

Reset always confirms in every mode. User-initiated place, read, list, and retrieve never
confirm. The chosen value persists until the user changes it (FR-029).

### `WorkspaceRunStatus` (StrEnum)

| Value | Meaning |
|---|---|
| `succeeded` | Process exited 0 before the time budget. |
| `failed` | Non-zero exit, missing tool, or public-fetch failure. |
| `timed_out` | Stopped by `run_timeout_seconds`. |
| `cancelled` | Stopped because of reset or an explicit cancel. |
| `refused` | Gate denied (Off, Plan dry-run recorded separately, user deny, busy, full, unavailable). |

Plan-mode dry-runs are **not** `WorkspaceRun` rows (nothing executed). They may still appear
on the turn's `WorkspaceUsageTrace.planned` preview.

### `WorkspaceRunOrigin` (StrEnum)

| Value | Meaning |
|---|---|
| `conversation` | Started from a chat turn (agent tools). |
| `user` | User-initiated REST from the workspace view (list/place/retrieve/reset). |
| `unattended` | Goal / workflow / proactive job. |

### `WorkspaceAction` (StrEnum) — gate input, not stored as its own table

`list` · `read` · `place` · `retrieve` · `write` · `delete` · `run` · `run_script` · `reset` · `ingest`

## Entities

### Workspace / `workspace_state` (singleton)

One row (`id = 1` CHECK, same pattern as `persona_state`). The files themselves are not in
Postgres; they live on the sidecar volume.

| Field | Type | Notes |
|---|---|---|
| `id` | `SMALLINT` | PK, CHECK `id = 1`. |
| `mode` | `TEXT` | `WorkspaceMode`; default `'ask'`. |
| `last_reset_at` | `TIMESTAMPTZ NULL` | Set when a confirmed reset completes. |
| `last_used_at` | `TIMESTAMPTZ NULL` | Updated on any successful mutating run or place. |
| `updated_at` | `TIMESTAMPTZ` | Mode changes. |

Availability and "how full" are **not** persisted here. They are live sidecar `/stat`
(`available: bool`, `bytes_used`, `bytes_ceiling`, `busy: bool`). FR-001 durability is the
volume, not this row.

**Validation**: `mode` IN the five values. Unknown values refused at the store, not coerced
to Ask (a new conversation must not reset the mode — FR-029 — so a corrupt value is an
error, not a silent defaulting).

### `WorkspaceRun` (table `workspace_runs`)

Durable record of one command or skill-script execution (FR-008, FR-025). File-only writes
that did not spawn a process are **not** runs; they show up on `files_touched` of a run when
they happened as part of one, or only on the turn trace / listing mtime otherwise.

| Field | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK, `gen_random_uuid()`. Stable identity for a later follow-through spec. |
| `started_at` | `TIMESTAMPTZ` | |
| `ended_at` | `TIMESTAMPTZ NULL` | Null only while in flight (this spec still waits in-turn; column exists so 116 can detach). |
| `command` | `TEXT` | What was asked to run (edited version if the user edited). |
| `origin` | `TEXT` | `conversation` \| `unattended`. |
| `thread_id` | `TEXT NULL` | Conversation thread when origin is conversation. |
| `message_id` | `UUID NULL` | Set when the originating turn's message id is known. |
| `skill_id` | `UUID NULL` | Set when a skill script ran; FK not enforced across packages (plain UUID). |
| `skill_script_path` | `TEXT NULL` | Bundled script filename, e.g. `scripts/helper.py`. |
| `status` | `TEXT` | `WorkspaceRunStatus`. |
| `exit_code` | `INT NULL` | |
| `output_preview` | `TEXT` | Truncated to `output_preview_chars`; full output is a workspace file when truncated. |
| `output_file_path` | `TEXT NULL` | Path inside the workspace if stdout/stderr was spilled to a file. |
| `files_touched` | `JSONB` | List of `{path, op: "created"|"updated"|"deleted"}`. |
| `error_summary` | `TEXT NULL` | Plain-language failure; must not contain Ze secrets. |

**Indexes**: `(started_at DESC)` for recent activity; `(thread_id, started_at DESC)` for
per-conversation inspectability.

**Validation**: `origin` and `status` closed enums. `command` non-empty. Secrets stripped
from `output_preview` / `error_summary` (and any chat-inlined preview) by
`ze_workspace.sanitize.redact()` with a denylist of env key names before persist and
before return to the client (SC-004). Child-env stripping is necessary but not
sufficient.

### `WorkspaceFile` (not a Postgres table)

A file on the sidecar volume. Attributes returned by list/stat/retrieve:

| Field | Type | Notes |
|---|---|---|
| `path` | `str` | Relative POSIX path inside the workspace. No leading `..`, no absolute paths. |
| `size` | `int` | Bytes. |
| `modified_at` | `datetime` | Last changed. |
| `is_dir` | `bool` | Directories are listable; retrieve of a dir is refused. |

Place never overwrites: if `path` exists, store as `stem-N.suffix` and return both names.

### Skill script storage (`skill_scripts`) — `zsk002`

| Field | Type | Notes |
|---|---|---|
| `id` | `UUID` | PK. |
| `skill_id` | `UUID` | FK → `skills.id` ON DELETE CASCADE. |
| `filename` | `TEXT` | Relative path as in the archive (`scripts/helper.py`). |
| `content` | `BYTEA` | Source of truth for execution. |
| `content_type` | `TEXT` | Inferred from extension. |

**Uniqueness**: `(skill_id, filename)`.

### `Skill` columns added/renamed in `zsk002`

| Field | Type | Notes |
|---|---|---|
| `has_scripts` | `BOOLEAN NOT NULL DEFAULT false` | Replaces `has_unsupported_scripts` (column rename). True iff at least one `skill_scripts` row (or parser detection when import stored none yet). |
| `executable_approved` | `BOOLEAN NOT NULL DEFAULT false` | Separate from instructions `status`. Default false: 114 approvals stay non-executing (FR-012, SC-005). |
| `executable_approved_at` | `TIMESTAMPTZ NULL` | |

`approve_skill` (instructions) MUST NOT set `executable_approved`.
`approve_skill_executables` requires `has_scripts` and does not by itself activate a
pending skill's instructions. A skill may be `active` with `executable_approved = false`
(instructions only) or, after the new action, `active` + `executable_approved = true`.

Content-change recheck that changes script bytes or `has_scripts` sets
`executable_approved = false` and returns the skill to `pending_review` (same as
instructions hash mismatch). Snapshot in `skill_reviews.content_snapshot` gains
`has_scripts` and the list of script filenames (not bytes).

### `SkillUsageTrace` (extend existing dataclass)

| Field | Type | Notes |
|---|---|---|
| existing | | `skill_id`, `name`, `source`, `trigger`, `similarity` |
| `script_ran` | `bool` | Default `false`. True only when a bundled script actually executed this turn. |

### `WorkspaceUsageTrace` (new, on `MessageTrace.workspace`)

| Field | Type | Notes |
|---|---|---|
| `mode` | `str` | Mode in effect for the turn. |
| `runs` | `list[{id, command, status, skill_script_path?}]` | Durable run ids. |
| `files` | `list[{path, op}]` | Created/updated/deleted/placed/retrieved. |
| `script_ran` | `bool` | Any skill script ran. |
| `unavailable` | `bool` | Sidecar was down; no fabricated success. |
| `planned` | `list[str] \| null` | Plan-mode previews when nothing executed. |

## State transitions

### WorkspaceMode

```text
(any mode) --user PATCH /workspace/mode--> (any mode)
default on first boot: ask
```

No automatic transition. Closing the chat app is not a transition.

### WorkspaceGate (mode × action → decision)

```text
allow | confirm | plan | deny
```

Conversation / agent tools (`origin=conversation`):

| Action | off | plan | ask | auto_edit | auto |
|---|---|---|---|---|---|
| list, read, place, retrieve | deny | allow | allow | allow | allow |
| write, delete | deny | plan | confirm | allow | allow |
| run, run_script | deny | plan | confirm | confirm | allow |
| reset | confirm | confirm | confirm | confirm | confirm |
| ingest | deny | plan | confirm | allow | allow |

User-initiated REST from the workspace view (`origin=user`): list, read, place, retrieve
**allow** in every mode including Off (FR-006, FR-014). Reset always confirms. REST delete
is user-initiated and allows without confirm.

Unattended origin: `run` / `run_script` allow only in `auto`; unattended `write`/`delete`
allow in `auto_edit` or `auto`; otherwise deny (skip/wait, do not confirm — there is no
user on the other end of a confirm_request for a cron tick).

`run_script` additionally requires `executable_approved` and skill `status == active`;
otherwise deny with a plain-language "scripts are not approved" / "skill is not active".

### WorkspaceRun

```text
(start) --> succeeded | failed | timed_out | cancelled | refused
```

No resume-from-failed in this spec (in-turn only). `ended_at` set on every terminal
status.

### Executable approval

```text
has_scripts=false          --> no approve-executables action
has_scripts=true,
  executable_approved=false --> POST …/approve-executables --> true
content-change of scripts  --> executable_approved=false, skill pending_review
disable / pending          --> scripts do not run (flag may remain true until re-review)
```

Rejecting instructions does not need a separate executable-reject: scripts never run
unless both `active` and `executable_approved`.

## Relationships

```text
workspace_state (1 row)
    └── governs WorkspaceGate for all tools and unattended callers

workspace_runs (*)
    ├── optional thread_id / message_id (conversation)
    └── optional skill_id + skill_script_path

skills 1 -- * skill_scripts
skills 1 -- * skill_reviews  (snapshot includes has_scripts)

MessageTrace.workspace  --> workspace_runs.id[] (denormalized ids, not a FK)
MessageTrace.skills_used[].script_ran
```
