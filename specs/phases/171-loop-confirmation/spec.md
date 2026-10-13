# Feature Specification: Loop Confirmation Path

**Feature Branch**: `171-loop-confirmation`

**Created**: 2026-10-12

**Status**: Implemented

**Input**: User description: "Phase 1b of the executive-function direction (`specs/arch/executive-function.md`, findings F2 and F10, decision D2). Suspected loops reach the user both ways: mount the existing `LoopReviewList` widget on a page, and at session resume Ze asks 'keep track of these?' for at most 3 suspected loops, which the user confirms or drops in chat. Also a language-neutral 'what's open' trigger (today an English-only regex; Ze is EN + PT) and a cap on the resume recap. Out of scope: corroboration promotion (172), commitment intake (173), scoring (175)."

**Governed by**: [`specs/arch/executive-function.md`](../../arch/executive-function.md) (F2, F10, §3.1 item 7, option 1b, §8 D2), [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md), [`specs/arch/claim-topology.md`](../../arch/claim-topology.md), [`specs/arch/attention-arbitration.md`](../../arch/attention-arbitration.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md). Phases [109](../109-open-loop-substrate/spec.md), [112](../112-session-context-continuity/spec.md), [132](../132-priority-turn-surfacing/spec.md), [160](../160-e5-routing-confidence/spec.md), [167](../167-routing-choice-criteria/spec.md), [168](../168-loop-extraction-gate/spec.md), [169](../169-loop-track-tool/spec.md), 170 (executive repair, specced on the "Executive Function Research" floor).

**Depends on**: Phase 169 (loop track tool: `LoopTracker`, `stamp_declared`, `DECLARED_CONFIDENCE`, `track_loop_succeeded`, `strip_track_claims`) and Phase 170 (executive repair: deadline-only drift predicate, evidence on gate-created loops) Implemented on `main`. Implementation starts after both land; the first task re-reads both diffs.

**Does not change**: the System One loop gate, its questions, bars or calibration (168); `track_loop` and its matching rule (169); the drift predicate, corroboration and evidence linking (170); priority scoring and ranking order (175); auto-promotion of suspected loops from independent sources (172); the 14-day `StaleSuspicionJob` expiry; the `open_loops` schema (no migration); the Priority page.

---

## Overview

The audit found that a suspected loop has no reachable way to be confirmed (F2). `review.confirm_loop` is called only by `POST /api/v0/loops/{id}/confirm`, whose only caller is the `LoopReviewList` widget, which no page mounts. The loops agent can list, close, drop and (after 169) track, but it cannot confirm a loop by id. `StaleSuspicionJob` drops every suspected loop after 14 days, and `PriorityView` ranks only `active` and `drifting` loops. So every implied loop from email, calendar, ingestion, and non-explicit conversation is created, never shown, and dropped.

This phase makes suspected loops reach the user in two ways (decision D2):

1. **A page.** `LoopReviewList` is mounted at `/loops` ("Open loops", Automation nav group). Suspected loops come first, with Keep and Drop.
2. **A question in chat.** On the first turn after a session gap, code picks at most 3 suspected loops that were not offered in the last 7 days and puts them in the resume recap. The speaking agent ends its reply with one short question, in the user's language, asking whether to keep track of them. The user answers in chat. The companion delegates to the loops agent, which now has a `confirm_loop` tool next to `drop_loop`.

Every confirm (page, REST, chat) goes through one function and writes what a 169 track-confirm writes: `active`, confidence 0.9, a fresh 7-day drift deadline. A confirmed loop then ranks like a declared one instead of sitting at 0.3.

Two smaller fixes ride along. The "what's open" trigger becomes language-neutral: it compares the turn's existing multilingual E5 prompt embedding with EN and PT example questions instead of an English regex (F10). The resume recap lists at most 5 ranked items, and an explicit "what's open" answer at most 10 (§3.1 item 7).

