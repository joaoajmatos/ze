# Implementation Plan: Mind (W5)

**Branch**: `189-web-mind` | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md (Clarifications 2026-10-17 are binding), `main` at b5fdc1c1 (183 shell and 184 composed answers landed). Planned to build in parallel with 186 World; 185 and 195 pieces are split into the last two task phases.

## Summary

Mind becomes one place at `/mind` with four modules (Beliefs, People, Entity search, Procedures) and an entity page at `/mind/:entityId`. Two additive backend reads make it honest: `claim_kind` on feed items, so belief rows show what kind of claim they are, and `searchEntities`, so the entity view starts from a real search instead of filtering the top 50 graph nodes. The 3D whole-graph view and its three.js dependencies are deleted. Procedures (candidates and library) move here from the Mind interim page and Doing.

## Technical Context

**Language/Version**: TypeScript 5, React 19, TanStack Query 5 (ze-web); Python 3.12 (ze-memory admin, ze-api router).
**Primary Dependencies**: none new. Removed: `react-force-graph-3d`, `three`, `three-spritetext`, `@types/three`.
**Storage**: no migration; reads only.
**Testing**: vitest + Testing Library; pytest with `AsyncMock` pools for the two backend reads; one `@pytest.mark.pg` test for the entity search SQL.
**Constraints**: FSD; DESIGN.md tokens; no raw fact key renders (SC-001); no whole-graph view; neighbourhood ≤ 24 nodes, deterministic.
**Scale**: single user; feed paged by `before`; search limit ≤ 50.

## Constitution Check

| Principle | Check |
|---|---|
| Spec first | spec.md + Clarifications; plan and tasks here. |
| Honest claims | Claim kind comes from the record (new field); no sparkline without a prior; "No entity named X" when search finds nothing. |
| Package boundaries | ze-memory admin + ze-api router for reads; ze-personal only drops its nav entry; ze-web consumes. |
| Pre-v1 hard cuts | Old Mind pages and widgets, the 3D graph and its dependencies, the procedures page and the Contacts nav entry go in this phase. |
| Tests | Fail-first per task. |
| Docs are part of done | [DOCS] tasks cover "Docs touched". |

## Blast radius

`graphify affected` on `main` b5fdc1c1 (graph refreshed at plan time) plus `rtk proxy grep`:

| Symbol | Callers | Change |
|---|---|---|
| `BrainMemoryPage` | `pages/brain-memory/index.ts`; `routes.tsx` (`mindLoaders.memory`), its test | Deleted. |
| `BrainGraphPage` | `pages/brain-graph/index.ts`; `routes.tsx` (`mindLoaders.graph`) | Deleted. |
| `MemoryFeed`, `TimelineScrubber`, `ProcedureCandidatesList` | `BrainMemoryPage.tsx` only | Deleted; rebuilt as `widgets/beliefs-feed` and `widgets/procedures`. |
| `MemoryGraph` (+ `entityNodeObject`, three.js) | `BrainGraphPage.tsx` only | Deleted; `lib/entityActivitySeries.ts` moves to `widgets/entity-neighbourhood/lib`. |
| `ProcedureManagement` | `pages/procedures/ui/ProceduresPage.tsx` (Doing interim `procedures` loader) | Deleted with `pages/procedures`; `DoingInterim` loses its Procedures section (188 deletes `DoingInterim` later). |
| `MindInterim` (grep) | `routes.tsx`, its test | Deleted; `MindPage` + `MindEntityPage`. |
| redirects (grep) | `places.ts`, `places.test.ts`, `routes.test.tsx`, `AppShell.test.tsx` (`/mind/graph`), `features/ask-bar` screen tests (195 deletes `resolve-screen`) | `/brain-graph` → `/mind`; `/mind/graph` → `/mind`; `/doing/procedures` → `/mind`; `/contacts` → `/mind`. |
| `useMemoryFeedQuery` etc. (`entities/memory-feed-item`) | old widgets; `/jarvis` `model/world.ts` | Kept; `/jarvis` unaffected. |
| `MemoryFeedItem` (ze-api schema), `get_memory_feed` (ze-memory admin) | `memory/router.py`, `tests/api/test_routes.py`, `v0/__init__.py` | Add `claim_kind: str | None`. |
| `get_memory_graph`, `get_entity_detail` | `memory/router.py` | Unchanged; new `search_entities` beside them. |
| `PersonalPlugin.ui_contributions` | manifest (`GET /api/v0/ui/manifest`), web plugin nav | The contacts entry is removed. `getContactsPage` stays. |
| `three`, `react-force-graph-3d`, `three-spritetext`, `@types/three` (package.json) | only `widgets/memory-graph` (grep) | Removed; `vite build` output no longer contains three.js. |

Parallel touch points with 186 (both edit them): `app/router/routes.tsx`, `shared/config/places.ts` (+ tests), `shared/lib/query-keys.ts`, `shared/lib/claim-posture.ts`. Each phase edits only its own place's lines; the second to land rebases.

## Design

### Backend (additive)

