# Feature Specification: Earned Memory Confirmations and Precise Forget

**Feature Branch**: `143-memory-claim-honesty`

**Created**: 2026-09-16

**Status**: Ready to implement

**Input**: User description: "Make I’ll remember / I forgot earned. Companion can still narrate success if the model skips tools. Close it on the turn path, not another prompt paragraph: Ze may confirm remembered/forgotten only after remember_fact / forget_fact returns ok. If the model claims memory without a successful tool, the response must be corrected/blocked/stripped so the user is not lied to. No shim, no dual door. Principle VIII. Same spec: forget match quality — today’s substring-then-loose cosine retracts too many facts; precision over recall (better ok false than retract the wrong facts). Out of this spec: P5 mail/calendar constraint veto; hard speech-act classifier; specialist catalog rewrites; Claude /memories filesystem; rewriting 140–142 write/read/routing."

**Governed by**: [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md) (Principle VIII — no shim, no dual door), [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md). Depends on Phase 140 (`remember_fact` / `forget_fact`), Phase 141 (prompt constitution; silent fact use), Phase 142 (speech-act routing). Follow-on living list: [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md). Does not start constraint veto (roadmap P5). Does not rewrite 140–142 write, read, or routing contracts.

---

## Overview

Phases 140–142 gave companion real remember and forget tools, a constitution that says “confirm only if ok,” and routing so forget is not used to cancel reminders. That is still **advice to the model**. On the live turn, companion can skip the tools and still tell the user it remembered or forgot. Forget matching is also unearned honesty: a loose substring or a weak similarity hit can retract the wrong facts, then the turn reports success.

This phase makes remembered and forgotten **earned on the turn path**. Confirmation is allowed only after `remember_fact` or `forget_fact` returns `ok`. An unearned claim in the reply is corrected, blocked, or stripped so the user is not lied to. Forget matching prefers a miss (`ok` false) over retracting the wrong biography. There is no second prompt paragraph that “should” fix this, and no compatibility door that still lets the old wording through.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Remembered and forgotten are earned on the turn (Priority: P1)

The user asks Ze to remember or forget something. Companion may call the existing tools. After the turn, the user-facing reply may say the fact is remembered or forgotten **only if** that tool returned success for this turn. If the model skips the tool, or the tool fails, or it returns no match, the user does not see a success story. The product does not rely on another instruction paragraph to police this. The path that builds the reply the user sees enforces it.

**Why this priority**: Unearned “I’ll remember” is the remaining lie after tools exist; prompt-only honesty already failed.

**Independent Test**: Drive companion with a remember utterance while the model returns a success sentence and no successful `remember_fact`. The stored reply must not claim memory. Repeat with a successful `ok` tool result: confirmation is allowed. Repeat for forget with `forget_fact`. A failed or missing tool must not produce a forgotten claim.

**Acceptance Scenarios**:

1. **Given** the user asks Ze to remember a durable fact, **When** the model replies “I’ll remember that” (or equivalent) without a successful `remember_fact` in this turn, **Then** the user-visible reply does not claim the fact is in memory.
2. **Given** `remember_fact` returns `ok` true in this turn, **When** Ze replies, **Then** it may confirm the fact is remembered.
3. **Given** `remember_fact` returns `ok` false (rejected write, missing fields, no id), **When** Ze replies, **Then** it does not claim the fact is remembered.
4. **Given** the user asks Ze to forget a biography fact, **When** the model claims it forgot without a successful `forget_fact` in this turn, **Then** the user-visible reply does not claim it is forgotten.
5. **Given** `forget_fact` returns `ok` true, **When** Ze replies, **Then** it may confirm forgotten.
6. **Given** `forget_fact` returns `ok` false (no match or store failure), **When** Ze replies, **Then** it does not claim forgotten.
7. **Given** any other agent or path that still emits companion-style memory confirmations without those tools, **When** this phase ships, **Then** there is not a second ungated door for the same wording (no shim that “lets streaming skip the gate”).

---

### User Story 2 - Forget matches the intended fact, or honestly misses (Priority: P2)

The user asks Ze to forget something specific. Forget looks for biography facts that actually match that request. A short or vague phrase must not wipe unrelated facts. A weakly similar biography must not be retracted as a convenience. If nothing is a precise match, the tool fails and the turn tells the truth (User Story 1 then forbids a forgotten claim).

