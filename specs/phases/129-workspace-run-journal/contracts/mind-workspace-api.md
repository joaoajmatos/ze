# Contract: Mind-Side Workspace Surface (`core/ops/ze-workspace`, `apps/ze-api`)

## `WorkspaceClient` (`ze_workspace/client.py`)

Replaces the blocking `run()`/bare `cancel()` methods.

```python
async def start_run(
    self,
    command: list[str],
    run_id: UUID,
    *,
    cwd: str = "",
    timeout_seconds: int = 120,
    stdin_b64: str | None = None,
    env: dict[str, str] | None = None,
) -> None:
    """POSTs /run with id=run_id. Raises WorkspaceBusyError on 409 (with the
    running id/command attached to the exception for the FR-007 refusal
    message — see Decision 5, though the primary path never reaches here
    because tools.py checks list_in_progress() first)."""

async def get_run(self, run_id: UUID) -> WorkspaceRunStatus | None:
    """GET /runs/{id}. Returns None on 404 (unknown/disposed handle)."""

async def watch_run(
    self, run_id: UUID
) -> AsyncIterator[JournalEventDTO]:
    """GET /runs/{id}/events as a streaming async generator. Raises
    WorkspaceNotFoundError on 404 before any event is yielded."""

async def cancel_run(self, run_id: UUID) -> None:
    """POST /runs/{id}/cancel. Raises WorkspaceNotFoundError (404) or
    WorkspaceRunAlreadyTerminalError (409) — both already exist."""
```

`run()` and the old bare `cancel()` are removed — no remaining caller after
this phase's `tools.py`/`followthrough.py` changes land in the same commit.

## `RunWatcher` (`ze_workspace/followthrough.py`)

`RunCompletionSource`/`SidecarPollCompletionSource` are deleted (Decision 6).
`detach()`/`reattach()` are reworked to consume `watch_run()`:

```python
class RunWatcher:
    async def detach(self, run: WorkspaceRun) -> None:
        """Starts a background task that calls client.watch_run(run.id),
        persisting each stdout/stderr chunk as an updated output_preview
        (best-effort, for live-watch — SC-002) and, on the exit event, calls
        store.complete_run(...) with the real exit_code/output/files_touched
        read off that event, then dispatches follow-through exactly as
        today."""

    async def reattach(self, run: WorkspaceRun) -> None:
        """Startup reconciliation. If run.sidecar_dispatched is False, the
        sidecar never received this id — mark it failed directly with a
        plain-language error_summary, no sidecar call. Otherwise call
        client.get_run(run.id):
          - still running -> resume via detach() (same as the live path)
          - terminal       -> complete_run(...) with the real result, exactly
                               as detach()'s exit-event branch
          - None (404)     -> mark failed, plain-language error_summary
                               ("the computer restarted and lost this run") —
                               Edge Case 3. Ze does not invent success."""
```

## `workspace_run` / `workspace_run_skill_script` tools (`ze_workspace/tools.py`)

Before calling the sidecar at all, both tools now call
`_store.list_in_progress()` (existing store method, previously unused by
these tools). If it returns a non-empty list, the tool returns the FR-007
refusal without touching the sidecar:

```
Another workspace command is already running: `{running.command}` (run {running.id}).
Wait for it to finish or cancel it before starting a new one.
```

This applies uniformly to `WorkspaceRunOrigin.CONVERSATION`, `.USER`, and
`.UNATTENDED` callers (all three reach the same tool functions), satisfying
FR-007's "This applies to conversation, user-initiated, and unattended
origins" without per-origin branching.

## REST surface (`ze_workspace/rest.py`, mounted in `apps/ze-api`)

No route signatures change. `cancel_run()` and `list_runs()` keep their
existing shape — they now return real, journal-backed data instead of
best-effort/placeholder data, which is a behavior improvement, not a contract
change. `_run_to_dict()` gains no new field (the `sidecar_dispatched` column
is an internal reconciliation detail, not user-facing).

## Removed

`RunCompletionSource` protocol, `SidecarPollCompletionSource` class, and the
`_RECONCILE_UNAVAILABLE_PREVIEW` placeholder string are all deleted from
`followthrough.py` — see Decision 6 in `research.md`. `bootstrap.py`'s
`completion_source` parameter to `build_workspace_stack()` is removed along
with them (no remaining implementation to inject).
