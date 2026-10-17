# Feature Specification: Mind (W5)

**Feature Branch**: `189-web-mind`

**Created**: 2026-10-17

**Status**: Draft (spec level; plan and tasks follow once scheduled)

**Input**: Maestro brief 2026-10-17, phase W5; overhaul plan sections a (Mind), b.4, e (Phase W5). User decision 4: entity-first neighbourhood; the whole-graph hairball is deleted.

**Governed by**: `DESIGN.md` (honesty visuals), `PRODUCT.md` (claims have kinds, provenance, decaying confidence), phases 88/93/94/119/121 (memory feed, as-of, graph, entity activity), 128/130 (social cognition), 138–139 (procedures), 140–149 (memory honesty: silent use, earned confirmations, precise forget).

**Depends on**: 183 (shell), 195 (screen context, "Chat about this"). Uses 185 (hypotheses list) for the entity view's "I suspect …" section; without it that section is absent.

**Doctrine functions served**: memory (what Ze believes and since when), social cognition (people and projects), reflection (hypotheses, procedures).

---

## Overview

Mind shows what Ze believes about the user and the people and projects around them, with kind, confidence and age, and the way to correct it, at `/mind` and `/mind/:entityId`. It replaces the interim Mind sections from 183 (Memory, Graph), the Contacts plugin page (rendered inside People) and the procedure library.

## Modules

- **Beliefs**: the memory feed as rows: glyph by claim kind, sparkline of confidence decay where the API gives both ends, source, "since"; keep/drop review inline (`reviewFacts`); facts and episodes visually distinct; raw fact keys never shown (`exercise_habit:` becomes a sentence via the value or is omitted); an "as of" scrubber as a readout (`getMemoryTimelineBounds`, `as_of` on `getMemoryFeed`), not a bar chart.
- **People**: contacts as rows with last contact, projects (WORKS_ON / COLLABORATES_WITH), stale follow-ups; the server-driven Contacts page rendered as HUD modules (191 generalises plugin pages; this phase handles Contacts directly).
- **Entity** (`/mind/:entityId`, search first): one-hop neighbourhood as a small field (`getEntityDetail`, `getMemoryGraph` scoped), activity over time as a sparkline (`getMemoryActivity`), facts about it, hypotheses involving it (185).
- **Procedures**: library, versions, invocations (`listProcedureLibrary`, `getProcedure`, `editProcedure`, `disableProcedure`).

## User Scenarios & Testing *(mandatory)*

1. **Every belief shows kind, confidence, source, since (P1).** Test: feed row posture mapping table.
2. **Review a fact inline (P1)** with keep/drop; the row updates.
3. **Search an entity and see its neighbourhood (P1)**; "No entity named X" keeps the search; no whole-graph render exists.
4. **As-of time travel (P2)** changes the feed and prints the date as a readout.
5. **Phone (P1)**: Beliefs → People → Entity search; the neighbourhood becomes a grouped list.

States: empty beliefs → "I have not learned anything yet. Tell me about yourself or connect Gmail."

## Requirements *(mandatory)*

- **FR-001**: `pages/mind`, `pages/mind-entity`; widgets `beliefs-feed`, `people`, `entity-neighbourhood`, `procedure-library`.
- **FR-002**: The neighbourhood layout is deterministic (radial by relation type) and capped (one hop, ≤ 24 nodes, "+N more" readout).
- **FR-003**: Hard cuts: `pages/{brain-memory,brain-graph}`, `widgets/{memory-feed,memory-graph,timeline-scrubber,procedure-management}`, the memory-growth chart, `react-force-graph-3d`, `three`, `three-spritetext` and `@types/three` dependencies if no other slice uses them, the Contacts plugin page route (rendered in People), `pages/mind/ui/MindInterim.tsx`, the procedures library part of `pages/procedures`.
- **FR-003a**: Screen context (phase 195): Beliefs publishes the selected beliefs as `selection` and the visible rows; the entity page publishes the entity as `subject`; every belief, person, entity and procedure module or row wires "Chat about this" (callbacks passed down by props from widgets, 195 FR-024), with a test per kind.
- **FR-004**: Acceptance: critique ≥ 29/40; detector 0; captures.

## Success Criteria *(mandatory)*

- **SC-001**: No whole-graph view exists; no raw fact key renders.
- **SC-002**: `make test-web`, `make typecheck-web`, `make web-build`, lint pass; bundle no longer includes three.js (check `vite build` output).

## Out of Scope

- Editing facts beyond keep/drop and the existing forget path; new memory APIs.

## Owning packages

ze-web only; no backend, no migration.
