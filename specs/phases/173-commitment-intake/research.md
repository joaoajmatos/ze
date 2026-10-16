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
