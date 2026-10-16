# Feature Specification: One Commitment Intake

**Feature Branch**: `173-commitment-intake`

**Created**: 2026-10-15

**Status**: Draft

**Input**: User description: "Phase 173, Option 2 of `specs/arch/executive-function.md` (finding F4). The speech-act judge (163) and the loop gate (168) judge the same user message in two separate System One batches and double-book: 'remind me at 5pm to call Ana' makes a reminder and a declared loop at 0.9, and the two surfaces disagree on goal versus loop. Replace both conversation judgments with one batched request per user message whose commitment Choice covers reminder, loop, goal, waiting_on, fact and none, plus the loop-gate Nouls. Pure code merges the answers, routes, and links loop, reminder and goal rows by pointer. Calibrate on new EN and PT held-out sets under the 168 rules."

**Governed by**: [`specs/arch/executive-function.md`](../../arch/executive-function.md) (Option 2, F4, §8 D3 and D6), [`specs/arch/system-one-models.md`](../../arch/system-one-models.md), [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md). Phases [142](../142-speech-act-routing/spec.md), [163](../163-speech-act-system-one/spec.md), [168](../168-loop-extraction-gate/spec.md), 169 (loop track tool), 171 (loop confirmation), 172 (corroboration).

**Depends on**: Phases 163 and 168 Implemented. Phase 172 Implemented on this branch (`zw003` is the `zw` chain head; this phase adds `zw004`).

**Does not change**: the in-turn routing of the companion (142 stays prompt-driven), the loop gate on the email, calendar and ingestion inflows, the Haiku title writer and its 109 fallback, `LoopTracker` (169), loop confirmation (171), corroboration (172), the contribution seam and claim vocabulary, the fact value writer and the family and biography questions that admit facts (163), and `PriorityView`.

**Waiting-on is not handled here**: `waiting_on` is a label only. Tracking what the user awaits is Phase 174 (D6, Gmail first).

**Web**: `apps/ze-web` `entities/loop` and the loops widget, `packages/ze-client` (generated), per FSD.

**Shared with the concurrent floor `181 Irreversible Write Confirmation`** (Keystone, changes tool confirmation, `call_tool` and goal and calendar tool metadata): `core/engine/ze-core/ze_core/orchestration/nodes/memory.py` (both floors may touch it), `ToolCall` / `call_tool` (read only here, for the successful-tool-call check), `plugins/ze-calendar/ze_calendar/agents/reminders/tools.py` (`set_reminder`, read only here) and the goal tools in `ze-automation` (read only here). Phase 173 edits none of the tool modules. Whichever floor lands second rebases `nodes/memory.py`.

---

## Overview

Every user message now passes two independent judgments after the turn. The speech-act judge (163) asks which kind of act it is: fact, reminder, loop, goal and so on. The loop gate (168) asks three questions about open concerns. They never see each other's answer. Observed live on 24 requests (executive-function Appendix A):

- "Remind me at 5pm today to call Ana." The agent sets a reminder. Speech-act says reminder 1.00. The loop gate says concern 0.87 and explicit 0.96, so a declared loop is created at confidence 0.9 as well. One request, two things. The loop never closes by itself, ranks at 0.9, and later drifts with the rationale "no corroborating evidence" for something that already fired.
- "I want to ship the side project MVP in six weeks." Speech-act says goal 1.00. The loop gate creates a suspected loop. The two surfaces disagree.
- "My landlord said he'd get back to me about the deposit." The user is waiting on someone. The gate holds it, because it models only what the user owes.

This phase merges the two into one intake. After the turn, one System One request asks a **commitment Choice** over `{reminder, loop, goal, waiting_on, fact, none}` and, in the same request, the loop-gate Nouls that the Choice cannot answer (`resolves_existing`, and `explicit_declaration` when the Choice is `loop`). One pure function merges the answers into one outcome:

1. **The turn already created the thing.** If the turn's tool calls show a successful reminder or goal creation, the intake creates no loop. When a loop would have been created, or one already exists for the same matter, it links to the reminder or goal by pointer instead.
2. **The Choice says loop.** The loop gate runs its existing decision (declared, suspected, resolve, hold).
3. **The Choice says goal, reminder or waiting_on and the turn created nothing.** No loop. `goal`, `reminder` and `waiting_on` are recorded on the trace. `waiting_on` is held and waits for Phase 174.
4. **The Choice says fact.** The existing fact admission path runs, unchanged.

