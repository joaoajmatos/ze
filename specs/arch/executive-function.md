# Executive Function — Audit, Aperture Check, and Next Directions

> **Status:** Draft for discussion; open questions answered 2026-10-12 (see §8 Decisions)
> **Date:** 2026-10-12
> **Read as of 2026-10-12.** Since then, phase 177 added quiet hours, urgency tiers and the
> interruption governor, and phase 181 replaced `CapabilityGate` modes with irreversible-write
> confirmation. Decision D3 (link commitments, do not merge them) is recorded as
> `commitments-linked-not-merged.md`.
> **Author:** Cairn (Spec Architect, floor "Executive Function Research")
> **Scope:** `core/cognition/ze-worldstate`, `core/arbitration/ze-priority`, `core/contracts/ze-proactive`,
> `core/automation/ze-automation`, `core/cognition/ze-correlation`, and the executive-adjacent parts of
> `ze-memory`, `ze-core`, `ze-calendar`, `ze-personal`, `ze-web`.
> **Constrained by:** [`ze-doctrine.md`](ze-doctrine.md), [`aperture-decision.md`](aperture-decision.md),
> [`attention-arbitration.md`](attention-arbitration.md), [`contribution-seam.md`](contribution-seam.md),
> [`system-one-models.md`](system-one-models.md), [`pre-v1-hard-cuts.md`](pre-v1-hard-cuts.md).
> **Not a phase.** This is a research and direction note. It changes no code and no other spec.
> It proposes options; the user picks.

---

## 1. Summary

1. **The executive layer is built broadly and works narrowly.** Most pieces the July doctrine asked for now
   exist: open loops, drift, a ranked `PriorityView`, a shared push budget, user overrides, turn
   surfacing, a conductor, and a System One loop gate. Read as a pipeline, the path from "the user said
   something" to "Ze reminds them at the right moment" is broken in at least four places (F1–F3, F9).
2. **Three defects are verified, not suspected.** (a) The absence-drift sweep can never select a loop
   (F1). (b) A suspected loop has no reachable way to be confirmed, so every implied loop expires
   unseen after 14 days (F2). (c) `GoalStore.list_stuck` crashes on any goal that is awaiting a gate and has
   unfired future gates, which silently removes goals from the priority ranking and stops stuck-goal
   alerts (F3). Each was reproduced against the real code, not a mock.
3. **Two judgments overlap and disagree.** The speech-act judge and the loop gate both read every user
   message. "Remind me at 5pm to call Ana" becomes a timed reminder *and* an active declared loop (F4).
4. **Interruption is governed for two sources and ungoverned for about fifteen.** The shared budget
   only covers loop and hypothesis pushes. It has never fired in the dev database (F5). There are no
   quiet hours, no urgency tiers, and no learning from how the user reacts (F5, F8).
5. **The aperture question is answered in structure, not yet in behavior.** The code chose Option A
   (flat open loops, goals kept separate, intervention discipline borrowed from the correlation engine).
   What is still open is not "loops or life-graph". It is what a *commitment* is, how Ze decides to
   interrupt, and what surface the user actually sees (§5).
