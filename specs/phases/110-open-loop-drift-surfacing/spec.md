# Feature Specification: Open-Loop Drift Detection & Surfacing

**Feature Branch**: `110-open-loop-drift-surfacing`

**Created**: 2026-07-23

**Status**: Implemented

**Input**: User description: "Open-Loop Drift Detection & Surfacing (Phase B of the Open-Loop Substrate, Phase A being specs/phases/109-open-loop-substrate/). Governed by specs/arch/ze-doctrine.md and specs/arch/aperture-decision.md (Option A ratified). Phase A built the OpenLoop substrate (capture, epistemic posture, lifecycle, memory-graph linkage) but loops are inert — only visible on explicit user request. Phase B must add: (1) automatic drift detection — heuristics that move an `active` loop to `drifting` when reality diverges from its implied plan/timeline; (2) proactive/inline surfacing and the interruption bar — deciding when a drifting or otherwise-notable loop earns a mention or a push notification, reusing the correlation engine's existing inline-vs-push asymmetry and calibrated surfacing bar. Must preserve the doctrine's arbitration order and claim-kind posture rules. Out of scope: goal↔loop unification, and building the generalised contribution seam as a standalone abstraction."

## Clarifications

### Session 2026-07-23

- Q: Should proactive pushes for drifting open loops share the correlation engine's existing daily push budget/counter, or use their own separate budget? → A: Separate sibling budget, independently configured for open loops.
- Q: Should `ze-worldstate` take a new direct package dependency on `ze-correlation` to reuse its push-bar mechanics, or reimplement the same algorithm locally? → A: New direct dependency — `ze-worldstate` imports and calls `ze-correlation`'s push mechanics directly; this is a new edge in the package dependency graph (`ze-worldstate` currently depends only on `ze-agents`, `ze-proactive`, `ze-memory`, `ze-data`, `ze-components`) and `CLAUDE.md`'s dependency graph table must be updated accordingly.
- Q: How should a drifting loop's inline mention get injected into a conversational turn's response — a new dedicated orchestration-graph node, or by extending the correlation engine's existing inline-connections node to also query loops? → A: A new dedicated graph node owned by the open-loop side, running alongside (not inside) the correlation engine's inline node; each node reads only its own domain's store, so this path introduces no new dependency edge (unlike the push path).
- Q: What default drift window should apply to a loop with no explicit implied timeframe, before it's eligible to be flagged as drifting? → A: 7 days — shorter than Phase A's ~14-day stale-suspicion expiry, since an active/confirmed loop is a stronger claim than an unconfirmed suspicion and warrants a sooner drift check.
- Q: What should determine that a drifting loop is "topically relevant" to the current turn, for the inline-mention check? → A: Entity-link overlap only — the turn's resolved entities overlap with the loop's linked entities, reusing Phase A's existing entity-resolution/matching infrastructure with no new per-turn embedding calls.

**Governed by**: [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md) (constitutional) and
[`specs/arch/aperture-decision.md`](../../arch/aperture-decision.md) (Option A ratified). This
is **Phase B of two** for the open-loop substrate; Phase A
([`109-open-loop-substrate`](../109-open-loop-substrate/spec.md)) built capture, epistemic
posture, lifecycle, and memory-graph linkage, and explicitly deferred everything in this spec.
This feature also reuses the surfacing discipline built for the correlation engine
([`specs/arch/correlation-engine.md`](../../arch/correlation-engine.md), Phases 58–59) rather
than inventing a second one.

---

## Overview

Phase A gave Ze a first-class primitive for unfinished business — the `OpenLoop` — but a loop,
once captured, is inert. It sits in `suspected` or `active` state and is only visible when the
user explicitly asks to review their loops. Nothing in the system currently notices when a loop
is going stale relative to what it implied, and nothing decides when a loop deserves a mention.
The doctrine names this precisely: reflection and perception are already feeding a hub whose
executive face has "no strong representation of what is open and what deserves attention"
(`docs/cognitive-architecture.md`). Phase A closed the *representation* half of that gap; this
feature closes the *attention* half.

Concretely, this feature adds two capabilities on top of the existing `ze-worldstate` substrate:

1. **Drift detection** — heuristics that recognise when an `active` loop's reality has
   diverged from what it implied (no observed progress within an expected window,
   contradicting evidence, an adverse change to a linked entity) and transition it to the
   already-defined `drifting` state (`LoopState.DRIFTING` exists in Phase A's types but nothing
   writes it yet).