The labels that no longer have a consumer are deleted: `drop` is replaced by `none`. `reminder`, `loop`, `goal` fold into the commitment Choice. No shim is kept.

## Clarifications

### Session 2026-10-15

Answers marked **(user)** were accepted by the user through the Maestro on 2026-10-15.

- Q1: Where does the intake run? → A: **(user)** Post-turn in `write_memory` only. In-turn routing stays prompt-driven (142). The intake never creates a reminder or goal; it reads what the turn did and decides whether a loop is created and what links to what.
- Q2: How do the Choice and the loop Nouls combine? → A: **(user)** One batched request carries the commitment Choice and the loop-gate Nouls. One pure `decide()` merges them.
- Q3: What happens to the speech-act labels? → A: **(user)** Keep `fact`, `forget`, `ingest` and `clarify`. Fold `reminder`, `loop`, `goal` and `waiting_on` into the commitment Choice. Delete `drop` (`none` replaces it). Any label left without a consumer is hard-cut.
- Q4: Is `waiting_on` handled here? → A: **(user)** Label only, recorded on the trace. Handling is Phase 174.
- Q5: How do rows link? → A: **(user)** A nullable `reminder_id` on `open_loops` (migration `zw004`) beside the existing `goal_id`. A turn that creates a reminder or goal creates no separate loop. No store merge (D3).
- Q6: Calibration spend? → A: **(user)** Write and commit the EN and PT held-out set first, then ask the user for the live spend through the Maestro.
- Q7 (Spec Architect default, **user** accepted): Does this reverse a 168 decision? → A: Yes, deliberately. 168 said the loop gate does not consult the speech-act `loop` act. F4 is the evidence that this was wrong. 168 left the agreement log "for a later phase to decide"; this is that phase.
- C1: Enable bars for the held-out verdict? → A: **(user)** Exactly FR-022: zero duplicate bookings, zero false loop creates, fact precision at least the 163 baseline and recall at least baseline minus 0.05, loop precision at least the 168 baseline and recall at least baseline minus 0.05, Choice accuracy at least 0.9, per language.
- C2: Fallback labels? → A: **(user)** Hard-cut the Haiku fallback `speech_act` field to `{fact, forget, ingest, clarify, none}`. No fallback-only label set.
- C3: Web change? → A: **(user)** Yes. The `/loops` row shows a "Has reminder" chip when `reminder_id` is set and a "Linked goal" chip when `goal_id` is set. This adds a [WEB] lane: FSD `entities/loop`, client regenerated with `make codegen`, generated files never hand-edited.

### Session 2026-10-16 (review of main..90ff30dd)

- R1 (rollout): When does 173 land? → A: **(user)** Only after the held-out verdict says `ENABLE`. Order: the held-out set is extended (FR-019, at least 15 gold-fact and 15 gold-loop rows per language, written from this spec only, committed before any held-out run); the review findings are fixed; the calibration runner is finished; the tuned live run (approved) chooses bars; then the Maestro asks the user for the one held-out verdict run. On `KEEP OFF`, 173 stays on its floor until the wording is fixed and checked on a fresh held-out set (FR-020). The surface never lands off-and-uncalibrated.
- R2 (Spec Architect resolution of review finding 5): FR-016 required a test that fails when a label has no reader, but `forget`, `ingest` and `clarify` had no reader beyond "not fact". → A: They stay (C2 fixes the fallback set) as named non-fact classes. Their post-turn job is to keep a retract (146), an ingest request (147) or a clarifying question out of the fact path; the in-turn tools handle the act itself. FR-016 now names their readers: decision-table row 9 gives each its own hold reason on the trace, calibration scores each as its own label, and in the Haiku fallback `admit_speech_act` reads each and admits no fact. The tests pin exactly that.
- R3 (Spec Architect resolution of review finding 6): The held-out set had 5 fact and 8 loop rows per language, so one noisy row flipped the verdict. → A: FR-019 adds per-language minimums of gold-positive rows in the held-out set, enforced by `--check-sets`: at least 15 `fact` rows and at least 15 rows where a loop is the right outcome (`gold_choice` `loop`, `turn_created` `none`, `gold_resolves` false). The FR-022 thresholds (C1, user) are unchanged. With 20 or more positives the 0.05 recall margin equals one row; between 15 and 19 it tolerates no miss, so the set aims for 20.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A timed request makes one thing (Priority: P1)

