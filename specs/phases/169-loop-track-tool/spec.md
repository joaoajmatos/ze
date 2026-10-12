# Feature Specification: Loop Track Tool

**Feature Branch**: `169-loop-track-tool`

**Created**: 2026-10-12

**Status**: Draft

**Input**: User description: "Give the loops agent an explicit tool to track a loop. Since phase 167 'keep that on my radar' routes to the loops agent, but the agent can only list, close and drop. Creation depends on the post-turn System One loop gate, which can hold. The agent may then tell the user it is tracking something that was never saved."

**Governed by**: [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md), [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md), [`specs/arch/claim-topology.md`](../../arch/claim-topology.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md). Phases [109](../109-open-loop-substrate/spec.md), [110](../110-open-loop-drift-surfacing/spec.md), [148](../148-extractor-dual-write-identity-skip/spec.md), [165](../165-response-feedback-retry/spec.md), [167](../167-routing-choice-criteria/spec.md) (research R9), [168](../168-loop-extraction-gate/spec.md).

**Depends on**: Phases 109, 110, 165, 167 and 168 Implemented on `main`.

**Does not change**: the System One loop gate, its questions, bars and calibration (168); the `suspected` creation path and its dismissal-fingerprint rule (109 FR-011); loop REST routes and their behavior (`confirm` stays `suspected`-only); `ze-web`; the `open_loops` schema (no migration); routing bars and `routing_criteria` text (167); the companion and its tools.

---

## Overview

Since phase 167, "keep that on my radar" routes to the loops agent. That agent has `list_open_loops`, `close_loop` and `drop_loop`. It cannot create a loop. Creation happens after the turn, in the 168 loop gate, which may hold. The reply is already written by then. If the agent says "I'll keep an eye on that" and the gate holds, Ze told the user something that is not stored. This is the failure the memory-honesty roadmap exists to remove (phases 140-150 did it for facts, reminders, goals and loop closing).

This phase adds one WRITE tool, `track_loop`, to the loops agent. A user who explicitly asks Ze to keep something in mind gets a loop immediately, inside the turn, and the agent confirms only after the tool returned success. The loop is user-stated, so it is `active`, `user_declared`, confidence 0.9, with the 7-day drift window unless the user named another. A matching open loop is reinforced instead of duplicated. The post-turn gate is skipped on a turn where `track_loop` succeeded, so one request never yields two loops. Two honesty guards mirror the close/drop one: the agent text is stripped of tracking claims the tool did not earn.

## Clarifications

### Session 2026-10-12

Answers marked **(user)** were given by the user through the Maestro. The rest are Spec Architect decisions with the reason; the user may overturn them.

