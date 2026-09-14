# Quickstart: Validating the Workspace Run Journal

Prerequisites: `make db-up && make migrate`, workspace mode set to `auto` (or
`ask` with confirmation) so `workspace_run` isn't refused by `WorkspaceGate`.
The sidecar can be run locally (`cd sidecar/workspace && uvicorn main:app
--port 8080`) with `WORKSPACE_ROOT` pointed at a scratch directory, or against
the deployed `ze-workspace` Fly app for an end-to-end check.

## 1. A run survives the mind restarting (User Story 1 / SC-001)

```bash
# Terminal A: start the mind
make dev

# In chat / via the API, ask Ze to run something that outlives the short wait:
#   "run `sleep 40 && echo done` in the workspace"
# Expect: "[still running] run <id>: ... continuing in the background"

# Terminal B, while it's still running: restart the mind
#   Ctrl-C the make dev process, then `make dev` again

# Wait for the sleep to finish (~40s from start), then check the thread:
#   the follow-up must say the command finished with exit 0 and output
#   containing "done" — NOT "(output unavailable — ze-api restarted...)"
```

Direct REST check (no chat needed):

```bash
curl -s -H "Authorization: Bearer $ZE_API_KEY" \
  http://localhost:8000/api/v0/workspace/runs?limit=1 | jq '.runs[0].output_preview'
# -> "done"
```

## 2. Watching a live run (User Story 2 / SC-002)

```bash
# Start a run that prints over time, capture its id from the tool reply, then:
curl -s -H "Authorization: Bearer $WORKSPACE_API_TOKEN" \
  http://ze-workspace.internal:8080/runs/<id>/events
# -> ndjson lines appear as the command prints, well before the final "exit" line
```

Confirm the follow-up still fires exactly once after exit (no double
follow-through from having watched live).

## 3. Cancel by handle (User Story 3 / SC-003)

```bash
# Start a long run, grab <id>, then:
curl -s -X POST -H "Authorization: Bearer $ZE_API_KEY" \
  http://localhost:8000/api/v0/workspace/runs/<id>/cancel
# -> {"status": "cancelled", ...} within 15s; the process is gone (check `ps`
#    on the sidecar host, or that a subsequent /stat shows busy: false)

# Cancelling again (already terminal):
curl -s -X POST ... /runs/<id>/cancel
# -> 409, "already finished"

# Cancelling a bogus id:
curl -s -X POST ... /runs/00000000-0000-0000-0000-000000000000/cancel
# -> 404, "not running"
```

## 4. One run at a time, even detached (User Story 4 / FR-007)

```bash
# Start run A (long-running), then immediately ask for run B in the same
# conversation. Expect the second request to be refused with A's handle and
# command named, e.g.:
#   "Another workspace command is already running: `sleep 40` (run <A-id>)."
# Then cancel or wait out A, and confirm a third request now starts.
```

## Test suite

```bash
make test-ze-workspace   # client/store/followthrough/tools, extended for this phase
make test-ze-api          # container wiring + REST route
cd sidecar/workspace && python -m pytest tests/   # new: journal spawn/watch/cancel/retention
```

All must pass, plus `make lint`, before this phase is considered done
(Constitution V).