The user says "Remind me at 5pm to call Ana". The agent sets the reminder. Today a declared loop at 0.9 is also created. After this phase, no separate loop is created: the intake sees that the turn created a reminder and stops.

**Why this priority**: This is F4 and the user-visible symptom. Duplicate booking is the first thing a user notices.

**Independent Test**: With a fake System One client answering Choice `reminder` and explicit 0.96, and a turn whose tool calls include a successful `set_reminder`, run `write_memory`. Assert zero loops created, one trace row for the Choice, and zero Haiku title calls.

**Acceptance Scenarios**:

1. **Given** a turn with a successful reminder tool call and Choice `reminder`, **When** the intake decides, **Then** no loop is created.
2. **Given** a turn with a successful goal-creation tool call and Choice `goal`, **When** the intake decides, **Then** no loop is created.
3. **Given** Choice `reminder` but no successful reminder call in the turn (the agent only talked), **When** the intake decides, **Then** no loop is created and the trace shows the Choice (the user asked for a ping and did not get one; creating a loop would hide that).
4. **Given** the same message in Portuguese ("Lembra-me amanhã às 9 de ligar ao dentista"), **When** the intake decides, **Then** the outcome is the same.

---

### User Story 2 - An existing loop and a new reminder point at each other (Priority: P1)

A suspected or active loop "Call Ana about the contract" exists. The user says "Remind me Friday at 10 to call Ana about the contract." The agent sets the reminder. The intake finds the matching loop and records the reminder's id on it. Later views can say "this loop has a reminder". The loop is not duplicated and not closed.

**Why this priority**: D3 asks for link rows, not a merge. Without the pointer, a reminder and a loop for the same matter are two unrelated rows.

**Independent Test**: A turn with a successful `set_reminder` returning reminder id R, and a matching loop L in the fake store. Assert `L.reminder_id == R` and no new loop. The same for a goal and `L.goal_id`.

**Acceptance Scenarios**:

1. **Given** a matching `suspected`, `active` or `drifting` loop and a successful reminder creation, **When** the intake runs, **Then** the loop's `reminder_id` is set once and not overwritten.
2. **Given** a matching loop that already has a `goal_id`, **When** a goal is created, **Then** the existing `goal_id` is not overwritten and the event is logged.
3. **Given** no matching loop, **When** a reminder is created, **Then** no loop is created and nothing is linked.
4. **Given** a terminal loop (`closed`, `dropped`), **When** it matches, **Then** it is never linked.

---

### User Story 3 - Goals are not double-booked as loops (Priority: P1)

The user says "I want to learn Portuguese up to B1 in three months". The Choice says `goal`. The agent proposes or creates the goal through its normal path. The loop gate used to create or hold a loop separately. After this phase, a `goal` Choice creates no loop, whether or not the turn created the goal. The Choice is recorded on the trace.

**Why this priority**: One answer per message. The two surfaces must stop disagreeing on goal versus loop.

**Independent Test**: Fake Choice `goal` at the shipped bar with high concern and explicit Nouls: no loop is created, in both a turn with and without a goal tool call.

**Acceptance Scenarios**:

1. **Given** Choice `goal` and a high loop concern Noul, **When** the intake decides, **Then** no loop is created.
2. **Given** Choice `goal` below the Choice bar, **When** the intake decides, **Then** the outcome is hold and no loop is created (a confident loop Choice is required to create one).

---

### User Story 4 - A lingering concern still becomes a loop (Priority: P1)

"I haven't decided whether to take the job offer yet" or "Preciso de renovar o passaporte antes da viagem". The Choice says `loop`. The Nouls give the explicit and resolves answers. The pure decision gives the same outcomes as the 168 table: declared loop, suspected loop, resolve, or hold. The loop behavior the user has today does not regress.

**Why this priority**: The merge must not weaken the loop path that works.

**Independent Test**: A table test over Choice `loop` and Noul scores reproduces every row of the 168 decision table.

**Acceptance Scenarios**:

1. **Given** Choice `loop` at or above the Choice bar and `resolves_existing` at or above its bar, **When** the intake decides, **Then** the outcome is resolve, as in 168.
2. **Given** Choice `loop`, concern at or above its bar and explicit at or above its bar, **Then** the outcome is create declared.
3. **Given** Choice `loop`, concern at or above its bar and explicit below its bar, **Then** the outcome is create suspected.
4. **Given** Choice `loop` with concern below its bar, **Then** the outcome is hold.
5. **Given** the user reports something done ("I finally sent the lease back") and the Choice is `none`, **When** `resolves_existing` is at or above its bar, **Then** the matching loop is resolved (resolve does not depend on the Choice being `loop`).

---

### User Story 5 - Waiting on someone is labelled and held (Priority: P2)

"My landlord said he'd get back to me about the deposit." The Choice says `waiting_on`. Nothing is created: no loop, no reminder. The Choice and its confidence are recorded on the trace so Phase 174 and the calibration report can measure how often it fires.

**Why this priority**: Labelling now gives Phase 174 a measured baseline without building its data model early.

**Independent Test**: Fake Choice `waiting_on` yields outcome hold with reason `waiting_on`, a trace row, and no store writes.

**Acceptance Scenarios**:

1. **Given** Choice `waiting_on` at any confidence, **When** the intake decides, **Then** nothing is created and the trace row carries the label.

---

### User Story 6 - Facts are admitted exactly as before (Priority: P1)

"I prefer aisle seats" and "my sister is called Ana" are `fact` Choices. The existing family Choice, biography Noul, value writer and persist rules run unchanged. The fact path must not regress in precision or recall. `forget`, `ingest` and `clarify` keep their current consumers.

**Why this priority**: 140 to 149 built the memory honesty chain on this path. The merge must not weaken it.

**Independent Test**: The speech-act gold fixtures (`speech_act_gold.py`) and the 163 gate table tests pass with the new Choice labels mapped one to one.

**Acceptance Scenarios**:

1. **Given** Choice `fact` at or above its bar, **When** the family Choice and biography Noul pass, **Then** the fact is persisted.
2. **Given** Choice `forget`, `ingest` or `clarify`, **Then** the downstream behavior is the same as in 163: no fact is persisted, and the outcome is hold with the label itself as the reason on the trace.

---

### User Story 7 - One request, honest and cheap (Priority: P1)

Per user message there is one System One request, where today there are two. The trace shows every question asked, which were consumed by the decision, and the merged outcome. Failures fall back as in 163 and 168: a skipped or invalid request creates no loop and persists no fact via System One; the existing fallbacks (the Haiku fact extractor and the 109 Haiku loop gate) behave as today. A failure never fails the turn.

**Why this priority**: Cost neutrality and fail-open are pinned System One rules.

**Independent Test**: A call-counting fake client records exactly one request for a non-trivial conversation turn; with the surface off it records zero and the old fallbacks run.

**Acceptance Scenarios**:

1. **Given** the surface is enabled and calibrated, **When** a non-trivial turn finishes, **Then** exactly one System One request is made and `max_attempts` is 1.
2. **Given** a trivial turn, **Then** no request is made.
3. **Given** the client skips, throws or returns an invalid answer, **Then** the turn completes, the fallbacks run, and the skip reason is on the trace.
4. **Given** a turn where `track_loop` succeeded, **Then** the loop-side outcome is suppressed as in 169 (`tracking_earned`).

---

### User Story 8 - The loops page shows links (Priority: P2)

On `/loops` a loop with a reminder shows a "Has reminder" chip, and a loop with a goal shows a "Linked goal" chip.

**Why this priority**: The link is only useful if the user can see it exists.

**Independent Test**: vitest renders a row with each pointer set, both set, and neither.

**Acceptance Scenarios**:

1. **Given** a loop item with `reminder_id`, **Then** the row shows "Has reminder"; **given** `goal_id`, **then** "Linked goal"; **given** neither, **then** no chip.

---

### User Story 9 - Calibration decides whether the intake turns on (Priority: P1)

A maintainer runs `make calibrate-commitment-intake` on a tuned set, picks bars, then runs once on a fresh held-out set and reads `ENABLE` or `KEEP OFF` per language. The held-out set is written and committed first, never tuned on. The report includes the old two-surface baseline side by side on the same rows.

**Why this priority**: The 164 lesson: bars are set only after a live run, and the verdict is read once.