2. **Surfacing** — deciding when a drifting (or otherwise notable) loop earns an inline mention
   during a turn, or an unprompted push, using the same two-tier bar the correlation engine
   already uses (low inline bar, high calibrated push bar with novelty/budget/grounding gates).

Both capabilities produce **inferences**, never facts, about the state of a loop — the doctrine's
"reflection may never emit a fact" rule applies in full: Ze may notice a loop looks like it's
drifting and offer that as a hedged observation, but it never asserts the loop *is* abandoned,
and it never auto-closes or auto-escalates a loop off the back of its own inference.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A stalling commitment is quietly flagged as drifting (Priority: P1)

An `active` loop ("send Maria the contract this week") passes its implied window with no new
supporting evidence (no email sent, no calendar event, no conversational update). Ze recognises
the drift and moves the loop to `drifting` state with an attached, evidence-cited rationale —
without notifying the user yet and without taking any action on the loop's behalf.

**Why this priority**: This is the detection half and the prerequisite for everything else in
this feature. Without it, "drifting" stays a dead enum value and there is nothing for the
surfacing logic to act on.

**Independent Test**: Seed an `active` loop with an implied timeframe that has since elapsed and
no corroborating evidence; run the drift sweep; verify the loop transitions to `drifting`, that
a rationale citing the absence of evidence is stored, and that no notification was sent and no
loop state beyond `drifting` changed.

**Acceptance Scenarios**:

1. **Given** an `active` loop whose implied window has elapsed with no new evidence, **When**
   the drift sweep runs, **Then** the loop transitions from `active` to `drifting`, and the
   drift rationale is recorded as an inference, not a fact.
2. **Given** an `active` loop with fresh corroborating evidence linked since confirmation,
   **When** the drift sweep runs, **Then** the loop remains `active`.
3. **Given** an `active` loop whose linked entity now has evidence directly contradicting the
   loop's premise (e.g. the meeting it was about was cancelled), **When** the drift sweep runs
   or the contradiction is written, **Then** the loop transitions to `drifting` immediately
   rather than waiting for the next scheduled sweep.
4. **Given** a loop already in `drifting`, `closed`, `dropped`, or `suspected` state, **When**
   the drift sweep runs, **Then** it is left unchanged (drift detection only ever applies to
   `active` loops).

---

### User Story 2 - A drifting loop is mentioned inline when the topic comes up (Priority: P1)

The user brings up a topic in conversation that overlaps with a `drifting` loop (e.g. asks about
Maria, or about their week). Ze's response includes a brief, hedged mention of the drifting loop
— "by the way, it looks like you haven't followed up with Maria on the contract yet" — using the
same low-bar, no-interruption-cost inline surfacing the correlation engine already uses for
hypotheses.

**Why this priority**: Inline is the lower-risk delivery surface — the user already opened the
conversational door, so the cost of a miss is low. It is also independently valuable without
needing the (higher-risk) push mechanism, mirroring the correlation engine's own Phase 58→59
sequencing.

**Independent Test**: Have the user reference an entity linked to a `drifting` loop during a
turn; verify the response includes a hedged, evidence-linked mention of the loop; verify a
turn whose resolved entities do not overlap with any drifting loop's linked entities produces no
mention.

**Acceptance Scenarios**:

1. **Given** a `drifting` loop linked to an entity, **When** the user's turn references that
   entity, **Then** the response may include a hedged mention of the loop with its evidence
   available, phrased as an observation ("it looks like…"), never as a verdict.
2. **Given** no `drifting` loop shares a linked entity with the turn's resolved entities, **When**
   the turn is processed, **Then** no loop mention is added.
3. **Given** a `drifting` loop was already mentioned inline in a recent turn, **When** the same
   topic recurs, **Then** it may be mentioned again (inline has no novelty/budget gating, per
   the existing correlation-engine asymmetry).

---

### User Story 3 - A high-confidence drifting loop earns a proactive nudge (Priority: P2)

Independent of conversation, a `drifting` loop that clears a much higher bar — confidence,
grounded evidence, relevance, novelty, and daily push budget — is worth interrupting the user
about even though they didn't ask. Ze sends a single push notification through the existing
notification channel, phrased as a hedged nudge, not a directive.

**Why this priority**: This is the higher-risk delivery surface. It depends on User Story 1
(nothing to push without drift detection) and benefits from User Story 2 having already
validated the surfacing framing; it is P2 because — exactly as the correlation engine's own
roadmap did — inline should be allowed to prove itself first.

**Independent Test**: Seed a `drifting` loop that clears every push-bar condition; run the push
sweep; verify exactly one push notification is sent, that it is logged so the same loop is not
re-pushed within the novelty window, and that a `drifting` loop failing any single condition
(confidence, relevance, novelty, grounding, budget) produces no push.