Doctrine fit: a suspected loop stays a suspicion until the user confirms it. Confirmation is an executive open-loop-state claim made by the user, never a fact. The offer is a question; the code forbids the agent to say a loop is tracked before a confirm tool succeeded. The user can see, confirm and refuse every inferred loop (agency).

## Clarifications

### Session 2026-10-12

Answers marked **(user, Qn)** were given by the user through the Maestro (questions Q1–Q6 in the "171 Loop Confirmation Handoffs" note); the user accepted every recommendation. The rest are Spec Architect decisions with the reason; the user may overturn them.

- Q: Where is `LoopReviewList` mounted? → A: **(user, Q1)** A new page `/loops`, label "Open loops", in the Automation nav group after Priority, not in the mobile bottom nav. Suspected loops are listed first under "Needs your OK"; active and drifting loops follow under "Tracking". The Priority page is not touched (170 edits it).
- Q: How is the resume question written? → A: **(user, Q2)** Code selects the loops and records the offer; the wording comes from the speaking agent, guided by the recap. The recap gains a "Not yet tracked" block with the titles and one instruction: end the reply with one short question in the user's language asking whether to keep track of them; never say they are tracked. No deterministic English text and no chat buttons in this phase (buttons are a 176 Today concern).
- Q: How often can the same suspected loop be offered? → A: **(user, Q3)** Not again within 7 days of an offer, so at most twice before the 14-day expiry. Silence is not an answer: an unanswered loop keeps its state and expires as today. A "no" in chat drops it through `drop_loop` (and records the 109 dismissal fingerprint).
- Q: What does a confirm write? → A: **(user, Q4)** One path for page, REST and chat: `review.confirm_loop` transitions `suspected → active` and then calls 169's `stamp_declared` with confidence 0.9 (`DECLARED_CONFIDENCE`) and `now + 7 days`. Provenance and claim kind keep their values (the origin stays honest: `email`, `conversation`, ...). The REST response therefore reports confidence 0.9.
- Q: How does "what's open" become language-neutral? → A: **(user, Q5)** Multilingual E5 similarity between the turn's prompt embedding (already computed in `fetch_context`) and a fixed list of EN + PT example questions. Detected when the best cosine similarity is at or above a threshold chosen offline on a labeled EN + PT set with a held-out split (free, local; no System One call). The regex is deleted (pre-v1 hard cut).
- Q: What are the caps? → A: **(user, Q6)** Resume recap: at most 5 ranked open items. Explicit "what's open": at most 10. Suspected-loop offers: at most 3.
- Q: When is an offer recorded? → A: When the recap that carries it is built, as a `push_log` row `worldstate_loop_offer:<loop_id>`. Code cannot see whether the model actually asked, so "offered" means "given to the speaking agent". This is the cost of letting the agent word the question; the trace records the offered ids so a missed question is visible.
- Q: Which suspected loops are offered first? → A: Highest confidence first, then newest `created_at`. With the same confidence (0.3 for all gate-created suspected loops today), the newest come first. Phase 172 will raise the confidence of corroborated ones, which then come first without a change here.
- Q: Does a turn without a gap ever offer? → A: No. Offers only ride the resume recap (decision D2: "at session resume"). The `/loops` page is the always-available path.
- Q: Does a retry or an eval turn offer? → A: A retry turn (`retry_mode`) neither offers nor records an offer; it reuses nothing from the original turn's offer. Eval turns behave like normal turns (eval threads rarely have a gap).
- Q: Does the chat confirm need a new tool or can it reuse `track_loop`? → A: A new `confirm_loop(loop_id)` tool, mirroring `close_loop` and `drop_loop` by id. `track_loop` matches by title through entity overlap and E5, which can pick a different loop than the one the user was asked about; an offered loop has an id, so confirm by id is exact. Both end in the same write (`stamp_declared`, 0.9), and a successful `confirm_loop` earns a tracking claim in the 169 honesty guard exactly as a successful `track_loop` does.
- Q: Who handles a bare "yes, keep the first two"? → A: The companion (conductor and sole speaker since 153) sees the previous turn in history and delegates to the loops agent with the titles. Routing criteria are not changed. The loops agent lists open loops, matches the titles, and calls `confirm_loop` or `drop_loop` once per loop.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Review suspected loops on a page (Priority: P1)

