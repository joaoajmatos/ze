# Feature Specification: Corroboration Promotion

**Feature Branch**: `172-corroboration-promotion`

**Created**: 2026-10-12

**Status**: Implemented

**Input**: User description: "Phase 172 (user decision D2 in `specs/arch/executive-function.md`): when an independent source mentions a suspected open loop's concern, its confidence rises, and above a calibrated System One bar it auto-promotes to active. Independence is defined in code. A System One same-concern judgment is used where entity and embedding matching is not enough. Provenance records the corroborating sources. Calibration as in 163-168: tuned and held-out sets, a `make calibrate-*` target, fail open, single attempt, ships off until calibrated. Promotion is open-loop state, never a fact; the user can drop; dropped loops are not re-promoted by the same evidence."

**Governed by**: [`specs/arch/executive-function.md`](../../arch/executive-function.md) (§8 D2, F2, F9), [`specs/arch/system-one-models.md`](../../arch/system-one-models.md) (pinned rules 2, 5, 6, 7, 8, 10), [`specs/arch/claim-topology.md`](../../arch/claim-topology.md), [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md). Phases [109](../109-open-loop-substrate/spec.md), [162](../162-system-one-client/spec.md), [168](../168-loop-extraction-gate/spec.md), 169 (loop track tool), 170 (executive repair), 171 (loop confirmation).

**Depends on**: Phase 168 Implemented. Phase 170 on `main` (evidence refs on gate-created loops, `_existence_checkers`, declared-path dedup, `record_corroboration` on active loops). Phase 171 on `main` for the web label only (the `/loops` page row). Implementation starts after 170 and 171 land; its first task re-reads both diffs.

**Does not change**: the 168 loop gate (questions, bars, `decide()`), the Haiku title writer, `find_matching_loop` and its E5 0.75 threshold, 170's `record_corroboration` on `active` loops and drift arithmetic, 169's `track_loop`, 171's confirmation paths (confirm still sets what 171 sets), the drop fingerprint rule (170 FR-014), `PriorityView` scoring, push and arbitration, the contribution seam and claim vocabulary, the `OpenLoop` claim kind and provenance of any loop.

---

## Overview

A `suspected` loop is Ze's guess that something is open. Today it changes only if the user confirms it; otherwise it expires after 14 days. When a later text matches it (entity overlap, or E5 title similarity of at least 0.75), the extraction code links the new evidence and does nothing else. Two signals are lost: the second mention came from a different place, and it may really be about the same matter.

This phase makes that second, independent mention count. When a new text that the 168 gate admits as a concern matches a `suspected` loop:

1. **Code** decides whether the new text is an independent source. Each text carries a source key (its inflow plus a thread, event or document reference). A source is independent only if its key and evidence are new to the loop and were never recorded on a dropped loop that matches it.
2. **System One** answers one Noul, `same_concern`: is this text about the same unfinished matter as the loop's title? Entity overlap alone is not enough. A loop linked to "Ana" matches every Ana email today.
3. **Code** acts on the answer. At or above `corroborate_hold`, the source is recorded, the evidence is linked and the loop's confidence rises by fixed arithmetic; the loop stays `suspected`. At or above the stricter `promote_hold`, the loop is also promoted to `active` at confidence 0.7, below a user-stated loop (0.9).

Every source of a loop (its origin and each counted corroboration, with the Noul score) is recorded in a new table, so the loop detail can say exactly why Ze is tracking it. A promoted loop stays an inference about what is open. It is never a fact, it keeps its original provenance and claim kind, and the user can drop it. A drop keeps its sources on record, so the same evidence cannot promote the topic again.

The surface ships off with null bars. With it off, uncalibrated, skipped or invalid, a suspected match behaves exactly as after Phase 170.

## Clarifications

### Session 2026-10-12

Answers marked **(user)** were accepted by the user through the Maestro (2026-10-12: questions 1A-6A and the listed Spec Architect decisions).

