# Research: One Commitment Intake

- **Current split (verified in code):** `write_memory` runs `_run_fact_extractor` (163 request: `speech_act`, `family`, `biography`) and `_run_loop_admission` (168 request: three Nouls) in one `asyncio.gather`. Two requests, no shared answer. `tracking_earned` already suppresses the loop side after `track_loop`.
- **Why post-turn cannot create reminders:** the reminder and goal exist before `write_memory` runs, created by the agent's own tool. The intake can only decide about loops and links.
- **Tool results:** `set_reminder` returns `{id, label, fire_at, undo}`; `create_goal` returns `{id, title, milestones, gates, undo}`. Both have `error` keys on failure.
- **Dependency direction:** `ze-worldstate -> ze-memory`; the merged judge therefore lives in `ze-worldstate` (D-1).
- **Matching:** `find_matching_loop` is entity overlap first, E5 title cosine 0.75 second; reused for linking.
- **F4 evidence:** 24 live calls (executive-function Appendix A) are the seed for hard-negative rows in the calibration sets (not copied into the held-out set verbatim).
- **T020, 181 re-read (2026-10-16, branch `181-irreversible-write-confirmation`):** `success` semantics unchanged for our check. A parked or denied write is built with `success=False` and `gate="parked"` / `"denied"` / `"refused_over_cap"`; `success=True` only for an executed call. `turn_creation` reads `success` plus a non-error payload id, so a parked `set_reminder`/`create_goal` is not a creation. 181 adds `ToolCall.parked`, `child_loop`, `approval` (not read here). 181 does not touch `nested_tools.py` or `nodes/memory.py` on its branch.

## Tuning notes

### Run 1 (T042, 2026-10-16, tuned set only, model `typesafe/jev-1.13`, seed 173)

Wording and criteria as of commit `0b3fe9d2`. 148 rows, 3 requests per row (intake + frozen 163 + frozen 168). Raw results saved to `eval/results/commitment_intake_tuned_run1.json` (gitignored); `--replay` re-scores them offline.

Suggested bars (tuned only): `choice_hold` 0.7, `family_hold` 0.7, `biography_hold` 0.55, `loop_hold` 0.65, `explicit_hold` 0.95, `resolves_hold` 0.95.

At those bars, per language (EN / PT), intake vs frozen baseline:

| metric | EN intake | EN baseline | PT intake | PT baseline |
|---|---|---|---|---|
| duplicate bookings | 0 | 17 | 0 | 17 |
| false loop creates | 0 | 8 | 0 | 6 |
| fact precision / recall | 1.00 / 0.86 | 1.00 / 0.71 | 1.00 / 0.71 | 1.00 / 0.57 |
| loop precision / recall | 1.00 / 0.64 | 0.36 / 1.00 | 1.00 / 0.57 | 0.38 / 1.00 |
| Choice accuracy | 0.878 | n/a | 0.878 | n/a |

FR-022 clauses failing on the tuned set: loop recall (needs >= 0.95) and Choice accuracy (needs >= 0.9). Everything else passes, `waiting_on` rows write nothing (0/10).

Cause (from the error list): explicit obligations with a time word ("I need to reply to the landlord this week", "Preciso de responder ao email do senhorio esta semana") get Choice `goal` or `reminder` at confidence 0.33 to 0.55, or `loop` at 0.44 to 0.61. The current `reminder` criterion says "Time wins" and carries no "the user must ask for a ping" test. The 12 `loop_turn_*` rows also read as `reminder` or `goal` because the assistant reply says it created one; they link correctly (row 5) but cost Choice accuracy against gold `loop`. Criteria and decision-table changes are outside ENG-B's files and wait on the Maestro.

### Run 2 (T042, 2026-10-16, tuned set only, same model and seed)

Wording after T028 (`63e0b014`: reworded `reminder`/`goal` criteria, row 7a), scoring after T044 (Choice accuracy over `turn_created` `none` rows, link accuracy reported apart). Raw results: `eval/results/commitment_intake_tuned_run2.json` (gitignored).

