# Feature Specification: Speech-Act Routing Across Stores

**Feature Branch**: `142-speech-act-routing`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "Speech-act routing across stores: remember-that vs reminder vs open loop vs goal vs ingest vs forget. Stop the fact extractor eating commitments. Product-sensitive routing table. Depends on spec 1 (admission + remember tools) and existing loop/reminder/goal agents. Defer constraint veto on mail/calendar writes (roadmap P5). Out of scope: rewriting news/prospecting/goals tool catalogs, Claude-style /memories filesystem."

**Governed by**: [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md), [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md). Depends on Phase 140 (`remember_fact` / `forget_fact` + admission gate), existing reminder agent (Phase 22), open-loop substrate (Phases 109–110), goal engine, ingestion (Phase 69). Phase 141 (prompt constitution) SHOULD already teach silent memory use but is not a hard blocker for routing tests. Constraint veto on mail/calendar writes is **deferred** (follow-up P5).

---

## Overview

“Remember that I have a dentist appointment Tuesday at 3” is not a biography fact. “I’ll start running this year” is not always a fact either. Today the fact extractor will eat commitments, timed tasks, and open concerns because it only knows “user said a sentence.” Reminders, loops, goals, and ingest already exist — they are not discoverable as the right door from companion.

This phase publishes a **routing table** and makes companion (and any turn that would otherwise extract a fact) follow it. Commitments stop becoming facts. Ambiguous utterances get a single primary store; secondary stores are explicit in the table (never silent dual-write of the same speech act as both fact and reminder). Forget applies to facts; cancel/complete language for reminders, loops, and goals uses those domains’ existing tools, not `forget_fact`.

---

## Routing table *(normative)*

Primary destination is the store Ze **writes**. “Also” is only allowed when the table says so. If a row says no, do not dual-write.

| # | User speech act (examples) | Primary destination | Also | Not |
|---|----------------------------|---------------------|------|-----|
| R1 | “Remember that I prefer aisle seats.” / “Please remember my partner’s name is Alex.” Durable identity, preference, standing constraint. | Fact via `remember_fact` (or extraction if it already passed Phase 140 gate **and** the user did not need an explicit speech act) | — | Reminder, loop, goal |
| R2 | “Forget that I like aisle seats.” / “Stop remembering X.” | `forget_fact` | — | Cancel reminder/loop/goal unless the user also names those |
| R3 | “Remind me Tuesday at 3 to call the dentist.” / “Nudge me in 20 minutes.” Timed ping with a fire time. | Reminder | — | Fact |
| R4 | “I have a dentist appointment Tuesday at 3” when the user asked to **remember the appointment as a timed event**, or used remind/calendar language. | Reminder (and calendar event only if they asked to put it on the calendar — existing calendar agent, not a new tool in this spec) | — | Fact |
| R5 | “I need to figure out whether to switch jobs.” / lingering unresolved concern without a fire time or a multi-week plan. | Open loop | — | Fact, reminder |
| R6 | “Help me ship the thesis by June” / multi-week outcome with milestones implied. | Goal | — | Fact of the goal text |
| R7 | “Read this PDF / ingest this” with a document. | Ingest | Extracted document facts still follow Phase 133 MemorySink (synthesized, cited) — not `remember_fact` | Treating the file as a single biography fact |
| R8 | “I’ll call Mom Tuesday.” Time-bound personal **commitment**. | Reminder if a usable time is present; otherwise open loop | — | **Fact** (extractor MUST drop) |
| R9 | “Never email anyone after 22:00.” / standing **constraint**. | Fact (constraint family) via remember or gated extraction | — | Reminder. **Do not** implement send-time veto on mail/calendar tools in this phase (follow-up P5) |
| R10 | Right-now / weather / filler. | Drop | — | All stores |
| R11 | “Remember to call Mom Tuesday at 3.” **Remember + time**. | Reminder (time wins) | — | Biography fact of the call |
| R12 | “What do you know about me?” / recall question. | Read path (Phase 141) — no write | — | New fact |
| R13 | Ambiguous “keep this in mind” with **no** time, **no** durable predicate, **no** clear concern. | Ask one clarifying question **or** open loop if it is an unresolved concern; do **not** guess a fact | — | Silent fact write |
| R14 | Forget/cancel a reminder, close a loop, abandon a goal. | That domain’s existing cancel/complete/close tools | — | `forget_fact` unless they also named a biography fact |

