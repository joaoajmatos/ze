# Feature Specification: Priority Turn Surfacing

**Feature Branch**: `132-priority-turn-surfacing`

**Created**: 2026-09-14

**Status**: Planned

**Input**: User description: "Spec the leftover open question in
specs/arch/attention-arbitration.md: conversation-turn assembly still mentions open
loops on their own path, while push and the briefing already rank through
PriorityView. Make conversation turns read PriorityView. Keep topical relevance
(a turn must still be about the thing being mentioned). Rank the eligible candidates
and mention the highest-priority relevant item across loops, stuck goals, hypotheses,
and stale-relationship nudges — not loops only. Resume recap / 'what's open' uses
the same ranking. Do not merge the loop and goal stores. Do not build contribution
arbitration. Do not change the shared push budget (already shipped)."

**Governed by**: [`specs/arch/attention-arbitration.md`](../../arch/attention-arbitration.md)
(open question: "Surfacing consumer" — whether conversation-turn assembly reads
`PriorityView` directly) and
[`specs/phases/123-attention-arbitration/spec.md`](../123-attention-arbitration/spec.md)
(`PriorityView` and the shared attention budget — shipped). Depends on
[`specs/phases/110-open-loop-drift-surfacing/spec.md`](../110-open-loop-drift-surfacing/spec.md)
(inline mention is still gated by topical relevance, not a dump of everything open),
[`specs/phases/127-priority-override/spec.md`](../127-priority-override/spec.md)
(user-directed reorderings already merge into `PriorityView.rank()` and MUST be
honored here), and
[`specs/phases/128-social-cognition-foundation/spec.md`](../128-social-cognition-foundation/spec.md)
(relationship-staleness is already a `PriorityView` source). MUST NOT merge loop and
goal stores (Phase 110 FR-014). MUST NOT build contribution-seam arbitration.

---

## Overview

Phase 123 gave Ze one ranked view of what deserves attention: drifting loops, stuck
goals, and live hypotheses, later joined by stale-relationship nudges (Phase 128) and
user-directed reorderings (Phase 127). Push already spends the shared interruption
budget from that ranking. The morning briefing already reads relationship nudges from
it. Conversation turns do not.

In a live reply, Ze can still mention an open loop because that loop shares an entity
with the turn — even when a stuck goal or a pinned higher item about the same topic
ranks above it. The user gets "several attention mechanisms" again, just inside the
thread instead of in push.

This phase makes the conversation's inline mention, and the "what's open" recap at a
session resume, consume the same ranking the rest of the product already uses. It does
not mention the globally hottest item on an unrelated turn. Relevance still decides
*whether* something may be mentioned; `PriorityView` decides *which* of the relevant
candidates is mentioned.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A turn mentions the most deserving relevant item, not only a loop (Priority: P1)

The user is talking about a topic that has both a drifting open loop and a stuck goal
(or a live hypothesis, or a stale-relationship nudge) attached. Ze's reply may still
mention that unfinished business — but it mentions the item `PriorityView` ranks
highest among those that are actually about this turn, including a user pin from the
priority snapshot. It does not mention an unrelated top-ranked item from elsewhere in
the user's life, and it does not prefer loops just because loops had their own mention
path first.

**Why this priority**: This is the leftover consumer. Without it, `PriorityView` is
the truth for push and the briefing, and a second truth in conversation.

**Independent Test**: Seed a turn whose topic overlaps both a drifting loop and a
stuck goal, with the goal ranked higher (including via a user pin). Complete the turn.
Confirm the inline mention is the goal (or lists relevant items in rank order with the
goal first), not the loop alone. Repeat with no overlapping entities and confirm
nothing from the global top of the ranking is injected.

**Acceptance Scenarios**:

1. **Given** a turn whose topic overlaps a drifting loop and a stuck goal, and the
   goal ranks higher, **When** the turn completes, **Then** the inline mention
   presents the goal first (or only), not the loop as if it were the only open item.
2. **Given** the user pinned a relevant item above the others in the priority
   snapshot, **When** a turn is about that same topic, **Then** the mention follows
   that pin.
3. **Given** a globally high-ranked item with no topical overlap with the turn,
   **When** the turn completes, **Then** that item is not injected into the reply.
4. **Given** no relevant open items, **When** the turn completes, **Then** there is
   no "still open" mention.

---

### User Story 2 - "What's open" and a resumed thread use the same ranking (Priority: P2)

After a gap, Ze quietly recaps what is still open so the user can continue. That recap
— and an explicit "what's open right now" question — lists unfinished business in
`PriorityView` order (loops, stuck goals, hypotheses, stale-relationship nudges), not
loops first because loops were wired earlier. Stores stay separate; this is one read.

**Why this priority**: Resume recap is the other conversation assembly path that still
pulls open loops (and in-flight goals) through their own lists. Same leftover as User
Story 1, at a session boundary rather than mid-thread.

**Independent Test**: Leave a thread idle long enough to trigger a resume recap, with
a stuck goal ranked above a drifting loop. Confirm the recap names the goal first.
Ask "what's open right now" in a live turn and confirm the same order.

**Acceptance Scenarios**:

1. **Given** a session gap that triggers a resume recap, and mixed open items with a
   known ranking, **When** the user sends the next message, **Then** the recap of what
   is open follows `PriorityView` order.
2. **Given** the user asks what is open right now, **When** Ze answers, **Then** the
   answer is one ordered list across the same sources `PriorityView` already ranks,
   not three separate unranked dumps.
