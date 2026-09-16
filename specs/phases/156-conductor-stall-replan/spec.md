# Feature Specification: Conductor Stall / Replan

**Feature Branch**: `156-conductor-stall-replan`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "156 Stall / replan: Turn-local Magentic-One-style outer loop — stall, rebrief next specialist with new prior_outputs, cap flailing delegates, ledger statuses stalled/replanned, user-visible ask vs silent retry policy pinned in research.md. Engine-enforced, not only a prompt. No durable workflow/goal rows. Depends on 155."

**Governed by**: [`specs/arch/companion-conductor-roadmap.md`](../../arch/companion-conductor-roadmap.md) phase 156, [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md), [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), mixed rewrite [`155-mixed-gather-act-conductor`](../155-mixed-gather-act-conductor/spec.md), sequential conductor [`153-sequential-routing-hard-cut`](../153-sequential-routing-hard-cut/spec.md), fat ACI [`151-fat-delegate-aci`](../151-fat-delegate-aci/spec.md), per-delegate gate [`152-per-delegate-gate`](../152-per-delegate-gate/spec.md), observability [`154-conductor-observability-eval`](../154-conductor-observability-eval/spec.md). Companion MUST NOT import calendar or messenger tools.

**Depends on**: 155 so gather+act actually reaches the conductor. 151 `prior_outputs`. 153/154 ledger on `MessageTrace`.

**Does not start**: 157 promote; parallel per-subtask gates; procedures; swarm.

---

## Overview

153’s conductor judge is prompt-only: companion is told to decide done / next / ask-user, but nothing in the engine stops a specialist from being called in a loop when the result is empty or useless. Mixed gather+act (155) makes that worse because more turns now enter the conductor.

This phase adds a **turn-local** Magentic-One-style outer loop: detect stall, rebrief the next (or same) specialist with updated `prior_outputs`, cap flailing delegates, and record `stalled` / `replanned` on the ledger the trace already shows. Silent retry vs asking the user is a pinned policy (research), enforced in the delegate path — not only extra prompt text. No workflow or goal row is created because a specialist stalled.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A stalled specialist is replanned once, then Ze asks (Priority: P1)

Companion is conducting (sequential or mixed). A specialist returns a stall (empty or error result with no usable output). The engine records `stalled`, allows **one** silent retry of the **same** specialist with fresh `prior_outputs` / `inputs`, ledger `replanned` then `running`. Choosing a different next specialist after a **success** stays companion’s inner loop (153), not an engine auto-switch after stall. If that still stalls or the per-specialist cap is hit, companion must ask the user (`ask_user`) instead of calling the specialist again. The user sees the ask in chat and on the trace ledger — not an endless mute wait.

**Why this priority**: Prompt-only judge is how flailing hides after 155.

**Independent Test**: Stub `run_delegate` to return stall twice. First extra call allowed; third blocked. Ledger contains `stalled` and `replanned`. Companion-facing result tells the model to ask, not to loop.

**Acceptance Scenarios**:

1. **Given** a conductor turn and a specialist result that is a stall, **When** companion would delegate that specialist again, **Then** the first retry is allowed, `prior_outputs` on that call include the stall context, and the ledger has `stalled` then `replanned`.
2. **Given** the same specialist has already used its silent retry, **When** companion tries another delegate to that name, **Then** the engine refuses the call and the ledger status is `ask_user` (or stays `stalled` with an ask required — see Assumptions).
3. **Given** a successful specialist after a replan, **When** the turn continues, **Then** the next specialist may run with the successful text in `prior_outputs` (151 unchanged).
4. **Given** a confirmation pause (152), **When** the worker is waiting on the user, **Then** that is not a stall and silent retry MUST NOT fire.

---

### User Story 2 - Caps are engine-enforced (Priority: P1)

Companion cannot prompt its way around the cap. A turn-local counter of `delegate_to_agent` invocations (and per-specialist counts) lives on conductor state. Exceeding the pinned caps blocks further delegates this turn. Speech-act one-shots (one delegate) stay under the cap. Independent parallel graph fan-out is not this loop.

**Why this priority**: “Engine-enforced, not only a prompt” is the product pin.

**Independent Test**: Unit-test the delegate wrapper/hook with a fake companion loop that requests 10 delegates; after the cap, further calls fail closed without invoking the specialist.

**Acceptance Scenarios**:

1. **Given** per-specialist and per-turn caps from research, **When** counts would exceed them, **Then** no additional specialist `run` occurs.
2. **Given** a speech-act turn with a single successful delegate, **When** it finishes, **Then** caps do not ask the user or mark `stalled`.
3. **Given** an independent parallel compound turn (no companion rewrite), **When** specialists gather, **Then** this stall loop does not wrap graph fan-out.

---

### User Story 3 - Trace and progress stay honest (Priority: P2)