**Conflict rule:** If two rows could apply, **time trigger beats biography fact** (R3, R4, R8, R11 beat R1). **Multi-week outcome beats loop** (R6 beats R5). **Explicit remember of a standing preference beats extraction** (R1 tool). Never write the same utterance to fact and reminder.

These rows are the product defaults for this spec. Remaining product questions (below) are non-blocking unless an implementer hits an utterance that matches none of the rows — then extend the table in this spec, do not invent a fifteenth store.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Timed “remember” becomes a reminder, not a fact (Priority: P1)

The user says to remember a timed task. Ze creates a reminder (existing reminder tools), not a biography fact. The fact extractor does not store the commitment.

**Why this priority**: This is the most common mis-route today and the commitment eval fixture’s reason for existing.

**Independent Test**: Utterances from R3, R8, R11: reminder (or loop if no time) exists; fact table unchanged for that utterance.

**Acceptance Scenarios**:

1. **Given** “Remind me Tuesday at 3 to call the dentist”, **When** the turn completes, **Then** a reminder exists and no new fact is stored for that appointment.
2. **Given** “I’ll call Mom Tuesday”, **When** extraction and routing run, **Then** no fact is stored; a reminder is stored if Tuesday is resolvable, otherwise an open loop.
3. **Given** “Remember to call Mom Tuesday at 3”, **When** routed, **Then** primary is reminder, not `remember_fact`.

---

### User Story 2 - Durable remember and forget still hit fact tools (Priority: P1)

Standing preferences still use Phase 140 tools. Forget of a preference does not cancel unrelated reminders.

**Why this priority**: Routing must not steal the remember door Phase 140 just built.

**Independent Test**: R1/R2 utterances: `remember_fact` / `forget_fact`; no reminder row.

**Acceptance Scenarios**:

1. **Given** “Remember that I prefer aisle seats”, **When** companion runs, **Then** `remember_fact` is used and no reminder is created.
2. **Given** “Forget that I prefer aisle seats”, **When** companion runs, **Then** `forget_fact` is used and existing unrelated reminders remain.

---

### User Story 3 - Concerns and multi-week outcomes hit loops and goals (Priority: P2)

Unresolved concerns become open loops. Multi-week outcomes become goals. Neither is stored as a user fact that “the user wants X” unless the user also asked to remember a standing preference.

**Why this priority**: Stops the extractor from flattening the world-state into predicates.

**Independent Test**: R5 vs R6 fixtures; loop store vs goal store; fact count zero for the utterance body.

**Acceptance Scenarios**:

1. **Given** an unresolved concern without a deadline, **When** routed, **Then** an open loop is created or matched, not a fact.
2. **Given** a multi-week outcome request, **When** routed, **Then** goal creation (existing goal agent/tools) is used, not a fact and not only a reminder.

---

### User Story 4 - Ingest and drop stay on their paths (Priority: P3)

Documents go through ingest. Ephemeral utterances hit no store. Constraint facts may be stored; they do not yet block mail/calendar sends.

**Why this priority**: Completes the table without expanding tool catalogs.

**Independent Test**: R7, R9, R10 fixtures.

**Acceptance Scenarios**:

1. **Given** an ingest request with a document, **When** handled, **Then** ingest runs; companion does not call `remember_fact` on the raw file.
2. **Given** ephemeral filler, **When** routed, **Then** no store write.
3. **Given** a standing constraint, **When** routed, **Then** a constraint fact may be stored and mail/calendar tools remain callable (veto deferred).

---

### Edge Cases