The user opens "Open loops" from the Automation group. They see the loops Ze suspected, with where each came from and Keep / Drop buttons, above the loops Ze is already tracking. Keep moves the loop to "Tracking". Drop removes it.

**Why this priority**: This is the cheapest reachable confirm path and the always-available fallback when the user ignores the chat question.

**Independent Test**: Render the page with a mocked loops query holding one suspected, one active and one drifting loop; assert section order, buttons per state, and that Keep calls the confirm mutation and Drop the drop mutation. Navigate to `/loops` from the nav.

**Acceptance Scenarios**:

1. **Given** the app is loaded, **When** the user opens the Automation group, **Then** "Open loops" appears after Priority and links to `/loops`; the top bar shows "Open loops".
2. **Given** suspected and active loops exist, **When** the page renders, **Then** suspected loops are listed first under "Needs your OK" with provenance and Keep / Drop; active and drifting loops follow under "Tracking" with Close / Drop.
3. **Given** the user presses Keep, **When** the request succeeds, **Then** the list refetches and the loop shows under "Tracking" as active.
4. **Given** there are no open loops, **When** the page renders, **Then** the existing empty state is shown.
5. **Given** the request fails, **When** the page renders, **Then** the existing error state with Retry is shown.

---

### User Story 2 - Every confirm means the same thing (Priority: P1)

Whether the user confirms on the page, through REST, or in chat, the loop becomes `active` at confidence 0.9 with a fresh 7-day drift deadline, exactly as when 169's `track_loop` confirms a matching suspected loop.

**Why this priority**: Today a confirmed loop keeps confidence 0.3 and ranks near the bottom of `PriorityView`, so confirming has almost no effect. Three confirm paths with different results would also be a honesty defect.

**Independent Test**: Unit test `review.confirm_loop` against a fake store: `transition(..., "active")` then `stamp_declared(id, confidence=0.9, deadline=now+7d)`; returned loop fields match. REST test: response confidence is 0.9.

**Acceptance Scenarios**:

1. **Given** a suspected loop at 0.3 from email, **When** it is confirmed through any path, **Then** state is `active`, confidence 0.9, `confirmed_at` set, `drift_deadline` 7 days out, `drift_rationale` empty, provenance still `email`.
2. **Given** an `active`, `drifting`, `closed` or `dropped` loop, **When** confirm is called, **Then** it fails with the existing invalid-transition error (409 on REST) and nothing changes.
3. **Given** a missing id, **When** confirm is called, **Then** it fails with not-found (404 on REST).

---

### User Story 3 - Confirm or drop in chat (Priority: P1)

The user says "keep the bank switch, drop the dentist one". The loops agent lists open loops, finds each title, calls `confirm_loop` for the first and `drop_loop` for the second, and only then says what it did. If it could not confirm, it does not say it is tracking.

**Why this priority**: The chat question in Story 4 is useless without a confirm path in chat.

**Independent Test**: Run `LoopsAgent` with a scripted LLM that calls `list_open_loops`, `confirm_loop`, `drop_loop`; assert store transitions and the reply. Honesty table: tracking claims stripped unless `confirm_loop` or `track_loop` succeeded.

**Acceptance Scenarios**:

1. **Given** a suspected loop, **When** `confirm_loop(loop_id)` runs, **Then** it returns `{ok: true, id, title, state: "active"}` and the store holds the Story 2 fields.
2. **Given** an invalid UUID, an unknown id, or a loop not in `suspected`, **When** `confirm_loop` runs, **Then** it returns `{ok: false, error}` and writes nothing.
3. **Given** the reply "I'll keep track of the bank switch." and a successful `confirm_loop` in the turn, **Then** the reply is unchanged.
4. **Given** the same reply and no successful `confirm_loop` or `track_loop`, **Then** the reply becomes `I could not track that.` (169 guard).
5. **Given** the user asks to confirm a loop that is already `active`, **When** the agent replies, **Then** it says it is already tracked and makes no write (the instructions say so; `confirm_loop` would fail).
6. **Given** a turn where the companion delegates to the loops agent, **When** `confirm_loop` succeeded inside the delegate, **Then** the flattened tool calls show it and Retry treats the turn as not retryable.

---

### User Story 4 - At session resume, Ze asks about at most 3 suspected loops (Priority: P1)

The user comes back after a gap. Ze answers their message and ends with something like "By the way, I noticed a few things you might want me to keep track of: switching banks, the dentist appointment. Want me to?" (or the Portuguese equivalent). It never names more than 3, never names one it asked about in the last 7 days, and never claims they are already tracked.

**Why this priority**: Decision D2. Chat is where the user already is; a page they never open does not fix F2.

**Independent Test**: `fetch_context` test with a gap and a fake surfacer returning offers: the rendered recap contains the "Not yet tracked" block with ≤3 titles and the instruction; `loop_offer_ids` is set in the node output; the surfacer recorded the offers. Without a gap, no block and no record. `TurnSurfacing.resume_loop_offers` tests: ordering, limit 3, 7-day cooldown via push log, store failure returns `[]`.

**Acceptance Scenarios**:

1. **Given** 5 suspected loops, none offered recently, **When** the first turn after a gap runs, **Then** the recap carries exactly 3 (highest confidence, then newest) and 3 offer rows are logged.
2. **Given** a loop offered 2 days ago, **When** the next resume happens, **Then** that loop is not offered again; after 7 days it may be.
3. **Given** no suspected loops (or all cooled down), **When** a resume happens, **Then** the recap has no "Not yet tracked" block and nothing is logged.
4. **Given** the push log or the loop store fails, **When** a resume happens, **Then** the turn proceeds with no offers and a warning is logged.
5. **Given** a retry turn, **When** `fetch_context` runs, **Then** no offer is selected or recorded.
6. **Given** a turn with offers, **When** the trace is written, **Then** `MessageTrace.loop_offer_ids` lists the offered ids; otherwise it is empty.
7. **Given** a resume with offers and nothing else to recap, **When** the recap is built, **Then** a recap is still applied (`resume_recap_applied` is true).

---

### User Story 5 - "What's open?" works in Portuguese (Priority: P2)

The user asks "O que tenho em aberto?" or "What's still on my plate?" and gets the ranked open items. "What time does the shop open?" and "abre a porta" do not trigger it.

**Why this priority**: F10. Ze is EN + PT; the ranked answer is unreachable in Portuguese today.

**Independent Test**: Offline calibration over `eval/calibration/open_query.jsonl` (train) and `open_query_holdout.jsonl` (never tuned on) with the real E5 model (slow test). Fast unit tests use a fake embedder for the detector logic. `surface_loops` reads the flag from state instead of calling the regex.

**Acceptance Scenarios**:

1. **Given** a positive EN or PT example from the held-out set, **When** detection runs, **Then** it is detected (target: recall ≥ 0.9 on held-out).
2. **Given** a negative example (store hours, "open the file", a question about an open job offer), **When** detection runs, **Then** it is not detected (target: false-positive rate ≤ 0.05 on held-out).
3. **Given** a detected query, **When** the turn runs, **Then** the agent context carries the open-priorities note with at most 10 items, and `surface_loops` adds no inline mentions.
4. **Given** the embedder fails, **When** detection runs, **Then** it returns false and the turn proceeds.

---

### User Story 6 - The resume recap stays short (Priority: P2)

A resume recap lists at most 5 ranked open items, the top of the merged ranking (pins first, as 132 already merges).

**Why this priority**: §3.1 item 7. An uncapped list floods the system prompt as the store grows.