**Why this priority**: Over-forget is the same honesty class as a fake remember; it ships in the same spec because forget success is otherwise untrustworthy.

**Independent Test**: Seed several facts. Retract with a query that is a precise match for one: only that fact is retracted. Retract with a query that is a substring of many values or only loosely similar: zero retractions (`ok` false), not a batch of near-misses.

**Acceptance Scenarios**:

1. **Given** one stored fact whose predicate or value is clearly the requested target, **When** the user asks to forget that target, **Then** that fact is retracted and unrelated facts remain current.
2. **Given** several stored facts whose values merely contain a short shared token from the query, **When** forget runs, **Then** it does not retract the set on substring coincidence alone.
3. **Given** stored facts that are only loosely similar to the query, **When** forget runs, **Then** it returns no match rather than retracting up to several near neighbors.
4. **Given** no precise match, **When** forget runs, **Then** the tool reports failure and no fact is marked forgotten.
5. **Given** a precise match on predicate name (the user named the stored label), **When** forget runs, **Then** that fact may be retracted without requiring a lucky similarity score.

---

### Edge Cases

- Model calls the tool **and** still writes an unearned confirmation while `ok` is false: the visible reply must follow the tool outcome, not the model’s sentence.
- Model calls the tool successfully **and** also recites unrelated “I also remembered X”: confirmation is earned only for the successful tool’s content, not for extra invented memories.
- Token streaming: wording that already left the model before the gate still must not be the **final** user-visible confirmation if the tool did not succeed. There is no streaming exemption.
- Empty, whitespace, or nonsense forget query: fail closed; retract nothing.
- Forget query that is an exact duplicate of many rows: retract only rows that meet the precise-match rule; do not treat “many weak hits” as success.
- User asked to forget a reminder, loop, or goal (Phase 142 R14): this phase does not retarget those stores; a biography miss stays a miss.
- Implicit preference stated without “remember that,” later extracted after the reply: the reply still must not claim “I’ll remember” unless `remember_fact` succeeded in this turn (extraction is not an in-turn success).
- Mixed language / casing / extra punctuation on an otherwise exact value: treat as the same target when the user clearly named that value; do not loosen into substring-of-any-value.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST allow a user-visible remembered confirmation only after `remember_fact` returns `ok` true in the same turn.
- **FR-002**: System MUST allow a user-visible forgotten confirmation only after `forget_fact` returns `ok` true in the same turn.
- **FR-003**: System MUST enforce FR-001 and FR-002 on the turn path that produces the user-visible reply (correct, block, or strip unearned claims). A new prompt paragraph alone does not satisfy this requirement.
- **FR-004**: System MUST treat a Python-level tool success that still carries `ok` false as not earned. Confirmation keys off the tool’s `ok` payload, not “the function returned without throwing.”
- **FR-005**: System MUST NOT leave an ungated companion reply path that can deliver remembered/forgotten confirmations without FR-001/FR-002 (no shim, no dual door).
- **FR-006**: Forget matching MUST prefer precision over recall: when the query does not uniquely and clearly identify stored biography facts, `forget_fact` MUST return `ok` false and retract nothing.
- **FR-007**: Forget matching MUST NOT retract facts solely because the query is a short substring of `predicate` or `value`, and MUST NOT retract a batch of merely similar facts as a fallback.
- **FR-008**: Forget matching MUST still retract a clearly identified fact (exact or equivalent predicate, or clearly identified value) when the user named that target.
- **FR-009**: Eval and grader criteria that currently reward unearned “I’ll remember” wording MUST be hard-cut to match FR-001–FR-003 (no dual standard in fixtures).
- **FR-010**: This phase MUST NOT implement mail/calendar constraint veto, a non-LLM speech-act classifier, specialist catalog rewrites, a memories filesystem, or a rewrite of Phase 140–142 write/read/routing contracts.

### Key Entities

