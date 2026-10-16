# Brief: fresh held-out set `commitment_intake_holdout2.jsonl`

**For**: the blind author (Brook). **From**: spec 173 (FR-003, FR-005, FR-019, FR-020, the decision contract, R4, R5, R7, R9). This brief is your only input.

## What you must not read

You write this set blind. Do not open, grep, diff or `git log -p` any of these:

- `eval/calibration/commitment_intake.jsonl` (tuned set) and `eval/calibration/commitment_intake_holdout.jsonl` (spent set)
- `eval/results/**`, `specs/phases/173-commitment-intake/research.md`, the Clarifications section of `spec.md`, and the 173 Handoffs note
- the diffs and messages of other people's commits on this branch (`git log`, `git show`); `git status` is fine
- the judge wording and criteria: `core/cognition/ze-worldstate/ze_worldstate/commitment_judge.py`, `core/cognition/ze-memory/ze_memory/fact_judge.py`, `eval/calibration/commitment_intake_baseline.py`

You may run `python3 eval/calibration/commitment_intake.py --check-sets`. When it reports that one of your texts equals a text in another set, it prints only your row id: rewrite that row and run the check again.

## What a row is

A row is one user message to a personal assistant, a short assistant reply, and the gold answer to the question "What kind of thing did the user just say?". Write natural messages a real person would type, in English (`en`) and European Portuguese (`pt`). Write the PT rows from scratch; do not translate the EN rows.

One JSON object per line, UTF-8:

| field | value |
|---|---|
| `id` | `h2-en-01` … / `h2-pt-01` …, unique |
| `lang` | `en` or `pt` |
| `text` | the user message |
| `assistant` | the assistant's reply in that turn, one or two sentences. When `turn_created` is `reminder` or `goal`, the reply says it created that item. Otherwise it creates nothing. |
| `gold_choice` | one label from the table below |
| `gold_explicit` | `true` only when the user explicitly asks the assistant to keep the matter in view or to track it. Allowed only with `loop`, `reminder` or `goal`. |
| `gold_resolves` | `true` when the user reports that an earlier concern is now done, settled or no longer relevant. Never with `loop`. |
| `turn_created` | `none`, `reminder` or `goal`: what the assistant's own tool really created in this turn. `reminder` only with gold `reminder` or `loop`; `goal` only with gold `goal` or `loop`. |
| `kind` | one of the kinds below |
| `gold_family` | fact rows only: `identity`, `preference`, `relationship`, `constraint` or `contact_detail` |
| `also_loop` | optional, default `false`. `true` only on a `mixed` row with gold `fact` whose text also carries a real open concern. |

## Labels (`gold_choice`)

| label | the user… |
|---|---|
| `reminder` | asks for a ping, alarm or nudge at a time ("remind me…", "ping me…", "lembra-me…"). |
| `loop` | carries an open concern of their own that is not resolved: something they owe, must decide or must get done. A first-person obligation with a deadline but no ask for a ping is a `loop`. |
| `goal` | wants to pursue an outcome over several weeks or more. A one-off task with a deadline is not a goal. |
| `waiting_on` | is waiting for another person or organization to act or reply. Nothing is owed by the user. |
| `fact` | states a durable fact about themselves in one of the five families. |
| `forget` | asks the assistant to forget a stored fact about them. Cancelling a ping, dropping a concern or abandoning a goal is not `forget`: label it as the kind of thing cancelled. |
| `ingest` | asks the assistant to read, save or file content (a link, a document, a page). |
| `clarify` | wants something kept or acted on, but the message does not say what (no time, no durable fact, no clear concern), so the assistant should ask one question. |
| `none` | anything else: chat, thanks, questions, right-now states, reports that something is done. |

Pick the one label that fits the whole message. If two acts compete, the row is `mixed`; give the label of the main act.

## Kinds (`kind`)

Every kind must appear in each language at least once.

- One kind per label for plain rows: `reminder`, `loop`, `loop_declared` (a `loop` with `gold_explicit` true), `goal`, `waiting_on`, `fact`, `forget`, `ingest`, `clarify`, `none`, and `resolves` (gold `none` with `gold_resolves` true).
- Hard negatives:
  - `reminder_loop_wording`: a reminder request whose wording also sounds like an ongoing concern; gold `reminder`, `turn_created` `reminder`.
  - `goal_loop_wording`: a goal whose wording also sounds like an ongoing concern; gold `goal`, `turn_created` `goal`.
  - `reminder_not_created`: the user asks for a reminder but the assistant only talks; gold `reminder`, `turn_created` `none`.
  - `goal_not_created`: the user states a goal but the assistant creates nothing; gold `goal`, `turn_created` `none`.
  - `loop_turn_reminder`, `loop_turn_goal`: a `loop` concern where the assistant did create a reminder or goal for it in the same turn.
  - `waiting_on` rows also serve as the hard negative for loops.
- `mixed`: two acts in one message. Include at least one with gold `fact` and `also_loop` true.

## Counts

Per language: at least 30 rows in total. At least 20 rows with gold `fact`. At least 20 rows where a loop is the right outcome (gold `loop`, `turn_created` `none`, `gold_resolves` false). Every label, every kind, every `turn_created` value and at least one `gold_resolves` row in each language. `--check-sets` enforces the minimums, which are 15 fact and 15 loop rows; the brief asks for 20 because, at 20 or more rows, the 0.05 recall margin tolerates one missed row.

## Before you hand it over

Read each row against the label table only, and fix a gold label when the table says otherwise. Make sure `--check-sets` exits 0, then commit only `eval/calibration/commitment_intake_holdout2.jsonl`. The commit message must not quote rows. After the commit, never edit the file.
