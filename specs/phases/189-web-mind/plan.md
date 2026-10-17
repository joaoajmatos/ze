# Implementation Plan: Mind (W5)

**Branch**: `189-web-mind` | **Date**: 2026-10-17 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md (Clarifications 2026-10-17 are binding), `main` at b5fdc1c1 (183 shell and 184 composed answers landed). Planned to build in parallel with 186 World; 185 and 195 pieces are split into the last two task phases. Revised after Gauge's review (M-1..M-10).

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
| `get_memory_graph` | `memory/router.py`; `/jarvis` uses `useMemoryGraphQuery` | Unchanged; new `search_entities` beside it. |
| `get_entity_detail`, `FactDigestItem`, `EntityDetailResponse` | `memory/router.py`, `widgets/memory-graph/ui/EntityDetailPanel.tsx` (deleted here) | Facts gain claim fields; neighbours ordered; `neighbour_total`. |
| `PersonalPlugin.ui_contributions` | manifest (`GET /api/v0/ui/manifest`), web plugin nav | The contacts entry is removed. `getContactsPage` stays. |
| `three`, `react-force-graph-3d`, `three-spritetext`, `@types/three` (package.json) | only `widgets/memory-graph` (grep) | Removed; `vite build` output no longer contains three.js. |

Parallel touch points: with 186, `app/router/routes.tsx`, `shared/config/places.ts` (+ tests), `shared/lib/query-keys.ts` (entity-search and contacts-page keys), `shared/lib/claim-posture.ts`, `entities/hypothesis`; with 188 and 190, `pages/doing/ui/DoingInterim.tsx` and `doingLoaders` (189 drops Procedures, 190 drops Workspace, 188 deletes the file; if 188 landed first, 189's edit is a no-op). Each phase edits only its own lines; the second to land rebases.

## Design

### Backend (additive)

- `ze_memory/admin.py::get_memory_feed`: select `claim_kind` for facts (`NULL::TEXT` for episodes); `MemoryFeedItem.claim_kind: str | None`.
- `ze_memory/admin.py::get_entity_detail`: facts select `claim_kind, confidence, reviewed, contradicted, provenance` too (`FactDigestItem` gains them); the neighbours query orders by degree DESC then `canonical_name` (LIMIT 20 stays) and a count query returns `neighbour_total` (distinct entity neighbours); `EntityDetailResponse.neighbour_total: int`.
- `ze_memory/admin.py::search_entities(pool, *, q, entity_type, limit) -> list[dict]`: `canonical_name ILIKE $1 ESCAPE '\\' OR EXISTS (SELECT 1 FROM jsonb_array_elements_text(e.aliases) a WHERE a ILIKE $1 ESCAPE '\\')` with `%`, `_` and `\\` escaped in `q` and wrapped in `%…%` (aliases are a JSONB array, zm001), optional type, ordered by degree (the same degree subquery `get_memory_graph` uses) then name; returns `GraphEntityNode` rows. `q` 1..80 chars.
- `api/v0/memory/router.py`: `GET /memory/entities` (`searchEntities`, `response_model=list[GraphEntityNode]`, summary, description, `limit` 1..50 default 20).
- `plugins/ze-personal/ze_personal/plugin.py`: drop the contacts `UiContribution` (the base default is `[]`; keep any other entries).

### Web

- `shared/lib/claim-posture.ts` (shared with 186): `postureOf(claim_kind, …) → told | evidenced | inferred | suspected | goal | plain`, glyph, chip label, plain-word state; no raw enum output.
- `entities/memory-graph`: add `useSearchEntitiesQuery(q, type)` beside `useEntityDetailQuery`.
- `entities/memory-feed-item`: `lib/belief.ts` (pure, ENG): `beliefSentence(key, value)`: when the value is already a sentence (3 or more words) it is the sentence; otherwise the predicate is humanised (`works_at` → "Works at", `exercise_habit` → "Exercise habit") and joined with the value ("Works at Acme"); an empty value → "A fact Ze holds"; the raw key with its underscores never renders. `sinceLabel`, source words for `provenance` and `agent`. `ui/BeliefRow.tsx`: glyph, sentence, confidence, source, since, reviewed/contradicted marks, Keep/Drop/Edit (44 px) by props (`onKeep`, `onDrop`, `onEdit`, later `onChatAbout`), used by both `beliefs-feed` and `entity-neighbourhood`.
- `entities/contact` (new): `useContactsPageQuery()` calling `getContactsPage`.
- `widgets/beliefs-feed`: `BeliefRow` for facts, a distinct episode row, Keep/Drop/Edit via `useReviewFactMutation` (`confirm`/`reject`/`edit`), infinite paging by `next_before`, the as-of readout (`getMemoryTimelineBounds`; a date control whose value prints as a mono readout, not a bar chart, with "kinds and confidence as of now"), empty state text.
- `widgets/people`: the Contacts tree through `ConnectedPrimitiveTree` inside a `Module`; loading/error/empty states.
- `widgets/entity-search`: search box (debounced 250 ms, `searchEntities`), results as rows (type, name, degree), "No entity named X" keeps the query; select navigates to `/mind/:entityId`.
- `widgets/entity-neighbourhood`: `lib/radial.ts` (pure, deterministic): centre entity; neighbours grouped by predicate around the circle in a fixed predicate order, sorted by name within a group; at most 20 (the ordered detail list) and "+N more" = `neighbour_total` − shown; `lib/entityActivitySeries.ts` (moved) for the sparkline labelled "last 20 facts and 10 episodes"; facts as `BeliefRow`s; phone: grouped list by predicate instead of the field.
- `widgets/procedures`: candidates first (`useProcedureCandidatesQuery`, `features/review-procedure`), then library rows (status, version, last invoked) with detail (`useProcedureDetailQuery`) and `features/procedure-review` controls (edit, disable).
- `pages/mind`: `MindPage` (desktop: Beliefs centre, People + Entity search + Procedures in the rail; phone: Beliefs → People → Entity search → Procedures). `pages/mind-entity`: `MindEntityPage` (`/mind/:entityId`; non-UUID → not found).
- Router: `mind` index → `MindPage`, `mind/:entityId` → `MindEntityPage`; delete `mindLoaders`; Doing interim drops `procedures`. Redirects: `/procedures` (was → `/doing/procedures`) now → `/mind` in one hop.

### Split phases

- **After 185** (`listHypotheses`): `entities/hypothesis` is created by 186 or here, whichever lands first (same file plan as 186 T003). The entity page's "I suspect …" module lists `listHypotheses?entity_id=` with posture, relation words, evidence labels and the 185 feedback actions (useful / not relevant / mute, and clear).
- **After 195**: Beliefs publishes `selection` and `visible`; the entity page publishes `subject` (`entity`); every belief row (`fact`), entity row and procedure row/module wires `ChatAboutChip` and `Module.onChatAbout` by props. People has no per-row chip (contact cards have no ids).

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

- `docs/frontend.md`: Mind place, widgets, deleted Brain pages and graph, the redirect table row (~67: `/brain-memory`, `/brain-graph`, `/mind/graph`, `/procedures`, `/contacts` → `/mind`).
- `docs/memory.md`: feed `claim_kind`, entity detail claim fields and `neighbour_total`; entity search route; Mind as the place to review beliefs.
- `specs/phases/188-web-doing/spec.md` and `191-web-plugins-in-places/spec.md` were edited at plan time (procedures and Contacts ownership).
- `docs/architecture.md`: REST table (`searchEntities`, feed field), web section.
- `docs/features.md`: Mind (beliefs, people, entity view, procedures).
- `core/cognition/ze-memory/README.md`: admin reads.
- `plugins/ze-personal/README.md`: contacts render in Mind › People, no nav entry.
- `AGENTS.md`: phase row 189; Learned Workspace Facts nav line (Knowledge group gone; Mind holds memory, people, procedures); `specs/README.md` row 189.

## Complexity Tracking

None.