154 already shows ask/stall if present. This phase actually writes `stalled` and `replanned` (or the pinned equivalents). Progress MAY emit a conductor key when asking after a stall. Eval covers: stall then successful replan; stall then ask; no promote.

**Why this priority**: 154 display-only stall would lie if 156 never writes the statuses.

**Independent Test**: Fixture ledger with `stalled`/`replanned` still renders (154 panel). New eval or unit ids for stall-then-ask.

**Acceptance Scenarios**:

1. **Given** a stall+replan turn, **When** trace is read, **Then** ledger includes those statuses (154 panel does not need a redesign if it already prints status strings).
2. **Given** the user is asked after a cap, **When** the assistant message is sent, **Then** it is a question or limitation, not a fake completed report.
3. **Given** that turn, **When** stores are queried, **Then** no new workflow or goal row exists because of the stall.

---

## Edge Cases

- Specialist returns a long apology with no facts: stall if research-defined emptiness/error detector matches; otherwise success (do not NLP-classify every reply this phase beyond pinned rules).
- Two specialists: first succeeds, second stalls — retry second only; do not re-run the first unless replan targets it.
- Cap hit mid-turn after a useful first specialist: ask with what is already known; do not discard `prior_outputs`.
- Nested depth stays 1 (151).
- Abort / user cancel: not silent retry; ledger may `skipped`.
- Resume after 152 confirmation: counters persist on turn state / checkpoint, not reset to allow a new flail budget unless research says resume keeps the same turn caps (Assumption: same turn, same caps).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST detect stall on conductor specialist results using the pinned detector in research (not prompt-only). On stall it MUST write `stalled` on the turn-local ledger.
- **FR-002**: The system MUST allow at most one silent retry per specialist name per turn, rebriefing via 151 `prior_outputs` / `inputs`, and MUST write `replanned` when that retry is issued.
- **FR-003**: After the silent retry is used, or when pinned per-turn delegate caps are exceeded, the system MUST block further `delegate_to_agent` to that specialist (or all specialists if the turn cap is hit) and require a user-visible ask (`ask_user`).
- **FR-004**: Stall/replan MUST be enforced in the engine/delegate path (companion-only `delegate_to_agent`), not solely in companion instructions. Instructions SHOULD describe the same policy.
- **FR-005**: Confirmation wait, deny, and 152 resume MUST NOT be classified as stall. Independent parallel graph execution MUST NOT use this loop.
- **FR-006**: 151 ACI fields, 152 gates, 153/155 rewrite, and 154 trace field names MUST remain. New ledger statuses MUST be additive.
- **FR-007**: This phase MUST NOT create workflow/goal rows, MUST NOT implement 157 promote, MUST NOT touch procedures (135–139), MUST NOT restore `_execute_compound` sequential, and MUST NOT split parallel gates.

### Key Entities

- **Stall**: A specialist invocation with no usable output per the research detector.
- **Silent retry / replan**: One engine-allowed extra delegate with updated brief; ledger `replanned`.
- **Ask after flail**: User-visible question; ledger `ask_user`.
- **Turn-local counters**: Per-specialist delegate count and total delegate count this turn (checkpointed with graph state, not a new table).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of tested first-stall fixtures perform exactly one silent retry with new `prior_outputs`.
- **SC-002**: 100% of tested second-stall / cap-hit fixtures invoke 0 further specialist runs and surface an ask.
- **SC-003**: 100% of tested confirmation-wait fixtures are not treated as stall.
- **SC-004**: 0 workflow/goal rows created in stall unit tests.
- **SC-005**: 100% of tested stall/replan turns persist `stalled` and `replanned` on the message trace ledger.

---

## Assumptions

- Silent retry is **one** per specialist **name** per turn, not one globally (two specialists can each retry once) unless the **turn** cap is hit first.
- Turn cap (research): **6** `delegate_to_agent` calls per conductor turn; per-specialist cap **2** (initial + one retry).
- Detector (research): stall if the tool result is an error, empty `response`, or the dedicated failure payload from `run_delegate`; not an LLM-as-judge on every success string this phase.
- Same graph turn (including confirmation resume) shares counters.
- 155 is Implemented before 156 product code.

## Out of Scope

- Promote to workflow/goal (157) when the job must outlive the turn.
- Durable Magentic ledger tables.
- Parallel fan-out stall.
- Procedures / swarm.

## Verbatim Constraints

- `stalled`
- `replanned`
- `ask_user`
- `prior_outputs`
- `inputs`
- `delegate_to_agent`
- `conductor_ledger`
- `MessageTrace`
- Principle VIII

## After this feature / Future work

157 promote when work must outlive the turn (including confirmation that never returns). Specified as `157-promote-conductor-instance`. Do not implement 157 in this tree.