**Independent Test**: `--check-sets` exits non-zero on shape violations offline. Pytest never collects the live path.

**Acceptance Scenarios**:

1. **Given** the two sets, **When** `--check-sets` runs, **Then** it checks row counts per language, every Choice label present, hard negatives present (reminder-with-loop wording, goal-with-loop wording, waiting-on), and no held-out text in the tuned set.
2. **Given** a live held-out run at frozen bars, **Then** it prints a verdict per language with the failing clause.
3. **Given** default CI, **Then** no OpenRouter or System One request is made.

---

### Edge Cases

- The user asks for a reminder and the reminder tool fails or is blocked by a confirmation (181): not a successful creation. The turn counts as "agent only talked" (Story 1, scenario 3). Whatever 181 defines as a successful, executed call is the only one that counts.
- A message mixes acts ("remind me at 5 to call Ana, and I want to learn Portuguese"). One Choice per message. The Choice with the highest confidence wins; a mixed message that the Choice judges below its bar is held. Multi-act handling is out of scope and recorded as a follow-up.
- The Choice is `loop` but the turn created a goal (the user phrasing was loop-like and the agent made a goal): the turn's tool calls win over the label. No separate loop, and the goal is linked if a loop matches.
- Retry and eval turns: no intake runs (existing guards in `write_memory`).
- A turn where `track_loop` succeeded: the loop side is suppressed (169); the fact side still runs.
- `reminder_id` references a reminder that is later cancelled or deleted: the pointer is kept as a historical link, reads tolerate a missing reminder, and cancelling a reminder does not close the loop (one rule: cancel the ping, keep the concern).
- Existing declared loops created before this phase from a timed request stay as they are; no backfill (pre-v1).
- The 163 `speech_act` and 168 `loop_gate` surface blocks in `config.yaml` are replaced by one `commitment_intake` block. Other inflows keep reading `loop_gate` bars until a later phase merges them; see Assumptions.

---

## Requirements *(mandatory)*

### Functional Requirements

**One request**

- **FR-001**: For a non-trivial conversation turn with the surface enabled and calibrated, exactly one System One request MUST be made, with `max_attempts=1`, replacing the current speech-act request and the current conversation loop-gate request.
- **FR-002**: The request MUST carry: one commitment Choice over `{reminder, loop, goal, waiting_on, fact, forget, ingest, clarify, none}`; the `family` Choice and `biography` Noul (163), used only when the commitment Choice is `fact`; the `resolves_existing` Noul; and the `is_open_concern` and `explicit_declaration` Nouls. The state MUST be the user message and the capped assistant reply, as in 163.
- **FR-003**: Choice criteria MUST be name-free and example-based per the 167 rules. `none` MUST replace `drop`. Cancelling a ping, dropping a concern or abandoning a goal MUST remain classified under the kind of thing cancelled, not as `forget` (146).

**Decision**

- **FR-004**: One pure function MUST merge the answers into one outcome from `{persist_fact, resolve_loop, create_loop_declared, create_loop_suspected, link, hold, skip, fallback}` with a reason, the consumed question ids, and, for `link`, the kind to link. It MUST never raise.
- **FR-005**: Loop creation MUST require the commitment Choice to be `loop` at or above `choice_hold` and the existing concern and explicit bars. A Choice of `reminder`, `goal`, `waiting_on`, `fact` or `none` MUST NOT create a loop.
- **FR-006**: A successful creation of a reminder or goal in the turn's tool calls MUST suppress loop creation for that turn whatever the Choice says, and MUST trigger linking when a matching live loop exists. "Successful" is read from the turn's recorded tool calls by pure code; the intake MUST NOT call a model to decide it.
- **FR-007**: `resolves_existing` at or above its bar MUST close the matching loop regardless of the Choice, as in 168.
- **FR-008**: `waiting_on` MUST create nothing and MUST be recorded on the trace with its confidence.
- **FR-009**: The `fact` path (family Choice, biography Noul, value writer, persist and hold rules) MUST behave as in 163 when the commitment Choice is `fact`.
- **FR-010**: Bars MUST compare at or above. Invalid or null bars make the surface uncalibrated, and the existing fallbacks run.

**Links**