- User says both “remember I prefer X” and “remind me at 3”: two speech acts in one turn — two writes, one per clause, not a merge into one fact.
- Reminder already exists for the same fire time and text: existing reminder dedup/behavior; do not also write a fact.
- Goal vs loop borderline (“I want to get fitter”): if no timeframe and no milestone language, loop (R5); if they ask to plan months of work, goal (R6). Prefer one clarifying question over dual-write (R13).
- User “forgets” a dentist appointment that was stored as a reminder: use reminder cancel, not `forget_fact` (R14).
- Extraction after a routed reminder: still `[]` for that commitment (Phase 140 FR-003 held).

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST route conversational speech acts according to the normative routing table in this spec (R1–R14), with the conflict rule (time beats fact; multi-week outcome beats loop; no silent fact+reminder dual-write).
- **FR-002**: System MUST stop the fact extractor from admitting commitments (R8) and timed remember-to-act utterances (R11).
- **FR-003**: Companion MUST use existing reminder, loop, goal, and ingest capabilities for those rows rather than inventing parallel stores.
- **FR-004**: System MUST NOT add remember/forget tools to news, prospecting, or goals catalogs in this phase; those agents keep their current tools. Routing happens from companion / turn-level admission, which may hand off to the existing domain agent.
- **FR-005**: `forget_fact` MUST only retract biography facts (R2). Cancel/close of reminders, loops, and goals MUST use those domains (R14).
- **FR-006**: Constraint facts (R9) MUST NOT newly disable mail or calendar writes in this phase (follow-up: constraint veto, roadmap P5).
- **FR-007**: Eval coverage MUST include remember, forget, ephemeral, constraint, and commitment, plus at least one reminder-timed, one loop, and one goal utterance from the table.
- **FR-008**: When an utterance matches no row, system MUST NOT silently write a fact; it may ask one clarifying question or open a loop (R13).

### Key Entities

- **Speech act**: The user’s intent (remember, forget, remind, concern, goal, ingest, drop), not the surface verb alone (“remember to…” can be a reminder).
- **Primary destination**: The one store that owns the write.
- **Follow-up P5 — constraint veto**: Future work: standing constraint facts block or confirm outbound mail/calendar actions. Not this phase.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of commitment and timed-remember fixtures create zero biography facts.
- **SC-002**: 100% of R3/R11 fixtures result in a reminder (when time parses) rather than `remember_fact`.
- **SC-003**: 100% of R1 fixtures still persist via `remember_fact` (or gated extraction for non-explicit durable statements) with no reminder.
- **SC-004**: R5 vs R6 fixtures land in loop vs goal stores respectively, with zero facts for the utterance body.
- **SC-005**: Graders find no dual-write of the same clause to fact and reminder.
- **SC-006**: Mail/calendar send tools remain enabled in the presence of constraint facts (veto not shipped).

---

## Assumptions

- Time parsing uses the existing reminder/calendar natural-language path; if time cannot be parsed for R8, fall back to open loop, not to fact.
- Calendar **event** creation stays the calendar agent’s job; this spec does not add a new calendar tool to companion. R4 “put it on my calendar” is a handoff, not a new API.
- Goal vs loop uses existing goal-agent entry points; this spec does not redesign goal planning.
- Phase 140 tools exist before this phase is implemented.
- Handoff to specialists uses existing delegate/routing mechanisms; this spec does not rewrite those agents’ catalogs.

## Remaining product questions *(non-blocking defaults already in the table)*

These are recorded so a later product pass can override the table without pretending the spec was silent:

1. **Calendar vs reminder for appointments (R4):** Default is reminder unless the user says to put it on the calendar. Override would be “always create a calendar event for dated appointments.”
2. **Goal vs loop for vague self-improvement (R6 vs R5):** Default is loop unless timeframe/milestones are present. Override would be “always offer a goal.”
3. **Constraint veto (P5):** Default this phase is store-only. Override (future spec) would confirm or block outbound mail/calendar.

## Out of Scope

- Phase 140 admission internals except that commitments must remain dropped from extraction.
- Phase 141 prompt order, except routing should not introduce unsolicited fact mentions.
- Constraint veto on mail/calendar writes (roadmap P5).
- Rewriting news, prospecting, or goals tool catalogs.
- Claude-style `/memories` filesystem.
- New stores or a unified “inbox of all speech acts” UI.

## Verbatim Constraints

- `remember_fact`
- `forget_fact`
- Routing table R1–R14
- No silent fact+reminder dual-write
- Constraint veto deferred (roadmap P5)