- Q: What does a track ask do to a match in `drifting`? → A: **(user)** Revive it to `active`. The loop gets confidence 0.9 and a fresh drift window. This adds `drifting → active` to the transition matrix, **only** on an explicit user ask (`user_asked=True`), never from inferred evidence, the sweep, or the REST `confirm` route. See FR-007 and the lifecycle contract.
- Q: Exactly which fields does a revive write? → A: **(Maestro, 2026-10-12, confirmed against the code)** `state='active'`, `confidence=0.9`, `confirmed_at=now`, `drift_deadline=now+window`, `drift_rationale=NULL`, `updated_at=now`, with `confirmed_at` and `updated_at` taken from the same SQL `now()` in one statement (`stamp_declared`). Nothing else changes (provenance, claim kind, title, evidence and entity links keep their values). The same field set applies to `confirmed` (from `suspected`) and `created`, minus the fields that do not exist yet. This is the exact write, not a repair of the drift sweep: the sweep stays inert for every other loop until phase 170 (finding F1, `specs/arch/executive-function.md`) adds a `last_activity_at` column. Phase 169 does not try to fix F1.
- Q: What does a track ask do to a match in `dropped`? → A: **(user)** Create a fresh loop. The old row stays `dropped`. An explicit ask is new user-stated evidence; the 109 fingerprint rule only suppresses inferred loops, and track never consults it.
- Q: How does the post-turn 168 gate treat a turn where `track_loop` succeeded? → A: **(user)** It is skipped (no admission call, no System One request, no judgment rows), mirroring the 148 `remember_fact` skip. Consequence: a `resolves_existing` signal in the same message is not acted on that turn.
- Q: Where does a time window come from? → A: **(user)** An optional `window_days` argument the agent fills only when the user named a timeframe. Code clamps it to 1-365. Default 7. Zero or absent means default. No date parser.
- Q: Provenance, state, confidence of a user-asked loop? → A: Identical to the existing explicit-declaration shape in `_create_declared_loop`: `LoopProvenance.USER_DECLARED`, `LoopState.ACTIVE`, claim kind `PRIORITY`, confidence 0.9 (`_DECLARED_CONFIDENCE`), `confirmed_at = now`, drift deadline `now + window`. Reason: a user asking to be tracked is the definition of a declaration; user-stated outranks suspicion (claims.py `PROMPT_SUPPLIED`), and reusing one shape avoids a second "kind" of declared loop. The seam mapping `USER_DECLARED → Provenance.PROMPT_SUPPLIED` is unchanged.
- Q: Who writes the title? → A: The agent's own tool call supplies `title`; the code trims, collapses whitespace and caps it at 120 characters. No Haiku title-writer call: the agent already holds the user's words and language, and an extra LLM call would add latency and a second failure point to a path that must be reliable.
- Q: Which write path? → A: The contribution seam, exactly as the gate does: `loop_to_contribution` + `submit_and_detect_collisions` around `loop_store.create`. Reinforce and revive create no new claim, so they do not go through the seam; they are state edits on an existing loop, like `review.confirm_loop` today.
- Q: Dedup and reinforce rule? → A: Reuse `find_matching_loop` (entity overlap primary, E5 0.75 title similarity tiebreaker) over `suspected`, `active`, `drifting`. Match found: `suspected` is confirmed (→ `active`, confidence 0.9, deadline set); `active` gets confidence raised to at least 0.9 and its evidence/entity links refreshed; `drifting` is revived (above). No match: create. The result tells the agent which of `created`, `confirmed`, `reinforced`, `revived` happened, so the reply can be accurate.
- Q: Does the tool need capability/confirmation gating? → A: No. The `loops` agent's single intent `manage` is already `Mode.AUTONOMOUS` and covers `close_loop`/`drop_loop`. Tracking is lower-risk than those: it adds a private, user-requested, non-outbound record that the user can list and drop. A confirmation per "keep that in mind" would defeat the feature. The tool is `constraint_gate=False`.
- Q: Reversibility declaration? → A: `REVERSIBLE`, `undo_tool="drop_loop"`, `effect_phrase="started tracking an open loop"`, with an `undo_note` that says dropping removes the loop (including a pre-existing one that was only reinforced). Retry (165) reads this: a turn with a `track_loop` call is not retryable ("It can be undone separately, but Retry does not undo actions"). That is the honest behavior: a retry must not run the tool twice.
- Q: Honesty enforcement? → A: Two layers. (1) Prompt: the agent may say it is tracking only after `track_loop` returned `ok: true` in this turn. (2) Code: `enforce_domain_cancel_confirmations` gains a tracking-claim family (EN + PT) that strips sentences claiming a loop is being tracked unless a flattened `track_loop` call returned `ok: true`, in the same style as `_CLOSE_CLAIM`. A fully stripped reply becomes `I could not track that.`
- Q: Routing calibration rows? → A: The existing training rows `train-loops-radar-*` and `train-loops-hold-*` already cover this intent. Add two training rows (EN + PT) in `eval/calibration/routing.jsonl` for the explicit-track wording ("put the lease renewal on my radar"). Never edit `routing_holdout*.jsonl`. No re-calibration of bars.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - "Keep that on my radar" really saves a loop (Priority: P1)

The user says "I haven't decided about the Porto move, keep it on my radar". Routing sends the turn to the loops agent. The agent calls `track_loop` with a short title. The tool creates an `active` `user_declared` loop at 0.9 with a 7-day drift deadline through the contribution seam. Only then does the agent say it is tracking the matter. The loop appears in the open-loops list and on `GET /api/v0/loops`.