- **FR-011**: A migration `zw004` in the ze-worldstate chain MUST add a nullable `reminder_id` to `open_loops` (a UUID without a foreign key, because reminders live in another package; reads tolerate a missing reminder). `goal_id` already exists.
- **FR-012**: When linking, the intake MUST find the matching live loop with the existing matching rule (`find_matching_loop`, entity overlap and E5 0.75) and set the pointer once. An existing pointer MUST NOT be overwritten. A terminal loop MUST NOT be linked.
- **FR-013**: The reminder or goal id MUST come from the turn's tool call result as recorded on the trace. Plugins are not changed to expose it. If the result does not carry an id, the intake MUST skip linking and log it.
- **FR-014**: `GET /api/v0/loops` and `GET /api/v0/loops/{id}` MUST expose `reminder_id` and `goal_id`. The generated client MUST be regenerated with `make codegen` and committed; generated files MUST NOT be hand-edited.
- **FR-014a**: The `/loops` row MUST show a "Has reminder" chip when `reminder_id` is set and a "Linked goal" chip when `goal_id` is set. The chips live in the loop entity and widget following FSD; they link nowhere in this phase. A vitest test MUST cover each chip and the absent case.

**Config and labels**

- **FR-015**: Surface config MUST live at `system_one.surfaces.commitment_intake` with `enabled`, `choice_hold`, `family_hold`, `biography_hold`, `loop_hold`, `explicit_hold`, `resolves_hold`. The `speech_act` surface block MUST be deleted. The `loop_gate` block MUST remain for the email, calendar and ingestion inflows. Bars ship `null` and the surface ships off until a held-out `ENABLE`.
- **FR-016**: `SpeechAct` values `reminder`, `loop`, `goal` and `drop` MUST be removed from `ze_memory.types` and every consumer; `SpeechAct` keeps exactly `{fact, forget, ingest, clarify, none}` (C2). The commitment Choice type MUST be exported through `ze_sdk.memory`. A label with no consumer after the change MUST be deleted, not kept. A consumer is one of: a decision-table row that gives the label its own outcome or its own named reason on `MessageTrace.judgments`, or, for the Haiku fallback, `admit_speech_act` reading the label with the fallback prompt offering it. `forget`, `ingest` and `clarify` are named non-fact classes (R2): row 9 holds each with reason `forget`, `ingest` or `clarify`, and the fallback admits no fact for them. Tests MUST fail when (a) a `CommitmentChoice` label, answered above every bar with nothing created and nothing resolved, has no outcome or reason of its own; (b) two labels share one hold reason; (c) the fallback prompt's label list and `SpeechAct` differ; (d) `admit_speech_act` maps a removed label (`reminder`, `loop`, `goal`, `drop`) to anything but `none`, or admits a fact for any label but `fact`.
- **FR-017**: The per-turn Haiku fallbacks (the fact extractor and the 109 Haiku loop gate) MUST behave as today when the intake is off, uncalibrated, skipped or invalid, except that the fact extractor's `speech_act` field and `admit_speech_act` MUST accept only `{fact, forget, ingest, clarify, none}`; any other value MUST be treated as `none`.
- **FR-018**: Judgments MUST be recorded on `MessageTrace.judgments` with the merged outcome, the consumed ids and the skip reason. The `waiting_on` and `link` outcomes MUST appear.

**Calibration**

