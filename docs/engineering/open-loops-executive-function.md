# Open loops: executive function for an assistant

Most of what you mean to follow up on is smaller than a goal. A promise in an email thread. A decision left pending. A project that is quietly stalling because one dependency never landed. Nobody types these into a task manager. They live in your head until they slip.

An assistant that only answers questions cannot help with this. It needs a model of what is still open. Ze calls the unit an open loop. This post covers the design, an audit that found the first version did not work, and the repairs.

## Two hands of one function

Ze has two ways to track a commitment.

**Goals** are heavy and declared. You hand Ze an objective, and it decomposes into milestones, runs specialists on a schedule, pauses at verification gates, and writes a retrospective. See [goals](../goals.md).

**Open loops** are light and ambient. A loop is a title, a state, a confidence, a deadline, and the evidence behind it. Ze extracts loops from conversation, email, calendar, and ingested documents. Most never become goals, and they should not.

Both are the first shipped slice of what [the doctrine](../../specs/arch/ze-doctrine.md) calls active concerns: the fourth face of Ze's world-state, the part that says what is open, promised, planned, or drifting. The doctrine named executive function as the main gap. Goals alone could not close it, because most real commitments never get declared.

## The shape of a loop

A loop moves through states:

- `suspected`: Ze thinks something is open. It is a guess.
- `active`: you confirmed it, or an independent source backed it up.
- `drifting`: a contradiction arrived, or a deadline passed without evidence.
- `closed` or `dropped`: the matter ended, or you said Ze was wrong.

![State machine showing an open loop moving from suspected to active, by an independent corroboration or a confirmation, then to drifting, where a contradiction or a missed deadline is the guard that triggers drift, and drifting loops finally resolving to closed or dropped](../diagrams/root/open-loops.svg)

Three rules from the doctrine apply here.

- **Honest provenance.** A loop records where it came from, and the origin of a model guess is never presented as something you said.
- **Confidence that decays.** A loop's confidence falls when its evidence falls away, and a missed deadline moves it toward `drifting`.
- **Posture follows kind.** A suspected loop reaches you as a question, never as a fact.

## The audit

By October 12, 2026, the pieces existed: loops, drift detection, a ranked priority view, a shared push budget, user overrides, a System One gate. Nobody had checked that the pieces worked together. A research note, [executive-function.md](../../specs/arch/executive-function.md), audited the whole path from "you said something" to "Ze reminds you at the right moment."

Its summary line is blunt: the executive layer was built broadly and worked narrowly. The audit reproduced three defects against real code, not mocks.

**F1: no loop could drift.** The query that finds loops that went quiet required `updated_at <= confirmed_at`. Both creation paths wrote `updated_at` after `confirmed_at`, by a few milliseconds. On a scratch Postgres the predicate was false for every loop. Nothing ever drifted by absence, so the "your loop went quiet" behavior never ran. The note's diagnosis: unit tests mocked the store, and nobody had run the SQL against a real row.

**F2: no suspected loop could be confirmed.** The only callers of the confirm function were a REST route and a widget that no page mounted. The loops agent had no confirm tool. A job dropped every suspected loop after 14 days. So every implied loop was created, never shown, and dropped. Only explicit declarations reached the ranking.

**F3: stuck-goal detection crashed.** The query for stuck goals called `.tzinfo` on a timestamp that is null for gates that have not fired. A goal with one open gate and any later gate raised an error. On the dev database, a goal idle for 108 days never produced an alert, and it dropped out of the priority ranking.

The audit also noted that the speech-act judge and the loop gate both read every message and could disagree (Phase 173 later merged them into one intake), that interruption governance covered two sources while about fifteen others were free, and that the dev database held no loops at all. It states its own limit up front: there was no real usage to measure, so nothing in it shows that the layer helps. That candor made the repair list credible.

## The repairs

The note recommended repairing first and adding features second. Phases 169 to 172 and the governor did that work.

| Phase | Repair |
|---|---|
| 168 | A System One gate asks yes/no questions (is this an open concern, does it resolve a loop, and for conversation, is it an explicit declaration). A small model writes only the title. |
| 169 | A `track_loop` tool lets you say "keep the Porto move on my radar" and get a loop in the same turn. |
| 170 | Drift fires on the deadline, and new evidence moves the deadline. Stuck-goal detection returns one row per goal. Loops carry evidence. A real-Postgres test harness was added (`make test-pg`) so SQL predicates run against real rows. |
| 171 | Suspected loops reach you. The `/loops` page lists them, one confirmation stamps a 0.9 confidence and a 7-day deadline, and at the start of a session Ze asks about up to three of them. |
| 172 | An independent source that matches a suspected loop can raise its confidence, and can promote it to active. This surface ships off (see [Calibrating a judgment model honestly](calibrating-a-judgment-model-honestly.md)). |
| 173 | One System One request per conversation turn replaces the speech-act judge and the loop gate. A reminder that Ze sets no longer also opens a loop. The loop links to the reminder or goal. A message that says you are waiting on someone writes nothing. |
| 177 | One governor sits on every proactive push. A shared daily budget covers discretionary nudges, quiet hours hold them, and reminders you set always fire. |

Phase 170 is the most instructive. The fix for F1 was not clever. It switched drift to a plain deadline comparison. The lasting change was the real-Postgres test target, because the defect class was "a SQL predicate that no test ever ran."

## Independence is code, not a model opinion

Phase 172 shows a design habit worth copying. When a new text matches a suspected loop, Ze must decide whether it counts as corroboration. A second mention from the same email thread should not count twice.

Code decides independence. A source counts only when its key (the inflow plus a thread, event, or document reference) is new to the loop, its evidence is not already linked, and its key does not sit on a matching dropped loop. If the source is not independent, Ze makes no model request.

Only for an independent match does System One answer one question: is this text about the same unfinished matter as the loop's title? Entity overlap is not enough, because a loop linked to "Ana" would match every Ana email. Code then applies fixed arithmetic. Corroboration raises confidence toward a cap of 0.6 and the loop stays suspected. A stronger score promotes it to active at 0.7 with a seven-day drift deadline.

Promotion changes loop state only. A promoted loop is still an inference about what is open. It is never stored as a fact, and you can drop it. A drop keeps the sources on record, so the same evidence cannot promote the topic again.

The model judges meaning. Code judges everything else.

## What is still open

The note ends with honest limits, and so does this post.

- The corroboration surface is off, and the judgment behind it needs a larger held-out set before another verdict.
- Intake runs from conversation, email, calendar, and ingestion. Waiting-for tracking and a Today view were recommended next and are not built.
- Nothing yet measures whether surfaced loops help you. Dogfooding is the next source of evidence.

## What to take from this

- Track the commitments people never write down, and keep them separate from goals.
- Give every inferred item a state, a source, and a decaying confidence.
- Audit the whole path, from input to the reminder, before adding features. Each part can pass its tests while the path stays broken.
- Run storage predicates against a real database. Mocks hide predicates that are always false.
- Let code define independence and arithmetic, and let a model answer only the question about meaning.

Related: [cognitive architecture](../cognitive-architecture.md), [System One](../system-one.md), and the specs for phases [109](../../specs/phases/109-open-loop-substrate/spec.md), [168](../../specs/phases/168-loop-extraction-gate/spec.md), [170](../../specs/phases/170-executive-repair/spec.md), [171](../../specs/phases/171-loop-confirmation/spec.md), and [172](../../specs/phases/172-corroboration-promotion/spec.md).