**Why this priority**: This closes the memory-honesty hole. Without it the agent's confirmation is a promise nothing keeps.

**Independent Test**: Run the agent with a scripted LLM that calls `track_loop`; the fake store holds one loop with the expected fields, the contribution passed `validate_and_submit`, and the final text is unchanged by the enforcer.

**Acceptance Scenarios**:

1. **Given** no matching loop, **When** `track_loop(title="Decide about the Porto move")` runs, **Then** one `OpenLoop` is created with state `active`, provenance `user_declared`, claim kind `PRIORITY`, confidence 0.9, `confirmed_at` set and `drift_deadline = confirmed_at + 7 days`, and the result is `{ok: true, outcome: "created", id, title, state: "active"}`.
2. **Given** `window_days=14`, **When** the tool runs, **Then** the deadline is 14 days out; `window_days=0`, absent, negative or non-integer gives 7; 400 clamps to 365.
3. **Given** an empty or whitespace title, **When** the tool runs, **Then** nothing is created and the result is `{ok: false, error: ...}`.
4. **Given** the tool failed (store error or seam rejection), **When** the agent replies, **Then** the reply carries no tracking claim (enforced in code, see Story 5).
5. **Given** entity resolution fails, **When** the tool runs, **Then** the loop is still created, without entity links, and a warning is logged.

---

### User Story 2 - Asking twice does not duplicate (Priority: P1)

The user already has a `suspected` loop "Switch banks" (inferred by the gate last week). Today they say "keep the bank switch on my radar". The tool finds the match and confirms it instead of creating a second one. If a matching `active` loop exists it is reinforced. If it is `drifting` it is revived. A dropped match does not block a fresh loop.

**Why this priority**: Without dedup, every repeat creates noise on the Priority page and double drift alerts.

**Independent Test**: Seed the fake store with one loop per state; assert the outcome string and resulting fields per state; assert `loop_store.create` is called only for no match and for `dropped`.

**Acceptance Scenarios**:

1. **Given** a matching `suspected` loop, **When** the tool runs, **Then** it becomes `active` with confidence 0.9 and a drift deadline, outcome `confirmed`, and no loop is created.
2. **Given** a matching `active` loop, **When** the tool runs, **Then** its confidence is `max(current, 0.9)`, evidence links are refreshed, outcome `reinforced`, its state is unchanged, and no loop is created.
3. **Given** a matching `drifting` loop, **When** the tool runs, **Then** it moves to `active` through the explicit-ask transition, confidence is set to 0.9, `drift_rationale` is cleared, the deadline is reset to `now + window`, outcome `revived`.
4. **Given** the only match is `dropped` (or `closed`), **When** the tool runs, **Then** a fresh loop is created; the old row is untouched.
5. **Given** two open loops could match, **When** the tool runs, **Then** `find_matching_loop`'s existing selection decides (single entity match wins, else best E5 score at or above 0.75); the tool adds no new matching rule.
6. **Given** a revived, confirmed or created loop, **When** the write completes, **Then** exactly the fields listed in the revive clarification are set, and `confirmed_at` equals `updated_at` (same statement). Whether the sweep later selects the loop is phase 170's concern.

---

### User Story 3 - One request, one loop: the post-turn gate steps aside (Priority: P1)

On a turn where `track_loop` returned `ok: true`, `write_memory` does not call the loop admission. No System One request is made for loops, no `is_open_concern` judgment rows are added to the trace, and no second loop appears. On every other turn the 168 gate behaves exactly as today.

**Why this priority**: The 168 gate would otherwise read the same user text, say `explicit_declaration`, and `_create_declared_loop` (which bypasses matching) would create a duplicate.

**Independent Test**: A `write_memory` test with a result whose flattened tool calls hold a successful `track_loop`: the `loop_admission` mock is never awaited. With a failed `track_loop` (or none), it is awaited as before.

**Acceptance Scenarios**:

1. **Given** a result containing a successful `track_loop` call (top level or nested inside a `delegate_to_agent` result), **When** `write_memory` runs, **Then** `loop_admission` is not called and no loop judgment rows are appended.
2. **Given** `track_loop` returned `ok: false` or raised, **When** `write_memory` runs, **Then** the gate runs as normal and may create a loop.
3. **Given** an eval or retry turn, **When** `write_memory` runs, **Then** behavior is unchanged (the existing guard already skips the gate).
4. **Given** the fact extractor on the same turn, **When** `track_loop` succeeded, **Then** the fact extractor still runs (only the loop gate is skipped).

---

### User Story 4 - A held-for-later concern can still be picked up by the gate (Priority: P2)

A user who talks about a worry without asking Ze to track it still gets the 168 behavior (suspected loop at 0.3, or declared if explicit). This phase must not change that. The only change on that path: the loops agent no longer needs the gate to honor an explicit "keep it on my radar".

**Why this priority**: Guards against regression of 168 and against scope creep into the gate.

**Independent Test**: The unmodified 168 tests (`test_admission.py`, `test_extraction.py`, `test_loop_admission_node.py`) pass with no edits except new cases.

**Acceptance Scenarios**:

1. **Given** a companion turn with no `track_loop` call, **When** `write_memory` runs, **Then** the gate runs and creates the same loops as before this phase.
2. **Given** the loop gate surface off, **When** the loops agent calls `track_loop`, **Then** the tool still works (it does not depend on System One).

---

### User Story 5 - The agent cannot claim tracking it did not do (Priority: P1)

If the model writes "I'll keep that on my radar" and `track_loop` did not succeed this turn, the sentence is removed. If nothing is left, the reply is `I could not track that.` If the tool succeeded, the reply is untouched. The same guard already exists for close/drop (`loop_review_earned`).

**Why this priority**: The tool alone does not stop a model from skipping it. Code, not prompt, must enforce honesty (memory-honesty roadmap, phases 143, 146).

**Independent Test**: Table-driven tests of `enforce_domain_cancel_confirmations` with EN and PT claims, with and without an earned `track_loop` call, including a nested call and a call returning `ok: false`.

**Acceptance Scenarios**:

1. **Given** the reply "Got it, I'm keeping that on my radar." and no `track_loop` call, **Then** the reply becomes `I could not track that.`
2. **Given** the same reply and a successful `track_loop`, **Then** the reply is unchanged.
3. **Given** a Portuguese claim ("Fico atento a isso", "Já está no meu radar") and no earned call, **Then** it is stripped.
4. **Given** a reply that only offers ("Want me to keep this on your radar?") or lists loops, **Then** it is not stripped (claims only; offers and list output are not claims).
5. **Given** a reply claiming both a close and a track, **Then** each claim is judged against its own earned flag.

---

### User Story 6 - Evals show track then list, EN and PT (Priority: P2)

A multi-turn eval scenario sends "keep the Porto move on my radar" then "what am I still sitting with?" and checks that the second turn lists the first. A Portuguese twin does the same. Each verifies an `open_loops` row exists after the first turn and cleans up.

**Why this priority**: The unit tests use fakes. Only the eval proves routing, the tool call, the stored row and the list round trip together.

**Independent Test**: `ze_list_scenarios()` shows both; a live `make eval` run passes routing and the `verify` check.

**Acceptance Scenarios**:

1. **Given** the EN scenario, **When** it runs, **Then** `expected_agent` is `loops` on the last turn, `verify` finds an `open_loops` row with the title (which only the `track_loop` call can have written, since eval threads skip the post-turn gate), and the judge criteria require turn two to list it.
2. **Given** the PT scenario, **When** it runs, **Then** the same holds and the title is in Portuguese.

---

### Edge Cases

