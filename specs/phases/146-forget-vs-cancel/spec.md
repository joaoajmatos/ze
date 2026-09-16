# Feature Specification: Forget vs Cancel Across Stores

**Feature Branch**: `146-forget-vs-cancel`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "Users say “forget the dentist” meaning reminder/loop/goal. forget_fact is biography-only. Route cancel speech to reminder/loop/goal tools; do not dual-write forget. Needs 143 precise miss + earned forgotten claims. Out: 144."

**Governed by**: [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md) (Principle VIII — no shim, no dual door), [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), Phase 142 routing table **R14**, [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md) item 146. Depends on Phase 143 (precise forget miss; forgotten claims only after `forget_fact` `ok` true). Plugin code imports `ze_sdk` / owning plugin, never `ze_core`.

---

## Overview

People say “forget the dentist” when they mean cancel a reminder, close a loop, or drop a goal. `forget_fact` only retracts biography. Phase 142 already wrote that rule; a miss or a wrong biography hit is still possible. Phase 143 now fails closed on weak biography matches and forbids an unearned “I forgot.”

This phase routes cancel speech to the existing reminder, loop, and goal tools. It does not also call `forget_fact` for the same utterance. “Forgotten” remains earned only for biography. Constraint veto on gated writes is not this spec.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Cancel speech hits the live store, not biography (Priority: P1)

The user has a dentist reminder (or loop, or goal) and says to forget/cancel/drop it. Ze cancels that domain item with that domain’s existing tool. Biography facts about dentists are not retracted unless the user also named a biography fact. The user is told the reminder/loop/goal was cancelled only if that domain action succeeded.

**Why this priority**: The remaining honesty gap after 142’s table and 143’s miss is acting on the wrong store.

**Independent Test**: Seed a reminder labeled around “dentist” and an unrelated biography fact containing “dentist.” Utter “forget the dentist” as cancel-the-reminder. Reminder is cancelled; biography stays; `forget_fact` is not also success for that utterance. Repeat for a loop and a goal with their cancel/close/abandon tools.

**Acceptance Scenarios**:

1. **Given** a pending reminder the user clearly means and no request to retract biography, **When** they say to forget/cancel that reminder, **Then** `cancel_reminder` (or equivalent existing reminder cancel) runs and `forget_fact` does not dual-write.
2. **Given** an open loop the user clearly means, **When** they say to forget/drop/close that concern, **Then** the existing loop close/drop path runs and `forget_fact` does not dual-write.
3. **Given** a goal the user clearly means, **When** they say to forget/abandon that goal, **Then** `abandon_goal` (or the existing abandon/complete tool) runs and `forget_fact` does not dual-write.
4. **Given** cancel speech with no matching reminder, loop, or goal, **When** Ze replies, **Then** it does not claim forgotten biography unless `forget_fact` returned `ok` true (Phase 143).

---

### User Story 2 - Biography forget stays biography-only (Priority: P1)

The user names a standing preference or identity fact to forget. `forget_fact` still runs with Phase 143 precision. That success does not cancel reminders, loops, or goals that merely share a word.

**Why this priority**: Closing the cancel door must not steal real biography forget.

**Independent Test**: Seed “prefers aisle seats” and a reminder “dentist.” “Forget that I like aisle seats” retracts the fact only. The reminder remains.

**Acceptance Scenarios**:

1. **Given** a clearly named biography fact (Phase 143 precise match), **When** the user asks to forget that fact, **Then** `forget_fact` may return `ok` true and reminders/loops/goals are untouched.
2. **Given** a vague “forget the dentist” that matches neither a precise biography fact nor a single domain item, **When** forget/cancel runs, **Then** Ze does not batch-retract biography **and** does not silently cancel unrelated domain items (ask or miss; fail closed).
3. **Given** the user names both a biography fact and a reminder in one turn, **When** Ze acts, **Then** each named target uses its own tool; that is two explicit targets, not a silent dual-write of one speech act.

---

### User Story 3 - Forgotten claims stay earned (Priority: P2)

If cancel speech was routed to a domain tool, the reply must not say Ze forgot a memory fact unless `forget_fact` `ok` is true. If the domain cancel succeeded, Ze may confirm the reminder/loop/goal is cancelled — that is not a forgotten-fact claim.

**Why this priority**: Prevents a second fake success after 143.

**Independent Test**: Cancel a reminder successfully; model still says “I’ve forgotten that.” User-visible text must not claim biography forgotten. It may confirm the reminder was cancelled.

