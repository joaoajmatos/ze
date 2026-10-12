# Feature Specification: Loop Extraction Gate (System One)

**Feature Branch**: `168-loop-extraction-gate`

**Created**: 2026-10-12

**Status**: Implemented

**Input**: User description: "O4 from the System One roadmap: replace the Haiku relevance gate that decides whether a text implies an open loop with typed System One Nouls. Haiku only writes the title (and optional window) after a positive gate. Off by default with null bars, a live calibration with a Haiku baseline side by side, and a held-out set that is never tuned on."

**Governed by**: [`specs/arch/system-one-models.md`](../../arch/system-one-models.md) O4, [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md), [`specs/arch/claim-topology.md`](../../arch/claim-topology.md). Phases [109](../109-open-loop-substrate/spec.md), [110](../110-open-loop-drift-surfacing/spec.md), [162](../162-system-one-client/spec.md), [163](../163-speech-act-system-one/spec.md), [166](../166-skill-suggestion-system-one/spec.md).

**Depends on**: Phase 162 Implemented (client, DI, trace judgments). Phase 109 Implemented (extraction gate, matching, `OpenLoop`). Phase 110 Implemented (`implied_window_days` into the drift deadline). Phase 167 (routing criteria, floor `164 Research Routing`) is not on `main` and is not a dependency; its held-out rule is reused.

**Does not change**: loop matching (`matching.py`, E5 0.75 plus entity overlap), the decay, drift, surfacing and push paths, inline loop mentions (a non-fit in the ADR), the contribution seam and `loop_to_contribution`, the `user_declared` path, loop REST and `ze-web`, the `OpenLoop` type and the `open_loops` table (no migration), the 163 speech-act surface, or the `memory_hooks` extension point for plugins.

---

## Overview

Phase 109 decides whether a piece of text implies an open loop with one Haiku JSON call that returns five fields: `is_loop`, `title`, `explicit_declaration`, `resolves_existing` and `implied_window_days`. It runs on every conversation turn (including "thanks"), every inbound email, every calendar reminder and every ingestion. Most of that traffic is negative. Haiku gives no calibrated probability, so the "be conservative" instruction in the prompt is the only dial.

This phase puts a System One judgment in front of Haiku. One batched request asks up to three independent Nouls: `is_open_concern`, `explicit_declaration` (conversation only) and `resolves_existing`. Pure code turns the answers into create-suspected, create-declared, resolve, hold or fallback. Haiku runs only after a positive gate, and only to write the title and an optional `implied_window_days`. Loop matching, dedup, dismissal fingerprints, confidence, provenance and the drift deadline arithmetic stay in code and do not change. With the surface off, uncalibrated, skipped or invalid, the 109/110 Haiku gate runs unchanged.

The conversation gate moves out of the generic `memory_hooks` fan-out into the `write_memory` node, beside `fact_extractor`, so its judgment rows land on `MessageTrace.judgments`. Email, calendar and ingestion have no message trace; they log their judgments only.

## Clarifications

### Session 2026-10-12

- Q: Which gate decisions move to System One? → A: Three batched Nouls: `is_open_concern`, `explicit_declaration` and `resolves_existing`. Haiku only writes the title after a positive gate. A single `is_open_concern` Noul alone would save nothing, because Haiku would still run on every text for the other fields.
- Q: What produces `implied_window_days`? → A: The same narrowed Haiku title writer returns it, only after a positive gate. A code date parser (EN+PT) is a **later phase**. The ADR's "windows in code" is wrong today (no parser exists); the ADR is updated to say the window stays model-written until that phase, while the arithmetic (`compute_drift_deadline`, 7-day default) stays in code.
- Q: Where does the conversation gate run, and what is traced? → A: In the `write_memory` node beside `fact_extractor`, awaited, so the judgment rows are appended to the message trace as 163 does. The loop commit (title writer, matching, store writes) stays fire-and-forget after the gate. Email, calendar and ingestion run the gate inside the extractor and log only. A trivial-turn skip is added for conversation. Each provenance builds its own capped state shape.
- Q: Does O4 consult the 163 `loop` speech-act? → A: No. The two judgments are independent. The calibration report logs, on conversation rows, where the 163 `loop` act and the loop gate agree or disagree, for a later phase to decide. No coupling, no shared request.
- Q: Ship state and acceptance rule? → A: Off, `null` bars, calibrated live in this phase with a Haiku baseline side by side. Enable only if the fresh held-out set (`eval/calibration/loop_gate_holdout.jsonl`, written before any run, never tuned on) shows, for EN and PT separately: zero false creates on negative rows, recall at least the Haiku baseline recall minus 0.05, and precision at least the Haiku baseline precision. At least 40 tuned rows and 20 held-out rows per language, spread across the four provenance text shapes.
- Q: What about the stale "skills is off" text? → A: Fixed as a [DOCS] task: `system_one.surfaces.skills` is enabled and calibrated (2026-10-12) in `config.yaml`; the ADR header and the AGENTS phase 166 row still say "off with null bars".

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Ordinary turns cost no Haiku call and create no loop (Priority: P1)

