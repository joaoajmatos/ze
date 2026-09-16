# Feature Specification: Eval `memory_proposals_count` Hard-Cut and Guide Phase-Index Honesty

**Feature Branch**: `150-eval-guide-honesty`

**Created**: 2026-09-16

**Status**: Implemented

**Input**: User description: "One spec, one directory (phase 150). Delete EvalChatResponse.memory_proposals_count (always 0; AgentResult.memory_proposals gone; judges use tool_calls). Sync AGENTS.md / CLAUDE.md phase indexes through 143 (and list these new pending specs if the indexes list phases). Hard-cut, no shim. Title should make both jobs obvious."

**Governed by**: [`specs/arch/pre-v1-hard-cuts.md`](../../arch/pre-v1-hard-cuts.md) (Principle VIII — no shim, no dual door), [`specs/arch/memory-honesty-roadmap.md`](../../arch/memory-honesty-roadmap.md) items 150 and 151 (bundled here). `AgentResult.memory_proposals` is already gone. Plugin code imports `ze_sdk` / owning plugin, never `ze_core`.

---

## Overview

Eval still exposes `EvalChatResponse.memory_proposals_count`, always `0`. Judges already use `tool_calls`. Keeping the field documents a ghost API. The same honesty class: `AGENTS.md` and `CLAUDE.md` phase indexes do not agree with shipped work through Phase 143, so the guides claim a different source of truth.

This phase **deletes** `memory_proposals_count` everywhere it is part of the eval contract (schema, server, generated clients, tests, docs) and **syncs** both guide indexes through 143, listing 144–150 as pending if those tables list phases. No deprecated alias. No “always 0” comment left as a shim.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Eval remember/forget is tool_calls only (Priority: P1)

An eval client or judge looks at a chat eval response. There is no `memory_proposals_count` field. Remember and forget are judged from `tool_calls` (`remember_fact` / `forget_fact`). In-tree callers and docs are updated in this same phase.

**Why this priority**: A forever-zero field is a compatibility shim before v1.

**Independent Test**: OpenAPI / `EvalChatResponse` / eval server payload omit the field. Tests that asserted `== 0` are deleted or rewritten to `tool_calls`. A payload that still includes the field is a spec fail.

**Acceptance Scenarios**:

1. **Given** `EvalChatResponse` after this phase, **When** a client reads the schema, **Then** `memory_proposals_count` is absent (not present and ignored).
2. **Given** the eval server handler, **When** it returns a chat eval result, **Then** it does not set or document that field.
3. **Given** generated TypeScript / docs / tests, **When** this phase ships, **Then** they do not keep a dual “legacy always 0” door.

---

### User Story 2 - Guide indexes match the phase list (Priority: P1)

Someone reading `AGENTS.md` or `CLAUDE.md` sees Phase 140–143 in the phase index when that file lists phases, consistent with specs. Phases 144–150 appear as pending if the table is the kind that lists later work. The two files do not disagree with each other on those rows.

**Why this priority**: Roadmap 151 is the same claim-vs-source-of-truth class.

**Independent Test**: Diff both indexes against `specs/README.md` for 140–150. 140–143 match shipped/current status; 144–150 are pending (or omitted only if that file’s table is a short “done only” list — then both files use the same rule). Default: if the table lists 140+, it lists through 150.

**Acceptance Scenarios**:

1. **Given** `CLAUDE.md` lists later phases, **When** this phase ships, **Then** it includes 140–143 accurately and lists 144–150 as pending if it continues the table.
2. **Given** `AGENTS.md` has a Phase status table, **When** this phase ships, **Then** it does not omit 140–143 while `CLAUDE.md` includes them (no split truth).
3. **Given** a reader compares the two guides, **When** looking at memory-honesty phases, **Then** they see the same story.

---

## Edge Cases

- OpenAPI codegen: regenerate rather than hand-edit a stale `types.gen.ts` **and** leave the Python field (that would be a dual door).
- External snippets in `docs/eval.md`: delete the column/row; do not mark deprecated.
- Tests that only check the field is 0: delete those assertions; they are not a behavior.
- Phase 143 status in guides should match reality at implement time (Done vs Tasks); do not invent Done if 143 is still in flight — **Assumption**: implement syncs to then-current `specs/README.md`.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST delete `EvalChatResponse.memory_proposals_count` from the eval API schema, eval server, generated clients, and tests. Callers in-tree MUST be updated in this phase (no shim, no always-0 leftover field).
- **FR-002**: Eval judges and docs MUST treat remember/forget as `tool_calls` (`remember_fact` / `forget_fact`), not a proposals count.
- **FR-003**: `AGENTS.md` and `CLAUDE.md` phase indexes MUST be synced through Phase 143 and MUST list 144–150 as pending when those indexes list phases.
- **FR-004**: The two guides MUST NOT disagree with each other on the presence or status of phases 140–150.
- **FR-005**: This phase MUST NOT implement 144–149 product behavior, a `/memories` filesystem, or restore `AgentResult.memory_proposals`.

### Key Entities

- **Eval chat response**: The eval HTTP result object formerly carrying `memory_proposals_count`.
- **Phase index**: The phase-status tables in `AGENTS.md` and `CLAUDE.md`.
- **tool_calls**: The remaining judge surface for remember/forget.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of eval schema and handler definitions omit `memory_proposals_count`.
- **SC-002**: 100% of in-repo tests and docs that mentioned the field are updated or deleted (zero “legacy always 0” descriptions).
- **SC-003**: Both guide phase tables agree on 140–143 and, if they list later phases, on 144–150 pending.
- **SC-004**: After this phase, there is one eval remember/forget signal (`tool_calls`) and one guide index story.

---

## Assumptions

- Bundling roadmap 150 and 151 in **one** spec directory is intentional; there is no Phase 151 folder.
- Client codegen runs as part of implement if `types.gen.ts` is generated; hand-keeping the field after Python deletion is forbidden.
- `specs/README.md` is already updated for 144–150 in the specify pass that created those dirs; guides catch up in **this** phase’s implement.
- Status strings (Done vs Pending) for 143 copy `specs/README.md` at implement time.

## Out of Scope

- Product work in 144–149 (already specified elsewhere).
- Restoring `AgentResult.memory_proposals`.
- Claude-style `/memories` filesystem.
- Rewriting 140–142 contracts.

## Verbatim Constraints

- `EvalChatResponse.memory_proposals_count`
- `AgentResult.memory_proposals`
- `tool_calls`
- `remember_fact`
- `forget_fact`
- `AGENTS.md`
- `CLAUDE.md`
- Principle VIII (no shim, no dual door)

## After this feature / Future work

Honesty roadmap items 144–149 remain separate product specs. Hard speech-act classifier stays later L after 148. No Phase 151 directory.