**Acceptance Scenarios**:

1. **Given** a `drifting` loop with confidence, relevance, and grounded evidence all above their
   respective push thresholds, and within the daily push budget, **When** the push sweep runs,
   **Then** a push notification is sent describing the loop as a hedged observation.
2. **Given** a `drifting` loop that was pushed recently, **When** the push sweep runs again
   before the novelty window elapses, **Then** it is not pushed a second time.
3. **Given** the daily push budget dedicated to open loops (a sibling counter, separate from the
   correlation engine's own budget) is exhausted, **When** a qualifying drifting loop is found,
   **Then** it is not pushed until the budget resets.
4. **Given** a loop clears confidence and relevance but its evidence no longer passes the
   grounding check (e.g. the cited fact was itself contradicted since the loop drifted),
   **When** the push sweep runs, **Then** it is not pushed.

---

### Edge Cases

- What happens when a loop drifts, gets mentioned inline, and is then confirmed/closed/dropped
  by the user in the same session? The push sweep must not push a loop that changed state after
  the drift sweep ran but before the push sweep executes — re-check current state immediately
  before sending.
- How does the system handle a loop with no implied timeframe at all (e.g. an open-ended
  "keep an eye on X")? Such loops use the default 7-day drift window rather than being silently
  exempt from drift detection forever.
- What happens if the same loop would independently qualify for both an inline mention and a
  push in the same period? The two surfaces are not mutually exclusive per the existing
  correlation-engine asymmetry, but a push should not immediately follow an inline mention of
  the same loop within a short cooldown, to avoid the user experiencing the same nudge twice.
- How does drift detection treat a loop whose evidence was only ever a `suspicion`-kind
  inference rather than a confirmed fact? Drift rationale must cite what evidence exists (or its
  absence) honestly rather than implying stronger grounding than the loop actually has.
- What happens when the drift sweep or push sweep encounters a transient failure (store or LLM
  error) partway through a batch? Already-processed loops keep their transitions; the failure is
  logged and the remaining loops are retried on the next scheduled run, consistent with existing
  job patterns (`stale_suspicion.py`).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST detect when an `active` open loop has had no new corroborating
  evidence within its implied drift window, or within a default 7-day drift window when no
  timeframe was implied, and transition it to `drifting`.
- **FR-002**: The system MUST detect when evidence contradicting a loop's premise is written
  (via the same write-time contradiction path Phase A's decay cascade already hooks into) and
  transition the affected `active` loop to `drifting` immediately, without waiting for the next
  scheduled sweep.
- **FR-003**: The system MUST run periodic drift detection as a scheduled job, reusing the
  existing `ze-proactive` scheduler pattern established by Phase A's stale-suspicion job.
- **FR-004**: The system MUST leave loops in any state other than `active` untouched by drift
  detection.
- **FR-005**: Every drift transition MUST record a rationale that cites the evidence (or
  documented absence of evidence) it was based on, tagged as an inference — never presented to
  the user as an established fact.
- **FR-006**: The system MUST support inline surfacing of a `drifting` loop during a
  conversational turn when the loop is topically relevant to that turn — determined by entity-
  link overlap between the turn's resolved entities and the loop's linked entities, reusing Phase
  A's existing entity-resolution/matching infrastructure — using a low bar with no novelty or
  budget gating, mirroring the correlation engine's inline surfacing discipline, via a dedicated
  orchestration-graph step owned by the open-loop side that runs alongside — not inside — the
  correlation engine's own inline node, so the two domains stay decoupled.
- **FR-007**: The system MUST support proactive/push surfacing of a `drifting` loop, gated by
  all of: a high confidence threshold, a relevance threshold, grounded evidence, novelty (not a
  near-duplicate of a recently pushed loop), and a push-rate budget — by taking a direct
  dependency on and calling into the correlation engine's existing push-bar mechanics
  (`ze-correlation`) rather than defining a second, divergent implementation of the same
  algorithm — but tracked against a separate, independently configured daily push budget
  dedicated to open loops (not shared with the correlation engine's own budget), so a burst of
  one kind cannot starve the other.
- **FR-008**: The system MUST log every push so that the same loop is not pushed again within
  the novelty window, mirroring the correlation engine's `PushLogStore` usage.
- **FR-009**: Every surfaced mention (inline or push) of a drifting loop MUST be phrased as a
  hedged observation ("it looks like…") and MUST never assert the loop's drifted or abandoned
  state as a verdict, per the doctrine's claim-kind posture rules.
- **FR-010**: The system MUST NOT autonomously close, drop, confirm, or otherwise change a
  loop's lifecycle state as a side effect of drift detection or surfacing — only the user's
  explicit action (existing Phase A review flow) may do so.
- **FR-011**: The system MUST re-check a loop's current lifecycle state immediately before
  sending a push, and skip the push if the loop is no longer `drifting` (e.g. the user already
  closed it).
- **FR-012**: The system MUST NOT push a mention of the same loop within a short cooldown period
  after that loop was already mentioned inline, to avoid duplicate interruptions of the same
  concern.
- **FR-013**: Drift detection and surfacing MUST both be implemented as direct calls — within
  `ze-worldstate` and its existing call sites (conversation turn assembly, the drift/push
  scheduled jobs), and via a new direct dependency from `ze-worldstate` to `ze-correlation` for
  the push-bar mechanics specifically — consistent with Phase A's style and explicitly not as a
  new generalised contribution-seam abstraction (`specs/arch/contribution-seam.md` remains
  design-only).
- **FR-014**: This feature MUST NOT modify the goal engine or introduce any unification between
  goals and loops.

### Key Entities *(include if feature involves data)*

- **Drift rationale**: the evidence-cited explanation attached to a loop's `active` → `drifting`
  transition — what is present, what is missing, or what contradicts it. An inference-kind
  annotation on the existing `OpenLoop`, not a new claim-kind.
- **Drift window**: the expected/default time-to-progress used to judge staleness for a given
  loop; derived from the loop's own implied timeframe when stated, falling back to a documented
  system default when the loop is open-ended.
- **Surfacing decision**: the record of whether and how (inline/push/neither) a `drifting` loop
  was surfaced for a given opportunity, reusing the correlation engine's existing push-log
  pattern for the push path.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: An `active` loop whose implied window elapses with no corroborating evidence is
  found in `drifting` state on the next scheduled sweep, with a stored rationale — demonstrating
  the "attention" half of the executive-function gap is no longer empty.
- **SC-002**: 100% of drift transitions and surfaced mentions are inference-posture, hedged
  language — none assert a loop's state as an observed fact, verified by inspecting surfaced
  copy and stored rationale kind.
- **SC-003**: 100% of loops surfaced via push clear every one of the push-bar conditions
  (confidence, relevance, grounding, novelty, budget); no push bypasses any single condition.
- **SC-004**: On a representative sample of turns with no topically relevant drifting loop, the
  system adds no inline mention (no false-positive surfacing).
- **SC-005**: No loop is ever auto-closed, auto-dropped, or auto-confirmed by this feature —
  100% of lifecycle-terminal transitions in logs/telemetry trace back to an explicit user action.
- **SC-006**: A loop that is closed or dropped by the user between the drift sweep and the push
  sweep is never pushed — zero stale pushes against already-resolved loops in testing.

---

## Assumptions

- **Drift window default**: loops without an explicit implied timeframe use a default drift
  window of 7 days — shorter than Phase A's ~14-day stale-suspicion expiry, since an `active`,
  user-confirmed loop is a stronger claim than an unconfirmed `suspected` one and warrants a
  sooner drift check (see Clarifications).
- **Reuse, not reinvention, of the push bar**: this feature takes a new direct package dependency
  from `ze-worldstate` on `ze-correlation` and calls its existing push mechanics
  (`core/ze-correlation/ze_correlation/push.py`'s threshold/novelty/budget/grounding pattern) for
  open loops rather than defining a parallel implementation, but tracks its own daily push budget
  as a sibling counter dedicated to open loops rather than sharing the correlation engine's
  budget (see Clarifications). `CLAUDE.md`'s package dependency graph table must be updated in
  the same commit as this dependency is introduced, per the constitution's Governance principle.
- **Inline surfacing hook point**: inline mentions are injected via a new, dedicated
  orchestration-graph step in the same phase of turn assembly the correlation engine already uses
  for its own inline connections (Phase 58), running alongside that node rather than extending
  it — so this path, unlike the push path, introduces no new package dependency (see
  Clarifications).
- **Contribution seam remains design-only**: this feature is intended to become the seam's
  second real client eventually, but per `contribution-seam.md` it must not build the
  generalised abstraction now — direct calls only, structured so extraction later is feasible.
- **No new UI paradigm**: the review/list surface from Phase A already displays `drifting` loops;
  this feature does not require new web UI beyond ensuring drift rationale is visible there.
- **Single-user model**: consistent with the constitution — no per-user scoping.