- **FR-019**: `eval/calibration/commitment_intake.jsonl` (tuned) MUST hold at least 60 rows per language and `eval/calibration/commitment_intake_holdout.jsonl` (held-out) at least 30 per language, written and committed before any live run. Row schema: `id`, `lang`, `text`, `assistant`, `gold_choice`, `gold_explicit`, `gold_resolves`, `turn_created` (`none`, `reminder`, `goal`), `kind`. Each Choice label MUST appear in each language, and the sets MUST include hard negatives for each F4 table row. The held-out set MUST also hold, per language, at least 15 rows with `gold_choice` `fact` and at least 15 rows where a loop is the right outcome (`gold_choice` `loop`, `turn_created` `none`, `gold_resolves` false); it should aim for 20 of each (R3). `--check-sets` MUST enforce both minimums.
- **FR-020**: The held-out set MUST NOT be used to tune bars, question wording, criteria or caps. A change after a held-out run requires a fresh held-out set (167 rule). A test MUST fail if any held-out text appears in the tuned set.
- **FR-021**: `make calibrate-commitment-intake` MUST run live over the tuned set with System One and, on the same rows, replay the old two-surface pipeline as a baseline. It MUST report per language: Choice accuracy, per-label precision and recall, duplicate bookings (a loop created where the gold says the turn created a reminder or goal), false loop creates, fact precision and recall, a reliability table per question, a bar grid and suggested bars. `--set holdout --bars ...` MUST print `ENABLE` or `KEEP OFF` per language with the failing clause. `--check-sets` MUST validate shapes offline.
- **FR-022**: The surface MAY be enabled only when, at the chosen bars, the held-out set shows for EN and PT separately: zero duplicate bookings; zero false loop creates on negative rows; fact precision at least the 163 baseline and fact recall at least the 163 baseline minus 0.05; loop recall at least the 168 baseline minus 0.05 and loop precision at least the 168 baseline; Choice accuracy at least 0.9. Otherwise it stays off and the tuning note records the failing clause. Recall is measured over the FR-019 gold-positive rows; with 20 or more positives the 0.05 margin tolerates one missed row, with fewer it tolerates none. Phase 173 lands only after an `ENABLE` (R1).
- **FR-023**: Live calibration spends credits. The maintainer MUST obtain the user's OK before any live run, after the held-out set is committed.
- **FR-024**: Default tests MUST mock the client. `make test-py` MUST NOT call OpenRouter or System One.

**Docs**

- **FR-025**: The System One ADR, `docs/system-one.md`, the worldstate and memory docs and READMEs, `docs/configuration.md`, AGENTS.md (phase row, migration table, calibrate targets), `docs/testing.md` and the specs index MUST describe the intake, the removed labels, the link columns and the calibrate target. The F4 finding in `specs/arch/executive-function.md` MUST be marked fixed with the outcome.

### Key Entities

- **CommitmentChoice**: the label set `{reminder, loop, goal, waiting_on, fact, forget, ingest, clarify, none}` with the model's confidence.
- **IntakeOutcome**: the merged decision: kind, reason, consumed question ids, optional link kind.
- **CommitmentIntakeSurfaceConfig**: `enabled` plus the seven bars; calibrated only when enabled and every bar is set.
- **TurnCreation**: pure-code reading of the turn's tool calls: which of reminder and goal were successfully created, with their ids.
- **LoopLink**: `reminder_id` and `goal_id` on an `OpenLoop`.
- **IntakeRow** (calibration data): a labeled message with the turn's creation state.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the held-out set, 0 duplicate bookings per language: a timed or goal request that the agent turned into a reminder or goal produces no extra loop.
- **SC-002**: On the held-out set, 0 false loop creates on negative rows, and loop recall and precision stay within the FR-022 margins of the 168 baseline.
- **SC-003**: Fact precision and recall stay within the FR-022 margins of the 163 baseline.
- **SC-004**: A non-trivial conversation turn makes exactly one System One request (down from two), measured by a call-counting fake in tests.
- **SC-005**: Choice accuracy on the held-out set is at least 0.9 per language, and every `waiting_on` row is held with no store write.
- **SC-006**: With the surface off, every existing 163 and 168 test that targets the fallbacks passes unchanged, and zero System One requests are made.
- **SC-007**: `make test-memory`, `make test-worldstate`, `make test-core`, `make test`, `make test-pg`, `make test-web`, `make typecheck-web` and `make lint` pass.

---

## Assumptions

- `zw003` (172) is the chain head on this branch; `zw004` follows it. If another floor adds a `zw` revision first, re-base.
- The turn's tool calls and their results (including reminder and goal ids) are available to `write_memory` as recorded `ToolCall` objects, as `tracking_earned` already relies on. If goal creation returns no id, linking for goals is skipped and logged.
- The conversation inflow is the only one that uses the merged request. The email, calendar and ingestion gates keep the `loop_gate` surface and its three-Noul request unchanged, because they have no speech act and no tool-created counterpart in the same turn.
- The package that owns the merged questions and `decide()` is a plan decision (ze-memory and ze-worldstate are separate packages and the request is built once); it must respect the dependency graph and the plugin import rule.
- `typesafe/jev-1.13` stays pinned; bars are re-calibrated when the model changes.
- A mixed-act message gets one Choice. Multi-act decomposition is a follow-up.
- Live calibration spend is approved by the user separately, after the held-out set is committed.