- Q: Who owns the suspected-match behavior versus Phase 170? → A: **(Cairn, 170 author)** 172 owns what a corroborating `suspected` match does, in both `_create_suspected_loop`'s matched branch and the declared-path match. 170's `record_corroboration` acts on `active` loops only and is not touched.
- Q: Is migration `zw003` free? → A: **(Cairn, Sextant)** Yes. 170 adds no migration (deadline-based drift); 171 adds no schema change (loop offers use `push_log`). `zw003` belongs to 172.
- Q: What is an independent source? → A: **(user)** A source key is `(inflow, source_ref)`: conversation uses the thread id; email uses the Gmail thread id (message id when there is no thread); calendar uses the event's `external_ref` (calendar loops carry no evidence after 170, so the key is their only identity); ingestion uses the ingestion id. A text is independent of a loop when its key is on none of the loop's recorded sources, its evidence refs are not already linked to the loop, and its key was never recorded on a `dropped` loop that matches it. A text with no source key is never independent. Alternatives offered: require a different inflow; also require a different email sender.
- Q: How many bars? → A: **(user)** Two bars on the one Noul: `corroborate_hold` and a stricter `promote_hold`. The decision table is in `contracts/corroboration-judgment.md`.
- Q: What happens on a match whose Noul is below `corroborate_hold`? → A: **(user)** The 170 behavior: link evidence and entities, no confidence change, no source row. The wrong-merge risk of the single-entity shortcut in `find_matching_loop` is recorded as a follow-up, not fixed here.
- Q: Which texts can corroborate? → A: **(user)** Only texts the 168 gate admits as a concern (`create_suspected` or `create_declared`), on both the System One path and the 109 Haiku fallback path. Matching needs the title Haiku writes after a positive gate. Held texts are not matched.
- Q: Where are the judgments recorded? → A: **(user)** The loop commit is fire-and-forget (168), so the judgment runs after `write_memory` returns and cannot reach `MessageTrace.judgments`. Each counted judgment is stored on its `open_loop_sources` row (score, model, latency); every judgment, counted or not, is logged as `corroboration_judgment`. Loop detail exposes the sources. This matches 168, where email, calendar and ingestion log only.
- Q: What does the user see on promotion? → A: **(user)** No push and no chat message. Promoted loops appear in the ranking and on the loops page with a "Promoted, seen in: …" label and can be dropped there or in chat.
- Q: Shape of a promoted loop? → A: **(user)** State `active`, confidence `max(current, 0.7)`, `confirmed_at = now`, drift deadline `now + 7 days`, in one statement guarded by `state = 'suspected'`. Provenance, claim kind, title, evidence and entities keep their values (as `confirm_loop` does). Promotion is a state edit, not a new claim, so it does not go through the contribution seam (169 precedent for reinforce and revive).
- Q: Calibration baseline and acceptance rule? → A: **(user)** Baseline: today's E5 title cosine at 0.75 on the same pairs. The surface may be enabled only when, for EN and PT separately on the held-out set: zero false promotions; corroborate precision at least 0.9 and at least the E5 baseline precision; corroborate recall at least the E5 baseline recall minus 0.05.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A second, independent mention promotes a suspected loop (Priority: P1)

On Monday the user tells Ze in chat "I still haven't sorted out the deposit with the landlord". The gate creates a `suspected` loop "Sort out the deposit with the landlord" (confidence 0.3). On Wednesday an email arrives from the letting agency: "Reminder: the deposit return form is still missing your signature." The gate admits it as a concern, the title matches the loop, the email thread is a new source, and System One answers `same_concern` 0.93, above `promote_hold`. The loop becomes `active` at 0.7 with a 7-day drift deadline and now ranks on the Priority page. Its detail lists two sources: the chat thread (origin) and the email thread (promoted, 0.93).

**Why this priority**: This is D2. Without it, an implied loop reaches the user only through confirmation, and a real concern that shows up twice still expires unseen.

**Independent Test**: With fake stores and a fake System One client answering 0.93, run the email commit against a store holding the suspected loop with a conversation origin row. Assert one `evidence` link, one source row (`role=corroboration`, `promoted=true`, score 0.93), state `active`, confidence 0.7, deadline now + 7 days, and no new loop.

**Acceptance Scenarios**:

1. **Given** a suspected loop with origin `(conversation, T1)` and a matched email on thread `G1`, **When** `same_concern` is at or above `promote_hold`, **Then** the loop is promoted and the source row is written with `promoted = true`.
2. **Given** the same match with `same_concern` at or above `corroborate_hold` and below `promote_hold`, **When** the commit runs, **Then** the loop stays `suspected`, its confidence becomes `min(0.6, 1 − (1 − c)(1 − 0.5·s))`, and the source row is written with `promoted = false`.
3. **Given** a loop already corroborated once (confidence 0.6), **When** a third independent source arrives at or above `promote_hold`, **Then** it is promoted at 0.7.
4. **Given** an answer of exactly a bar, **When** the decision runs, **Then** it counts as at or above.
5. **Given** two commits racing to promote the same loop, **When** both run, **Then** exactly one promotion happens (the guarded update), and both source rows are kept if their keys differ.

---

### User Story 2 - The same source cannot corroborate itself (Priority: P1)

The agency sends a follow-up in the same email thread. The user mentions the deposit again in the same chat thread. An ingestion re-runs over the same document. None of these is an independent source, so none raises confidence or promotes, and no System One request is made.

**Why this priority**: Without a code-owned independence rule, one noisy thread could promote its own guess.

**Independent Test**: For each non-independent case, a call-counting fake System One client records zero calls; the loop's state, confidence and source rows are unchanged; evidence is linked as after 170.

**Acceptance Scenarios**:

1. **Given** a loop whose origin is `(email, G1)`, **When** another message on `G1` matches, **Then** it is not independent.
2. **Given** a loop whose origin is `(conversation, T1)`, **When** the user repeats the concern in `T1`, **Then** it is not independent; **when** they repeat it in thread `T2`, **then** it is independent.
3. **Given** a text whose evidence ref is already linked to the loop (re-ingested message), **When** it matches, **Then** it is not independent.
4. **Given** a text with no source key, **When** it matches, **Then** it is not independent and a debug line says why.
5. **Given** a loop created before this phase (no origin row), **When** a matched text has a source key, **Then** independence is checked against the loop's corroboration rows and evidence only.

---

### User Story 3 - Same person, different matter, is not corroboration (Priority: P1)

The suspected loop "Reply to Ana about the budget" is linked to the entity Ana. An email from Ana about her birthday party is admitted as a concern ("RSVP to Ana's party"). Today `find_matching_loop` returns the budget loop because it is the only loop linked to Ana. System One answers `same_concern` 0.08. The budget loop is not corroborated or promoted.

**Why this priority**: This is the case entity and embedding matching cannot settle, and the reason the phase calls System One.

**Independent Test**: Fake answer 0.08 on an entity-shortcut match: no confidence change, no source row, a `corroboration_judgment` log line with outcome `not_same`, and the 170 link behavior.

**Acceptance Scenarios**:

1. **Given** a match with `same_concern` below `corroborate_hold`, **When** the commit runs, **Then** confidence, state and source rows are unchanged and the 170 behavior applies.
2. **Given** any judged match, **When** the decision is made, **Then** one `corroboration_judgment` log line records loop id, inflow, outcome, score, latency and skip reason.

---

### User Story 4 - Dropping is respected (Priority: P1)

The user drops a promoted loop ("that's handled, stop tracking it"). A week later a new suspected loop on the same topic is created from a new chat message. The agency's old email thread then gets one more message. It cannot promote the new loop, because that thread is a source of the dropped loop. A brand-new source can still corroborate it.

**Why this priority**: Agency. The user's drop must not be undone by the evidence that was already shown to them.

**Independent Test**: Seed a dropped loop with source `(email, G1)` and a new suspected loop matching it; a matched text on `G1` makes no System One call and changes nothing; a text on `G2` is judged normally.

**Acceptance Scenarios**:

1. **Given** a dropped loop with sources S, **When** a text whose key is in S matches a suspected loop that also matches the dropped loop, **Then** it is not independent.
2. **Given** a dropped or closed loop, **When** any text matches it, **Then** it is never promoted or corroborated (terminal states are not candidates).
3. **Given** a promoted loop, **When** the user drops it, **Then** the drop works as in 170 (fingerprint over all its evidence) and its source rows are kept.

---

### User Story 5 - Off, unsure and failing paths change nothing (Priority: P1)

The surface ships off with null bars. When it is off, uncalibrated, the client skips or throws, or the answer is invalid, a suspected match behaves exactly as after 170. A failure never fails a commit, a turn or an inflow job.

