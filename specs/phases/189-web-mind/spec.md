# Feature Specification: Mind (W5)

**Feature Branch**: `189-web-mind`

**Created**: 2026-10-17

**Status**: Implemented. Was: ready to implement on `main` with 183 and 184 (plan and tasks written 2026-10-17 against `main` b5fdc1c1). Phase 6 tasks wait for 185 (hypotheses) and Phase 7 tasks wait for 195 (screen context); everything else starts now, alongside 186.

**Input**: Maestro brief 2026-10-17, phase W5; overhaul plan sections a (Mind), b.4, e (Phase W5). User decision 4: entity-first neighbourhood; the whole-graph hairball is deleted.

**Governed by**: `DESIGN.md` (honesty visuals), `PRODUCT.md` (claims have kinds, provenance, decaying confidence), phases 88/93/94/119/121 (memory feed, as-of, graph, entity activity), 128/130 (social cognition), 138–139 (procedures), 140–149 (memory honesty: silent use, earned confirmations, precise forget).

**Depends on**: 183 (shell) and 184 (on `main`). Split tasks: the entity view's "I suspect …" section needs 185 (`listHypotheses`); screen context and "Chat about this" need 195. Both are separate task phases at the end; the rest builds in parallel with 186.

**Doctrine functions served**: memory (what Ze believes and since when), social cognition (people and projects), reflection (hypotheses, procedures).

---

## Clarifications

### Session 2026-10-17 (planning against the code, parallel build)

