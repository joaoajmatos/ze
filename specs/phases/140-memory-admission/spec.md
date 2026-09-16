# Feature Specification: Memory Admission and Conversational Remember/Forget

**Feature Branch**: `140-memory-admission`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "Write-side memory admission plus conversational remember/forget. Replace the weak every-turn fact extractor (keep/drop, closed predicate families, empty turns return []). Eval fixtures for remember / forget / ephemeral / constraint / commitment. Real remember_fact / forget_fact tools on companion first. Explicit speech acts write PROMPT_SUPPLIED facts with reviewed=true. Never claim memory without a successful write. AgentResult.memory_proposals is unused in production — replace with tools, no shim, no dual door. Still go through contribution seam + NLI; user-supplied does NOT skip the seam. Every-turn extraction MAY remain if the gate usually returns []."

**Governed by**: [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md) (Principle VIII — no shim, no dual write door), [`specs/arch/claim-topology.md`](../../arch/claim-topology.md), [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md). Depends on Phase 133 (perception facts on the seam) and Phase 134 (`memory_facts` hard-cut). Follow-up: Phase 141 (read-side prompt constitution), Phase 142 (speech-act routing across stores). Does not rewrite specialist agent catalogs, does not add a Claude-style memories filesystem, does not add constraint veto on mail/calendar writes.

---

## Overview

Today Ze treats almost every turn as a fact mine. A cheap post-turn extractor invents predicates, keeps noisy or ephemeral statements, and has no keep/drop gate comparable to open-loop extraction. Meanwhile the user has no honest way to say “remember that” or “forget that”: companion has no memory tools, and the leftover `memory_proposals` field on the agent result is unused in production. When Ze says it will remember, that claim is unearned.

This phase tightens **write-side admission** and adds **explicit remember/forget speech acts**. Extracted facts must pass a conservative keep/drop gate with closed predicate families; empty or social turns usually write nothing. When the user explicitly asks Ze to remember or forget, companion calls real tools that write or retract through the same contribution seam and contradiction checks as every other perception fact. User-supplied does not skip the seam. Ze may confirm memory only after a successful write.

There is one explicit write door: the tools. The unused proposals field is removed from the production write path (hard-cut, not wrapped).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Empty and ephemeral turns do not pollute memory (Priority: P1)

After a turn that is greeting, logistics, or clearly temporary (“I’m at the store”, today’s weather), the extractor returns no facts. After a turn that states a durable preference, identity, or constraint in a closed family, a fact may be admitted as synthesized perception — still through the seam.

**Why this priority**: Noise from every-turn extraction is the current failure mode; a conservative gate is the MVP even before remember tools.

**Independent Test**: Run eval fixtures labeled ephemeral vs remember vs constraint vs commitment against the extractor gate. Ephemeral and commitment fixtures yield `[]`. Remember/constraint fixtures yield at most the allowed family. Empty assistant-only chatter yields `[]`.

**Acceptance Scenarios**:

1. **Given** a turn with no durable user self-disclosure, **When** post-turn extraction runs, **Then** it returns an empty list and no memory write occurs.
2. **Given** an ephemeral statement (location-right-now, one-off mood, today’s weather), **When** extraction runs, **Then** it is dropped.
3. **Given** a durable preference or identity statement that matches a closed predicate family, **When** extraction runs, **Then** at most that family is proposed as synthesized perception and submitted through the contribution seam.
4. **Given** a time-bound personal commitment (“I’ll call Mom Tuesday”), **When** extraction runs in this phase, **Then** it is not stored as a fact (Phase 142 routes it elsewhere).

---

### User Story 2 - “Remember that” writes only after a successful tool write (Priority: P1)

The user says to remember something durable. Companion calls `remember_fact`. The write is prompt-supplied, reviewed, and goes through the contribution seam and contradiction checks. Only after the tool reports success does Ze tell the user it is remembered. If the seam rejects the write, Ze does not claim memory.

**Why this priority**: This is the honest speech act the product is missing.

**Independent Test**: Drive companion with a remember utterance; assert the tool is invoked; assert seam submission with prompt-supplied provenance and reviewed true; assert the user-facing claim is gated on tool success. Failure path: mocked seam reject → no “I’ll remember” claim.

**Acceptance Scenarios**:

1. **Given** the user says to remember a durable fact, **When** companion handles the turn, **Then** it calls `remember_fact` rather than stuffing a proposals list.
2. **Given** `remember_fact` succeeds through the seam, **When** Ze replies, **Then** it may confirm the fact is remembered.
3. **Given** the seam or contradiction check rejects the write, **When** Ze replies, **Then** it does not claim the fact is in memory.
4. **Given** a successful remember write, **When** the stored fact is inspected, **Then** provenance is prompt-supplied, reviewed is true, and `source_function` remains perception.

---

### User Story 3 - “Forget that” retracts a remembered fact (Priority: P2)

The user asks Ze to forget something previously stored. Companion calls `forget_fact`. After a successful retraction, Ze does not keep citing that fact as current memory. Failed retraction is not described as forgotten.

**Why this priority**: Remember without forget is a trap; second slice after the write tool exists.

**Independent Test**: Seed a fact, utter forget, assert `forget_fact` and post-success absence from active retrieval. Failed store call does not produce a forget confirmation.

**Acceptance Scenarios**:

1. **Given** a stored fact and a forget request that identifies it, **When** companion handles the turn, **Then** it calls `forget_fact`.
2. **Given** a successful forget, **When** the user later asks related questions, **Then** that fact is not treated as current memory.
3. **Given** forget cannot match or the store rejects, **When** Ze replies, **Then** it does not claim the fact is forgotten.