- Title longer than 120 characters: trimmed to 120 on a word boundary; empty after trimming: error result.
- Two `track_loop` calls in one turn (the agent tracks two concerns): each is independent; the second may match the first and report `reinforced`. The gate skip applies if any call succeeded.
- `track_loop` succeeded but the reply is produced by the conductor synthesis: the nested-call flattening in `flatten_tool_calls` finds it; the skip still applies.
- A `track_loop` call whose result is a JSON string rather than a dict: parsed with `tool_payload`, as for close/drop.
- The user asks to track something they previously dropped, with identical evidence: a fresh loop is created (answer 2); the dropped row keeps its fingerprint.
- Concurrent `track_loop` and the sweep on the same loop: the revive uses a guarded update (`WHERE state = 'drifting'`); a lost race returns `{ok: false, error: ...}` and the agent reports the failure.
- `window_days` supplied as a float or string by the model: coerced with the existing `_whole_days` rules; invalid means default.
- Memory hooks from other plugins still run on this turn; only the worldstate gate is skipped.
- Eval threads skip write-side effects of `write_memory`, but tool calls execute, so `track_loop` does write in evals. The `verify` block cleans it up.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The loops agent MUST expose a WRITE tool `track_loop(title: str, window_days: int = 0)`. Its description MUST tell the model to call it only when the user explicitly asks to keep something in mind, to call `list_open_loops` first only if unsure of a duplicate, and to never claim tracking before the tool returned `ok: true`. `window_days` is `int` with default 0 because the tool schema builder (`ToolSpec.llm_schema`) drops non-primitive annotations such as `int | None`.
- **FR-002**: With no matching open loop, the tool MUST create an `OpenLoop` with provenance `USER_DECLARED`, state `ACTIVE`, claim kind `PRIORITY`, confidence 0.9, `confirmed_at = now` and `drift_deadline = now + window` (7 days by default), through `loop_to_contribution` and `submit_and_detect_collisions`, with the same `producer_kind="open_loop"` as the gate.
- **FR-003**: `window_days` MUST be clamped to 1-365; zero, absent, negative, non-numeric or boolean means the 7-day default.
- **FR-004**: The title MUST be whitespace-normalized and capped at 120 characters; an empty title MUST return `{ok: false, error}` and write nothing.
- **FR-005**: The tool MUST resolve entities from the title text with the worldstate entity resolver and link them (and no evidence refs), failing open: a resolver error logs a warning and the loop is created without entity links.
- **FR-006**: Before creating, the tool MUST call `find_matching_loop` with `states=["suspected","active","drifting"]`. A match MUST NOT produce a second loop. By state: `suspected` → confirm to `active`, confidence 0.9, drift deadline set (`confirmed`); `active` → confidence `max(current, 0.9)`, entity links refreshed (`reinforced`); `drifting` → revive (`revived`, FR-007). A `dropped` or `closed` match MUST NOT block creation and the fingerprint rule MUST NOT be consulted.
- **FR-007**: The store MUST allow `drifting → active` only through an explicit-ask path. `LoopStore.transition(loop_id, new_state, *, user_asked: bool = False)`; the new edge is permitted only when `user_asked=True`. The REST `confirm` route, `review.confirm_loop`, the decay cascade and the drift sweep MUST keep rejecting it. A revive MUST set confidence 0.9, clear `drift_rationale`, stamp `confirmed_at`, and set a new drift deadline (`now + window`).
- **FR-008**: The tool result MUST be a dict `{ok, outcome, id, title, state}` on success (`outcome` one of `created`, `confirmed`, `reinforced`, `revived`) and `{ok: false, error}` on every failure. It MUST NOT raise to the agent loop.
- **FR-009**: A loop written by `track_loop` (created, confirmed or revived) MUST get `confirmed_at` and `updated_at` from the same SQL `now()` in one statement (`stamp_declared`), together with `confidence`, `drift_deadline` and `drift_rationale = NULL`, per the revive clarification. This documents the exact write. It is not a fix for finding F1 (see Assumptions).
- **FR-010**: `write_memory` MUST NOT call `loop_admission` when any flattened tool call in the turn's `AgentResult` is a `track_loop` call whose payload has `ok: true`. The fact extractor, event extractor, entity extractor and `memory_hooks` MUST run as before. The skip MUST be logged at debug with the loop id.
- **FR-011**: `enforce_domain_cancel_confirmations` MUST strip sentences that claim a loop is being tracked (EN and PT patterns) unless a flattened `track_loop` call returned `ok: true`. A fully stripped reply MUST be `I could not track that.` Offers, questions and list output MUST NOT match. Existing cancel/close/abandon/forget behavior MUST be unchanged.
- **FR-012**: `track_loop` MUST declare `reversibility=REVERSIBLE`, `undo_tool="drop_loop"`, an `undo_note` and `effect_phrase="started tracking an open loop"`. `validate_tool_declarations()` MUST pass. A turn with a `track_loop` call MUST be not retryable (`HAS_REVERSIBLE_ACTION`), as 165 already decides from the declaration.
- **FR-013**: `LoopsAgent` MUST list `track_loop` in `tools`, update its intent description and `_AGENT_INSTRUCTIONS` (when to track, one call per distinct concern, confirm only after success, say which outcome happened), and keep `Mode.AUTONOMOUS`. The agent's `description` and `routing_criteria` MUST mention tracking so E5 and the Choice stay aligned.
- **FR-014**: The tool's collaborators (store, graph store, entity resolver, embedder, collision store, NLI client) MUST reach it through one injected service, `LoopTracker`, built in `ze_api/container.py` and registered in the agent dependency map by type. The tool function receives it as the `loop_tracker` dep. `ze_worldstate` MUST NOT import `ze_core`; plugins MUST NOT import `ze_worldstate`.
- **FR-015**: Two EN/PT eval scenarios (Story 6) MUST be added, and two training rows in `eval/calibration/routing.jsonl`. Held-out files MUST NOT be edited.
- **FR-016**: No new migration. No new REST route. No `ze-web` change.

