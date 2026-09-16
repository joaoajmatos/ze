# Feature Specification: Constraint Veto on Gated Writes

**Feature Branch**: `144-constraint-veto-mail-calendar`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "Standing reviewed constraint facts must block or honestly confirm outbound mail and calendar writes. Intercept messenger/calendar write tools; read reviewed constraint facts; confirm or refuse. “I won’t send that because of your constraint” is earned only if the veto actually ran. No new remember API. Out: recitation, forget-vs-cancel, ingest, extractor, specialist constitution rewrite as a bundle, /memories filesystem." **Scope pin (same day):** the veto must not be a closed mail/calendar catalog. Plugins extend; a check that only knows `send_email` / calendar mutations is future dual-door debt. Ship **one** opt-in write gate that any plugin can join. Mail and calendar remain the first required adopters, not the only possible ones.

**Governed by**: [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md) (Principle VIII — no shim, no dual door), [`specs/arch/ze-doctrine.md`](../../arch/ze-doctrine.md), [`specs/arch/contribution-seam.md`](../../arch/contribution-seam.md), [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md) item 144 (P5). Depends on Phase 140 (`constraint` family + `remember_fact`), Phase 141 (reviewed facts always-on), Phase 142 (R9 stores the constraint as a fact and **defers** this veto), Phase 143 (earned “I won’t…” language — a veto claim is the same honesty class). Plugin code imports `ze_sdk` / owning plugin, never `ze_core`.

---

## Overview

Standing constraints such as “never email after 22:00” already live as reviewed biography facts. They do not stop writes that would violate them. The model can still send or schedule, or can *say* it refused because of a constraint without any check having run.

This phase adds **one** enforcement path for writes that a plugin marks as constraint-gated. Before those writes complete, Ze reads **reviewed** constraint facts and either refuses, or asks for an honest confirmation. The user-visible line “I won’t do that because of your constraint” is allowed only after that veto actually ran. There is no new remember tool. There is no second path that still performs the same kind of write without the check.

Mail send and calendar mutations are the first required adopters. The gate is not those tool names. A later messenger, reminder, or outreach plugin joins the same gate instead of copying a mail-only if-list.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - One write gate plugins can join (Priority: P1)

A plugin author adds or already owns a write that acts in the user’s world on their behalf (send a message, create an event, set a timed ping, send outreach). They mark that write as constraint-gated. From then on, reviewed standing constraints are evaluated before the write completes. They do not fork a private “check constraints” helper, and they do not leave an ungated twin of the same write.

Writes that are not gated (memory remember/forget, internal stores, read tools) are unchanged. Marking is opt-in so `remember_fact` is not treated as an email.

**Why this priority**: Without a shared gate, every new plugin reimplements or skips P5. That is the dual door this phase exists to prevent.

**Independent Test**: A write marked constraint-gated that violates a seeded reviewed constraint cannot complete without refuse or confirm. The same write unmarked is out of this story except as a negative: in-tree outbound message/calendar/reminder writes required below must be marked. A new fictional gated write (or a test double) is enough to prove the gate is not hard-coded to `send_email`.

**Acceptance Scenarios**:

1. **Given** a write marked constraint-gated and a reviewed constraint that applies to it, **When** that write is invoked, **Then** it does not complete without refuse or explicit user confirmation.
2. **Given** a write marked constraint-gated and no applicable reviewed constraint, **When** it is invoked, **Then** this phase does not invent a veto.
3. **Given** a write that is not constraint-gated (for example `remember_fact`), **When** it runs, **Then** this phase does not intercept it as a constraint veto.
4. **Given** this phase ships, **When** an implementer looks for a mail-only special case beside the gate, **Then** there is no second complete path for the same gated write (no shim, no twin).
5. **Given** a future plugin marks a new outbound write constraint-gated, **When** a reviewed constraint applies to that write, **Then** the same gate refuses or confirms — no new core catalog entry of tool names is required.

### User Story 2 - In-tree outbound and calendar-like writes adopt the gate (Priority: P1)

Existing in-tree writes that send mail, mutate the calendar, or set/cancel user reminders must be on the gate in this phase, so shipping “the seam” without the tools the user already has is not a hollow pass. Prospecting outreach that sends to a person is the same class of write and MUST join. Read-only listing and true drafts (save without send) follow the draft rule in Edge Cases.

**Why this priority**: These are the live doors Phase 142 deferred. Leaving reminders or outreach ungated while mail is gated is the catalog tax again.

**Independent Test**: Seed a reviewed constraint about not contacting or not scheduling in a window. Drive `send_email`, calendar create/update/delete, reminder writes, and prospecting send/outreach that would violate it: no silent complete. Drive non-matching writes: no invented veto.

**Acceptance Scenarios**:

1. **Given** a reviewed constraint that forbids the intended send, **When** the user asks Ze to send that mail, **Then** `send_email` does not complete without refuse or explicit confirmation.
2. **Given** a reviewed constraint that forbids the intended calendar mutation, **When** the user asks Ze to `create_event`, `update_event`, or `delete_event` in that way, **Then** the write does not complete without refuse or confirmation.
3. **Given** a reviewed constraint that forbids the intended reminder write, **When** Ze would create or fire a reminder that violates it, **Then** that write does not complete without refuse or confirmation.
4. **Given** a reviewed constraint that forbids contacting a person or sending outreach in a window, **When** prospecting would send that outreach, **Then** the send does not complete without refuse or confirmation.
5. **Given** read-only calendar or mail listing, **When** the user asks what is there, **Then** this phase does not intercept as a write veto.

### User Story 3 - Veto language is earned; no new remember API (Priority: P2)

If the model claims it refused because of a constraint, that sentence is user-visible only after the gate ran this turn. Companion does not gain another remember tool. Specialists do not get `remember_fact` on their catalogs in this phase.

**Why this priority**: Same honesty class as Phase 143. A prompt that says “respect constraints” beside an ungated write is a shim.

**Independent Test**: Model reply claims a constraint refusal with no gate run → claim stripped or absent. After a real refuse/confirm, the claim may remain. No new remember tool in catalogs.

**Acceptance Scenarios**:

1. **Given** the model says it will not send or schedule because of a constraint, **When** the veto did not run this turn, **Then** the user-visible reply does not claim that refusal.
2. **Given** the veto ran and refused or held for confirm, **When** Ze replies, **Then** it may say it will not proceed (or is waiting) because of the user’s constraint.
3. **Given** this phase ships, **When** an implementer looks for a new remember API, **Then** none was added; constraints still enter via `remember_fact` / gated extraction.
4. **Given** an unreviewed or retracted constraint, **When** a gated write is attempted, **Then** that fact does not veto.

---

## Edge Cases

- Constraint fact exists but is not reviewed: no veto.
- Constraint was forgotten (Phase 143 precise `forget_fact` `ok`): no veto.
- Multiple reviewed constraints: if any applicable constraint forbids the write, refuse or confirm; do not require the model to pick one.
- Ambiguous applicability (constraint text could reasonably apply or not): confirm rather than silent complete; do not silent-refuse on a stretch reading (fail toward asking).
- A constraint about email does not automatically forbid a calendar write, and the reverse, unless the fact clearly covers both (or messaging/scheduling in general). Ambiguous overlap waits for confirmation.
- User explicitly overrides after confirmation: the write may proceed; later turns still re-check unless the constraint itself changed.
- `draft_email` (save without send): not treated as outbound send; time-of-send constraints do not veto drafts. A constraint that forbids *composing* to a person still SHOULD confirm or refuse a draft to that person when the draft clearly names them.
- Time-window constraints use the user’s configured timezone at evaluation time, not a silent UTC guess.
- Streaming: an early “I won’t send…” token is not the final user-visible veto claim unless the veto ran.
- Any agent calling a gated write: the veto is on the write, not on companion prompt text.
- Workspace, finance import, contact store, and memory remember/forget are not constraint-gated in this phase unless they are the same outbound/schedule class (they are not). Workspace keeps its own mode gate.
- Archive / local-only mutations that do not contact a person and do not create a timed fire are not required adopters.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST evaluate **reviewed** facts in the `constraint` family before a **constraint-gated** write completes. Which writes are gated is declared by the owning plugin (opt-in mark on the write), not a core hard-coded list of mail/calendar tool names.
- **FR-002**: System MUST refuse the write, or hold it for explicit user confirmation, when a reviewed constraint applies to that gated write. Silent complete against an applicable constraint is forbidden.
- **FR-003**: System MUST allow a user-visible “I won’t … because of your constraint” (or equivalent) only after that veto actually ran in this turn. A prompt paragraph alone does not satisfy this requirement.
- **FR-004**: System MUST NOT veto from unreviewed, retracted, or non-`constraint` facts.
- **FR-005**: System MUST NOT leave an ungated twin of a constraint-gated write that completes the same act without FR-001 (no shim, no dual door). Adding a new outbound plugin MUST join this gate rather than a second checker.
- **FR-006**: System MUST NOT add a new remember API. Constraints continue to enter memory through existing `remember_fact` / Phase 140 gated extraction.
- **FR-007**: Plugin implementation MUST import from `ze_sdk` / the owning plugin, never `ze_core`.
- **FR-008**: This phase MUST mark as constraint-gated all in-tree writes that send mail to a person, mutate calendar events, create or cancel user reminders, or send prospecting outreach. It MUST NOT require gating of `remember_fact`, `forget_fact`, read tools, or unrelated internal stores.
- **FR-009**: Matching MUST be conservative: apply when the fact clearly governs that write (channel, party, time window, or named calendar). If applicability is unclear, confirm; do not silent-send and do not silent-refuse on a stretch reading.
- **FR-010**: This phase MUST NOT implement response-level unsolicited recitation, forget-vs-cancel across stores, ingest-vs-remember honesty, extractor dual-write races, specialist constitution rewrite as a bundle, or a `/memories` filesystem.

