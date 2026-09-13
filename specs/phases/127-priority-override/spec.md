# Feature Specification: User-Directed Priority Override

**Feature Branch**: `127-priority-override`

**Created**: 2026-08-25

**Status**: Done

**Input**: User description: "User-Directed Priority Override — a follow-up to Phase 123 (Attention Arbitration / PriorityView) that depends on Phase 124 (Contribution Seam Core), Phase 125 (Contribution Seam Extension), and Phase 126 (Contribution Collision Detection). Give the user a snapshot view of PriorityView's current ranked list (loops, stuck/near-gate goals, hypotheses) and let them rearrange priorities two ways: (1) via the UI, by directly dragging items to reorder them, and (2) via conversational means, by telling Ze in chat to reprioritize something. Both paths express the user's intent as a user-stated Contribution (per specs/arch/contribution-seam.md), submitted through Phase 124/125's validated Contribution write path, targeting the same world-state face PriorityView already ranks on -- not a silent override that bypasses the seam. Because a user's explicit reprioritization may conflict with PriorityView's own computed ranking (e.g. the user deprioritizes an item PriorityView's drift/idle-days/confidence math says is most urgent), this is expected to produce real collisions between a user-stated contribution and the executive function's own Priority claim -- Phase 126's collision detector should observe and log these, which is itself evidence for whether real cross-contribution arbitration (contribution-seam.md step 5) is ever warranted. This feature does not build that arbitration -- it only produces the first real-world source of user-vs-executive-function collisions for 126 to observe. Open design question to resolve during specification/clarification: whether the conversational reprioritization path is implemented as a dedicated core tool the routing layer calls (and what tool-authoring/trust implications that has, since core tools are a higher-trust, higher-blast-radius surface than plugin tools) versus some lighter-weight mechanism -- this needs explicit design attention because of the trust/authority questions involved, not a default yes."

