# Feature Specification: Memory Read Contract and Prompt Constitution

**Feature Branch**: `141-memory-prompt-constitution`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "Read-side memory contract plus prompt constitution. Pin reviewed profile always-on; retrieve the rest; format confidence/recency/provenance in _format_memory. Reorder _build_system_prompt: constitution + agent job before retrieved biography. Shared constitution + rewrite companion (and memory-use rules). Do NOT rewrite every specialist agent in this spec. Silent use of retrieved facts. No unsolicited fact inline-mentions. TurnSurfacing stays for open items (loops/goals). Defer constraint veto on mail/calendar writes."

**Governed by**: [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), [`specs/arch/claim-topology.md`](../../arch/claim-topology.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md). Depends on Phase 106 (retrieval relevance), Phase 132 (`TurnSurfacing` for open items), Phase 134 (fact provenance). Phase 140 (admission + remember tools) should land first so prompt rules describe a real write path, but this spec is read-side and can be implemented against current stores. Follow-up: Phase 142 (speech-act routing). Constraint veto on mail/calendar writes is explicitly deferred.

---

## Overview

Retrieved memory is dumped into identity before the agent is told who it is or what its job is. Formatting still speaks an old provenance dialect and hides confidence and recency. Companion has no shared constitution for how to use memory: it may parrot facts unsolicited, or bury the job instructions under a biography blob.

This phase pins a **read contract**: reviewed profile facts are always in context; other facts are retrieved, not dumped wholesale. `_format_memory` shows confidence, recency, and provenance so the model can treat approximate inferences as approximate. `_build_system_prompt` leads with shared constitution and the agent’s job, then retrieved biography. Companion is rewritten to use memory silently. Unsolicited inline mentions of facts are forbidden. Open-item surfacing (loops, goals) stays on `TurnSurfacing` and is not replaced by fact name-dropping.

Specialist agents (calendar ISO-8601 rules, mail, news, prospecting, goals) are not rewritten here.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Stable identity is always present; the rest is retrieved (Priority: P1)

When a turn starts, reviewed profile facts (who the user is, standing preferences already confirmed) are in context without a similarity query. Other facts enter only if retrieval judges them relevant. The model can see whether a line is user-stated, inferred, how confident, and how recent.

**Why this priority**: Wrong or missing identity is worse than a missing retrieved tidbit; this is the read MVP.

**Independent Test**: Fixture with reviewed profile facts plus many irrelevant retrieved-pool facts. Prompt contains the profile set. Irrelevant pool facts are absent. Formatted lines include confidence, recency, and provenance — not the old synthesized-vs-raw dialect alone.

**Acceptance Scenarios**:

1. **Given** reviewed profile facts exist, **When** companion (or any agent using the shared formatter) builds a prompt, **Then** those facts are present even if they would not have won a similarity race.
2. **Given** a large pool of non-profile facts, **When** the user asks about an unrelated topic, **Then** those facts are not all dumped into the prompt.
3. **Given** a retrieved inferred fact, **When** formatted, **Then** the line shows it is approximate (confidence / provenance / recency), not as gospel identity.

---

### User Story 2 - Constitution and job precede biography (Priority: P1)

The system prompt states who Ze is and what this agent is doing **before** the retrieved biography block. Companion’s instructions include memory-use rules: use facts silently when they change the answer; do not announce “I remember that you…” unsolicited.

**Why this priority**: Instruction order is the difference between a tool that has a job and a biography that happens to answer.

**Independent Test**: Inspect `_build_system_prompt` output order: constitution + agent job appear before `_format_memory` / identity biography. Companion instructions contain silent-use rules.

**Acceptance Scenarios**:

1. **Given** a normal companion turn, **When** the system prompt is built, **Then** shared constitution and companion job text appear before the retrieved-memory biography.
2. **Given** companion instructions after this phase, **When** reviewed, **Then** they tell the model to apply relevant facts without unsolicited recitation.
3. **Given** a specialist agent (calendar, mail, news, prospecting, goals), **When** this phase ships, **Then** its domain instruction file is unchanged except for inheriting the shared prompt order/formatter.

---

### User Story 3 - No unsolicited fact mentions; open items stay on TurnSurfacing (Priority: P2)

Ze does not inject “by the way, you like X” fact chips into the turn. If something should surface unsolicited, it is an open item (loop, goal, workflow) via existing `TurnSurfacing`, not a memory fact.

**Why this priority**: Stops a second, conflicting mention channel.

**Independent Test**: Turn with retrieved but not user-asked preference facts and no overlapping open items: response and inline components contain no unsolicited fact mention. Turn with an overlapping open loop still surfaces via `TurnSurfacing`.