### Key Entities

- **Reviewed constraint**: A current, reviewed biography fact in the `constraint` family (Phase 140 keep family; Phase 141 reviewed-always-on).
- **Constraint-gated write**: A plugin write marked to run through this phase’s gate. First required set: outbound mail send, calendar create/update/delete, reminder writes, prospecting send/outreach.
- **Write description**: Enough of the intended act for matching (what kind of act, optional channel, parties, time). Plugins supply this for gated writes so “never email after 22:00” is not a blank check on every tool.
- **Applicable constraint**: A reviewed constraint that reasonably governs this gated write.
- **Veto outcome**: Refuse, confirm-and-wait, or allow. Allow only when no applicable reviewed constraint forbids the write.
- **Earned veto claim**: User-visible language that Ze blocked or held a write because of a constraint, allowed only after the veto ran.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: In 100% of tested constraint-gated writes that violate a seeded reviewed constraint, the write does not complete without refuse or explicit confirmation.
- **SC-002**: In 100% of tested `send_email` and calendar create/update/delete writes that violate a seeded reviewed constraint, the write does not complete without refuse or confirmation.
- **SC-003**: In 100% of tested reminder and prospecting-outreach writes that violate a seeded reviewed constraint, the write does not complete without refuse or confirmation.
- **SC-004**: In 100% of tested turns where the model claims a constraint refusal and the veto did not run, graders find zero user-visible veto claims.
- **SC-005**: In 100% of tested gated writes with no applicable reviewed constraint, the veto does not block the write.
- **SC-006**: After this phase, product tests have a single rule for constraint-based refusal language: earned by a real veto, or absent. A test double that is not mail/calendar can still be blocked by the same gate.

---

## Assumptions

- Constraint-gated is **opt-in per write**. Default off. That keeps memory and internal stores out. The anti-debt rule is FR-005 + FR-008: in-tree outbound/schedule writes must opt in; a new plugin with the same class of write must opt in rather than a new if-branch in core.
- Matching uses a write description (kind, channel, parties, time), not substring of the tool name. Conservative applicability, not a new NLI product. Vague constraints wait for confirmation rather than silent complete.
- Confirmation reuses the existing user confirmation request (approve / deny), not a new UI chrome.
- “Reviewed” means the same reviewed-fact set Phase 141 already injects; this phase does not invent a second review flag.
- Companion remains without extra remember tools. Specialists keep existing catalogs (Phase 142 forbade extra remember tools there).
- Phase 143’s earned-confirmation machinery may be reused for veto claims; this spec does not re-open remember/forget `ok` gating.
- Directory name stays `144-constraint-veto-mail-calendar` for the existing spec-kit folder; the feature is the gate, not those two domains only.

## Out of Scope

- Response-level unsolicited recitation (Phase 145).
- Forget vs cancel across stores (Phase 146 / R14).
- Ingest vs remember honesty (Phase 147 / R7).
- Extractor dual-write / dedup races (Phase 148).
- Specialist memory constitution rewrite as a bundle (Phase 149).
- Claude-style `/memories` filesystem.
- Rewriting Phase 140–142 write/read/routing contracts as a bundle.
- A new remember API on specialist catalogs.
- Gating workspace, finance import, or contact-table writes (different gates / not this class).
- A hard NLI constraint parser (later if conservative matching is too deaf).

## Verbatim Constraints

- `constraint_gate`
- `send_email`
- `create_event`
- `update_event`
- `delete_event`
- `draft_email`
- `constraint`
- `remember_fact`
- `forget_fact`
- `ok`
- Principle VIII (no shim, no dual door)
- “I won’t send that because of your constraint”
- `ze_sdk`
- `ze_core`

## After this feature / Future work

Ordered siblings, not this phase. See [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md).

1. Phase 145 — Response-level unsolicited recitation.
2. Phase 146 — Forget vs cancel across stores (R14).
3. Phase 147 — Ingest vs remember honesty (R7).
4. Phase 148 — Extractor dual-write / dedup races (hard classifier later).
5. Phase 149 — Specialist memory constitution.
6. Phase 150 — Eval + guide honesty (`memory_proposals_count` hard-cut + AGENTS.md / CLAUDE.md indexes).