**Independent Test**: `TurnSurfacing.recap_mentions(limit=5)` with 8 ranked items returns the first 5 in merged order; `_assemble_resume_recap` passes 5; `_open_priorities_note` passes 10.

**Acceptance Scenarios**:

1. **Given** 8 ranked items, **When** a resume recap is built, **Then** it lists 5.
2. **Given** 8 ranked items and an explicit "what's open", **When** the note is built, **Then** it lists 8; with 14 items it lists 10.

---

### User Story 7 - Evals cover PT "what's open" and the confirm tool (Priority: P3)

Eval scenarios check that "O que tenho em aberto?" and "What's still on my plate?" are answered with ranked open items, and the routing set gains EN + PT rows for "keep the X one" / "drop the Y one" style confirm and drop requests to the loops agent.

**Why this priority**: Unit tests use fakes; evals prove the language path end to end. The resume question needs a session gap that the eval harness cannot produce, so it is covered by graph-level tests, not evals.

**Independent Test**: `ze_list_scenarios()` lists the new scenarios; a live run passes them.

**Acceptance Scenarios**:

1. **Given** the PT scenario, **When** it runs, **Then** the judge criteria require a list of open items, not a generic reply.
2. **Given** the routing training set, **When** the offline routing check runs, **Then** the new loops rows route to `loops`; no held-out file changed.

---

### Edge Cases

- A suspected loop expires (14 days) between the offer and the user's answer: `confirm_loop` fails with an invalid transition; the agent says it is no longer open and offers to track it again (`track_loop`).
- The user answers "yes" to the offer much later in the same session: the titles are still in history; same flow.
- The user answers with a new title that does not match any offered loop ("yes, and also the car insurance"): the agent confirms what matches and may call `track_loop` for the new concern (169).
- Two suspected loops share a title: the agent asks which one (existing instruction for close/drop); the page shows both with provenance.
- The same loop is confirmed on the page and in chat concurrently: the second transition fails (state is no longer `suspected`); the agent reports it is already tracked.
- The resume turn routes to a specialist with a terse reply (calendar): the instruction still applies; every agent renders the recap through `_build_system_prompt`.
- The recap holds offers but the agent ignores the instruction: the offer is still recorded and cooled down for 7 days; the trace shows the ids; the page still shows the loop.
- A prompt that is both a "what's open" query and a resume: the recap (5 items + offers) and the open-priorities note (≤10 items) are both injected, as today.
- Detection on an image turn: uses the same embedding as retrieval (the caption), as today.
- `push_log.was_sent_within_hours` raises: offers are skipped for that turn (fail closed, no nagging).

## Requirements *(mandatory)*

### Functional Requirements

**Page (`ze-web`)**

- **FR-001**: `ze-web` MUST have a route `/loops` with nav label "Open loops", placed in the Automation nav group after Priority, `showInMobileNav: false`, with its own page slice (`pages/loops`) that renders `LoopReviewList`.
- **FR-002**: `LoopReviewList` MUST group loops into "Needs your OK" (`suspected`) first and "Tracking" (`active`, `drifting`) second, hide an empty group's heading, and label the suspected Keep button "Keep" (it calls the existing confirm mutation). Each row MUST show provenance. Existing empty and error states MUST stay.

**Confirm semantics**

- **FR-003**: `review.confirm_loop` MUST transition `suspected → active` and then call `LoopStore.stamp_declared(loop_id, confidence=DECLARED_CONFIDENCE, deadline=now + DEFAULT_DRIFT_WINDOW_DAYS)`; the returned `OpenLoop` MUST carry the stamped values. It MUST NOT change provenance, claim kind, title, evidence or entity links. Every other source state MUST keep raising `InvalidLoopTransitionError`.
- **FR-004**: `POST /api/v0/loops/{id}/confirm` MUST keep its route, status codes and response shape; its `confidence` field reports the stamped value.

**Chat confirm (loops agent)**

