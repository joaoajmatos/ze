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

### Run 3 and frozen bars for the holdout2 verdict (T049, 2026-10-16, tuned set only)

Wording: Mortise's `108e02c9` (goal/loop deadline tie-break, `clarify` bare pointers, `resolves_existing` ignores save requests). Scoring: FR-022 with the `also_loop` field and the false-resolves clause (`4b8c5806`). Same model and seed 173. Raw results: `eval/results/commitment_intake_tuned_run3.json` (gitignored).

Distributions on the tuned set (what each bar sits between):

- `resolves_existing`: true resolves rows score 0.95 and up; every other row scores 0.27 or less.
- `is_open_concern`: gold loop rows score 0.74 and up; loop recall stays 1.00 for `loop_hold` 0.50 to 0.70 and falls from 0.75.
- `choice_hold`: identical results from 0.5 to 0.8 (loop recall 28/28, zero false creates, zero duplicates); loop recall drops at 0.9 (25/28) and 0.95 (21/28).
- `biography`: gold fact rows score 0.63 and up.
- `explicit_declaration`: gold explicit rows score 0.95 and up; two non-explicit loop rows score 0.94 and 0.95, so `explicit_hold` sits on the edge. It only decides declared versus suspected and is not an FR-022 clause.

Frozen bars (centre of each plateau; `resolves_hold` in the wide gap but biased high because a false resolve is the costlier error):

| bar | frozen value |
|---|---|
| `choice_hold` | 0.65 |
| `family_hold` | 0.65 |
| `biography_hold` | 0.55 |
| `loop_hold` | 0.60 |
| `explicit_hold` | 0.95 |
| `resolves_hold` | 0.80 |

Tuned set at these bars, EN / PT (baseline in brackets): Choice accuracy 1.00 / 1.00, link accuracy 24/24 both, duplicate bookings 0 / 0 (18 / 16), false loop creates 0 / 0 (5 / 5), false resolves 0 / 0 (0 / 0), fact precision 1.00 / 1.00, fact recall 1.00 / 0.83 (0.83 / 0.67), loop precision and recall 1.00 / 1.00 (precision 0.38 / 0.40), `waiting_on` writes 0/10. The one tuned miss is `ci-t-pt-049`, a fact row the model reads as `fact`@0.49.

Wording and bars are frozen at the commit that carries this note. holdout2 (`e3084f1f`) was written blind and has had no model run. One verdict follows; any later change needs a fresh held-out set (FR-020).

Config proposal if the verdict is `ENABLE`: `enabled: true`, `choice_hold: 0.65`, `family_hold: 0.65`, `biography_hold: 0.55`, `loop_hold: 0.6`, `explicit_hold: 0.95`, `resolves_hold: 0.8`.

### holdout2 verdict (T053, 2026-10-16): EN ENABLE, PT KEEP OFF, overall KEEP OFF

One live run on `commitment_intake_holdout2.jsonl` (184 rows, 92 per language, written blind, `typesafe/jev-1.13`, seed 173) at the bars and wording frozen in `7ae261d6`. Raw results: `eval/results/commitment_intake_holdout2_verdict.json` (gitignored). Nothing was re-scored or re-tuned afterwards; the diagnosis reads the saved answers only.

| FR-022 clause | EN | PT |
|---|---|---|
| duplicate bookings = 0 | 0 pass (baseline 7) | 0 pass (baseline 6) |
| false loop creates = 0 | 0 pass (baseline 5) | 0 pass (baseline 3) |
| fact precision >= baseline | 1.00 vs 1.00 pass | 1.00 vs 1.00 pass |
| fact recall >= baseline - 0.05 | 0.636 vs 0.500 pass | 0.609 vs 0.409 pass |
| loop precision >= baseline | 1.00 vs 0.64 pass | 1.00 vs 0.69 pass |
| loop recall >= baseline - 0.05 | 0.909 vs 0.955 - 0.05 = 0.905 pass | 0.909 vs 0.909 pass |
| false resolves <= baseline | 2 vs 2 pass | 2 vs 2 pass |
| Choice accuracy >= 0.9 | 0.928 pass | **0.892 FAIL** |

Verdict: **EN ENABLE**, **PT KEEP OFF** (one clause: Choice accuracy 0.892, 9 of 83 wrong on the rows where the turn created nothing; 8 wrong would have passed), **OVERALL KEEP OFF**. The shipped config stays `enabled: false` with null bars. Link accuracy 9/9 both.

Diagnosis (saved answers only). The 9 PT Choice errors:

- Three are `resolves` rows (`h2-pt-90`, `-91`, `-92`: "Aceitei a proposta de emprego, ficou resolvido", "Já paguei a multa", "Marquei a inspeção do carro para dia 14"). Their gold Choice is `none` and the Choice question has no "resolves" option; the model reads `fact` or `loop`, and the pipeline still resolves the loop correctly for two of them (the outcome is right, the Choice label is not what the metric scores). EN has the same three rows wrong.
- Two are `mixed` rows where a fact sits beside a question ("Sou vegetariano — que receitas rápidas me sugeres com grão-de-bico?"): the model reads `none` (the question wins), gold `fact`.
- Two are `loop_declared` rows read as `reminder` at 0.49 to 0.57 ("Não me deixes esquecer o processo do seguro", "Mantém-me a par das revisões da tese, é para entregar até dia 20"); the loop is still created via row 7a, so the outcome is right.
- One is `h2-pt-49` ("Vivo a dizer que vou cancelar a subscrição do ginásio...", gold `loop`) read as `fact`@0.48, held.
- Plus `h2-pt-86` (a third party's passport, gold `none`) read as `fact`@0.26, held.

Not clause-failing, but real:

- **SC-005 is violated once per language.** `h2-en-65` and `h2-pt-65` ("I sent my CV to the recruiter on Monday and I'm waiting for her reply", gold `waiting_on`) read as `waiting_on`@1.00 but score `resolves_existing` 0.86 and 0.88, above `resolves_hold` 0.80, so a loop is resolved. `waiting_on` rows write 1/5 per language. FR-022 does not list this and the first verdict did not show it.
- **False resolves** equal the baseline (2 per language): `h2-*-65` and `h2-*-85` ("last year I was worried about my taxes, but that's all sorted now", gold `none`, resolves 0.94 to 0.95).
- **Loop misses** (EN `h2-en-30`, `-31`; PT `h2-pt-30`, `-49`): "keep an eye on my visa extension", "don't let me lose track of the insurance claim" read as `loop` at 0.79 to 0.89 but `is_open_concern` falls under 0.60, so they are held as `not_open_concern`.
- Explicit-vs-implied accuracy is 0.59 in both languages for the intake and the baseline (declared versus suspected only; not an FR-022 clause).

Per FR-020 any change from here needs a fresh held-out set. The task rule is to stop here and ask the Maestro.