6. **Recommendation (updated with the user's decisions).** Repair first (Option 1), add corroboration
   promotion for suspected loops, then one commitment intake (Option 2) with link rows, then waiting-for
   tracking (Option 5, Gmail first). Start dogfooding as soon as loops are reachable. Then a Today surface
   with deadline and inferred-stakes scoring (Option 4), and last an interruption governor calibrated on
   real use (Option 3). Phase numbers start at 170 (§7). Do not add new executive features before
   Option 1: each would sit on top of the inert paths below.
7. **Evidence limit, stated up front.** The dev database holds no loops and no hypotheses, and
   Phase 168 turned the loop gate on today. There is no production usage to read. Behavior claims below come from
   code, a scratch Postgres run, and live System One calls. Nothing here measures whether the executive
   layer helps the user.

---

## 2. Method and evidence labels

| Label | Meaning |
|---|---|
| **[code]** | Read in the working tree at `0b9845b1`. Graphify (`affected`) was used for blast radius, then the files were read; graphify does not follow `ze_sdk` re-exports, so those were grepped. |
| **[dev-db]** | Read-only SQL against `ze-postgres-1` (session forced read-only; nothing written, nothing migrated). Planner row estimates (`n_live_tup`) were stale, so all counts below come from `count(*)`. |
| **[scratch]** | The real `PostgresLoopStore` against a throwaway Postgres container (`postgres:16-alpine`, deleted afterwards). The dev database was not used for writes. |
| **[live]** | Live System One calls (`typesafe/jev-1.13` via OpenRouter, shipped bars). Small: 24 calls. |

Reproduction notes are in Appendix A.

**What the dev database is.** It is a single-developer sandbox: 293 messages between 2026-06-11 and
2026-10-12, 313 facts, 4 goals, 13 action records, 12 reminders, 11 push-log rows, 4 notifications,
**0 open loops, 0 hypotheses, 0 priority overrides, 0 collisions**. Some rows are seed data. It is
not evidence about a deployed instance. If a deployed instance exists, its counts would settle
several questions below (D1).

---

## 3. What executive function is in the code today

The decomposition follows the usual executive-function literature, mapped onto what Ze ships.

Legend: **Works** = reached in normal use and verified. **Inert** = built and wired, but a defect keeps it
from acting. **Partial** = works for part of the job. **Absent** = nothing in the code.

| # | Function | Packages that do it | State | One-line verdict |
|---|---|---|---|---|
| 1 | Maintain concerns (intake, upkeep, closing) | `ze-worldstate` (loops, `LoopInflow`, loop gate), `ze-automation` (goals), `ze-calendar` (reminders), `ze-memory` (`task_state`) | **Partial** | Intake works; confirmation and upkeep do not. Five representations of "a thing I owe" with no shared identity. |
| 2 | Prioritise and allocate attention | `ze-priority` (`PriorityView`, overrides, merge), `TurnSurfacing` | **Partial** | A ranking exists and has consumers, but it ranks incommensurable scores and drops sources silently on error. |
| 3 | Decide when to interrupt or initiate | `AttentionArbitrationJob`, `ze-proactive` budget, push bar in `ze-correlation`, plus ~15 independent jobs | **Partial** | One governed path, never exercised. Everything else is cron plus a cooldown. |
| 4 | Plan and sequence | `ze-automation` (goal planner/executor/gates, workflow planner/scheduler), conductor (151–157) | **Works** | The strongest part. Gates, replan, promote-to-goal are real. |
| 5 | Monitor follow-through, notice failure | drift sweep, `StuckGoalJob`, workflow-failure alerts, accountability, action ledger | **Inert** (drift, stuck goals), **Works** (workflow failure) | The two checks that matter most for "you are not doing what you said" do not fire. |
| 6 | Inhibit (do not act, do not say) | `CapabilityGate`, spend budget, constraint veto (144), recitation gate (145), Retry write-block, dismissal fingerprint, push-bar novelty | **Works** | Strong on *actions*. Weak on *interruptions* (no quiet hours, no availability). |
| 7 | Switch tasks and keep context | resume recap (112), compaction, concurrent thread identity (159), conductor stall/replan (156) | **Works** | Good. One flaw: the recap lists every ranked item without a cap. |
| 8 | Learn from outcomes | action ledger → goal learning (137) → procedures (138–139), `feedback_records` (165) | **Partial** | Goal path closes the loop. Interruptions and replies feed nothing. |

### 3.1 Per-function notes

**1. Maintain concerns.**
- *Intake.* `LoopInflow` runs one System One request (three Nouls) on conversation, email, calendar and
  ingestion text, then pure code decides in `loop_judge.decide()`. Haiku only writes the title. [code]
  Held-out calibration was clean for EN and PT (Phase 168).
- *Lifecycle.* `suspected → active → drifting → closed | dropped`. `suspected` loops need a human confirm
  to become `active`. Only conversation text with an explicit first-person obligation is created
  `active` directly (`create_declared`, confidence 0.9). [code]
- *Upkeep.* Active loops never lose confidence over time. Only an evidence-linked fact contradiction
  decays them, and gate-created loops carry no evidence (F9). Nothing expires an `active` loop. [code]
- *Duplicate representations.* A commitment can be a loop, a goal, a reminder, a workflow, or a
  `memory_task_state` row. `OpenLoop.goal_id` exists and is never written. [code]

**2. Prioritise.** `PriorityView.rank()` reads active/drifting loops, idle or gate-blocked goals, recent
hypotheses and (when injected) stale relationships. Each source maps to a 0–1 value by its own formula:
loops use *confidence* plus a drift bonus; hypotheses use confidence × relevance; goals and
relationships use idle days. [code] The user override (Phase 127) is the only importance input, and it
decays in 48 hours unless pinned. There is no deadline, stakes, or time-to-due term (F6).

**3. Interrupt.** Two push paths are ranked and share a budget of 3 a day: loops (via `LoopSurfacer`)
and hypotheses (via `CorrelationPushCandidateSource`), arbitrated by `AttentionArbitrationJob` on a
4-hour cron. [code] Every other proactive job decides on its own (F5).

**4. Plan.** Goals have milestones, verification gates, adaptive replanning (cap 1), idle detection and
a 15-minute advance sweep. Workflows have branching, retry and `on_failure` policy. The conductor
(companion) sequences specialists in-chat and can promote the instance to a workflow or goal. [code]
This area has no new findings.

**5. Monitor.** Three kinds of "you are off track" signal exist: loop drift, stuck goals, workflow
failure. Only workflow failure fires (F1, F3). The action ledger records what Ze did (sends, reminders,
workspace runs, goal traces), but its only reader is the goal-learning path. Nothing reads a sent email
and asks "did anyone reply?" (F12).

**6. Inhibit.** Capability modes, confirmation, spend ceilings, constraint veto, recitation gate and
Retry's write block all govern what Ze *does*. What Ze *says unprompted* has novelty and relevance bars
for loops and hypotheses only. There is no quiet-hours or do-not-disturb setting anywhere in the code. [code]

**7. Switch.** Resume recap, compaction, per-thread cancel and conductor stall are in place. A recap
injects the whole ranked list into the system prompt on session resume; there is no limit. [code]

**8. Learn.** Goal learnings require action-record evidence and independent contexts before promotion.
Procedures are governed. Reply thumbs write `feedback_records`, with no reader in v1 by design. For
*interruptions* there is nothing: notification `read_at`, loop confirm/drop, and the hypothesis `feedback`
field are all unread (F8).

### 3.2 Where components have no consumer, or duplicate a judgment

| Component | Problem | Evidence |
|---|---|---|
| `LoopReviewList` widget | Never mounted on any page since Phase 109. | [code] only its own folder and tests reference it |
| `POST /api/v0/loops/{id}/confirm` | No caller except that widget. | [code] |
| `LoopsAgent` | Lists, closes, drops. Cannot confirm. | [code] `agents/tools.py` |
| `OpenLoop.goal_id` | Column and field, never written. | [code] |
| `ze_memory.surfacing.SurfacingGate` (`apply_feedback`) | Imported only by its test. The live push path uses static thresholds. | [code] |
| `worldstate.push.thresholds` and `inline_cooldown_hours` in `config.yaml` | Read by nothing. The arbitration job calls `eligible_candidates()` with defaults. | [code] |
| `correlation.push.enabled` / `dry_run` | Honored by `CorrelationPushConsumer.run_once` only. `CorrelationPushCandidateSource` ignores both, so a hypothesis can be pushed with `enabled: false`. | [code] |
| `ze_priority.LearningContextAdapter` | No caller. | [code] |
| `SpeechAct.LOOP / GOAL / REMINDER` | Judged on every turn; only `FACT` is consumed post-turn. | [code] `extractor.py`, `speech_act_judge.py` |
| Speech-act judge vs loop gate | Two System One batches per turn on overlapping questions, no shared result. | [live] §F4 |

---

## 4. Findings register

Severity reflects effect on the executive layer doing its job, not code quality.

### F1 — The absence-drift sweep cannot select any loop — *Critical* — [scratch]

`PostgresLoopStore.list_drift_candidates` requires `state = 'active' AND drift_deadline IS NOT NULL AND
updated_at <= confirmed_at`. Both creation paths write `updated_at` *after* `confirmed_at`:
`_create_declared_loop` calls `set_drift_deadline` (which sets `updated_at = now()`), and
`review.confirm_loop` does the same after the transition. On the scratch database both paths gave
`updated_at − confirmed_at` of 1.4 ms and 7.8 ms, the SQL predicate was false, and
`list_drift_candidates()` returned `[]` with the deadline moved a day into the past.

Consequences: no loop ever drifts by absence. The contradiction path is the only other way to drift, and
it needs an evidence link that gate-created loops do not have (F9). So `LoopSurfacer.inline_candidates`
(drifting only), the loop half of `AttentionArbitrationJob`, and the whole "your loop went quiet"
behavior of Phase 110 never run. This is the same class of defect Phase 168 found in the 109 gate: unit
tests mock the store, and the SQL predicate was never run against a real row.

*Status:* **Fixed in Phase 170.** Drift is now deadline-based (`state = 'active' AND drift_deadline <=
now()`), and `PostgresLoopStore.record_corroboration` moves the deadline forward on new evidence, so one
early touch no longer exempts a loop forever. No `last_activity_at` column (Phase 170 research R1).

*Fix size:* S. Replace the predicate with an explicit `last_activity_at` or compare against a
dedicated "touched by evidence" timestamp, and add a Postgres-backed test.

### F2 — Suspected loops can never be confirmed in practice — *Critical* — [code]

`suspected → active` needs `review.confirm_loop`. Its only callers are the REST route and the
`LoopReviewList` widget. The widget is not mounted anywhere. `LoopsAgent` has no confirm tool.
`StaleSuspicionJob` drops every `suspected` loop after 14 days. `PriorityView` ranks only `active` and
`drifting` loops.

So every implied loop (email, calendar, ingestion, and conversation text that is not an explicit
first-person obligation) is created, never shown, and dropped. Only `create_declared` loops reach the
ranking. The Phase 168 gate calibration measured intake quality; nothing measures whether intake
reaches the user.

*Fix size:* S–M. The design choice is real (decided, D2): a mounted widget is the cheap fix; a
chat-native "keep track of this?" at session resume respects agency better.

### F3 — `list_stuck` crashes on multi-gate goals — *High* — [dev-db], [code]

The gate half of `list_stuck` joins every gate with status `pending` or `awaiting_approval` for a goal in
`awaiting_gate`. Gates that have not fired yet have `fired_at IS NULL`, and the next line calls
`fired_at.tzinfo`. A goal with one open gate and any later pending gate raises `AttributeError`.

On the dev database, "AI Engineering Weekly Report" has one `awaiting_approval` gate (idle 108 days) and
six pending gates. Calling `list_stuck(0, 0)` and `list_stuck(7, 14)` both raise. Effects:

- `StuckGoalJob` never alerts for such a goal. `last_stuck_alert_at` is `NULL` after 108 idle days. (The
  dev server may also have been down on Tuesdays at 09:00; the crash is the cause I can prove.)
- `PriorityView.rank()` reports `sources_failed = {'goal'}` and carries on without goals. `/priority`,
  recaps, inline mentions and "what's open" all lose every goal. The per-source degradation (FR-009)
  hides this behind a warning log line.
- Even without a NULL, the query returns one row per open gate, so a goal could appear twice.
- `ze-automation` has no test named for `list_stuck` against SQL.

*Status:* **Fixed in Phase 170.** `list_stuck` selects one row per goal from the earliest open gate that
has fired, skips gates with `fired_at IS NULL`, and carries a Postgres-backed regression test.

*Fix size:* S. One row per goal (the earliest fired gate), skip unfired gates, add a Postgres-backed test.

### F4 — Speech-act and loop gate double-book and disagree — *High* — [live] — **Fixed by Phase 173 (2026-10-16)**

> Phase 173 replaced the two conversation requests with one commitment intake. A turn that created a reminder or goal now creates no loop and links to it. The held-out verdict (EN and PT, 147 blind rows) shows zero duplicate bookings where the old pipeline made 5 and 3. The table below is the 2026-10-12 evidence.

24 live calls, shipped bars (`loop_hold` 0.75, `explicit_hold` 0.85, `resolves_hold` 0.8):

| Utterance | Speech-act | Loop gate (concern / explicit) → decision |
|---|---|---|
| "Remind me at 5pm today to call Ana." | reminder 1.00 | 0.87 / 0.96 → **create_declared** |
| "Lembra-me amanhã às 9 de ligar ao dentista." | reminder 1.00 | 0.82 / 0.97 → **create_declared** |
| "I need to renew my passport before the March trip." | goal 0.99 | 0.95 / 0.98 → create_declared |
| "Preciso de responder ao email do João sobre o orçamento." | goal 0.63 | 0.96 / 0.97 → create_declared |
| "I want to learn Portuguese up to B1 in three months." | goal 1.00 | 0.64 / 0.06 → hold |
| "I want to ship the side project MVP in six weeks." | goal 1.00 | 0.80 / 0.11 → create_suspected |
| "I haven't decided whether to take the job offer yet." | loop 0.82 | 0.95 / 0.03 → create_suspected |
| "My landlord said he'd get back to me about the deposit." | loop 0.53 | 0.52 / 0.02 → hold |
| "I finally sent the signed lease back to the agency." | drop 0.66 | resolves 0.96 → resolve |

Reading: a timed reminder becomes a reminder row *and* an active loop at confidence 0.9. The loop
never closes unless the user says so, ranks at 0.9 indefinitely (F6), and would later "drift" with the
rationale "no corroborating evidence" for something that already fired. The calibration set itself
labels "Remind me that I have to send the lease back" as a loop, so this is designed behavior, not drift.
Speech-act says *goal* where the gate says *declared loop* for the same sentence; in neither case is the
other's answer used. The user's own waiting ("landlord will get back to me") is held: the gate only
models obligations the user owes, not things the user awaits.

*Fix size:* M. See Option 2 (done, Phase 173).

### F5 — Interruption governance covers two sources; ~15 are free — *High* — [code], [dev-db]

Budgeted and ranked: loop pushes and hypothesis pushes (max 3 a day, 4-hour cron). Not budgeted: morning
brief, stuck goals, goal suggestion, goal narrative, weekly accountability, cost anomaly, weekly insights,
contact review, finance recurring, messenger inbound, calendar reminders, user reminders, dream review
(opt-in), workflow failure, workspace completion, confirmation timeout. All of those call the notifier
directly. `urgency` is `"normal"` almost everywhere. There are no quiet hours, no calendar-aware
availability, and no urgency tiers. `ProactiveScheduler` uses an in-memory job store with default
misfire handling, so a cron job whose minute passes while the server is down is skipped without a retry.

`push_log` in the dev database has no `attention_push` row: the shared budget has never been exercised.
`SourceKind` for the budget includes `"goal"`, but the job only ranks loops and hypotheses.

*Not necessarily wrong:* a reminder the user asked for should not compete with a discretionary nudge.
The gap is that there is no *policy* saying which is which (decided, D4).

### F6 — Priority conflates certainty with importance — *Medium* — [code]

- A declared loop scores its confidence, 0.9, and never decays, so it outranks nearly every goal
  and hypothesis until closed. A drifting loop adds up to +0.8.
- Hypotheses (claim kind: suspicion) can outrank commitments.
- Goal urgency is idle days only; `time_horizon` is unused. Loop `implied_window_days` becomes a drift
  deadline but never an urgency term.
- Reminders, calendar events and workflow runs are not sources, so the only items with a real
  deadline never compete.

### F7 — The morning briefing ignores the ranking — *Medium* — [code]

`MorningBriefing` reads `PriorityView` only to pick relationship nudges. Its content is unreviewed facts,
scheduled workflow names, recent failures, nudges, a dream summary and news. It does not list today's
calendar, due reminders, or the top open items. The briefing is also the highest-reach existing surface
for executive content.

### F8 — No learning from how the user reacts to interruptions — *Medium* — [code]

`notifications.read_at`, loop confirm/drop, hypothesis `feedback`, and reply thumbs go unread. The adaptive
threshold code (`SurfacingGate.apply_feedback`) is dead. All push bars are static.

### F9 — Gate-created loops carry no evidence — *Medium* — [code]

`LoopInflow._commit_for` calls `propose_loop_candidates(..., evidence_refs=[])` for every inflow. Result:
(a) the contradiction cascade (`list_by_evidence`) can never reach these loops; (b) the push grounding check
passes vacuously (`passes_grounding` returns true when there are no labels); (c) `compute_evidence_fingerprint([])`
is the same hash for every loop, so once the user drops a loop, any later loop that matches it by
entity or title is suppressed forever, even on new evidence; (d) nothing can mark a loop as "corroborated",
because linking evidence is also what refreshes `updated_at`.

*Status:* **Fixed in Phase 170.** Gate-created loops link evidence (conversation and email turn episodes, ingestion references; calendar has none), the declared path dedups and calls `record_corroboration`, and the push grounding gate checks the loop title.

### F10 — "What's open?" is an English-only regex — *Low* — [code]

`TurnSurfacing.is_global_open_query` matches "what's open / outstanding / on my plate". The user and the
whole System One calibration are EN + PT. "O que tenho em aberto?" gets no ranked answer.

### F11 — Cron-only executive checks have no catch-up — *Low/Medium* — [code]

Stuck goals run weekly (Tuesday 09:00), drift daily (05:00), arbitration every 4 hours. If the host is a
laptop, a missed run is lost. Whether the real host is always on is a deployment fact I cannot see.

### F12 — The action ledger has no follow-through consumer — *Observation* — [code]

Sends, reminders, calendar writes and workspace runs are recorded as `ActionRecord`s. The only reader is
goal learning. Nothing opens an "awaiting reply" concern after Ze sends an email or makes a request, and
nothing in `MessagingSignalSource` closes one.

### F13 — The priority snapshot 500s on a relationship item — *High* — [code]

`PrioritySnapshotItem.source_kind` and the override schemas declare `Literal["loop", "goal",
"hypothesis"]`, but `PriorityView` also ranks `relationship` nudges once the person store is wired (it is,
in `container.py`). `GET /api/v0/priority/snapshot` fails response validation whenever a stale-relationship
nudge exists. The same response also hid which sources `PriorityView` could not read.

*Status:* **Fixed in Phase 170.** The snapshot returns `{items, sources_failed}`, the source-kind Literal
adds `relationship`, and the web page names any source it could not read.

*Fix size:* S.

---

## 5. Is the aperture question answered?

**In structure, yes. In behavior, not yet.**

What the code chose, versus the July brief:

| Aperture question | What the code chose | Evidence |
|---|---|---|
| First-class unit | Flat open loops. Goals stay a separate heavyweight store (FR-014). `goal_id` unused. | [code] |
| Surfacing discipline | Option B's discipline for loops and hypotheses only: confidence, relevance, novelty, NLI grounding, shared budget, hedged wording, claim-then-notify. Inline mentions are relevance-gated by entity overlap, not by a calibrated bar. | [code] |
| "Projection of the world-state, not a parallel structure" | Mostly met: loops reuse `memory_relationships`; `PriorityView` is a query. Reminders, workflows and calendar events are outside it. | [code] |
| Life-graph | Reached only by accretion, as the brief predicted. Nothing yet queries the graph for "pressure points". | [code] |

So Option A was built, with B's interruption *discipline* partially present. What remains genuinely open:

1. **What is a commitment?** Loop, goal, reminder, workflow and task-state each hold part of it
   (D3). F4 is the first symptom of not having an answer.
2. **What does Ze do with time?** Priority has no deadline term and interruption has no availability term. That
   is the part of Option B the brief called "genuinely unsolved", and it is untouched.
3. **What does the user see?** There is a Priority page, inline chips, a recap and a push. There is no
   daily "what needs me" surface (F7).
4. **Where does importance come from?** Today: user pins and a drift bonus. Confidence source remains the
   doctrine's open calibration question.
5. **How does Ze know it helped?** Nothing records whether a mention was acted on (F8).

The aperture decision did not turn out wrong. It turned out *unproven*, because the pieces that would
prove it are inert (F1–F3).

---

## 6. Options

Sizes use the repo's convention: S (one small phase), M (one phase), L (two to three phases).
"Doctrine fit" covers licensing (executive may produce priorities and open-loop state, never facts),
honesty (hedged wording, honest provenance, no verdicts from suspicions), and agency (the user can see,
correct and refuse).

### Option 1 — Make the existing loop real (repair and wire)

- **User notices:** things they said they would do appear in "what's open"; a quiet loop is flagged;
  a stuck goal produces an alert; `/priority` shows goals again.
- **Builds on:** everything in §3; no new concepts.
- **Scope:** F1, F2, F3, F9, F10, and the config and dead-code findings in §3.2. Add a Postgres-backed
  integration test harness (scratch container, as in Appendix A) so SQL predicates are tested against rows. Make
  `PriorityView` report a failed source in the API response, not only a log line. Delete the dead
  components rather than wire them (pre-v1 hard cuts).
- **Size:** S + M (two phases): *1a repair* (F1, F3, F9, tests), *1b confirmation path* (F2, F10; D2: mount the review list and add a chat-native prompt, §8).
- **Plus (D2):** a separate *corroboration* phase follows 1b: an independent second source raises a
  suspected loop's confidence and can promote it (§8, D2).
- **Risks:** low. The main risk is scope creep into redesign; keep priority scoring (F6) out.
- **Doctrine fit:** licensing unchanged. Honesty improves (no phantom "no evidence" rationale). Agency:
  confirmation becomes reachable.

### Option 2 — One commitment intake — **Done (Phase 173, enabled 2026-10-16)**

- **User notices:** saying "remind me at 5pm to call Ana" creates one thing, not two. "I want to learn
  Portuguese" is routed to a goal suggestion, not left unrouted. "My landlord will get back to me" is held
  as a waiting-on item.
- **Builds on:** Phases 142, 163, 168; the System One client; `OpenLoop.goal_id`.
- **Scope:** one batched System One judgment per user message whose Choice covers
  `{reminder, loop, goal, waiting_on, fact, none}`; pure code routes and links. The loop gate stops asking
  what speech-act already answered. Link rows (`loop ↔ reminder ↔ goal`) instead of a store merge (decided, D3): one request creates one thing, and related items point at each other. Delete or
  consume the unused speech-act labels. New held-out sets (EN + PT), reusing the 168 calibration rules.
- **Size:** M–L (two phases: intake + linking; then `waiting_on` direction if Option 5 is not taken).
- **Risks:** re-calibration cost and drift between two surfaces during the change; System One cost per
  turn (one batch replaces two, so likely neutral). A merge of stores is a larger, separate decision.
- **Doctrine fit:** executive licence only (open-loop state). Provenance stays honest: user-stated
  obligation vs inferred. Agency: unchanged.

### Option 3 — Interruption governor

- **User notices:** fewer, better-timed nudges; nothing at night; hard-timed things (reminders, calendar prep)
  always arrive; a "this was useful / not now" signal that changes what comes next.
- **Builds on:** `AttentionArbitrationJob`, `ze-proactive` budget, System One O6 (queued interrupt Score),
  notification `read_at`, `feedback_records`.
- **Decided (D4):** user-requested timed alerts are exempt from the discretionary budget; add quiet hours and urgency tiers. The user's actual hours are asked when this phase is specced.
- **Scope:** (a) classify every outbound push into a tier (user-requested and timed; accountability;
  discretionary) and apply the budget only to discretionary; (b) quiet hours and availability from
  calendar and recent activity; (c) outcome capture on pushes; (d) calibrated O6 Score and threshold
  adaptation using real outcomes; (e) catch-up for missed cron runs (F11).
- **Size:** L (three phases: governor and tiers; outcome capture; calibrated Score).
- **Risks:** highest of the five. Calibrating without real usage data would repeat the pattern of
  tuning gates that never fire. A bad bar is a spam or silence failure, and the user feels both.
- **Doctrine fit:** this is the doctrine's "governed initiative". Needs a clear rule that a Score never
  licenses a stronger claim kind (system-one-models anti-pattern list).

### Option 4 — A Today surface (the command centre)

- **User notices:** one place, in the web app and in the morning briefing, that says what needs them today:
  due reminders, calendar commitments, top open loops, stuck goals, with a reason for each rank and one-tap
  done / snooze / drop / pin.
- **Builds on:** `PriorityView`, Phase 127 overrides, `TurnSurfacing`, reminders and calendar stores.
- **Scope:** split "importance", "urgency" and "confidence" in scoring; add time-to-due from explicit
  dates; add an **inferred stakes** term (decided, D5): a System One Score calibrated on a held-out set,
  shown in the ranking explanation and trace, always outranked by pins and Phase 127 overrides, and
  labeled as an inference, never a fact; add reminders, calendar events and workflow runs as `PriorityView` sources; rewrite the briefing
  to read the ranking; add a Today page. Cap the recap.
- **Size:** L (scoring model; sources; surface).
- **Risks:** it can turn into "a smarter to-do app", the con the aperture brief named. The ranking has
  never been judged on real data. Needs Option 1 first so there is something truthful to show.
- **Doctrine fit:** Priority is a licensed executive claim. Every row must carry provenance and a hedge
  where it rests on an inference. Agency: strongest of the five, because the user can act on each row.

### Option 5 — Waiting-for and follow-through

- **User notices:** after Ze sends an email or the user says "I asked Ana for the figures", Ze tracks it, closes it
  when a reply arrives, and surfaces it after a quiet period.
- **Builds on:** action records (135–136), `MessagingSignalSource`, thread map (85), loop drift.
- **Scope:** a `waiting_on` loop kind, opened from a send or a spoken request; closed by an inbound
  reply on the thread; drift measured from the last outbound. First cross-domain consumer of the ledger.
- **Decided (D6):** yes, Gmail first, after Option 2.
- **Size:** M–L.
- **Risks:** thread matching quality; Gmail only; depends on F1 being fixed, since drift is the whole point.
- **Doctrine fit:** action records are evidence, never facts. Honest wording ("no reply seen since...").

### Comparison

| | Visible to user | Depends on | Size | Risk | Needs real usage data |
|---|---|---|---|---|---|
| 1 Repair | Medium (things start working) | none | S + M | Low | No |
| 2 One intake | Medium | 1a | M–L | Medium | Held-out sets only |
| 3 Governor | High, if right | 1, usage | L | **High** | **Yes** |
| 4 Today | **High** | 1, ideally 2 | L | Medium | Helpful |
| 5 Waiting-for | Medium–High | 1a, ideally 2 | M–L | Medium | No |

---

## 7. Recommended order (updated 2026-10-12)

Phase numbers start at 170 and are provisional until each is specced. 169 is the loop-track tool, specced on
its own floor; it changes `store.py` transitions (including `drifting → active` on an explicit ask), so it
overlaps 170 (see the handoff message and §9).

| Phase | Content | Option | Size | Depends on |
|---|---|---|---|---|
| **170** | **Executive repair:** F1 drift predicate, F3 `list_stuck`, F9 evidence on gate-created loops, report failed `PriorityView` sources, delete dead code and unread config, honor `correlation.push.enabled/dry_run`, Postgres-backed test harness | 1a | S–M | 169 merge order |
| **171** | **Confirmation path:** mount `LoopReviewList`; chat-native "keep track of these?" at session resume, max 3; language-neutral "what's open" trigger (F10); cap the recap | 1b | M | 170 |
| **172** | **Corroboration promotion:** independent source raises a suspected loop's confidence and can auto-promote above a calibrated bar; System One same-concern judgment where entity/embedding match is not enough; provenance records corroborating sources; held-out calibration. Implemented ([spec](../phases/172-corroboration-promotion/spec.md)) | new (D2) | M | 170 (evidence), 171 |
| **173** | **One commitment intake:** one judgment per message across reminder, loop, goal, waiting-on, fact; link rows; loop gate stops double-booking. Implemented ([spec](../phases/173-commitment-intake/spec.md)) | 2 | M–L | 170 |
| **174** | **Waiting-for (Gmail):** `waiting_on` loops from sends and spoken requests, closed by a thread reply | 5 | M–L | 170, 173 |
| *dogfood* | Starts when 171 lands. At least two weeks, overlapping 172–174. Weekly check in §8 D7. Produces labeled data | – | – | 171 |
| **175** | **Scoring model:** split importance, urgency, confidence; time-to-due from dates; inferred-stakes System One Score with held-out calibration; reminders, calendar and workflows as sources | 4 | M–L | dogfood data |
| **176** | **Today surface:** web page plus briefing rewrite; done / snooze / drop / pin actions that also capture outcomes | 4 | M | 175 |
| **177** | **Interruption governor, part 1:** tiers, quiet hours, urgency, budget on discretionary only, cron catch-up (needs no calibration; may move earlier) | 3 | M | none hard. Implemented (spec `phases/177-interruption-governor`) |
| **178–179** | **Governor, part 2:** push outcome capture; calibrated interrupt Score (O6) and threshold adaptation | 3 | L | dogfood data, 176 |

Why this order: each step makes the next one measurable. Repair makes the pipeline produce something;
the confirmation path and corroboration let implied loops reach the user; intake stops duplicates before
more loops accumulate; dogfood supplies the labeled data that the stakes Score and the governor cannot be
calibrated without (the dev database has none, and Ze has never been deployed, D1).

Not recommended: a loop/goal store merge now (D3), a new life-graph projection, or more intake sources.

---

## 8. Decisions (user, 2026-10-12)

The seven questions from the first draft were answered. Recommendations were accepted except where noted.

| # | Decision |
|---|---|
| **D1** | No deployed instance exists; Ze has never been deployed. Evidence comes from dogfooding only. The roughly two-week dogfood step stays in the plan. |
| **D2** | **Both** confirmation paths: mount the review list, and add a chat-native "keep track of these?" at session resume, at most 3 items. **Addition from the user:** when an independent source mentions a suspected loop, that should influence something, and can promote it if it passes a confidence bar. Design: independent corroboration raises the suspected loop's confidence and can auto-promote it to `active` above a calibrated bar. A System One same-concern judgment (Noul or Choice) is used where entity or embedding matching is not enough. Calibrate on a held-out set as in Phases 163–168. Provenance must record the corroborating sources. Doctrine fit: the loop stays an inference (suspicion) until corroborated or confirmed; promotion is a priority/open-loop-state claim by the executive function, never a fact; independence must be defined in code (different source type or different thread/document), not by the model. |
| **D3** | Link rows now: one request creates one thing, and related items point at each other. Revisit a store merge after dogfood. |
| **D4** | Exempt user-requested timed alerts from the discretionary budget; add quiet hours and urgency tiers. The user's hours: set in Settings (Settings › Notifications; ships off). |
| **D5** | **Overrides the recommendation:** importance comes from dates and pins **plus inferred stakes**. The stakes inference is a System One Score, calibrated on a held-out set, shown in the trace and the ranking explanation so the user can see why, and always outranked by the user's pins and Phase 127 overrides. Doctrine fit: an inference (never a fact), hedged in its wording, derived from cited text, with the Score never licensing a stronger claim kind (system-one-models anti-patterns). |
| **D6** | Yes to waiting-for tracking, Gmail first, after Option 2. |
| **D7** | Accepted weekly success check: duplicates created = 0; loops confirmed or closed per week; pushes acted on versus dismissed; any alert the user would have wanted but did not get. |

Open for later phases (not blocking 170–174): the user's quiet hours (settled in 177: set in Settings); the
definition of "independent source" for D2 (settled in the 172 spec); the stakes Score's levels and
what text it reads (settled in the 175 spec).

---

## 9. What this note does not decide

- Phase numbers, spec-kit directories, or task breakdowns. That starts after the user picks an option.
- Any change to the doctrine's licensing table, the claim vocabulary, or the contribution seam.
- Whether the Today surface replaces or sits beside the Priority page.
- Contribution *arbitration* (seam step 8). Phase 126 has logged no collisions in the dev database (0 rows), so the evidence gate for step 8 is not met.

Phase 170 (repair) can be specced now. Because Phase 169 changes `store.py` transitions, spec 170 must state the merge order with 169 and re-read the 169 diff before touching `PostgresLoopStore`.

---

## Appendix A — Reproduction

**F1 (scratch).** Start `postgres:16-alpine` on a spare port. Create `goals`, `memory_relationships`, and `open_loops`
(zw001 + zw002 columns). With `PostgresLoopStore`: (1) create an `active` loop with `confirmed_at = now()`
then `set_drift_deadline(...)`; (2) create a `suspected` loop and call `review.confirm_loop`;
(3) `UPDATE open_loops SET drift_deadline = now() - interval '1 day'`; (4) read `updated_at - confirmed_at`
and call `list_drift_candidates()`. Observed deltas 7.8 ms and 1.4 ms; result `[]`.

**F3 (dev-db, read-only).** Connect with `server_settings={'default_transaction_read_only': 'on'}`; call
`PostgresGoalStore.list_stuck(idle_days=0, alert_cooldown_days=0)` and `(7, 14)`. Both raise
`AttributeError: 'NoneType' object has no attribute 'tzinfo'` at `goals/postgres.py:1017`.
`PriorityView.rank()` on the same pool returns `sources_failed={'goal'}`.

**F4 (live).** `OpenRouterSystemOneClient` with `typesafe/jev-1.13`. For each utterance: one request with the
`speech_act` Choice from `speech_act_judge.SPEECH_ACT_QUESTIONS`, one with `loop_judge.questions_for("conversation")`
decided by `loop_judge.decide` at the shipped bars. 24 requests in total.

## Appendix B — Dev database snapshot (2026-10-12, read-only)

| Table | Rows | Note |
|---|---|---|
| `open_loops` | 0 | No loop has ever been created here; the 109 gate was inert until 168 |
| `correlation_hypothesis` | 0 | |
| `priority_overrides` | 0 | |
| `contribution_collisions` | 0 | |
| `goals` | 4 | One `awaiting_gate` for 108 days, `last_stuck_alert_at` NULL |
| `push_log` | 11 | `morning_brief` ×3 (May–June), `workflow_failure` ×8; **no `attention_push`** |
| `notifications` | 4 | All `workflow_failure` |
| `action_records` | 13 | goal milestones, workflow runs, 9 reminder creates |
| `messages` | 293 | 64 with a trace; 7 have a `judgments` key, only 2 hold rows (speech-act); none holds a loop-gate row |