**Governed by**: [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md) (constitutional —
§Arbitration's fixed precedence order, "governance > user-stated identity/preference > grounded
fact > inference > suspicion" — this feature is the first place a user-stated instruction and
the executive function's own `Priority` claim can concretely disagree), and
[`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md) (every reprioritization
instruction must travel as a typed `Contribution`, never a direct write). Depends on
[`specs/phases/123-attention-arbitration/spec.md`](../123-attention-arbitration/spec.md) (the
`PriorityView` ranking this feature lets a user see and contest),
[`specs/phases/124-contribution-seam-core/spec.md`](../124-contribution-seam-core/spec.md) and
[`specs/phases/125-contribution-seam-extension/spec.md`](../125-contribution-seam-extension/spec.md)
(the validated `Contribution` write path this feature's two intake surfaces submit through), and
[`specs/phases/126-contribution-collision-detection/spec.md`](../126-contribution-collision-detection/spec.md)
(the observer this feature is expected to give its first real evidence to). Does not build real
cross-contribution arbitration (`contribution-seam.md`'s step 5) — this feature produces a
source of user-vs-executive collisions for that future decision, it does not resolve them.

---

## Overview

Phase 123 gave Ze a computed view of what deserves attention — `PriorityView` ranks open loops,
stuck goals, and hypotheses by urgency, but today nothing lets the user look at that ranking, let
alone disagree with it. A user who thinks Ze has its priorities wrong (the loop it thinks is most
urgent isn't, or something Ze ranks low actually matters most right now) has no way to tell it so
in a way the system durably respects — only to route around Ze's ranking by acting on the thing
themselves.

This feature closes that gap two ways: a snapshot view of the current ranking, and two paths to
tell Ze "no, actually, put this first" — dragging items in the view, or saying so in
conversation. Both paths are, in doctrine terms, the user submitting a `user-stated`
contribution about priority — the same kind of proposal any other cognitive function makes to
the shared world-state, carried through the validated `Contribution` write path Phase 124/125
built, not a private override that bypasses it.

Because `PriorityView`'s own ranking is a computed `Priority` claim (the executive function's
license, per the doctrine's contribution model), and a user's explicit instruction can disagree
with it, this feature is expected to be the first place the two genuinely collide in production —
exactly the trigger condition Phase 126's collision detector exists to observe. This feature
does not decide who wins that argument in general (that is `contribution-seam.md`'s step 5,
still gated on real evidence); it only makes sure the disagreement is expressed honestly, through
the seam, where it can be seen — while still honoring the user's most recent instruction for
what they are shown, per this spec's Requirements.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Seeing what Ze currently thinks matters most (Priority: P1)

As the user, I can open a view that shows me `PriorityView`'s current ranked list — the same
loops, stuck goals, and hypotheses Ze's proactive nudges are drawn from — so I know what Ze
considers most urgent right now, instead of only finding out when it interrupts me.

**Why this priority**: Without a visible snapshot, there is nothing for the user to agree or
disagree with — this is the precondition for both reprioritization paths.

**Independent Test**: Seed a drifting loop, a stuck goal, and a recent hypothesis. Open the
snapshot view. Assert all three appear, each labeled with its source and current rank, matching
what `PriorityView.rank()` would return at that moment.

**Acceptance Scenarios**:

1. **Given** open loops, stuck goals, and hypotheses exist, **When** the user opens the snapshot
   view, **Then** they see one ordered list spanning all three, each item labeled with its source
   and title.
2. **Given** nothing is currently open across all three sources, **When** the user opens the
   view, **Then** they see an empty state, not an error.

---

### User Story 2 - Reordering priorities by dragging (Priority: P1)

As the user, I can drag an item in the snapshot view to a new position, and that action tells Ze
I want it treated as more (or less) urgent than the ranking currently shows.

**Why this priority**: This is the most direct expression of user intent the feature offers, and
the one most users will use.

**Independent Test**: Open the snapshot view with three ranked items. Drag the third item above
the first. Assert a user-stated Contribution is submitted referencing that item and the
requested position, and assert the next time the view is opened, that item is displayed at the
requested position.

**Acceptance Scenarios**:

1. **Given** a ranked snapshot view, **When** the user drags an item to a new position, **Then**
   a user-stated Contribution is submitted through the validated Contribution write path
   referencing the item and its requested relative order.
2. **Given** a user has dragged an item above another that `PriorityView`'s own computed ranking
   ranks lower, **When** the view is reopened, **Then** the dragged item is shown at the
   requested position, and the item's underlying computed priority score (from Phase 123) is
   unchanged by the drag.
3. **Given** a plain drag (not an explicit pin), **When** enough time passes without the user
   reaffirming or pinning it, **Then** the item's displayed position gradually reverts toward
   `PriorityView`'s unmodified computed order rather than holding indefinitely.
4. **Given** an item the user has dragged, **When** the user explicitly pins it (a distinct
   action from the drag itself), **Then** its position stops decaying and holds until the user
   unpins it, changes it, or the item closes/completes/drops.

---

### User Story 3 - Reordering priorities in conversation (Priority: P2)

As the user, I can tell Ze in chat to reprioritize something ("focus on the Berlin move first,"
"the stuck report goal can wait"), and it has the same effect as dragging it in the view.

**Why this priority**: Lower than the UI path because it depends on correctly identifying which
item the user means from natural language, which is inherently less precise than a direct drag —
but it matters because not every reprioritization happens while the view is open.

**Independent Test**: With the same three items seeded as User Story 1, tell Ze in conversation to
deprioritize the item currently ranked first. Assert a user-stated Contribution equivalent to
User Story 2's is submitted, and the next snapshot view reflects it.

**Acceptance Scenarios**:

1. **Given** a ranked set of items exists, **When** the user names one in conversation and states
   a reprioritization intent, **Then** Ze confirms which item it understood before submitting the
   Contribution (disambiguation, not a silent guess).
2. **Given** the user's conversational instruction names an item, **When** Ze cannot identify it
   with reasonable confidence, **Then** it asks the user to clarify rather than submitting a
   Contribution against the wrong item.
3. **Given** the user says something that reads as an ordinary reprioritization ("focus on X
   first"), **When** Ze submits the Contribution, **Then** it is a decaying override by default —
   the user must say something that unambiguously requests permanence ("always keep this first,"
   "pin this") for it to be treated as a pin instead.

---

### Edge Cases

- What happens when a user reprioritizes an item that closes, completes, or drops before the next
  snapshot view? The stale instruction is not applied — the snapshot never resurrects an item that
  no longer belongs in any of the three source lists, pinned or not.
- What happens when the user issues two conflicting instructions for the same item over time (drag
  it up, then later tell Ze to deprioritize it)? The most recent instruction is authoritative —
  this is the same user revising their own prior statement, not a collision between two different
  functions (Phase 126's collision detector does not log this; see Phase 126 FR-010's supersession
  carve-out).
- What happens to a pin when the user later issues a plain (non-pinning) reprioritization for the
  same item? The new instruction supersedes the pin — it becomes a fresh decaying override unless
  the user pins it again; a pin is not permanent once established regardless of later
  instructions.
- What happens to a decaying override's displayed position while it's mid-decay? It moves
  smoothly back toward `PriorityView`'s unmodified computed position rather than jumping
  discontinuously once some threshold is crossed. This position is recomputed each time the
  snapshot view is opened or refreshed, not updated live while the view stays open.
- What happens when the user's instruction and `PriorityView`'s own computed ranking disagree
  about the same item? The disagreement is not silently resolved in either direction — it is
  expressed as a real collision between a user-stated contribution and the executive function's
  `Priority` claim, observable to Phase 126's detector, per this spec's Clarifications on how (if
  at all) that disagreement is also shown to the user.
- What happens if the user tries to reprioritize an item that does not exist or that they
  misdescribed in conversation? Ze asks for clarification rather than guessing and submitting a
  Contribution against the wrong target (User Story 3, Acceptance Scenario 2).

## Clarifications

### Session 2026-08-25

- Q: What confirmation or trust-gating should the conversational reprioritization path require,
  given it commits a Contribution to shared world-state from a conversational surface — should it
  be treated like other high-trust, high-blast-radius actions (e.g. requiring the same kind of
  confirmation gate other consequential agent actions use), or can it commit directly once the
  target item is disambiguated? → A: Require the same confirmation gate as other consequential
  agent actions before the Contribution is submitted — disambiguating the target is not
  sufficient on its own, given the write lands on shared world-state and the same instruction can
  be issued again immediately if the confirmation was accidental.
- Q: When a user's reprioritization instruction disagrees with `PriorityView`'s own computed
  ranking for the same item, should that disagreement be shown to the user in the snapshot view
  (e.g. "Ze's own ranking would place this differently"), or does it stay a log-only signal for
  Phase 126's collision detector, invisible in the UI? → A: Show it — a subtle in-view indicator
  on any item where the user's requested position and Ze's own computed ranking disagree, so the
  user knows they are overriding Ze's judgment, not just reordering a static list.
- Q: Does a user's reprioritization persist as a durable pin (the item stays at the user's
  requested relative position until the user changes or clears it) or as a decaying signal, like
  the confidence-based priority scores it's layered over (its influence fades over time, and the
  view gradually reverts to `PriorityView`'s unmodified computed order)? → A: Neither alone —
  a plain reprioritization (drag, or a conversational instruction like "focus on this for now")
  is a decaying override by default, fading back toward `PriorityView`'s unmodified computed
  order over a bounded window. Separately, the user can explicitly **pin** an item (a distinct,
  intentional action — e.g. a pin toggle in the view, or an unambiguous conversational phrasing
  like "always keep this at the top," not the same act as an ordinary reprioritization) to make
  that override durable — holding until the user unpins it, changes it, or the item itself
  closes/completes/drops. This keeps the low-friction common case self-healing while still
  giving the user a way to make an instruction stick.

### Session 2026-08-26

- Q: How should a submitted Contribution express the user's "requested relative order" (FR-005),
  the thing FR-010 compares against `PriorityView`'s own computed ranking to detect disagreement —
  as an absolute numeric position, as a relation to another named item (e.g. "above item X"), or
  as an unanchored directional nudge ("more/less urgent") with no fixed target? → A: Anchor-relative
  — the Contribution states the item's position relative to another named item (e.g. "above item
  X" / "below item Y"), not a raw index. This matches how both the drag path (a drop position next
  to a neighbor) and the conversational path ("focus on X first") naturally express intent, and it
  stays meaningful as items enter or leave the three source lists between submission and display,
  where a fixed numeric index would not.
- Q: When two or more items each carry an active override (decaying or pinned) whose
  anchor-relative positions contradict each other (e.g. item A says "above item B" while item B
  independently says "above item A," or several pinned items each claim to be first), how should
  the contradiction be resolved? → A: Most-recent-instruction-wins — the same supersession
  principle FR-012 already applies within one item's own history extends across items: for any
  pair of overrides that contradict, the one submitted later takes effect for that pair, and the
  earlier one is treated as superseded for that specific ordering conflict (it is not cleared
  entirely — it still holds against items it doesn't contradict). This keeps one consistent
  conflict-resolution rule rather than introducing a second mechanism alongside FR-012, including
  when a pin is on the losing side of a later plain instruction for a different item.
- Q: Should a decaying override's displayed position update live while the snapshot view stays
  open, or only recompute the next time the view is opened? → A: Recompute on open — the decay
  function is evaluated fresh each time the view is opened (or refreshed), consistent with the
  "snapshot view" framing used throughout this spec; "moves smoothly rather than jumping
  discontinuously" (Edge Cases) describes the decay function being continuous/monotonic over
  elapsed time, not that an already-open view animates in real time. No live-update channel is
  required for this feature.
- Q: What should happen if a reprioritization Contribution fails to submit (write-path rejection
  or a transient error)? → A: Revert and notify — on the drag path, the item visually snaps back
  to its pre-drag position and a brief inline error is shown; on the conversational path, Ze tells
  the user the instruction could not be applied (with the reason, if known). Neither path leaves
  the user believing an override took effect when it was not actually recorded through the
  Contribution write path.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide a snapshot view of `PriorityView`'s current ranked list —
  open loops, stuck/near-gate goals, and non-stale hypotheses — showing each item's source,
  title, and current position.
- **FR-002**: Users MUST be able to reorder the snapshot view by dragging an item to a new
  position.
- **FR-003**: Users MUST be able to issue an equivalent reprioritization instruction
  conversationally, naming the item and the desired change.
- **FR-004**: Both the drag path and the conversational path MUST express the user's intent as a
  user-stated Contribution submitted through the validated Contribution write path (Phase
  124/125) — neither path may write directly to a source store, bypassing the seam.
- **FR-005**: A submitted reprioritization Contribution MUST reference the specific item(s)
  affected and the user's requested relative order, expressed as a position relative to another
  named item (e.g. "above item X" / "below item Y"), not a fixed absolute index.
- **FR-006**: The conversational path MUST confirm which item it identified before submitting a
  Contribution when the user's phrasing does not unambiguously name one, and MUST ask for
  clarification rather than guess when it cannot identify the item with reasonable confidence.
- **FR-007**: The conversational path MUST require the same confirmation gate used for other
  consequential agent actions before the Contribution is committed — target disambiguation alone
  is not sufficient authorization to write to shared world-state.
- **FR-008**: A reprioritization instruction MUST default to a decaying override — the snapshot
  view holds the affected item at the user's requested relative position with full weight
  immediately after submission, then that weight fades over a bounded window until the item's
  displayed position reverts to `PriorityView`'s unmodified computed order — without altering the
  item's underlying computed priority score from Phase 123 at any point.
- **FR-009**: Users MUST be able to explicitly pin a reprioritization, as a distinct action from
  an ordinary reprioritization instruction (FR-008), so that it does not decay — holding the item
  at the requested position until the user unpins it, issues a new instruction for that item, or
  the item itself closes/completes/drops.
- **FR-010**: When a user's requested position for an item (decaying or pinned) disagrees with
  what `PriorityView`'s own computed ranking would produce, the system MUST surface that
  disagreement to the user within the snapshot view (not silently reorder without indication), in
  addition to it being observable to Phase 126's collision detector.
- **FR-011**: A reprioritization instruction targeting an item that has since closed, completed,
  or dropped MUST NOT be applied — the snapshot never resurrects an item outside all three source
  lists on the strength of a stale override, decaying or pinned.
- **FR-012**: A second reprioritization instruction for the same item from the same user MUST
  supersede the prior one (the most recent instruction is authoritative, and a plain instruction
  replaces an existing pin with a fresh decaying override) — this is the user revising their own
  prior statement, not a new collision for Phase 126 to log (per Phase 126 FR-010's supersession
  carve-out).
- **FR-015**: If a reprioritization Contribution fails to submit through the Contribution write
  path (rejection or transient error), the system MUST NOT leave the user believing the override
  took effect — the drag path MUST revert the item to its pre-drag displayed position with a
  brief inline error, and the conversational path MUST tell the user the instruction could not be
  applied.
- **FR-014**: When two or more active overrides (decaying or pinned) express anchor-relative
  positions that contradict each other, the system MUST resolve the contradiction by the same
  most-recent-instruction-wins rule FR-012 applies within a single item's history — for any
  contradicting pair, the later-submitted override takes effect for that pair, and the
  earlier-submitted one remains in force against any other item it does not contradict.
- **FR-013**: This feature MUST NOT implement real cross-contribution arbitration (automatic
  precedence resolution between the user's override and `PriorityView`'s computed ranking beyond
  FR-008/FR-009's display-level override) — it produces the disagreement as observable evidence,
  per Phase 126, rather than resolving it.

### Key Entities

- **Reprioritization Contribution**: A user-stated `Contribution` (per `contribution-seam.md`)
  carrying the target item's source and identifier, the user's requested relative position
  (anchor-relative — expressed against another named item, not an absolute index), and whether it
  was submitted as a plain instruction or an explicit pin — submitted through the same validated
  write path as any other function's contribution, not a bespoke override channel.
- **Priority override**: The user-set relative position for a specific item, layered on top of —
  not a replacement for — the item's computed `Priority` score. Decays back to the computed
  order over a bounded window by default; held durably instead when the user has explicitly
  pinned it, until unpinned, replaced, or the item leaves all three `PriorityView` source lists.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can view Ze's current priority ranking and identify what it considers most
  urgent without needing to check three separate places (loops, goals, hypotheses) themselves.
- **SC-002**: A user can express a reprioritization by dragging, and see it reflected the next
  time they open the view, without needing to know which underlying mechanism (loop, goal, or
  hypothesis) their target item belongs to.
- **SC-003**: A user can express the same reprioritization conversationally with the same
  end result as dragging, including being asked to clarify rather than acted on incorrectly when
  their instruction is ambiguous.
- **SC-004**: Every reprioritization instruction, from either path, is traceable after the fact to
  a specific submitted Contribution — no reprioritization takes effect through an unaudited
  write.
- **SC-005**: When a user's reprioritization disagrees with Ze's own computed ranking, the user
  can tell that disagreement exists from the view itself, without needing to inspect a log.
- **SC-006**: A user who reprioritizes an item without explicitly pinning it sees that override
  naturally fade over time rather than needing to remember to undo it; a user who explicitly pins
  an item sees it hold until they change their mind.

## Assumptions

- This feature depends on Phase 123's `PriorityView.rank()` (the ranked list being viewed and
  pinned against) and on Phase 124/125's validated `Contribution` write path (the channel every
  reprioritization instruction travels through) — it does not re-implement either.
- The conversational path's underlying mechanism (a dedicated core tool the routing layer calls,
  versus a lighter-weight mechanism) is a planning-time decision, not fixed by this spec — this
  spec's contract is FR-006/FR-007's behavior (disambiguate, confirm, don't guess), not the
  specific implementation surface. That decision should weigh that core tools are a higher-trust,
  higher-blast-radius surface than plugin tools, consistent with FR-007's confirmation
  requirement.
- "Reasonable confidence" for conversational item identification (FR-006) is a planning-time
  threshold, not fixed by this spec, consistent with how Phase 123's hypothesis staleness
  threshold and Phase 126's recency window were both left as implementation details.
- The default decay window (FR-008) is a planning-time value, not fixed by this spec — the
  contract is that a plain reprioritization fades back to the computed order over some bounded
  period, not a specific number of hours or days.
- A priority override is per-item, not a global reordering scheme — reprioritizing or pinning one
  item does not require the user to also specify positions for every other item in the list.
- This feature does not change what `PriorityView.rank()` computes (Phase 123's scoring is
  untouched) — it adds a display-level override (decaying by default, durable when pinned) and an
  observable user-vs-executive-function disagreement, per FR-008/FR-009/FR-010.
