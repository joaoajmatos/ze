# Quickstart: Workspace Follow-Through

Validates User Stories 1–4 end to end. Assumes Phase 115 (workspace mode, sidecar,
`workspace_run` tool) is running — see
`specs/phases/115-workspace-sidecar/quickstart.md` for base setup.

## Prerequisites

```bash
make db-up
make migrate            # applies zws001 (Phase 115) + zws002 (this phase)
make dev                # ze-api on :8000, workspace mode defaults to Ask
```

Set workspace mode to Auto (skips confirms, isolates this phase's timing behavior
from Phase 115's confirm flow):

```bash
curl -sX PATCH localhost:8000/api/v0/workspace/mode \
  -H "Authorization: Bearer $ZE_API_KEY" -H "Content-Type: application/json" \
  -d '{"mode": "auto"}'
```

## Scenario 1 — short run finishes in the turn (User Story 1, SC-001)

Send a conversation message that asks Ze to run a command that completes in a couple
seconds (e.g. `ls`). Expect:

- The turn's reply contains the run's result on the same turn.
- `GET /api/v0/workspace/runs?limit=1` shows that run with `ended_at` set,
  `follow_through_notified: false` (never applicable — it finished in-turn).
- No follow-up turn appears afterward on that thread; no push is sent.

## Scenario 2 — long run detaches (User Story 1, SC-002)

Ask Ze to run a command that sleeps past the configured short wait (e.g. a script
`sleep 60`). Expect:

- The turn ends within a few seconds of the short-wait constant elapsing; the reply
  says the work is still running and names the run.
- The user can send another message on that thread immediately (SC-002: under 5s).
- `GET /api/v0/workspace/runs?limit=1` shows `ended_at: null`.

## Scenario 3 — follow-up on completion, connected (User Story 2)

With the ze-web client connected via WebSocket, wait for Scenario 2's run to finish
(~60s total). Expect:

- A new assistant turn appears on that same conversation without the user sending
  anything, describing the result.
- No ntfy push arrives.
- `GET /api/v0/workspace/runs?limit=1` now shows `ended_at` set,
  `follow_through_notified: true`.

## Scenario 4 — follow-up on completion, disconnected (User Story 2, SC-004)

Repeat Scenario 2 with the ze-web client closed (no WebSocket connection). Expect:

- An ntfy push arrives referencing the run.
- Reconnecting the client and opening the thread shows the follow-up turn was
  already written to the conversation history (delivered on completion, not on
  reconnect).

## Scenario 5 — cancel (User Story 3, SC-005)

Start a long-running command, then before it finishes:

```bash
curl -sX POST localhost:8000/api/v0/workspace/runs/<run_id>/cancel \
  -H "Authorization: Bearer $ZE_API_KEY"
```

Expect:

- `200` with `status: "cancelled"` within 15 seconds of the call.
- The follow-up turn (or in-turn message, if cancel raced the short wait) tells the
  user it was stopped, not that it succeeded.
- Any files the run had already written remain in `GET /api/v0/workspace/files`.
- A second cancel call on the same run id returns `409`.

## Scenario 6 — busy while detached (User Story 4, SC-006)

While Scenario 2's run is still detached (`ended_at: null`), ask Ze to run a second
command in the same or a different conversation. Expect:

- The second request is refused with a message naming the currently-running command,
  not silently queued or interleaved.
- After the first run finishes or is cancelled, the same request succeeds.

## Scenario 7 — restart reconciliation (D5, no numbered SC but covered by SC-003)

Start a long-running command, restart `ze-api` (`Ctrl-C` and `make dev` again) before
it finishes, then let it finish. Expect:

- The follow-up turn still appears once the run reaches a terminal status, despite
  the in-memory watcher having been recreated by the restart.