**Acceptance Scenarios**:

1. **Given** retrieved facts that are relevant to wording but not asked about, **When** companion replies, **Then** it may use them silently and MUST NOT add an unsolicited fact inline-mention.
2. **Given** an active open loop or in-flight goal that passes existing surfacing rules, **When** the turn runs, **Then** `TurnSurfacing` still mentions those open items.
3. **Given** this phase, **When** `surface_loops` / turn surfacing is inspected, **Then** it is not extended to dump memory facts as mention chips.

---

### Edge Cases

- No reviewed profile yet (new user): prompt still has constitution + job; biography may be empty; do not invent identity.
- All retrieved facts below the relevance floor: profile (if any) remains; rest omitted.
- Stale high-confidence inferred fact: recency/provenance formatting must make staleness visible; this phase does not add a new decay job.
- User explicitly asks “what do you know about me?”: recitation is solicited and allowed; silent-use rule does not forbid answers to direct questions.
- Constraint facts in context: the model SHOULD honor them in advice this phase; it MUST NOT newly block mail/calendar tools (deferred veto).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST always include reviewed profile facts in the agent memory context when they exist, without requiring a retrieval hit.
- **FR-002**: System MUST retrieve non-profile facts (existing relevance floor / budget) rather than dumping the full fact table into the prompt.
- **FR-003**: `_format_memory` MUST present confidence, recency, and provenance on formatted fact lines (replace the obsolete synthesized-vs-raw-only presentation).
- **FR-004**: `_build_system_prompt` MUST order content so shared constitution and the agent’s job precede retrieved biography / formatted memory.
- **FR-005**: System MUST ship a shared constitution block plus rewritten companion instructions covering memory-use (silent application, no unsolicited recitation).
- **FR-006**: System MUST NOT rewrite specialist agent instruction catalogs in this phase (calendar ISO-8601, mail, news, prospecting, goals tool lists stay as they are).
- **FR-007**: System MUST NOT emit unsolicited inline mentions of memory facts.
- **FR-008**: `TurnSurfacing` MUST remain the channel for open items (loops/goals); this phase MUST NOT fold fact dumps into that channel.
- **FR-009**: Constraint veto on mail/calendar writes is out of scope (follow-up after Phase 142); presence of a constraint fact in the prompt MUST NOT by itself disable those tools in this phase.

### Key Entities

- **Reviewed profile fact**: A user-confirmed standing fact treated as always-on identity, not a retrieved extra.
- **Retrieved fact**: A non-profile memory fact admitted to the prompt only by retrieval.
- **Shared constitution**: Standing rules for all agents using the shared prompt builder (memory use, honesty, no unsolicited fact mentions).
- **Open item**: Loop, goal, or workflow already ranked by `TurnSurfacing` — not a memory fact.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In fixtures with a reviewed profile plus 20+ irrelevant facts, 100% of reviewed profile facts appear in the prompt and fewer than the retrieval budget of irrelevant facts appear.
- **SC-002**: In a sampled companion prompt, constitution and job text occur before the biography/memory block in 100% of turns.
- **SC-003**: On a turn where facts are relevant only as silent context, graders find zero unsolicited “I remember that you…” fact mentions and zero new fact inline components.
- **SC-004**: An overlapping open-loop fixture still produces the existing open-item surfacing behavior.
- **SC-005**: Calendar/mail/news/prospecting/goals agent instruction files have no required rewrite in this phase’s task list.

---

## Assumptions

- “Reviewed profile” means facts already marked reviewed (onboarding seeds, successful `remember_fact` from Phase 140, or existing reviewed rows) — this phase does not invent a new profile store.
- Token budget for retrieved facts stays on the order of the current companion policy (~200 tokens) unless plan research shows the formatter overhead requires a documented bump.
- Identity builder may still exist; constitution + job-before-biography is the required order even if identity is refactored.
- Phase 140 landing first is preferred so companion tools and silent-use rules agree; if 141 implements first, constitution must not tell the model to call remember tools that do not exist yet.

## Out of Scope

- Write-side admission and remember/forget tools (Phase 140).
- Cross-store speech-act routing (Phase 142).
- Constraint veto on outbound mail/calendar (deferred follow-up; note for implementers: do not sneak it into companion instructions as a hard tool block).
- Rewriting specialist agents’ domain catalogs.
- Claude-style memories filesystem.
- Changing push budget or `PriorityView` ranking.

## Verbatim Constraints

- `_format_memory`
- `_build_system_prompt`
- `TurnSurfacing`
- reviewed profile always-on
- silent use of retrieved facts
- no unsolicited fact inline-mentions
