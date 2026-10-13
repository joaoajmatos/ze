# ze-priority

Attention arbitration — one ranking of what Ze should care about, and one push budget.

## Role in Ze

Open loops, goals, hypotheses, and contact follow-ups each compete for attention. This package scores them on one scale, so Ze can answer "what matters now?" the same way in chat, in the web app, and in proactive pushes. It also lets the user reorder the ranking in plain words.

### Key features

- `PriorityView.rank()` ranks drifting loops, stuck or near-gate goals, hypotheses, and stale relationships
- User overrides (`PriorityOverride`) merge into the ranking at read time. They decay over 48 hours unless pinned
- `reprioritize_item` — a conversational tool that makes a named item more or less urgent
- `AttentionArbitrationJob` — one scheduled job that pushes only the top candidate, within a shared daily budget. It reads `worldstate.push.enabled` for loops and `correlation.push.enabled`/`dry_run` for hypotheses
- The snapshot response carries `{items, sources_failed}`, so the page can name the sources it could not read. `source_kind` accepts `loop`, `goal`, `hypothesis`, and `relationship`
- `TurnSurfacing` — inline mentions and the resume recap use the same merged ranking. It detects "what's open" questions with `OpenQueryDetector`, which compares the message to example questions by E5 similarity in English and Portuguese. The recap lists at most 5 items. An explicit "what's open" answer lists at most 10. At resume, it offers up to 3 suspected loops as a question. A loop it offered stays quiet for 7 days, tracked in `push_log`

### Integration

`ze-api` builds the `PriorityView`, the override store, and the arbitration job in `compose.py`. The job replaces the old per-source push sweeps in `ze-worldstate` and `ze-correlation`. Overrides enter the world-state as a pair of contributions through the seam. `ze-collision` logs a user-versus-Ze disagreement. The web app shows the snapshot at `/priority`.

## Responsibilities

| Module | What it provides |
|---|---|
| `view.py` | `PriorityView` — gathers signals and ranks them |
| `scoring.py` | Scoring functions for loops, goals, hypotheses, and relationships |
| `merge.py` | Merges active overrides into a ranking, with decay |
| `service.py` | `submit_reprioritization()` — the one validated write path |
| `store.py` | `PriorityOverrideStore` Protocol and Postgres store |
| `contribution.py` | Turns an override into seam contributions |
| `tools.py`, `agent.py` | The `reprioritize_item` tool |
| `turn.py` | `TurnSurfacing` — open-item mentions, resume loop offers, and recap for a turn |
| `open_query.py` | `OpenQueryDetector` — E5 similarity check for "what's open" questions |
| `arbitration.py` | `AttentionArbitrationJob` |
| `rest.py` | Snapshot helper for the REST routes |
| `migrations/` | `zpri001` — creates `priority_overrides` |

## Dependencies

`ze-agents`, `ze-proactive`, `ze-worldstate`, `ze-automation`, `ze-correlation`, `ze-plugin`, `ze-collision`, `asyncpg`.

## Configuration

| Key in `config.yaml` | Description |
|---|---|
| `proactive.attention_arbitration.enabled` | Turn the arbitration job on or off (default on) |
| `proactive.attention_arbitration.cron` | Job schedule (default `0 */4 * * *`) |
| `proactive.budget.max_pushes_per_day` | Shared push budget (default 3) |

REST routes: `GET /api/v0/priority/snapshot`, `POST /api/v0/priority/override`, `POST /api/v0/priority/override/{override_id}/unpin`.

## Testing

From the repo root:

```bash
make test-priority
```

See [docs/testing.md](../../../docs/testing.md).