The user chats about the weather, thanks Ze, asks a how-to question. Today every one of those turns triggers a Haiku relevance call. With the surface calibrated, trivial turns skip the gate entirely and the rest get one cheap System One request whose `is_open_concern` Noul is below its bar. No Haiku call runs and no loop is created.

**Why this priority**: This is the cost and conservatism win, and the whole reason for the gate. FR-009 of 109 (conservative, relevance-gated) must still hold.

**Independent Test**: Fake System One client returns `is_open_concern` below the bar for "what's a good way to cook salmon". The fake LLM client records zero calls, `loop_store.create` is not called, and the trace carries one `is_open_concern` row with `consumed` true.

**Acceptance Scenarios**:

1. **Given** a trivial turn ("thanks!"), **When** the write path runs, **Then** no System One request and no Haiku call are made, and no judgment rows are added for loops.
2. **Given** a non-trivial negative turn and a calibrated surface, **When** the Noul is below `loop_hold`, **Then** no Haiku call is made and no loop is created.
3. **Given** the same turn on the eval path or a Retry, **When** the write path runs, **Then** no loop gate runs (unchanged from the 109 hook).

---

### User Story 2 - A real concern still becomes a loop, with a title (Priority: P1)

The user says "I keep meaning to book a dentist appointment". The `is_open_concern` Noul is above `loop_hold`; `explicit_declaration` is below its bar. Haiku writes a short title and an optional window. A `suspected` loop at confidence 0.3 is created exactly as in 109. If the user instead says "remind me I need to cancel the gym membership" and `explicit_declaration` is above its bar, the loop is created `active` at 0.9 with provenance `user_declared`, with the drift deadline from the written window or the 7-day default.

**Why this priority**: The gate must not cost recall or change what a created loop looks like.

**Independent Test**: Fake gate answers drive both branches; the created `OpenLoop` fields (state, confidence, provenance, claim kind, drift deadline) equal the 109 results for the same inputs.

**Acceptance Scenarios**:

1. **Given** a positive concern and a non-explicit text, **When** the commit runs, **Then** a `suspected` loop at 0.3 with the conversation provenance is created, evidence and entities are linked, and matching/dismissal rules (109 FR-010/011) apply unchanged.
2. **Given** a positive concern and an explicit declaration on a conversation turn, **When** the commit runs, **Then** an `active` loop at 0.9 with provenance `user_declared` is created and its drift deadline uses the written `implied_window_days` or the 7-day default.
3. **Given** a positive gate and an empty title from the writer (or a writer failure), **When** the commit runs, **Then** no loop is created and a warning is logged.
4. **Given** the written window is not a positive whole number, **When** the commit runs, **Then** it is ignored and the default applies.

---

### User Story 3 - "It's done" closes the matching loop (Priority: P1)

The user says "I paid the car insurance this morning". The `resolves_existing` Noul is above its bar. Haiku writes the title of the resolved commitment; code finds the matching open loop (entity overlap plus E5 title similarity, unchanged) and closes it. With no match, nothing happens.

**Why this priority**: 109 T030 behavior must survive the hard cut.

**Independent Test**: Fake answers set `resolves_existing` above its bar; an existing matching loop is `closed`; with no match no loop is created or closed.

**Acceptance Scenarios**:

1. **Given** `resolves_existing` at or above `resolves_hold`, **When** the commit runs and a matching active loop exists, **Then** it transitions to `closed` and nothing new is created.
2. **Given** both `resolves_existing` and `is_open_concern` at or above their bars, **When** the decision runs, **Then** the resolve path wins (109 contract: resolves implies not a loop), and the other Noul is recorded as not consumed.
3. **Given** `resolves_existing` above its bar and no matching loop, **When** the commit runs, **Then** no loop is created.

---

### User Story 4 - Off, unsure and failing paths keep the 109 Haiku gate (Priority: P1)