- **Mind owns procedures, library and candidates.** Today the candidates review sits on the Mind interim page (`BrainMemoryPage`) and the library under Doing (`/doing/procedures`). Procedures are what Ze learned how to do (reflection), so Mind's Procedures module holds both, and 188 drops "procedure candidates" from Doing. 188's spec is updated accordingly (2026-10-17). Both floors still edit `pages/doing/ui/DoingInterim.tsx` and `doingLoaders`: if 188 lands first and has deleted `DoingInterim`, 189's edit there is a no-op.
- **Neither the feed nor the entity detail exposes claim kind.** `memory_facts.claim_kind` exists (zm016, NOT NULL) but `getMemoryFeed` does not return it, and `getEntityDetail` facts carry only id, key, value, agent, created_at. This phase adds `claim_kind` to `MemoryFeedItem`, and `claim_kind`, `confidence`, `reviewed`, `contradicted`, `provenance` to the detail's facts (`FactDigestItem`), so entity facts render as belief rows with Keep/Drop/Edit (no migration).
- **The entity detail neighbours are an arbitrary 20** (`LIMIT 20`, no order, no total). The query gains `ORDER BY degree DESC, canonical_name`, the response gains `neighbour_total`, and the field caps at 20 with "+N more" from the total. Facts (20) and episodes (10) stay capped, so the activity sparkline is labelled "last 20 facts and 10 episodes".
- **Belief rows keep Edit.** Keep, Drop and Edit (`reviewFacts` `confirm`/`reject`/`edit`) all stay, at 44 px.
- **The as-of control filters by `created_at`**; kind, confidence and review state are current values, and the readout says "kinds and confidence as of now". Facts carry no prior confidence, so belief rows show no sparkline (DESIGN.md: draw it only when the API gives both ends).
- **Entity search is client-side over the top 50 graph nodes today.** "Search first" needs a server search: `GET /api/v0/memory/entities?q=&entity_type=&limit=` (`searchEntities`), name and alias match ordered by degree, in `ze_memory.admin` + the ze-api memory router. No migration.
- **People renders the Contacts plugin page inside the People module** (`getContactsPage`, the server-driven tree that holds contact details). Its separate nav entry is removed (`ze-personal` `ui_contributions`), and `/contacts` redirects to `/mind`. A person entity opens in the entity view from search. The contact cards carry no ids, so People has no per-row "Chat about this" (191's spec is updated: News is the only remaining plugin nav entry).
- **The claim posture table moves to `shared/lib/claim-posture.ts`**, shared with 186 World (whichever lands first creates it).

## Overview

Mind shows what Ze believes about the user and the people and projects around them, with kind, confidence and age, and the way to correct it, at `/mind` and `/mind/:entityId`. It replaces the interim Mind sections from 183 (Memory, Graph), the Contacts plugin page (rendered inside People) and the procedure library.

## Modules

- **Beliefs**: the memory feed as rows: glyph by claim kind (new `claim_kind` field), confidence, source, "since" (no sparkline: facts have no prior value); keep/drop review inline (`reviewFacts`); facts and episodes visually distinct; raw fact keys never shown (`exercise_habit:` becomes a sentence via the value or is omitted); an "as of" scrubber as a readout (`getMemoryTimelineBounds`, `as_of` on `getMemoryFeed`), not a bar chart.
- **People**: the server-driven Contacts page (`getContactsPage`) rendered inside the People module (191 generalises plugin pages; this phase handles Contacts directly). Projects and relations of a person show in the entity view.
- **Entity** (`/mind/:entityId`, search first via `searchEntities`): one-hop neighbourhood as a small field (`getEntityDetail` neighbours and edges), activity over time as a sparkline (from the entity's facts and episodes, as `entityActivitySeries` does today), facts about it, hypotheses involving it (185, split phase).
- **Procedures**: candidates review first (`listProcedureCandidates`, `reviewProcedureCandidate`), then the library, versions and invocations (`listProcedureLibrary`, `getProcedure`, `editProcedure`, `disableProcedure`).

## User Scenarios & Testing *(mandatory)*

1. **Every belief shows kind, confidence, source, since (P1).** Test: feed row posture mapping table.
2. **Review a fact inline (P1)** with keep/drop; the row updates.
3. **Search an entity and see its neighbourhood (P1)**; "No entity named X" keeps the search; no whole-graph render exists.
4. **As-of time travel (P2)** changes the feed and prints the date as a readout.
5. **Phone (P1)**: Beliefs → People → Entity search; the neighbourhood becomes a grouped list.

States: empty beliefs → "I have not learned anything yet. Tell me about yourself or connect Gmail."

## Requirements *(mandatory)*

- **FR-001**: `pages/mind`, `pages/mind-entity`; widgets `beliefs-feed`, `people`, `entity-search`, `entity-neighbourhood`, `procedures`; `BeliefRow` in `entities/memory-feed-item/ui`.
- **FR-002**: The neighbourhood layout is deterministic (radial by relation type) and capped (one hop, ≤ 20 nodes from the ordered detail query, "+N more" from `neighbour_total`).
- **FR-003**: Hard cuts: `pages/{brain-memory,brain-graph,procedures}`, `widgets/{memory-feed,memory-graph,timeline-scrubber,procedure-management,procedure-candidates}`, `react-force-graph-3d`, `three`, `three-spritetext` and `@types/three` (only `widgets/memory-graph` uses them), the Contacts nav entry (`ze-personal` `ui_contributions`; the `getContactsPage` route stays, People renders it), `pages/mind/ui/MindInterim.tsx`, the Doing interim's Procedures section (`/doing/procedures` redirects to `/mind`).
- **FR-003b**: Backend (additive, no migration): `MemoryFeedItem.claim_kind`; `FactDigestItem` claim fields; ordered neighbours and `neighbour_total` on `getEntityDetail`; `searchEntities`.
- **FR-003a**: Screen context (phase 195): Beliefs publishes the selected beliefs as `selection` and the visible rows; the entity page publishes the entity as `subject`; every belief, entity and procedure module or row wires "Chat about this" (People's contact cards have no ids) (callbacks passed down by props from widgets, 195 FR-024), with a test per kind.
- **FR-004**: Acceptance: critique ≥ 29/40; detector 0; captures.

## Success Criteria *(mandatory)*

- **SC-001**: No whole-graph view exists; no raw fact key renders.
- **SC-002**: `make test-web`, `make typecheck-web`, `make web-build`, lint pass; bundle no longer includes three.js (check `vite build` output).

## Out of Scope

- Editing facts beyond keep, drop, edit and the existing forget path; memory APIs beyond the additive reads in FR-003b.

## Owning packages

ze-web; ze-memory (`admin.py` feed column and entity search) and ze-api (memory router) for the two additive reads; ze-personal (`ui_contributions`); no migration.
