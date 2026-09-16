# Feature Specification: Specialist Memory Constitution

**Feature Branch**: `149-specialist-memory-constitution`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "Constitution + job order on calendar, mail, news agents. Not a new remember API (142 forbade extra remember tools on those catalogs)."

**Governed by**: [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md) (Principle VIII — no shim, no dual door), Phase 141 (shared constitution + job before biography; specialists deferred), Phase 142 (no extra `remember_fact` on those catalogs), [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md) item 149. Plugin code imports `ze_sdk` / owning plugin, never `ze_core`.

---

## Overview

Phase 141 put constitution and job **before** retrieved biography for the shared prompt builder, and rewrote companion. Calendar, mail, and news still have domain jobs that can be buried under biography, or they narrate remembering facts they cannot write. They must not gain `remember_fact` / `forget_fact` (Phase 142).

This phase applies constitution + job-before-biography to calendar, mail, and news, and teaches silent, honest memory use: apply facts; do not claim remember-tool success; do not recite unsolicited. No new remember API.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Job and constitution lead on calendar, mail, and news (Priority: P1)

When calendar, messenger (mail), or news builds a system prompt, shared constitution and that agent’s job appear **before** retrieved biography. The agent still receives reviewed facts for silent use.

**Why this priority**: 141’s order is the product; specialists were an explicit deferral.

**Independent Test**: For each of the three agents, inspect prompt order: constitution + job before formatted memory. Domain job text (ISO times, send rules, news retrieval) is still present and not pushed below a biography dump.

**Acceptance Scenarios**:

1. **Given** a calendar turn with retrieved facts, **When** the system prompt is built, **Then** constitution and calendar job precede biography.
2. **Given** a mail/messenger turn with retrieved facts, **When** the system prompt is built, **Then** constitution and mail job precede biography.
3. **Given** a news turn with retrieved facts, **When** the system prompt is built, **Then** constitution and news job precede biography.

---

### User Story 2 - Specialists do not narrate a remember API they do not have (Priority: P1)

Calendar, mail, and news do not tell the user they remembered or forgot via `remember_fact` / `forget_fact`. They may use facts silently (preferences, constraints as context — **not** Phase 144 write-gate veto). They do not gain those tools on their catalogs.

**Why this priority**: Honesty: specialists can still *speak* companion’s memory dialect without the tools.

**Independent Test**: Drive each specialist with biography in context. Model output claims “I’ll remember that.” User-visible reply must not claim remember-tool success. Catalog listing does not include `remember_fact` / `forget_fact`.

**Acceptance Scenarios**:

1. **Given** calendar, mail, or news, **When** tool catalogs are listed, **Then** they do not include `remember_fact` or `forget_fact`.
2. **Given** a specialist turn where the model claims it remembered a fact, **When** those tools are absent, **Then** the user-visible reply does not claim remember-tool success.
3. **Given** a relevant preference in context, **When** the specialist answers a domain question, **Then** it may apply the fact silently.

---

### User Story 3 - One constitution family, not a second dialect (Priority: P2)

Specialist memory rules are the same family as companion’s 141 constitution (silent use, no unsolicited recitation framing, job first). A specialist-only contradictory paragraph that still allows “I remember that you…” as style is a dual door.

**Why this priority**: Principle VIII.

**Independent Test**: Shared constitution text (or equivalent MUST rules) is what specialists inherit; they do not keep an old “chat about memory” block that contradicts it.

**Acceptance Scenarios**:

1. **Given** this phase ships, **When** calendar/mail/news instructions are read, **Then** they do not contradict the shared constitution on silent use and unsolicited recitation framing.
2. **Given** prospecting, goals, or other specialists, **When** this phase ships, **Then** they are not required to be rewritten here (calendar, mail, news only).

---

## Edge Cases

- Agent uses shared `_build_system_prompt` already: still verify job text order and domain instructions; do not add a second builder.
- Empty biography: constitution + job still lead.
- User asks a specialist “what do you know about me?”: they may answer from context without claiming a write; they should not pretend to run `remember_fact`.
- Constraint facts in calendar/mail context: visible for judgment; **blocking gated writes** is Phase 144, not this spec.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Calendar, mail (messenger), and news system prompts MUST place shared constitution and the agent job before retrieved biography.
- **FR-002**: Those agents MUST follow silent fact use and MUST NOT use unsolicited “I remember that you…” framing (same family as Phase 141).
- **FR-003**: Those agents MUST NOT add `remember_fact` or `forget_fact` to their tool catalogs.
- **FR-004**: Those agents MUST NOT claim remember-tool or forget-tool success in user-visible replies.
- **FR-005**: Plugin implementation MUST import `ze_sdk` / owning plugin, never `ze_core`.
- **FR-006**: This phase MUST NOT implement Phase 144 veto, 146–148 as a bundle, a `/memories` filesystem, or rewrite 140–142 write/read/routing contracts as a bundle.

### Key Entities

- **Shared constitution**: Phase 141 rules for how Ze uses memory (job first, silent use, no unsolicited recitation framing).
- **Specialist job**: Calendar / mail / news domain instructions (times, send, articles).
- **Remember API**: `remember_fact` / `forget_fact` — companion-only; not added here.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: For 100% of the three named agents, tested prompts show constitution + job before biography.
- **SC-002**: For 100% of those agents, catalogs exclude `remember_fact` and `forget_fact`.
- **SC-003**: In 100% of tested specialist turns that claim remember-tool success without those tools, graders find zero such user-visible claims.
- **SC-004**: After this phase, calendar/mail/news do not keep a contradictory memory-chat dialect beside the shared constitution.

---

## Assumptions

- Mail means the messenger agent (Gmail tools), not a renamed package.
- Shared prompt assembly from 141 may already order blocks; this phase still rewrites **domain instruction** text where it lags companion.
- Reply-path recitation enforcement on specialists MAY reuse 143/145 machinery if it already sits on a shared reply path; this spec’s MUST is constitution + order + no fake remember claims, not a new veto product.
- Prospecting, goals, workflows, reminders-as-own-agent: out unless they share the same instruction module (they do not, by default).

## Out of Scope

- New remember API on specialist catalogs.
- Constraint veto (144).
- Forget vs cancel (146), ingest (147), extractor races (148) as bundles.
- Claude-style `/memories` filesystem.
- Rewriting 140–142 contracts as a bundle.

## Verbatim Constraints

- `remember_fact`
- `forget_fact`
- `_build_system_prompt`
- `_format_memory`
- “I remember that you…”
- Principle VIII (no shim, no dual door)
- `ze_sdk`
- `ze_core`

## After this feature / Future work

Phase 150 eval + guide honesty. See [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md).