- `ze_memory/admin.py::get_memory_feed`: select `claim_kind` for facts (`NULL::TEXT` for episodes); `MemoryFeedItem.claim_kind: str | None`.
- `ze_memory/admin.py::search_entities(pool, *, q, entity_type, limit) -> list[dict]`: `canonical_name ILIKE '%' || $1 || '%' OR EXISTS (alias ILIKE …)` (escape `%`/`_` in `q`), optional type, ordered by degree (the same degree subquery `get_memory_graph` uses) then name; returns `GraphEntityNode` rows. `q` 1..80 chars.
- `api/v0/memory/router.py`: `GET /memory/entities` (`searchEntities`, `response_model=list[GraphEntityNode]`, summary, description, `limit` 1..50 default 20).
- `plugins/ze-personal/ze_personal/plugin.py`: drop the contacts `UiContribution` (the base default is `[]`; keep any other entries).

### Web

- `shared/lib/claim-posture.ts` (shared with 186): `postureOf(claim_kind, …) → told | evidenced | inferred | suspected | goal | plain`, glyph, chip label, plain-word state; no raw enum output.
- `entities/memory-feed-item`: add `useSearchEntitiesQuery(q, type)`; `lib/belief.ts` (pure): `beliefSentence(item)`: the value as a sentence, never the raw `key` (`exercise_habit: …` → the value only; an empty value → omitted row label "A fact Ze holds"); `sinceLabel`, source words for `provenance` and `agent`.
- `entities/contact` (new): `useContactsPageQuery()` calling `getContactsPage`.
- `widgets/beliefs-feed`: rows (glyph, sentence, confidence readout, source, since, reviewed/contradicted marks), facts and episodes distinct, keep/drop inline via `useReviewFactMutation` (`confirm`/`reject`), infinite paging by `next_before`, the as-of readout (`getMemoryTimelineBounds`; a date control whose value prints as a mono readout, not a bar chart), empty state text.
- `widgets/people`: the Contacts tree through `ConnectedPrimitiveTree` inside a `Module`; loading/error/empty states.
- `widgets/entity-search`: search box (debounced 250 ms, `searchEntities`), results as rows (type, name, degree), "No entity named X" keeps the query; select navigates to `/mind/:entityId`.
- `widgets/entity-neighbourhood`: `lib/radial.ts` (pure, deterministic): centre entity; neighbours grouped by predicate around the circle in a fixed predicate order, sorted by name within a group; cap 24, "+N more" readout; `lib/entityActivitySeries.ts` (moved) for the sparkline; facts list (belief rows); phone: grouped list by predicate instead of the field.
- `widgets/procedures`: candidates first (`useProcedureCandidatesQuery`, `features/review-procedure`), then library rows (status, version, last invoked) with detail (`useProcedureDetailQuery`) and `features/procedure-review` controls (edit, disable).
- `pages/mind`: `MindPage` (desktop: Beliefs centre, People + Entity search + Procedures in the rail; phone: Beliefs → People → Entity search → Procedures). `pages/mind-entity`: `MindEntityPage` (`/mind/:entityId`; non-UUID → not found).
- Router: `mind` index → `MindPage`, `mind/:entityId` → `MindEntityPage`; delete `mindLoaders`; Doing interim drops `procedures`.

### Split phases

- **After 185** (`listHypotheses`): `entities/hypothesis` is created by 186 or here, whichever lands first (same file plan as 186 T003). The entity page's "I suspect …" module lists `listHypotheses?entity_id=` with posture, relation words, evidence labels and the 185 feedback actions (useful / not relevant / mute, and clear).
- **After 195**: Beliefs publishes `selection` and `visible`; the entity page publishes `subject` (`entity`); every belief row (`fact`), person (contact rows have no ids: the People module's chip uses `kind: "entity"` only from entity rows, not the contacts tree), entity row and procedure row/module wires `ChatAboutChip` and `Module.onChatAbout` by props.

## Project Structure

### Documentation (this feature)

```
specs/phases/189-web-mind/
├── spec.md
├── plan.md
└── tasks.md
```

### Source Code

```
core/cognition/ze-memory/ze_memory/admin.py ; apps/ze-api/ze_api/api/v0/memory/{router,schemas}.py
plugins/ze-personal/ze_personal/plugin.py
apps/ze-web/src/pages/{mind,mind-entity}/
apps/ze-web/src/widgets/{beliefs-feed,people,entity-search,entity-neighbourhood,procedures}/
apps/ze-web/src/entities/{memory-feed-item,contact,hypothesis}/ ; shared/lib/claim-posture.ts
apps/ze-web/src/app/router/routes.tsx ; shared/config/places.ts ; pages/doing/ui/DoingInterim.tsx
apps/ze-web/package.json ; packages/ze-client/src/generated/*
```

## Docs touched ([DOCS] tasks)

- `docs/frontend.md`: Mind place, widgets, deleted Brain pages and graph, redirects.
- `docs/memory.md`: feed `claim_kind`; entity search route; Mind as the place to review beliefs.
- `docs/architecture.md`: REST table (`searchEntities`, feed field), web section.
- `docs/features.md`: Mind (beliefs, people, entity view, procedures).
- `core/cognition/ze-memory/README.md`: admin reads.
- `plugins/ze-personal/README.md`: contacts render in Mind › People, no nav entry.
- `AGENTS.md`: phase row 189; Learned Workspace Facts nav line (Knowledge group gone; Mind holds memory, people, procedures); `specs/README.md` row 189.

## Complexity Tracking

None.
