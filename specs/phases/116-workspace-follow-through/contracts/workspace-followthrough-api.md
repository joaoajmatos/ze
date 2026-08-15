# Contract: Workspace Follow-Through — REST additions + internal orchestrator

Extends `specs/phases/115-workspace-sidecar/contracts/workspace-api.md`. All auth,
error shape, and `WorkspaceRunResponse` fields from that contract apply unchanged;
only the additions below are new.

## REST

### `POST /api/v0/workspace/runs/{id}/cancel`

**operation_id**: `cancelWorkspaceRun`

Stops an in-progress run (User Story 3). No confirmation required (FR-009) — this is
not workspace reset.

**Response** `200`: updated `WorkspaceRunResponse` with `status: "cancelled"`,
`ended_at` set.

**Response** `409`: `{ "detail": "already finished" }` when the run's `ended_at` is
already set (FR: "nothing is killed; they are told it already finished" —
User Story 3 Acceptance Scenario 3). Cancelling a row that never started detaching
(already terminal from an in-turn completion) is the same 409.

**Response** `404`: unknown run id.

**Side effects**: calls `WorkspaceClient.cancel()` (sidecar `/cancel`, Phase 115
shape) to stop the subprocess, persists `status = cancelled`, `ended_at = now()`,
leaves `files_touched`/`output_preview` as already recorded (partial output stays
inspectable — spec's "workspace is left as it is"). The `RunWatcher` task for that
run observes the now-terminal row (same code path as a natural finish) and proceeds
through normal follow-through: a follow-up turn saying it was stopped, no completion
push if connected, one if not.

### `GET /api/v0/workspace/runs` (extended)

Unchanged endpoint from Phase 115; `WorkspaceRunResponse` gains one field:

```json
{
  "follow_through_notified": false
}
```

Used by the workspace page and the chat "still running" chip to distinguish a
detached-and-pending row (`ended_at: null`) from one whose follow-up has already
been dispatched.

### Conversation turn reply shape (not a new endpoint)

When FR-002 applies (still running after the short wait), the turn's
`final_response` text states the run is still running and names the run id, and
`MessageTrace.workspace` (Phase 115's `WorkspaceUsageTrace`) carries
`runs: [{id, command, status: "in_progress"}]` so the trace panel and the chat chip
can render "still running" without a second request. `status: "in_progress"` here is
a trace-only projection for a null-`ended_at` row — never written to
`workspace_runs.status`, which stays one of Phase 115's five closed values.

## Internal orchestrator contract (`core/ze-workspace/ze_workspace/followthrough.py`)

Not a network contract — this is the Protocol boundary `apps/ze-api` implements so
`ze-workspace` never imports `ze_core`/`ze_api` (Constitution III).

```python
class TurnStarter(Protocol):
    async def invoke_raw_turn(self, thread_id: str, prompt: str) -> None: ...
    """Starts a normal follow-up turn on thread_id. Must internally acquire the
    ThreadTurnLock for thread_id before invoking the graph, and release it after —
    RunWatcher does not manage the lock itself, it only awaits this call."""

class PushSender(Protocol):
    async def send_completion(self, run: WorkspaceRun) -> None: ...
    """Delivers a completion notification. Internally decides connected-vs-push
    (D4) — RunWatcher always calls this unconditionally for a terminal
    origin=conversation run; the Protocol implementation is what makes it a no-op
    when the client is connected."""

class RunWatcher:
    def __init__(self, store: WorkspaceStore, turn_starter: TurnStarter,
                 push_sender: PushSender) -> None: ...

    async def detach(self, run: WorkspaceRun, pending_completion: Awaitable[...]) -> None:
        """Called once the short wait elapses without pending_completion resolving.
        Schedules an asyncio.Task that awaits pending_completion, persists the
        terminal status via store, then — only when run.origin == "conversation" —
        calls turn_starter.invoke_raw_turn(...) and push_sender.send_completion(run),
        marking follow_through_notified True first (data-model.md)."""

    async def reattach(self, run: WorkspaceRun) -> None:
        """Startup reconciliation (D5): re-derives pending_completion for a run
        with ended_at IS NULL from the sidecar's current process state and calls
        detach() again. If follow_through_notified is already True on an otherwise-
        terminal row found at startup (crash landed between store write and
        dispatch), re-dispatches once — that gap is not double-delivery, it is the
        one delivery that never went out."""
```

**Busy-check contract**: `WorkspaceGate`'s existing busy check (Phase 115) is
extended to treat any run with `ended_at IS NULL` as busy, not only a run the calling
turn itself is waiting on — a second `workspace_run`/`workspace_run_skill_script`
call from a different turn, and unattended callers per FR-015, both see the same
busy refusal while a detached run is outstanding.
