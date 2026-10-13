# ze-worldstate

Open-loop substrate for Ze — active concerns, honest provenance, evidence-linked confidence.

## Role in Ze

Goals are the heavyweight, explicitly-declared end of Ze's executive function. Most real commitments never get declared as a goal: a promise made in an email thread, a decision left pending, a project quietly stalling because a dependency didn't land. `ze-worldstate` tracks these as **open loops** — the lightweight, ambient half of executive function, and the shipped first slice of what `specs/arch/ze-doctrine.md` calls **active concerns**, the fourth face of Ze's world-state.

An open loop moves through `suspected → active → drifting → closed | dropped`. Confidence decays on its own; a contradiction or a missed deadline pushes a loop into `drifting`. Only an explicit user ask (`track_loop`) can move a `drifting` loop back to `active`. Loops reuse `ze-memory`'s graph tables (`memory_relationships`, a dedicated `open_loop` bucket) for dedup and neighbourhood expansion rather than a parallel model — this package owns loop lifecycle and surfacing, not a second memory store.

### Key features

- `OpenLoop` / `LoopState` — the lifecycle type and its five states
- Extraction (`extraction.py`) — conservative, relevance-gated loop extraction wired into all four inflows: conversation, email, calendar, and ingestion. The 109 Haiku gate stays as the fallback. Its parse tolerates the code fence Haiku puts around JSON; before phase 168 it did not, so this extraction created no loops in production. Each created loop links the evidence that triggered it: the conversation or email turn episode, or the ingestion ref. The calendar inflow passes no evidence, because its event has no UUID record
- Loop gate (`loop_judge.py`, `admission.py`) — phase 168. One System One request asks `is_open_concern`, `resolves_existing`, and (conversation only) `explicit_declaration`; a pure `decide()` maps the answers to resolve, create-declared, create-suspected, hold, or fallback. `LoopInflow` runs the gate, asks Haiku for a title (and an optional window in days) only after a positive gate, and commits. Surface `system_one.surfaces.loop_gate` is on in the shipped config (`loop_hold` 0.75, `explicit_hold` 0.85, `resolves_hold` 0.8), after an `ENABLE` verdict on the held-out set for English and Portuguese
- Track tool (`tracking.py`, `agents/tools.py`) — phase 169. The `track_loop` tool, on the `loops` agent, starts tracking a concern the user asked Ze to keep in mind. `LoopTracker` matches existing loops and returns one outcome: `created`, `confirmed`, `reinforced`, or `revived`. The reply may claim tracking only after a successful call
- Confirm — phase 171. A confirm, from the Open loops page or the `confirm_loop` tool on the `loops` agent, stamps a suspected loop like a declaration: confidence 0.9 and a 7-day drift deadline. The `track_loop` result also reports whether tracking was earned (`tracking_earned`)
- Matching (`matching.py`) — entity-overlap + embedding-similarity dedup against existing loops
- Decay (`decay.py`) — confidence decay cascade, invoked at every evidence-writing code path
- Drift (`drift.py`) — deadline computation and contradiction/absence rationale for the `active → drifting` transition. The sweep selects `active` loops whose `drift_deadline` has passed. New evidence on an active loop calls `record_corroboration`, which moves the deadline to at least 7 days from now (the default window is a code constant)
- `LoopSurfacer` (`surfacing.py`) — a push-bar-gated path (`ze_correlation`'s shared push budget) for `drifting` loops that sends a hedged mention. The grounding gate checks the loop title against its evidence
- Review (`review.py`) — confirm / close / drop lifecycle transitions
- Jobs (`jobs/`) — `DriftSweepJob` and `StaleSuspicionJob`, scheduled via `ze-proactive`. `ze-priority`'s `AttentionArbitrationJob` replaced the old `PushSweepJob`

### Integration

`ze-api`'s container calls `build_worldstate_stack()` at startup, which wires `PostgresLoopStore` against the shared `ze-memory` graph store. The conversation gate runs in the `write_memory` node beside the fact extractor and commits fire-and-forget. A turn where `track_loop` succeeded skips the gate. The messenger, calendar, and ingestion inflows call a loop extractor (`ze_worldstate.inflow`) that runs the same gate, can create suspected loops or resolve existing ones, logs its judgments, and writes no message-trace rows. When the gate is off, uncalibrated, or skips, the 109 Haiku gate runs (see the note above on its parse failure). `GET/POST /api/v0/loops` (`rest.py`) exposes review actions to `ze-web`'s `widgets/loop-review`.

## Responsibilities

| Module | What it provides |
|---|---|
| `types.py` | `OpenLoop`, `LoopState`, `LoopProvenance`, `TrackOutcome`, `TrackResult` |
| `store.py` | `LoopStore` protocol, `PostgresLoopStore` |
| `extraction.py` | Relevance-gated loop extraction from inflow text; the 109 Haiku gate is the fallback |
| `loop_judge.py` | System One loop gate: three Noul questions, bars, pure `decide()` |
| `admission.py` | `LoopInflow`: gate, Haiku title writer, commit |
| `tracking.py` | `LoopTracker`: normalize, match, and write a user-asked loop |
| `matching.py` | Entity-overlap + embedding dedup against existing loops |
| `decay.py` | Confidence decay cascade, called at the evidence-writing code path |
| `drift.py` | Drift deadline computation and rationale composition |
| `surfacing.py` | `LoopSurfacer` — push-bar-gated ntfy path with a hedged mention |
| `review.py` | Confirm / close / drop lifecycle transitions |
| `inflow.py` | Wiring helpers for the four inflows (conversation, email, calendar, ingestion) |
| `jobs/` | `DriftSweepJob`, `StaleSuspicionJob` |
| `bootstrap.py` | `build_worldstate_stack()` — DI wiring for `ze-api` |
| `rest.py` | `GET/POST /api/v0/loops` handlers |
| `migrations/` | `zw001` (open_loops table), `zw002` (drift columns) |

Every `WRITE` tool in this package declares `reversibility` and an `effect_phrase`. Retry reads these declarations to decide if a reply can be regenerated.

## Dependencies

![ze-worldstate package dependencies](../../docs/diagrams/core/cognition/ze-worldstate/dependencies.svg)

<sub>[Interactive version](../../docs/diagrams/core/cognition/ze-worldstate/dependencies.html)</sub>

Third-party: `asyncpg`.

## Usage

```python
from ze_worldstate.bootstrap import build_worldstate_stack
from ze_worldstate.types import OpenLoop, LoopState

stack = build_worldstate_stack(shared, settings)
loops = await stack.loop_store.list(states=[LoopState.ACTIVE])
```

Wired by `ze-api`, not imported directly by plugin code — plugins that want to emit loop-relevant events use their existing `SignalSource` / inflow hooks, which `ze-worldstate` already listens to.

## Testing

From the repo root:

```bash
make test-worldstate
```

See [docs/testing.md](../../docs/testing.md).
