# Feature Specification: Response-Level Unsolicited Recitation

**Feature Branch**: `145-unsolicited-recitation`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "141 forbids “I remember that you…” in the prompt; the reply can still recite. Same turn-path philosophy as 143. Extend companion reply gate (or shared constitution enforcement) to unsolicited recitation. TurnSurfacing still owns open items. Out: 144 veto."

**Governed by**: [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md) (Principle VIII — no shim, no dual door), [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md) item 145. Depends on Phase 141 (prompt forbids unsolicited “I remember that you…”; silent fact use; `TurnSurfacing` owns open items) and Phase 143 (earned confirmation on the turn path). Plugin code imports `ze_sdk` / `ze_personal`, never `ze_core`.

---

## Overview

Phase 141 told the model not to open with “I remember that you…”. Phase 143 gates remembered/forgotten **success** claims on tool `ok`. The **reply** can still recite biography the user did not ask for — a second unearned memory performance.

This phase extends the same turn-path gate that 143 uses (companion reply enforcement, or shared constitution enforcement on that path) so unsolicited recitation is corrected, blocked, or stripped before the user sees it. Open items stay on `TurnSurfacing`. Constraint veto on gated writes (Phase 144) is not this spec.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Biography is not recited unless asked (Priority: P1)

The user says something that does not ask Ze to recall biography. Companion has facts in context and may still write “I remember that you like aisle seats.” The user-visible reply must not volunteer that recitation. If the user **asks** what Ze knows, recall remains allowed (Phase 141 read path).

**Why this priority**: Prompt-only anti-recitation already failed; the remaining lie is in the reply.

**Independent Test**: Inject reviewed facts. Drive a turn whose user text is not a recall question. Model output contains “I remember that you…” (or equivalent unsolicited recitation). Stored/user-visible reply does not. Drive an explicit recall question: stating known facts is allowed.

**Acceptance Scenarios**:

1. **Given** reviewed facts in context and a user turn that does not ask for recall, **When** the model recites biography with “I remember that you…” or equivalent unsolicited memory framing, **Then** the user-visible reply does not include that recitation.
2. **Given** the user asks what Ze knows or asks about a specific stored fact, **When** Ze replies, **Then** it may state those facts (silent use without the forbidden framing is still preferred; answering the question is allowed).
3. **Given** Phase 143 earned “I’ll remember that” after `remember_fact` `ok` true, **When** this gate runs, **Then** it does not strip that **confirmation** as recitation.
4. **Given** `TurnSurfacing` mentions an open item, **When** this gate runs, **Then** it does not strip or re-own that mention.

---

### User Story 2 - One reply door (Priority: P2)

Unsolicited recitation is enforced on the same class of path as 143: the path that produces the user-visible companion reply. A second streaming or specialist dialect that still recites is a dual door.

**Why this priority**: Principle VIII.

**Independent Test**: Companion reply path with streaming partials still ends without unsolicited recitation in the final visible text. No parallel companion-style recitation door is added.

**Acceptance Scenarios**:

1. **Given** token streaming of an unsolicited recitation sentence, **When** the turn finishes, **Then** the final user-visible reply does not contain that recitation.
2. **Given** this phase ships, **When** companion delivers a reply, **Then** there is not an ungated twin that skips the recitation gate.

---

## Edge Cases

- “I remember that you asked me to send this email” as task paraphrase vs biography recitation: strip biography-framed recitation; do not treat ordinary task restatement as recitation.
- Earned remember/forget confirmations (143) are not recitation.
- Open-item lines from `TurnSurfacing` are not recitation.
- User quotes their own past (“as I told you, I like aisle seats”): Ze repeating that in-turn content is not unsolicited memory recitation.
- Empty or tiny replies: do not invent recitation; do not fail the turn.
- Multilingual equivalents of “I remember that you…”: treat as recitation when they clearly frame stored biography as a memory reveal.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST enforce a ban on unsolicited biography recitation on the companion turn path that produces the user-visible reply (correct, block, or strip). A new prompt paragraph alone does not satisfy this requirement.
- **FR-002**: System MUST still allow stating facts when the user asked for recall, and MUST still allow silent use of facts without recitation framing (Phase 141).
- **FR-003**: System MUST NOT treat Phase 143 earned remembered/forgotten confirmations as unsolicited recitation.
- **FR-004**: System MUST leave open-item mentions to `TurnSurfacing`; this phase MUST NOT move or duplicate that ownership.
- **FR-005**: System MUST NOT leave an ungated companion reply path that can deliver unsolicited “I remember that you…” recitation (no shim, no dual door).
- **FR-006**: This phase MUST NOT implement constraint veto on gated writes (Phase 144), forget-vs-cancel, ingest honesty, extractor races, specialist constitution as a bundle, or a `/memories` filesystem.

### Key Entities

- **Unsolicited recitation**: User-visible language that reveals stored biography as a memory performance without the user asking to recall.
- **Asked recall**: A user turn that requests what Ze knows or names a fact to check.
- **Open item mention**: `TurnSurfacing` content about loops, goals, workflows — not biography recitation.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tested non-recall turns where the model output contains unsolicited biography recitation, graders find zero such recitation in the user-visible reply.
- **SC-002**: In 100% of tested explicit recall questions, stating the asked facts remains allowed.
- **SC-003**: In 100% of tested turns with an earned remember/forget confirmation, that confirmation is still allowed when the tool `ok` rule of Phase 143 is met.
- **SC-004**: After this phase, tests have a single recitation rule: gated on the reply path, not “the prompt said not to.”

---

## Assumptions

- Detection uses conservative framing (“I remember that you…”, “I remember you…”, “as I recall you…”) plus close equivalents. Ordinary empathy without a memory-reveal frame is allowed.
- Companion is the in-scope agent. Specialist constitution is Phase 149.
- Reuse the Phase 143 reply-gate location rather than a second enforcement product.
- Open items remain `TurnSurfacing` even if the model also tries to recite them; this gate only strips biography recitation, not surfacer output.

## Out of Scope

- Constraint veto on gated writes (Phase 144).
- Forget vs cancel across stores (Phase 146).
- Ingest vs remember honesty (Phase 147).
- Extractor dual-write races (Phase 148).
- Specialist memory constitution (Phase 149).
- Claude-style `/memories` filesystem.
- Rewriting Phase 140–142 write/read/routing contracts as a bundle.

## Verbatim Constraints

- `TurnSurfacing`
- `remember_fact`
- `forget_fact`
- `ok`
- “I remember that you…”
- Principle VIII (no shim, no dual door)
- `ze_sdk`
- `ze_core`

## After this feature / Future work

See [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md). Next honesty specs: 146 forget-vs-cancel, 147 ingest, 148 extractor races, 149 specialists, 150 eval+guides.

## Approach

- Extend the Phase 143 companion reply gate (or the shared constitution enforcement already on that path) so unsolicited biography recitation is stripped/blocked in the user-visible reply.
- Keep earned `remember_fact` / `forget_fact` `ok` confirmations and `TurnSurfacing` open-item lines.
- Tests and eval scenarios for non-recall recitation vs asked recall; do not implement Phase 144 veto here.