- **FR-005**: The loops agent MUST expose a WRITE tool `confirm_loop(loop_id: str)` that calls `review.confirm_loop` and returns `{ok: true, id, title, state}` on success and `{ok: false, error}` for an invalid UUID, a missing loop or an invalid transition. It MUST NOT raise to the agent loop. It MUST declare `reversibility=REVERSIBLE`, `undo_tool="drop_loop"`, an `undo_note`, and `effect_phrase="confirmed an open loop"`.
- **FR-006**: `LoopsAgent.tools`, its intent description, `description`, `routing_criteria` and `_AGENT_INSTRUCTIONS` MUST cover confirming: list first, match a unique title, call `confirm_loop` or `drop_loop` once per loop, say a loop is tracked only after `confirm_loop` or `track_loop` succeeded, and say "already tracked" for an `active` match without writing.
- **FR-007**: The 169 honesty guard MUST treat a successful `confirm_loop` (payload `ok: true`) as earning a tracking claim, exactly like a successful `track_loop`. The helper MUST be renamed from `track_loop_succeeded` to `tracking_earned` (hard cut; all callers updated).

**Resume offer**

- **FR-008**: `TurnSurfacing` MUST expose `resume_loop_offers(limit: int = 3) -> list[LoopOffer]` that reads `suspected` loops, skips any loop with a `worldstate_loop_offer:<id>` push-log row in the last 168 hours, orders by confidence descending then `created_at` descending, returns at most `limit`, and logs one push-log row per returned loop. On any store or push-log error it MUST return `[]` and log a warning (fail closed).
- **FR-009**: `ResumeRecap` MUST gain `loop_offers` and render, when non-empty, a block headed "Not yet tracked (Ze noticed these; the user has not confirmed them):" listing the titles, followed by the instruction: "End your reply with one short question, in the user's language, asking whether they want you to keep track of these. Do not say they are being tracked." `has_content()` MUST be true when only offers are present.
- **FR-010**: `_assemble_resume_recap` MUST call `resume_loop_offers()` only on the resume branch and never when `retry_mode` is set. `fetch_context` MUST return `loop_offer_ids` (list of id strings) in its state update.
- **FR-011**: `AgentState`, the trace node, `MessageTrace`, the message store parser, `MessageTraceResponse` (REST) and the generated `@myguyze/ze-client` types MUST carry `loop_offer_ids: list[str]` (default empty), following the `resume_recap_applied` path.

**Language-neutral "what's open"**

- **FR-012**: The English regex `_GLOBAL_OPEN_RE` MUST be deleted. `ze_priority` MUST gain an `OpenQueryDetector` that holds a fixed list of EN + PT example questions, embeds them once (lazily) with the injected E5 embedder, and returns true when the best cosine similarity between a given prompt embedding and an example is at or above `OPEN_QUERY_THRESHOLD`. It MUST return false on any embedder error.
- **FR-013**: `TurnSurfacing.is_global_open_query` MUST take the prompt embedding (`is_global_open_query(embedding) -> bool`) and delegate to the detector. `fetch_context` MUST call it with the embedding it already computes, store the result as `open_items_query: bool` in its state update, and pass it to `_open_priorities_note`. `surface_loops` MUST read `state["open_items_query"]` and MUST NOT call the surfacer for detection.
- **FR-014**: `OPEN_QUERY_THRESHOLD` and the example list MUST be chosen offline by `eval/calibration/open_query.py` over `eval/calibration/open_query.jsonl` (train, EN + PT, positives and hard negatives) and verified once on `eval/calibration/open_query_holdout.jsonl`, which MUST NOT be tuned on. The verdict (recall and false-positive rate per language on held-out) MUST be recorded in `research.md`. Target: recall ≥ 0.9 and false-positive rate ≤ 0.05 on held-out for each language. A `make calibrate-open-query` target MUST run it (local model, no credits).

**Caps**