Choice accuracy 0.98 EN / 0.96 PT (was 0.92 / 0.94 on the same run-1 rows under T044); link accuracy 24/24 both; `waiting_on` writes 0/10; duplicate bookings 0 against 18 / 17 for the baseline.

Two bar sets, both from the tuned set only:

| bars (choice=family, bio, loop, explicit, resolves) | EN | PT |
|---|---|---|
| suggested: 0.95, 0.55, 0.60, 0.95, 0.95 | passes every FR-022 clause (fact R 0.86 vs 0.71, loop P/R 1.00/1.00) | loop recall 0.857 vs baseline 1.00: FAILS |
| hand-picked: 0.85, 0.60, 0.60, 0.85, 0.90 | false loop create 1: FAILS zero-false-creates (loop P 0.93) | passes every clause (fact R 0.71 vs 0.57, loop P/R 1.00/1.00) |

The whole difference is `ci-t-en-073` / `ci-t-pt-073`, mixed rows with gold `fact` ("I'm allergic to nuts, and I still haven't answered the school about the trip"). The text also carries a real open concern, so the model's `loop` Choice at 0.93 EN / 0.80 PT is defensible, but the gold counts it as a false create. The suggested `choice_hold` 0.95 only avoids it because EN-073 scores 0.93, which is a grid-edge fit to one ambiguous row. Two PT loop rows (`ci-t-pt-029`, `-031`) score `loop` at 0.88 / 0.91 and are held at 0.95. A bar around 0.85 recovers them but lets the mixed row through.

Open question for the Maestro: score a `mixed` row whose text also carries an open concern as "loop acceptable" (neither a false create nor a required hit), for example with an optional `also_loop` row field. Changing the held-out rows is still allowed before the first held-out run.

### Frozen bars for the held-out verdict (2026-10-16, chosen on the tuned set only)

`also_loop` landed first (`460e7ce3`): a mixed row that states a fact and also carries a real open concern accepts a loop answer (neither a false create nor a required hit). Marked by text only, before any held-out model output exists: tuned `ci-t-en-073`, `ci-t-pt-073`; held-out `ho-en-40`, `ho-pt-40` (the other mixed rows either created a reminder or have a loop gold, which the schema excludes).

Run 2 re-scored offline (`--replay`, no new spend). The tuned set is flat across `choice_hold` 0.5 to 0.8 (EN perfect, PT fact recall 5/6 from `ci-t-pt-049`, `none`@0.55 on a fact row, which no bar below 0.55 can recover while keeping precision), loop recall stays 1.00 for `loop_hold` 0.50 to 0.70, false resolves are zero for `resolves_hold` at or above 0.85 (false rows reach 0.84, true rows start at 0.90), and `explicit_hold` 0.95 gives the fewest false declared. Centres of those plateaus, not their grid edges:

| bar | frozen value |
|---|---|
| `choice_hold` | 0.65 |
| `family_hold` | 0.65 |
| `biography_hold` | 0.55 |
| `loop_hold` | 0.60 |
| `explicit_hold` | 0.95 |
| `resolves_hold` | 0.90 |

Tuned set at these bars, EN / PT: Choice accuracy 1.00 / 0.98, link accuracy 24/24 both, duplicate bookings 0 / 0 (baseline 18 / 17), false loop creates 0 / 0, fact precision 1.00 / 1.00 and recall 1.00 / 0.83 (baseline 0.83 / 0.67), loop precision and recall 1.00 / 1.00 (baseline precision 0.37 / 0.39), `waiting_on` writes 0/10.

Config proposal if the verdict is `ENABLE` (`system_one.surfaces.commitment_intake`): `enabled: true`, `choice_hold: 0.65`, `family_hold: 0.65`, `biography_hold: 0.55`, `loop_hold: 0.6`, `explicit_hold: 0.95`, `resolves_hold: 0.9`. Nothing in the shipped config changes before the verdict. Wording is frozen at the commit that carries this note; any change after the held-out run needs a fresh held-out set (FR-020).