**Why this priority**: No regression in the default build and no new failure mode.

**Independent Test**: With the surface off, the 170 extraction tests pass unchanged and a call-counting fake records zero calls. With a skipping, throwing or malformed fake, the 170 behavior applies and the log line carries the skip reason.

**Acceptance Scenarios**:

1. **Given** `system_one.surfaces.corroboration.enabled` is false, **When** a suspected match happens, **Then** no request is made.
2. **Given** enabled with a null bar, or `corroborate_hold` greater than `promote_hold`, **When** a match happens, **Then** no request is made and a warning is logged.
3. **Given** a skip, exception or invalid answer, **When** a match happens, **Then** the 170 behavior applies.
4. **Given** the surface off, **When** loops are created, **Then** origin source rows are still written (provenance does not depend on the surface).

---

### User Story 6 - The user can see why a loop is tracked (Priority: P2)

On the loops page a promoted loop shows "Promoted, seen in: chat, email". The loop detail lists each source: inflow, role, when, and for corroborations the same-concern score and whether it promoted.

**Why this priority**: Honest provenance. A loop Ze promoted on its own must say why, so the user can judge and drop it.

**Independent Test**: A TestClient call to `GET /api/v0/loops/{id}` for a promoted loop returns `sources` with two rows; `GET /api/v0/loops` returns `promoted: true`. A vitest test renders the label.

**Acceptance Scenarios**:

1. **Given** a promoted loop, **When** the list is fetched, **Then** its item has `promoted: true` and `source_inflows` naming each distinct inflow.
2. **Given** any loop, **When** its detail is fetched, **Then** `sources` lists its origin row (if any) and every counted corroboration in time order.
3. **Given** the generated client, **When** `make codegen` runs, **Then** the committed files match.

---

### User Story 7 - Calibration decides whether the surface turns on (Priority: P2)

A maintainer runs `make calibrate-corroboration`. It scores the tuned set at a grid of bars with System One and, side by side, the E5 title cosine baseline. It prints per language and per inflow: corroborate precision and recall, false promotions, a reliability table and suggested bars. A separate held-out run with frozen bars prints `ENABLE` or `KEEP OFF` per language with the failing clause. `--check-sets` validates the data offline.

**Why this priority**: The 164 lesson. Bars are set only after a live run, and the held-out set is never tuned against.

**Independent Test**: `--check-sets` exits non-zero on any shape violation; pytest never collects the live path.

**Acceptance Scenarios**:

1. **Given** the two sets, **When** `--check-sets` runs, **Then** it checks row counts per language, every inflow present, hard negatives present, and no tuned text in the held-out set.
2. **Given** a live held-out run, **When** it finishes, **Then** it prints the verdict per language against the acceptance rule.
3. **Given** default CI, **When** the suite runs, **Then** no System One or OpenRouter request is made.

---

### Edge Cases

- The matched loop is `active` or `drifting`: 170's behavior (and 169's) applies; no same-concern judgment runs. Only `suspected` matches are candidates.
- A loop matched on the declared path (an explicit first-person statement in chat matching a suspected loop) follows the same rule: independence first, then the Noul. The user saying it in another thread is an independent source.
- The new text is judged `resolve` by the gate: the 168 close path runs; no corroboration.
- The same commit matches a suspected loop and the dismissed check suppresses it (same evidence fingerprint as a dropped loop): suppression wins, as in 170.
- Several suspected loops share the entity: `find_matching_loop` picks one by title similarity, as today; only that one is judged.
- The loop title or text is in another language than the other: the Noul is asked as is; the calibration sets include cross-language pairs.
- A unique-key conflict on the source row (two commits recording the same key): the second insert is a no-op and its judgment does not count.
- The System One call succeeds but the promote update finds the loop no longer `suspected` (the user confirmed or dropped it meanwhile): the source row is kept with `promoted = false`; no state change.
- 169 `track_loop` and 171 confirm act on suspected loops at the same time as a promotion: whichever update lands first wins; the guarded promote is a no-op on a non-suspected loop.
- Eval and Retry turns: no loop commit, so nothing here runs (168 guard).
- The 14-day stale expiry: a corroborated but unpromoted loop still expires on the same schedule; corroboration does not extend it.

---

## Requirements *(mandatory)*