**Acceptance Scenarios**:

1. **Given** a successful domain cancel and no `forget_fact` `ok` true, **When** Ze replies, **Then** it does not claim a biography fact is forgotten.
2. **Given** `forget_fact` `ok` false (precise miss) on cancel-shaped speech, **When** Ze replies, **Then** there is no forgotten-fact confirmation (Phase 143).
3. **Given** this phase ships, **When** cancel speech is handled, **Then** there is not a second path that still calls `forget_fact` “just in case” for the same speech act (no shim dual-write).

---

## Edge Cases

- Several reminders share “dentist”: do not cancel the set on a short token; ask which, or miss. Same precision spirit as Phase 143.
- User says “forget that” with no referent: miss; do not pick a store.
- Domain cancel fails (already fired reminder, unknown id): tell the truth; do not fall back to `forget_fact`.
- Loop vs reminder both exist for the same words: one primary store from Phase 142 conflict rules (time/reminder vs lingering concern); do not write both.
- Workflows: not required in this phase unless the user clearly names a workflow run; then existing workflow cancel is in-family with domain cancel, still not `forget_fact`. Default: out unless clearly named (Assumption).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST route forget/cancel/drop/abandon speech that targets a reminder, open loop, or goal to that domain’s existing cancel/close/abandon tools, not to `forget_fact`.
- **FR-002**: System MUST NOT dual-write `forget_fact` for the same cancel speech act that is handled as a domain cancel (Phase 142 R14).
- **FR-003**: System MUST keep `forget_fact` for clearly identified biography facts, with Phase 143 precision (miss rather than wrong retract).
- **FR-004**: System MUST allow a user-visible forgotten-**fact** claim only when `forget_fact` returns `ok` true this turn (Phase 143). Domain cancel success MUST NOT license that claim.
- **FR-005**: System MUST allow confirming a cancelled reminder, closed loop, or abandoned goal only when that domain action succeeded this turn.
- **FR-006**: System MUST NOT leave a companion path that still treats “forget the dentist” as biography retract by default (no shim).
- **FR-007**: This phase MUST NOT implement constraint veto on gated writes (Phase 144), unsolicited recitation, ingest honesty, extractor races, specialist constitution as a bundle, or a `/memories` filesystem.

### Key Entities

- **Cancel speech**: User language aimed at stopping a reminder, loop, or goal, including colloquial “forget.”
- **Biography forget**: Retraction of a reviewed fact via `forget_fact`.
- **Domain cancel outcome**: Success or failure of `cancel_reminder`, loop close/drop, or `abandon_goal` (existing tools).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tested “forget the [reminder]” turns with a clearly matching reminder, the reminder is cancelled and biography is not retracted.
- **SC-002**: In 100% of tested biography-forget turns with a precise fact match, the fact is retracted and unmatched reminders remain.
- **SC-003**: In 100% of tested domain-cancel successes without `forget_fact` `ok` true, graders find zero forgotten-fact claims.
- **SC-004**: In 100% of tested dual-write probes, a single cancel speech act does not both cancel a domain item and retract biography unless the user named both targets.

---

## Assumptions

- Existing tools are `cancel_reminder`, `abandon_goal`, and the existing loop close/drop review path (`close_loop` / drop). This phase does not invent a fourth store.
- Companion may hand off to the owning agent; the product rule is the write that happens, not which Python class spoke.
- Workflows are cancelled only when clearly named; default speech “forget the dentist” is reminder/loop/goal, not workflow.
- Ambiguous multi-match in one store: ask or miss; do not batch-cancel.
- Phase 144 veto is untouched.

## Out of Scope

- Constraint veto on gated writes (Phase 144).
- Response-level unsolicited recitation (Phase 145) except where a forgotten-fact claim overlaps 143 (already required).
- Ingest vs remember honesty (Phase 147).
- Extractor dual-write races (Phase 148).
- Specialist memory constitution (Phase 149).
- Claude-style `/memories` filesystem.
- Rewriting Phase 140–142 write/read/routing **tables** as a bundle (R14 is already the rule; this phase enforces the cancel door).

## Verbatim Constraints

- `forget_fact`
- `ok`
- `cancel_reminder`
- `abandon_goal`
- `close_loop`
- R14
- Principle VIII (no shim, no dual door)
- `ze_sdk`
- `ze_core`

## After this feature / Future work

See [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md). Next: 147 ingest honesty, 148 extractor races, 149 specialists, 150 eval+guides.
