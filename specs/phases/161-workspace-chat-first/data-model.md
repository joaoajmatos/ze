# Data Model: Workspace Chat-First

## WorkspaceState

| Field | Change |
|-------|--------|
| `mode` | **Removed** (column drop `zws005`) |
| `last_reset_at` | Unchanged |
| `last_used_at` | Unchanged |
| `updated_at` | Unchanged |

Singleton row `id = 1`. Insert default no longer supplies `'ask'`.

## WorkspaceGateDecision

| Value | Change |
|-------|--------|
| `allow` | Keep |
| `confirm` | Keep |
| `deny` | Keep |
| `plan` | **Removed** — Plan mode is gone |

## WorkspaceMode

**Removed** (enum and all product use).

## WorkspaceUsageTrace

| Field | Change |
|-------|--------|
| `mode` | **Removed** |
| `runs`, `files`, `script_ran`, `unavailable`, `planned` | `planned` may stay empty; no `[plan]` dry-run path |

## Workspace run / file

Unchanged from 115/129. Origin still conversation | user | unattended.

## Procedure candidates

`workspace_run_is_approved(run)` — succeeded conversation or unattended (or user) runs count as approved. No mode argument. Precondition text must not name modes.

## Validation

- Gate never reads persisted policy.
- REST status has no `mode` field.
- OpenAPI has no `/workspace/mode`.