### Functional Requirements

**Source keys and provenance**

- **FR-001**: Every loop commit MUST carry an optional source key `(inflow, source_ref)`. Conversation: the turn's `thread_id`. Email: the Gmail thread id, or the message id when there is none. Calendar: the event's `external_ref`. Ingestion: the ingestion id. Plugins pass `source_ref` as a plain string through the extractor callable (they never import `ze_worldstate`).
- **FR-002**: A new table `open_loop_sources` (migration `zw003`, ze-worldstate chain) MUST record, per loop, one row per source: `role` (`origin` or `corroboration`), `inflow`, `source_ref`, optional evidence kind and id, and for corroborations the `same_concern` score, `promoted` flag, model id and latency. `(loop_id, inflow, source_ref)` MUST be unique. Rows are deleted with their loop.
- **FR-003**: Every loop created through `propose_loop_candidates` with a source key MUST get an `origin` row, whether or not the corroboration surface is enabled. A loop created without a key gets none.

**Independence (code only)**

- **FR-004**: A matched text MUST be independent of a suspected loop only when all hold: it has a source key; the key is not on any of the loop's source rows; none of its evidence refs is already linked to the loop; the key is not on any source row of a `dropped` loop that matches the same title (the 109 dismissed lookup). The rule MUST live in a pure function with unit tests for each clause.
- **FR-005**: A non-independent match MUST make no System One request and MUST keep the 170 behavior.

**Judgment**

- **FR-006**: For an independent match on a `suspected` loop, with the surface enabled and calibrated, one System One request with `max_attempts=1` MUST ask one Noul, `same_concern`. The state MUST contain only the loop title (capped), the new text's inflow, and the new text capped with the 168 per-inflow caps.
- **FR-007**: Pure code MUST decide (contract `contracts/corroboration-judgment.md`): **promote** (score at or above `promote_hold`), **corroborate** (at or above `corroborate_hold`), **not_same** (below), **fallback** (off, uncalibrated, invalid bars, skip, exception, invalid answer). Bars compare at or above.
- **FR-008**: Surface config MUST live at `system_one.surfaces.corroboration` with `enabled`, `corroborate_hold`, `promote_hold`. Bars are null until a held-out `ENABLE`. Invalid values become null with a warning. `corroborate_hold > promote_hold` MUST be treated as uncalibrated.
- **FR-009**: Every judged match MUST be logged as `corroboration_judgment` (loop id, inflow, outcome, score, latency, skip reason). Fail open: no exception from this surface reaches the commit's caller.

**Effects**

- **FR-010**: **corroborate** MUST link evidence and entities (as 170), insert a `corroboration` source row with `promoted = false`, and set confidence to `min(0.6, 1 − (1 − c)(1 − 0.5·s))`, where `c` is the current confidence and `s` the score. The loop stays `suspected`.
- **FR-011**: **promote** MUST do everything **corroborate** does, then in one statement guarded by `state = 'suspected'` set `state = 'active'`, `confidence = GREATEST(confidence, 0.7)`, `confirmed_at = now()`, `drift_deadline = now() + 7 days`, `drift_rationale = NULL`, `updated_at = now()`, and mark the source row `promoted = true` only if the update changed a row.
- **FR-012**: Promotion MUST NOT change provenance, claim kind, title, evidence or entity links, MUST NOT write a memory fact, and MUST NOT go through the contribution seam.
- **FR-013**: **not_same** and **fallback** MUST keep the 170 behavior and write no source row.
- **FR-014**: The constants 0.6 (corroborated cap), 0.5 (weight), 0.7 (promoted confidence) and 7 days MUST be named constants in code, not config, and not model output.
- **FR-015**: Terminal loops (`closed`, `dropped`) MUST never be promoted or corroborated. Dropping a loop MUST keep its source rows.

**Surface**

- **FR-016**: `GET /api/v0/loops` items MUST gain `promoted: bool` (a corroboration row with `promoted = true` exists) and `source_inflows: list[str]`. `GET /api/v0/loops/{id}` MUST gain `sources: list[LoopSourceItem]` in time order. The generated client MUST be regenerated and committed.
- **FR-017**: The loops page row added by Phase 171 MUST show "Promoted, seen in: …" (inflow labels) for a promoted loop. No push, notification or chat message announces a promotion.