---

### User Story 4 - One explicit write door (Priority: P2)

Production no longer persists agent-result memory proposals. Companion (first) is the agent that can remember/forget via tools. Other agents in this phase do not gain a second door. Tests that only existed to exercise the unused proposals persist path are updated or deleted, not shimmed.

**Why this priority**: Principle VIII — dual door is the bug.

**Independent Test**: Search producers of memory proposals; write_memory must not persist that field. Agent result type no longer carries a live persist contract for it.

**Acceptance Scenarios**:

1. **Given** an agent result that still has a proposals list in old tests, **When** write_memory runs after this phase, **Then** those items are not persisted as the explicit door.
2. **Given** companion, **When** its tool list is inspected, **Then** it includes `remember_fact` and `forget_fact` and no other new memory-write API.
3. **Given** research, calendar, mail, and other specialists, **When** this phase ships, **Then** they do not receive remember/forget tools yet (Phase 142 may route speech acts to existing domain tools instead).

---

### Edge Cases

- Remember of an ephemeral or commitment utterance: tool or admission still drops or the later router (Phase 142) redirects; this phase must not persist it as a durable fact just because the user said “remember”.
- Duplicate remember of an equivalent fact: seam / NLI path decides merge or collision; no silent second ungated insert.
- Forget of something never stored: honest miss, no fake success.
- Mixed turn (durable preference plus “remind me at 3pm”): this phase may extract the preference if it passes the gate; the reminder is not a fact (Phase 142).
- User-supplied fact that contradicts an existing fact: NLI / seam still runs; user-supplied does not skip.
- Extraction still runs after a successful remember in the same turn: it must not double-write the same predicate as synthesized.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST replace the current every-turn fact extractor policy with a keep/drop gate: empty or non-durable turns return no facts; only closed predicate families may be proposed.
- **FR-002**: System MUST treat ephemeral content (right-now location, one-off mood, day’s weather, social filler) as drop.
- **FR-003**: System MUST NOT store time-bound commitments as facts in this phase (eval fixture `commitment` expects drop from the fact extractor).
- **FR-004**: System MUST provide `remember_fact` and `forget_fact` tools, registered on companion first.
- **FR-005**: System MUST stamp successful `remember_fact` writes as `PROMPT_SUPPLIED` with `reviewed=true`, `source_function` perception, claim kind fact, and MUST submit them through the contribution seam and NLI/contradiction path. User-supplied MUST NOT skip the seam.
- **FR-006**: System MUST NOT claim to the user that something is remembered or forgotten unless the corresponding tool write succeeded.
- **FR-007**: System MUST hard-cut the production persist path for `AgentResult.memory_proposals` (remove or no-op with the field gone — no dual door, no compatibility shim). Explicit writes go through the tools only.
- **FR-008**: Every-turn extraction MAY remain after the gate if it usually returns an empty list; it MUST NOT become a second explicit-remember door.
- **FR-009**: Eval fixtures MUST cover at least `remember`, `forget`, `ephemeral`, `constraint`, and `commitment` speech acts for the extractor/tools.
- **FR-010**: Constraint statements MAY be admitted as facts in the constraint family; enforcing those constraints as vetoes on mail or calendar writes is out of scope (roadmap follow-up, not this phase).

### Key Entities

- **Admitted fact**: A memory fact that passed the keep/drop gate or a successful remember tool, with provenance (synthesized vs prompt-supplied), reviewed flag, and seam envelope.
- **Remember speech act**: User intent to store a durable fact; fulfilled only by `remember_fact` success.
- **Forget speech act**: User intent to retract a fact; fulfilled only by `forget_fact` success.
- **Predicate family**: Closed set of durable categories the extractor may emit (identity, preference, constraint, and similarly durable self-facts — not commitments, not ephemeral).

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: On the ephemeral and empty-turn eval fixtures, extraction writes zero facts.
- **SC-002**: On the remember eval fixture, a prompt-supplied reviewed fact exists after the turn if and only if the remember tool succeeded.
- **SC-003**: On the forget eval fixture, a previously stored matching fact is no longer treated as current memory after a successful forget.
- **SC-004**: On the commitment fixture, zero new facts are stored from extraction.
- **SC-005**: On the constraint fixture, a constraint-family fact may be stored; no mail or calendar send is blocked by this phase.
- **SC-006**: 100% of explicit remember writes in tests go through the contribution seam; zero tests persist via memory proposals as the write door.

---

## Assumptions

- Companion is the first (and in this phase only) agent that gets remember/forget tools; routing “remember that” when another agent is active is Phase 142.
- Closed predicate families can be specified in the plan as a finite list; adding a family later is a spec change, not an open-ended LLM vocabulary.
- Forget matches by predicate and/or sufficient natural-language identity of an existing fact; exact matching algorithm is a plan decision.
- Open-loop extraction’s conservative gate is the behavioral model to copy, not a shared library requirement.
- Phases 141 and 142 are separate specs; this phase can ship and be tested without prompt-constitution rewrite or cross-store routing.

## Out of Scope

- Read-side retrieval contract, `_format_memory` constitution order, silent use of facts (Phase 141).
- Routing table across reminders, loops, goals, ingest (Phase 142).
- Constraint veto on outbound mail/calendar (follow-up after 141/142).
- Rewriting news, prospecting, or goals tool catalogs.
- Claude-style `/memories` filesystem.

## Verbatim Constraints

- `remember_fact`
- `forget_fact`
- `PROMPT_SUPPLIED`
- `reviewed=true`
- `AgentResult.memory_proposals`
- `extract_facts`
- Contribution seam + NLI (user-supplied does not skip)