### Key Entities

- **LoopTracker**: service in `ze_worldstate/tracking.py` holding the collaborators; `track(title, window_days) -> TrackResult`.
- **TrackResult**: dataclass with `ok`, `outcome`, `loop`, `error`.
- **TrackOutcome**: string constants `created`, `confirmed`, `reinforced`, `revived`.
- **User-asked transition**: the `drifting → active` edge in `LoopStore.transition`, valid only with `user_asked=True`.
- **Tracking claim**: a sentence stating that a concern is being tracked or kept in mind, matched by `_TRACK_CLAIM`.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In a scripted turn where the agent calls `track_loop`, the loop exists in the store before the reply text is final, in 100% of unit-test runs; with the tool failing, no reply contains a tracking claim.
- **SC-002**: A repeated request for the same concern yields exactly one open loop across 4 consecutive asks (unit test, per state).
- **SC-003**: On a turn with a successful `track_loop`, zero loop-gate System One requests and zero second loops (asserted with call-counting fakes).
- **SC-004**: `make test`, `make test-worldstate`, `make test-core`, `make test-agents` and `make lint` pass; the 168 and 109 tests pass with no edits to existing cases.
- **SC-005**: Both eval scenarios pass routing and the `verify` check in one live run; the routing training set stays 100% on its loops rows, and no held-out file changed (`git diff` empty for them).
- **SC-006**: Every tracking claim in the table-driven honesty test set (at least 6 EN, 6 PT) is stripped without an earned call and kept with one.

## Assumptions

- **Drift sweep is inert until phase 170 (finding F1).** `list_drift_candidates` requires `updated_at <= confirmed_at`, but `set_drift_deadline` and `transition` bump `updated_at` after `confirmed_at` is set, so no loop is a drift candidate. Phase 170 fixes this with an explicit `last_activity_at` column, after 169 lands. 169 changes none of that machinery; `stamp_declared` is only the precise write for a user-asked loop and 170 may replace it. Unverified on a live database.
- A reinforced `active` loop becomes drift-ineligible after the write, because `set_confidence` bumps `updated_at`. This is the existing meaning of "corroborating evidence since confirmation" and is intended.
- Reinforce and revive are state edits on an existing claim, not new claims, so they skip the contribution seam. If the seam later requires a "reinforcement" contribution type, that is a separate phase.
- `undo_tool="drop_loop"` on a reinforced pre-existing loop drops that loop; the `undo_note` says so. Accepted: the user's undo intent is "stop tracking this".
- Routing still decides whether a turn reaches the loops agent. A "keep that in mind" turn the router sends to the companion stays on the 168 path (gate, suspected or declared). Giving the companion a track tool is out of scope.
- The enforcer's claim regex is conservative and pattern-based, like its siblings; a paraphrase it misses is still bounded by the prompt rule and the tool-first flow.