**Calibration**

- **FR-018**: `eval/calibration/corroboration.jsonl` (tuned) MUST hold at least 40 rows per language and `eval/calibration/corroboration_holdout.jsonl` at least 20 per language, written before any live run. Row schema: `id`, `lang`, `loop_title`, `loop_inflow`, `inflow`, `text`, `new_title`, `gold_same`, `kind`. Each set MUST cover all four inflows, and at least a third of each language's rows MUST be hard negatives (`same_entity_other` or `same_topic_other`).
- **FR-019**: `make calibrate-corroboration` MUST run live over the tuned set with System One and the E5 baseline (`cosine(new_title, loop_title) >= 0.75`), and report per language and inflow: corroborate precision and recall, false promotions, a reliability table, a bar grid and suggested bars. `--set holdout --bars C,P` MUST print `ENABLE` or `KEEP OFF` per language with the failing clause. `--check-sets` MUST validate FR-018 offline.
- **FR-020**: The surface MAY be enabled only when the held-out run shows, for EN and PT separately: zero false promotions (promote on `gold_same = false`); corroborate precision at least 0.9 and at least the E5 baseline precision; corroborate recall at least the E5 baseline recall minus 0.05. The held-out set MUST NOT be used for tuning; a change after a held-out run requires a fresh held-out set before the next verdict. A test MUST fail if a held-out text appears in the tuned set.
- **FR-021**: Default tests MUST mock the client. `make test-py` MUST NOT call OpenRouter or System One.

**Docs**

- **FR-022**: The System One ADR, `docs/system-one.md`, the worldstate docs and README, `docs/configuration.md`, AGENTS.md (phase row, migration table, worldstate layout, calibrate target) and the specs index MUST describe the surface, the table and the target.

### Key Entities

- **SourceKey**: `(inflow, source_ref)`, the code identity of where a text came from.
- **LoopSource**: one recorded source of a loop: role, key, optional evidence, and for corroborations the score, promoted flag, model and latency.
- **CorroborationSurfaceConfig**: `enabled`, `corroborate_hold`, `promote_hold`; calibrated only when enabled, both set, and ordered.
- **CorroborationDecision**: kind (`promote`, `corroborate`, `not_same`, `fallback`), reason, score.
- **CorroborationRow** (calibration data): a labeled pair of loop title and new text.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the held-out set, 0 false promotions per language at the shipped bars (a promotion of a different matter never happens in the measured set).
- **SC-002**: On the held-out set, corroborate precision is at least 0.9 and recall is no more than 0.05 below the E5 baseline, per language; otherwise the surface stays off and the tuning note says why.
- **SC-003**: In tests, 100 percent of non-independent matches (same thread, same evidence, no key, dropped-loop source) make zero System One calls and change nothing.
- **SC-004**: Every promoted loop lists at least two sources from different source keys on its detail.
- **SC-005**: With the surface off, every 170 extraction test passes unchanged and zero System One calls are made.
- **SC-006**: A same-entity, different-matter text never raises a loop's confidence in the test suite.
- **SC-007**: `make test-worldstate`, `make test`, `make test-messenger`, `make test-calendar`, `make test-ingestion`, `make test-web`, `make typecheck-web` and `make lint` pass; `make test-pg` passes with the new migration applied.

---

## Assumptions

- Phases 170 and 171 land first. Their diffs are re-read before implementation; this spec assumes 170's `contracts/loop-evidence.md` (episode evidence for conversation and email, ingestion ref, none for calendar) and 171's `/loops` page.
- The source keys exist today: `thread_id` in the conversation `configurable`, `msg.thread_id` / `msg.message_id` in the messenger processor, `signal.external_ref` in the calendar job, `ingestion_id` in the ingestion sink.
- Existing loops get no origin backfill (the dev database has no loops; pre-v1).
- `typesafe/jev-1.13` stays pinned; bars are re-calibrated when the model changes.
- A promoted loop at 0.7 ranks below user-stated and user-confirmed loops in `PriorityView`, which ranks loops by confidence. This is intended.
- Corroboration on `active` loops (170) is not gated by the Noul in this phase; gating it is a candidate follow-up, as is fixing the single-entity shortcut in `find_matching_loop`.