- **FR-015**: `TurnSurfacing.recap_mentions` MUST take `limit: int | None`. The resume recap MUST pass `RECAP_LIMIT = 5`; the open-priorities note MUST pass `OPEN_QUERY_LIMIT = 10`. Limits apply after the 127 merge, so pins come first.

**Tests, evals, boundaries**

- **FR-016**: Unit tests MUST cover FR-002 through FR-015. A real-Postgres test in the 170 harness (`@pytest.mark.pg`) MUST cover FR-003 (confirm writes 0.9 and a deadline the 170 sweep later selects) and FR-008 (cooldown through the real push log).
- **FR-017**: Two eval scenarios (EN and PT "what's open") and four routing training rows (EN + PT confirm and drop by title) MUST be added. Held-out files MUST NOT be edited.
- **FR-018**: No migration. No new REST route. `ze_core` MUST NOT import `ze_priority` or `ze_worldstate` (it reaches the surfacer through `config["configurable"]["turn_surfacer"]`, as today).

### Key Entities

- **Suspected loop**: an `OpenLoop` in state `suspected`; an inference until confirmed.
- **Loop offer**: a suspected loop given to the speaking agent at session resume (`LoopOffer`: `loop_id`, `title`, `provenance`), recorded as a push-log row `worldstate_loop_offer:<id>`.
- **Confirm**: the user-made `suspected → active` transition, stamped like a declaration (confidence 0.9, 7-day deadline).
- **Open-items query**: a user turn asking what is open, detected by E5 similarity to example questions.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A suspected loop can be confirmed by the user from the page and from chat; in tests, 100% of confirms through page, REST and chat leave the loop active at confidence 0.9 with a deadline 7 days out.
- **SC-002**: At session resume the user is asked about at most 3 suspected loops, and no loop is asked about twice within 7 days (verified over a simulated 14-day sequence of daily resumes: each loop offered at most 2 times).
- **SC-003**: In chat-confirm tests, 0 replies claim tracking without a successful confirm or track call.
- **SC-004**: "What's open" questions are detected with recall ≥ 0.9 and false positives ≤ 5% on the held-out set, separately for English and Portuguese.
  - **Outcome (2026-10-13)**: the original bar was MISSED in Portuguese on both held-out sets (recall 0.80, then 0.667 before rewording the examples; EN 0.90 and 0.917; false positives 0.000). By user decision the detector ships at threshold 0.88 under an amended bar set after seeing the results: EN recall ≥ 0.9, PT recall ≥ 0.65, false positives ≤ 5%. Both held-out sets are now seen and are regression sets only. See `research.md` Verdict. Follow-up: a System One Noul `asks_what_is_open`.
- **SC-005**: Resume recaps never list more than 5 ranked items; explicit "what's open" answers never more than 10.
- **SC-006**: `make test-py`, `make test-pg`, `make test-web`, `make typecheck-web` and `make lint` pass; the new eval scenarios pass in one live run.

## Assumptions

- **169 and 170 land first.** 171 reuses `stamp_declared`, `DECLARED_CONFIDENCE`, the 169 honesty guard, and 170's real-Postgres harness and deadline-only drift predicate. Without 170, a confirmed loop would never drift (F1); confirming would still rank it correctly.
- **The offer is worded by the model.** The code controls which loops, how many and how often; the model controls language and placement. A model that skips the question costs one 7-day cooldown for those loops; the page remains.
- **Companion honesty.** The companion is the speaker on most turns and does not run the domain honesty guard. It reports the loops agent's delegate result. A false tracking claim by the companion itself is not enforced in code in this phase (same as 169); the recap instruction forbids it.
- **E5 is enough for F10.** The prompt embedding is already computed for retrieval, so detection adds no model call. A System One Noul was considered and rejected for per-turn cost (Q5).
- **Suspected confidence stays 0.3** for gate-created loops until 172 adds corroboration; the offer order is newest-first in practice until then.
- **No migration.** Offers use the existing `push_log` table.
- **Doctrine functions served:** executive function (open-loop state, attention) and the agency principle (see, correct, refuse).