- **Earned confirmation**: A user-visible statement that something was remembered or forgotten, allowed only after the matching tool returned `ok` true this turn.
- **Unearned claim**: Confirmation language (or equivalent) in the reply without that successful tool outcome.
- **Tool outcome**: The remember or forget result for this turn, including `ok` and any identifiers of written or retracted facts.
- **Forget target**: The biography fact(s) the user asked to retract; a miss is a first-class outcome, not a prompt to guess.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tested remember turns where the remember write did not succeed, graders find zero user-visible remembered confirmations.
- **SC-002**: In 100% of tested remember turns where the remember write succeeded, a remembered confirmation is allowed (not required to be robotic).
- **SC-003**: In 100% of tested forget turns where the forget write did not succeed, graders find zero user-visible forgotten confirmations.
- **SC-004**: On a fixture with several stored facts and a query that only loosely overlaps them, zero facts are retracted.
- **SC-005**: On a fixture with one clearly named stored fact among distractors, exactly that fact is retracted.
- **SC-006**: After this phase, there is a single confirmation rule in product tests: earned or absent — not “prompt says don’t lie” as a passing substitute.

---

## Assumptions

- Companion remains the only agent with `remember_fact` / `forget_fact`. Enforcement focuses on that agent’s user-visible reply. Other agents do not gain a parallel confirmation dialect in this phase.
- Detecting unearned claims may use conservative confirmation language (remembered / I’ll remember / forgotten / I forgot and close equivalents). Ordinary acknowledgements (“got it,” “okay”) without a memory-success claim are allowed.
- Extra invented memories in the same sentence as an earned confirmation are unearned for the extra content; the gate may strip the whole confirmation clause when it cannot separate them safely (fail closed on mixed claims).
- Forget still only retracts biography facts (Phase 142 R14). Improving cancel of reminders, loops, and goals is a later spec.
- Matching tightness is a plan-time algorithm choice; the spec pins outcomes (precision over recall), not a numeric similarity score.
- Post-turn extraction may still admit synthesized facts after the reply. That is not in-turn `remember_fact` success and does not license a remembered confirmation in the reply.

## Out of Scope

- Mail/calendar constraint veto (roadmap P5).
- Hard (non-LLM) speech-act classifier.
- Rewriting news, prospecting, calendar, or mail tool catalogs / specialist prompt constitution.
- Claude-style `/memories` filesystem.
- Rewriting Phase 140 admission, Phase 141 read constitution, or Phase 142 routing table.
- Making extraction itself non-LLM, or removing silent dual-write races between extraction and tools (later honesty work).
- Removing or shimming eval’s unused `memory_proposals_count` field except as listed on the honesty roadmap (not this phase unless a test here would otherwise lie).

## Verbatim Constraints

- `remember_fact`
- `forget_fact`
- `ok`
- `_retract_facts_matching`
- Principle VIII (no shim, no dual door)
- Confirm remembered/forgotten only after the matching tool returns `ok`

## After this feature / Future work

Ordered follow-ons. None of these is this phase. Sizes are suggested starting points for later specify runs. See also [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md).

1. **Phase 144 — Constraint veto on mail/calendar writes (P5)** — Standing constraint facts still do not block or confirm outbound mail and calendar actions. Wait until remembered/forgotten claims are earned so a veto is not itself an unearned “I won’t email after 22:00” line. Size: M.
2. **Phase 145 — Response-level unsolicited recitation** — Phase 141 forbids “I remember that you…” in the prompt; the reply path can still recite. Same turn-path philosophy as this phase, after confirmations are gated. Size: S.
3. **Phase 146 — Forget vs cancel across stores (R14 honesty)** — Users still say “forget the dentist” meaning a reminder. Companion may miss or hit biography by accident. Needs earned forget first so cancel is not a second fake success. Size: M.
4. **Phase 147 — Ingest vs remember honesty (R7)** — File ingest still writes synthesized facts while the model can talk as if `remember_fact` ran. Size: S.
5. **Phase 148 — Extractor honesty: dual-write and classifier** — Admission is still LLM JSON; extraction can race or duplicate an in-turn remember. A hard classifier is larger; start with dual-write races once confirmations are gated. Size: M (races) then L (hard classifier).
6. **Phase 149 — Specialist memory constitution** — Calendar, mail, and news prompts were deferred in 141. Size: M.
7. **Phase 150 — Eval `memory_proposals_count` hard-cut** — The field is always zero; judges already use tool calls. Delete rather than document forever. Size: S.
8. **Phase 151 — AGENTS.md / CLAUDE.md phase-index drift** — Companion guides disagree on later phase status; not product honesty but the same “claim vs source of truth” class. Size: S.