The surface ships off with null bars. When it is off, uncalibrated, the client skips, an answer is malformed, or any Noul needed for the decision is missing, the 109/110 Haiku gate runs exactly as today: one call, the same five fields, the same branches. A thrown exception from System One never fails the turn.

**Why this priority**: No regression on the default build, and no new failure mode when the vendor is down.

**Independent Test**: Run the existing `test_extraction.py` and `test_contribution.py` fixtures unchanged with the surface off, with a skipping client and with a malformed-answer client; results equal the 109 results. With the surface off no System One request is made.

**Acceptance Scenarios**:

1. **Given** `system_one.surfaces.loop_gate.enabled` is false, **When** a loop is proposed, **Then** no System One request is made and the Haiku gate runs.
2. **Given** enabled with a `null` bar, **When** a loop is proposed, **Then** no request is made, a warning is logged once per call, and the Haiku gate runs.
3. **Given** a skip (timeout, overload, missing key) or an invalid answer, **When** a loop is proposed, **Then** the Haiku gate runs and, on the conversation path, the trace carries skip rows with the reason.
4. **Given** a Noul answer of exactly its bar, **When** the decision runs, **Then** it counts as positive (at or above); exactly below counts as negative.

---

### User Story 5 - Email, calendar and ingestion use the same gate, logged only (Priority: P1)

An inbound email, a calendar reminder and an ingested document run the same gate with their own capped input shape. `explicit_declaration` is never asked for these (a third party's text cannot declare the user's commitment), so they can only create `suspected` loops or resolve one. Judgments are logged with structured fields; nothing is added to any message trace.

**Why this priority**: Without it, three of the four inflows would stay on Haiku forever and the calibration set (which spans four text shapes) would have no production counterpart.

**Independent Test**: Each of the three extractors is built with a fake client and surface config; a negative text makes no Haiku call, a positive text creates a `suspected` loop with the right provenance, and none of them ever creates an `active` loop.

**Acceptance Scenarios**:

1. **Given** an email body of 20,000 characters, **When** the gate runs, **Then** the System One state carries at most the email cap.
2. **Given** a calendar event, **When** the gate runs, **Then** the state is the title and summary, capped.
3. **Given** a gate for a non-conversation provenance, **When** the questions are built, **Then** `explicit_declaration` is absent from the request.
4. **Given** the Haiku fallback runs for a non-conversation provenance, **When** Haiku returns `explicit_declaration` true, **Then** the 109 behavior applies unchanged (see edge cases); the FR-005 narrowing covers the System One path only.

---

### User Story 6 - Calibration shows System One beats or matches Haiku before anything is enabled (Priority: P2)

A maintainer runs `make calibrate-loop-gate`. The script scores the tuned set and the held-out set with System One at a grid of bars and, side by side, with the production Haiku gate as a baseline. It prints per language and per provenance: precision, recall, false creates on negative rows, explicit and resolves accuracy, a reliability table, suggested bars, and a verdict on the held-out set against the acceptance rule. It also logs agreement with the 163 `loop` speech-act on conversation rows. An offline `--check-sets` mode validates the dataset shape with no network.

**Why this priority**: The 164 failure was shipping bars that a fresh set contradicted. There is also no Haiku baseline anywhere in the repo today, so "replace" has nothing to beat without this run.

**Independent Test**: `--check-sets` passes only if the tuned set has at least 40 rows per language, the held-out set at least 20 per language, every provenance appears in both, positives and negatives are present, and no tuned row text appears in the held-out set. Pytest never collects the live path.

**Acceptance Scenarios**:

1. **Given** the two labeled sets, **When** `--check-sets` runs, **Then** it exits non-zero on any shape violation and prints the counts.
2. **Given** a live run, **When** it finishes, **Then** it prints the verdict `ENABLE` or `KEEP OFF` with the failing clause, per language.
3. **Given** default CI, **When** the suite runs, **Then** no System One or OpenRouter request is made.

---

### Edge Cases

