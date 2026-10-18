# Quickstart: Trace Telemetry (187b)

## Automated
- `make test-core`, `make test-agents`, `make test` (ze-api), `make test-seed`, `make test-py`.
- `make test-web`, `make typecheck-web`, `make lint`.
- `rtk proxy grep -rn "total_duration_ms\|pendingArrivals\|arrivalsByMessage\|sentAtByMessage\|pendingSentAt" core apps packages plugins --include='*.py' --include='*.ts' --include='*.tsx'` returns nothing outside generated history fixtures.

## Manual against `make dev-full`
1. Ask "what's on my calendar tomorrow". Watch the trace panel: the signal path fills stage by stage with server times; the total, tokens, cost and context fill appear on the readouts; routing shows the shortlist against its bars; judgment gauges show bars.
2. Reload and open the same reply from history: the same stage times and readouts.
3. Ask for something that needs a confirmation (send an email draft); wait 20 s; approve. The signal path shows the second run after a gap labelled with the wait; the total includes it and `paused_ms` reads about 20 s.
4. Force a tool failure (stop the workspace sidecar, ask Ze to list workspace files): the live tool row shows failed with its real duration, and the committed row matches.
5. Compound ask ("check my calendar and my email"): tool rows from both subtasks land by start time, matched to committed rows by id.
