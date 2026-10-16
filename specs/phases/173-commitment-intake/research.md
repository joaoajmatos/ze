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

### Held-out verdict (T043, 2026-10-16): KEEP OFF

One live run on `commitment_intake_holdout.jsonl` (120 rows, 60 per language, `typesafe/jev-1.13`, seed 173) at the frozen bars above and the wording of the commit that froze them (`92dd67cc`). Raw results: `eval/results/commitment_intake_holdout_verdict.json` (gitignored). Nothing was tuned or re-scored afterwards; the diagnosis below reads the saved answers only.

| FR-022 clause | EN | PT |
|---|---|---|
| duplicate bookings = 0 | 0 pass (baseline 5) | 0 pass (baseline 5) |
| false loop creates = 0 | **1 FAIL** | **1 FAIL** |
| fact precision >= baseline | 1.00 vs 1.00 pass | 1.00 vs 1.00 pass |
| fact recall >= baseline - 0.05 | 1.00 vs 0.86 pass | 1.00 vs 0.86 pass |
| loop precision >= baseline | 0.93 vs 0.65 pass | 0.93 vs 0.64 pass |
| loop recall >= baseline - 0.05 | **0.875 vs 0.938 - 0.05 = 0.888 FAIL** | 0.875 vs 0.875 pass |
| Choice accuracy >= 0.9 | 0.94 pass | **0.88 FAIL** |

Verdict: **EN KEEP OFF** (false loop create, loop recall), **PT KEEP OFF** (false loop create, Choice accuracy), **OVERALL KEEP OFF**. The shipped config stays `enabled: false` with null bars. Link accuracy 10/10 both; `waiting_on` rows write nothing (0/6).

Diagnosis (saved answers only, no re-tuning):

- **False loop creates (both languages), `ho-en-11` and `ho-pt-11`** ("I need to finish the first draft of my thesis chapter by the end of March", gold `goal`, an F4 hard negative). EN: `goal`@0.56 is below `choice_hold` 0.65, so row 7a falls through to the loop rules (`is_open_concern` 0.86, `explicit` 0.98) and creates a declared loop. PT: `loop`@0.95 outright. Under the user's own Q1 definition ("obligation with a deadline and no ask is a loop; goal = multi-week outcome"), this text sits on the border, so the gold is arguable, but the clause counts it.
- **Loop recall (EN, and the two PT misses), `ho-en-52`, `ho-en-54`, `ho-pt-52`, `ho-pt-54`.** "My neighbour still hasn't answered about the fence", "The tap is still leaking and nobody has come to fix it" are `waiting_on` to the model (0.64 to 1.00), so they are held as designed. These four rows were written by ENG-B in the T005 extension with gold `loop`; they read as `waiting_on` under the contract's own definition, so the gold is probably wrong, not the model. The set is spent, so the labels cannot be fixed in place.
- **Choice accuracy (PT 0.88).** Two `clarify` rows read as `none` at 0.34 to 0.48 (`ho-pt-31`, `ho-pt-32`; EN `ho-en-31` the same), `ho-pt-37` (a resolves row) reads `fact`@0.40, and `ho-pt-11` and the PT `waiting_on`/`loop` rows above.
- **Not clause-failing but wrong writes:** `ho-en-30` and `ho-pt-30` ("Save this recipe page for later: <url>", gold `ingest`) score `resolves_existing` 0.93 and 0.91, above `resolves_hold` 0.90, so the intake resolves a loop on an ingest request. The old baseline had 0 false resolves; the intake has 1 per language. FR-022 does not list false resolves, but it is a real defect to fix.
- **`ho-en-40`, `ho-pt-40`** (the `also_loop` mixed rows) created suspected loops and were accepted by design.

What the evidence supports: the structure works (zero duplicate bookings against 5, fact side at or above baseline, link 10/10, `waiting_on` never written). It does not yet meet FR-022 because (1) the `goal` versus `loop` border for deadline tasks is still unresolved, (2) `resolves_existing` fires on save-for-later requests, (3) `clarify` is weak at low confidence, and (4) four of my own held-out gold labels are doubtful.

Per FR-020 any wording, criteria or bar change now needs a fresh held-out set.