- Empty or whitespace text: no gate, as today (`_propose` returns early).
- Conversation image turn: the hook used `ctx.prompt`; the node keeps `ctx.prompt` (caption handling is unchanged).
- `provenance="user_declared"` bypasses the gate entirely, as today (extraction.py L202).
- Same turn with a 163 `loop` act and a negative loop gate (or the reverse): no coupling; the calibration log records the disagreement.
- Haiku fallback path on email, calendar and ingestion keeps the 109 behavior including honoring a model-returned `explicit_declaration`. The narrowing (no active loops from third-party text) applies to the System One path only; narrowing the fallback is out of scope and is a candidate follow-up. Pre-v1 note: this is a deliberate asymmetry, recorded so the next phase can hard-cut it.
- Very long conversation prompts: capped for the request only; the title writer sees the same capped text.
- Two loop-gate calls racing on the same text (two turns): matching dedup (109 FR-010) is unchanged; the gate adds no new race.
- System One returns a Noul for a question that was not asked (provider quirk): ignored; the decision uses only asked questions.
- Retry and eval threads: no loop gate (the node's `is_eval`/`is_retry` guard applies, as for the hook it replaces).
- The `memory_hooks` extension point stays for plugins; only the worldstate conversation hook is removed from the container list.
- Eval scenarios cannot exercise loop creation (eval threads skip write-side effects); coverage is the unit tests and the live calibration.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: When the surface is enabled and calibrated, one batched System One request with `max_attempts=1` MUST carry the independent Nouls `is_open_concern`, `resolves_existing` and, for conversation provenance only, `explicit_declaration`. Each question has its own bar. A bar from one question MUST NOT be applied to another.
- **FR-002**: Pure code MUST decide the outcome (decision table in `contracts/loop-gate-judgment.md`): **resolve** (`resolves_existing` at or above `resolves_hold`), **create-declared** (conversation only; `is_open_concern` at or above `loop_hold` and `explicit_declaration` at or above `explicit_hold`), **create-suspected** (`is_open_concern` at or above `loop_hold`), **hold** (all below), **fallback** (off, uncalibrated, skip, invalid or missing answer). Resolve wins over create. A hold creates nothing and runs no Haiku call.
- **FR-003**: After a resolve or create outcome, Haiku MUST be called once as a title writer only: the input is the capped text plus the outcome kind; the output is `title` and, for creates only, an optional integer `implied_window_days`. The writer MUST NOT decide whether a loop exists. An empty title or writer failure creates and closes nothing.
- **FR-004**: Loop state, confidence (0.3 suspected, 0.9 declared), provenance honored as passed, claim kind, drift deadline arithmetic (`compute_drift_deadline`, 7-day default), matching, dismissal fingerprints (109 FR-011), evidence and entity linking, collision detection and the contribution seam MUST be unchanged.
- **FR-005**: `explicit_declaration` MUST only be asked, and an `active`/`user_declared` loop MUST only be created from it, when the provenance is `conversation`. Email, calendar and ingestion on the System One path create `suspected` loops or resolve only.
- **FR-006**: The conversation gate MUST run inside the `write_memory` node beside `fact_extractor`, awaited, inside the existing `not is_eval and not is_retry` guard. Its judgment rows MUST be appended to the message trace without replacing the 163 rows. `consumed` is true only for the questions that decided the outcome. The commit (title writer, matching, store writes) MUST stay fire-and-forget. The generic `conversation_memory_hook` MUST be removed from the container's `memory_hooks` list (hard cut, no shim); the `memory_hooks` mechanism itself stays.
- **FR-007**: A conversation turn that `is_trivial_turn` accepts MUST skip the gate entirely, on both the System One and Haiku paths, with no request and no trace rows.
- **FR-008**: Each provenance MUST build its own named, capped state: conversation (user text), email (message text), calendar (title and summary), ingestion (fact lines). Caps are named constants chosen in the plan. No assistant reply, `AgentState`, session history or database row is sent.
- **FR-009**: Email, calendar and ingestion extractors MUST run the same gate and MUST log each judgment (provenance, question ids, answers, outcome, latency, skip reason) through `get_logger`. They MUST NOT write trace rows.
- **FR-010**: The extractor factories MUST receive the `SystemOneClient` and settings through constructor injection, at every construction site (`build_container`, `make_loop_extractor`, and any other caller found by `graphify affected make_loop_extractor_from_parts`). A missing client means fallback, never an error.
- **FR-011**: Surface config MUST live at `system_one.surfaces.loop_gate` with `enabled`, `loop_hold`, `explicit_hold` and `resolves_hold`. Bars are `null` until calibrated. Enabled with any null bar means fallback with a warning once per call. Invalid values (NaN, out of range, wrong type) become `null` with a warning. The shipped config is `enabled: true` with calibrated bars (FR-018); it was `enabled: false` with `null` bars until the held-out verdict.
- **FR-012**: Fail open: any exception from the client, a malformed or missing answer, or an unknown question id MUST yield the Haiku gate result and, on the conversation path, skip rows with the reason. The turn never fails because of this surface.
- **FR-013**: The Haiku gate (`_run_extraction_gate` and its prompt) MUST remain as the fallback with its five-field behavior unchanged. The title writer is a separate, narrower prompt.
- **FR-014**: Default tests MUST mock the client. Default `make test` MUST NOT call OpenRouter or System One.
- **FR-015**: `eval/calibration/loop_gate.jsonl` (tuned) MUST hold at least 40 labeled rows per language, and `eval/calibration/loop_gate_holdout.jsonl` (held-out, already written) at least 20 per language, each spanning all four provenance text shapes with positives, negatives, explicit and resolves rows. Row schema: `id`, `lang`, `provenance`, `text`, `gold_loop`, `gold_explicit`, `gold_resolves`, `kind`.
- **FR-016**: The held-out set MUST NOT be used to tune bars, question wording, criteria text or caps. It is read only for the final verdict. If a tuning change is made after a held-out run, a fresh held-out set MUST be written before the next verdict (167 rule). A test MUST fail if any held-out text appears in the tuned set.
- **FR-017**: `make calibrate-loop-gate` MUST run live over both sets with System One and, side by side, with the production Haiku gate. It MUST report per language and per provenance: precision, recall, false creates on negative rows, explicit and resolves accuracy, a reliability table per Noul, a bar grid and suggested bars. It MUST print a verdict computed on the held-out set (FR-018) and, on conversation rows, a log of agreement between the 163 `loop` speech-act and the loop gate. `--check-sets` MUST validate the dataset shape offline.
- **FR-018**: The surface MAY be enabled in the shipped config only when, at the chosen bars, the held-out set shows for EN and PT separately: zero false creates on negative rows (a create on a row with `gold_loop` false, including resolves rows, is a false create), recall at least the Haiku baseline recall minus 0.05, and precision at least the Haiku baseline precision. Otherwise the surface stays off and the tuning note records the failing clause.
- **FR-019**: The ADR MUST be updated: O4 row and implementation notes (three Nouls, Haiku title writer with window, windows-in-code moved to a later phase), sequencing, Appendix A and B rows, and the stale "skills off" text. AGENTS.md MUST get the 168 phase row and the corrected 166 row.

### Key Entities

- **LoopGateQuestions**: the three Noul definitions (instructions only; Nouls take no criteria) with fixed ids `is_open_concern`, `explicit_declaration`, `resolves_existing`.
- **LoopGateSurfaceConfig**: `enabled` plus the three bars; `calibrated` is true only when enabled and all bars are set.
- **LoopGateDecision**: kind (`resolve`, `create_declared`, `create_suspected`, `hold`, `fallback`), reason, consumed question ids.
- **LoopAdmission**: what the gate returns to the node: the decision, the System One result, the asked question ids, the consumed set, the skip reason and an optional async commit.
- **TitleWriterResult**: `title` and optional `implied_window_days`.
- **LoopGateRow** (calibration data): labeled text with provenance and gold fields.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On a calibrated surface, a trivial or negative conversation turn makes zero Haiku calls (asserted in tests with a call-counting fake).
- **SC-002**: With the surface off, null-barred, skipped or invalid, every 109/110 extraction test passes unmodified in outcome (same loops created, closed or ignored).
- **SC-003**: On the shipped held-out set (48 rows), the live verdict is reported per language; the surface is enabled only on `ENABLE` for both languages (FR-018).
- **SC-004**: The Haiku baseline precision, recall and false-create count for both sets are recorded in the tuning note, so the replacement has a measured bar to meet.
- **SC-005**: Every conversation turn that runs the gate leaves one judgment row per asked question on its message trace, with `consumed` true only for deciders.
- **SC-006**: No email, calendar or ingestion text ever produces an `active` loop through the System One path.
- **SC-007**: `make test`, `make test-worldstate`, `make test-core` pass and `make lint` is clean.

## Assumptions

- `typesafe/jev-1.13` stays pinned; the bars are re-calibrated when the pinned model changes (ADR rule).
- Conversation text for the gate is the user prompt only, as today; the assistant reply is not sent.
- Haiku remains the model for the title writer (`DEFAULT_EXTRACTION_MODEL`).
- Cap values and the exact Noul wording are plan-time choices, tuned only on the tuned set.
- The ADR's mention of `is_open_concern` as a single Noul is superseded by the three-Noul decision in the clarifications.
- Phase 167 is on another floor; this phase adds only the 168 row to shared indexes and does not touch 167 text.
