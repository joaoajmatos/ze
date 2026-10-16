# Contract: commitment judgment and decision table

One System One request per non-trivial conversation turn (`max_attempts=1`).

## Questions (module `ze_worldstate/commitment_judge.py`)

| id | type | used when | meaning |
|---|---|---|---|
| `commitment` | choice | always | `reminder, loop, goal, waiting_on, fact, forget, ingest, clarify, none` |
| `family` | choice | Choice = `fact` | 163 family Choice (`ze_memory/fact_judge.py`) |
| `biography` | noul | Choice = `fact` | 163 biography Noul |
| `is_open_concern` | noul | Choice = `loop` | 168 wording |
| `explicit_declaration` | noul | Choice = `loop` | 168 wording |
| `resolves_existing` | noul | always | 168 wording |

All six are sent in every request (one batch); pure code reads only the ones the Choice makes relevant and lists the rest as not consumed on the trace. State: `{user, assistant[:1000]}`.

## Inputs to `decide()`

`result: SystemOneResult`, `cfg: CommitmentIntakeSurfaceConfig`, `created: TurnCreation` (`reminder_id`, `goal_id`, both optional, read from the turn's tool calls), `tracked: bool` (`tracking_earned`).

## Decision table (first match wins)

| # | Condition | Outcome | Reason |
|---|---|---|---|
| 1 | result skipped | `fallback` | skip reason |
| 2 | any needed answer missing or invalid | `fallback` | `invalid_answer` |
| 3 | any bar null | `fallback` | `uncalibrated` |
| 4 | `resolves_existing` >= `resolves_hold` | `resolve_loop` | `resolves` |
| 5 | `created` has reminder or goal | `link` (kind from `created`) | `turn_created`; never creates a loop and persists no fact (a tool call that created a reminder or goal outranks a contradicting `fact` label) |
| 6 | Choice = `waiting_on` | `hold` | `waiting_on` (label only, Phase 174) |
| 7 | Choice in `reminder, goal` | `hold` | `reminder_not_created` / `goal_not_created` |
| 8 | Choice = `fact` and confidence >= `choice_hold` | fact rules of 163 (`family`>= `family_hold`, `biography` >= `biography_hold`) -> `persist_fact` or `hold` | as 163 |
| 9 | Choice in `forget, ingest, clarify, none` | `hold` | choice name |
| 10 | Choice = `loop`, confidence < `choice_hold` | `hold` | `loop_unsure` |
| 11 | Choice = `loop`, `is_open_concern` < `loop_hold` | `hold` | `not_open_concern` |
| 12 | Choice = `loop`, `tracked` | `hold` | `tracked` (169) |
| 13 | Choice = `loop`, `explicit_declaration` >= `explicit_hold` | `create_loop_declared` | `explicit` |
| 14 | Choice = `loop` | `create_loop_suspected` | `implied` |

A confidence below `choice_hold` on any non-loop Choice is `hold` with reason `choice_unsure`. Bars compare at or above. `decide()` never raises.

Row 5 note: a successful tool call outranks the label. The loop-side link target is found by the existing `find_matching_loop` (entity overlap, then E5 0.75 title similarity) over live loops (`suspected`, `active`, `drifting`).

## Fallbacks

`fallback` (rows 1-3) runs today's Haiku paths: the Haiku fact extractor and the 109 Haiku loop gate. Surface off or no client: the same.