3. **Given** `PriorityView` cannot read one source, **When** a recap or "what's open"
   answer is assembled, **Then** the remaining sources still appear, in rank order;
   the turn does not fail.

---

### Edge Cases

- What if several relevant items tie? The mention may include a short bounded list,
  still in rank order, at most as many items as today's loop-mention list would have
  shown. It MUST NOT grow into a dump of everything open.
- What if `PriorityView` fails entirely? The turn still completes. No mention is
  required. The system MUST NOT invent a loop-only fallback that contradicts a known
  higher-ranked relevant item it could not rank.
- What if the user has no pins and only loops are relevant? Behavior looks like
  today's loop mention. This phase MUST NOT regress that case.
- What if an unconfirmed co-occurrence hypothesis is relevant? Phase 130's rule
  stands: unconfirmed inferences MUST NOT be presented as settled identity, and MUST
  NOT take shared attention-budget slots. Hedged mention is allowed only in the
  posture already specified there.
- What if the briefing already used `PriorityView` for relationship nudges? This
  phase does not rewrite the rest of the briefing (news, unreviewed facts, workflow
  failures). Those are not attention-arbitration sources.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Inline unfinished-business mentions on a conversation turn MUST be
  chosen from items that are topically relevant to that turn (entity overlap with
  the turn's resolved entities, same relevance rule Phase 110 uses for loops).
- **FR-002**: Among those relevant candidates, the mention MUST follow
  `PriorityView` ranking — including user-directed pins and decaying overrides from
  Phase 127 — across loops, stuck or near-gate goals, live hypotheses, and stale-
  relationship nudges.
- **FR-003**: A globally high-ranked item MUST NOT be injected into a turn it is not
  topically relevant to.
- **FR-004**: Resume recap of what is still open MUST list items in `PriorityView`
  order rather than source-by-source (loops, then goals, then other).
- **FR-005**: An explicit "what's open" question MUST be answered from `PriorityView`
  as one ordered list across the same sources, not as separate unranked lists.
- **FR-006**: Loop and goal stores MUST remain separate. This spec is a read-side
  consumer of `PriorityView`. It MUST NOT unify those stores.
- **FR-007**: This spec MUST NOT change the shared daily push budget or the greedy
  push check already shipped in Phase 123.
- **FR-008**: This spec MUST NOT build contribution-seam conflict resolution.
  Collision logging stays observational.
- **FR-009**: If one `PriorityView` source fails, remaining sources MUST still be
  usable for mentions and recap (same degrade-gracefully rule as Phase 123). If
  ranking is entirely unavailable, the turn still completes without a mention.
- **FR-010**: Unconfirmed social-cognition inferences MUST keep Phase 130 posture:
  not presented as settled identity, not spending the shared attention budget.
- **FR-011**: Inline mentions MUST stay a short bounded list (no larger than today's
  loop-mention list). Ranking MUST NOT become a dump of the full priority snapshot
  into every turn.

### Key Entities

- **Priority ranking**: The existing `PriorityView` projection (Phase 123/127/128).
  This phase does not add a new ranking; it consumes it in conversation assembly.
- **Relevant candidate**: An open item whose linked entities overlap the turn's
  resolved entities (or the equivalent topical match already used for that source).
  Relevance is the gate; ranking is the order.
- **Inline mention**: The short "still open" note attached to a reply. After this
  phase it may name a loop, a stuck goal, a hypothesis, or a stale-relationship
  nudge — whichever ranks highest among relevant candidates.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tests where a turn is relevant to both a drifting loop and a
  higher-ranked stuck goal, the inline mention presents the goal first (or only),
  not the loop alone.
- **SC-002**: In 100% of tests where the globally top-ranked item has no topical
  overlap with the turn, that item is absent from the reply.
- **SC-003**: In 100% of resume-recap tests with mixed open items, the recap names
  them in `PriorityView` order.
- **SC-004**: A user pin on a relevant item is respected in the inline mention in
  100% of pin tests.

## Assumptions

- `PriorityView.rank()` / `rank_subset()` already combine loops, goals, hypotheses,
  relationship-staleness, and user overrides. Conversation assembly does not
  re-score those sources.
- Topical relevance for loops remains entity-overlap (Phase 110). Goals,
  hypotheses, and relationship nudges use the same entity-overlap idea against
  whatever entities those records already link — no new embedding call per turn.
- "What's open right now" is answered from the ranking even without entity
  overlap, because the user asked for the global list. Inline unsolicited mentions
  stay relevance-gated.
- The morning briefing's relationship section already reads `PriorityView`. This
  phase does not rebuild news, unreviewed-facts, or workflow-failure sections.
- Phase 112 resume recap remains the session-gap vehicle; this phase only changes
  how the "what is open" slice of that recap is ordered and sourced.

## Verbatim Constraints

- `PriorityView` — the ranking this phase MUST consume; MUST NOT invent a second
  conversation-only ranking
- `surface_loops` — the existing conversation-turn mention path this phase
  replaces as the source of *which* item is mentioned; topical relevance stays

## Out of Scope

- Merging `OpenLoop` and goal stores (Phase 110 FR-014)
- Contribution-seam arbitration (still gated on collision evidence)
- Changing push-budget numbers or the greedy push check
- Social-cognition ADR step 4 (relationship-strength scores, user-settable cadence)
- Rewriting the morning briefing beyond conversation/resume consumers
- A new "what's open" page (Phase 127 already shipped the snapshot view)
