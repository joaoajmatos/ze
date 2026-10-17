# Tasks: Mind (W5)

**Input**: [spec.md](./spec.md), [plan.md](./plan.md), DESIGN.md.

**Build gate**: starts now on `main` (183 and 184 landed), in parallel with 186. Phase 6 waits for 185 on `main`; Phase 7 waits for 195 on `main`. If either has not landed when Phases 1–5 and 8 are done, the floor goes to review without it and the split phase lands as a follow-up commit on the same floor. The Spec Architect (Lintel) stays on call.

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. Vitest + Testing Library with a mocked `@myguyze/ze-client`; pytest with `AsyncMock` pools; `@pytest.mark.pg` for real SQL.

**Lanes**: `[ENG]` Claude Sonnet lane lead (backend reads, page, router, neighbourhood, gates). `[JR]` OpenCode junior (exact files given). Floor Reviewer reviews per user story. `[DOCS]` Docs Steward.

**Tags**: `[BACKEND]` Python · `[WEB]` ze-web, generated client · `[DOCS]` docs and specs.

**Rules for the implementer**
- FSD: `pages → widgets → features → entities → shared`; widgets get callbacks by props; no widget-to-widget import.
- No raw fact key renders; no whole-graph view; claim kind only from the record.
- DESIGN.md tokens only; 44 px targets; reduced motion respected.
- Shared with the 186 floor: `app/router/routes.tsx`, `shared/config/places.ts` (+ tests), `shared/lib/query-keys.ts`, `shared/lib/claim-posture.ts`, `entities/hypothesis`. Edit only Mind's lines; rebase if 186 landed first.
- Generated client (`packages/ze-client/src/generated/*`) belongs to ENG: commit `make codegen` output with each task that changes the OpenAPI.
- Before changing a shared export, run `graphify affected "<Symbol>" --depth 2` and `rtk proxy grep`; update every caller in the same change.
- Shared worktree: `git add <paths>`; `git commit -m ... -- <paths>`; never `git add -A` or `git stash`. Commit only when the ENG lead or Maestro asks; split commits by user story.

---

## Phase 0: Gate [ENG]

- [x] T001 [ENG] [WEB] Branch from current `main`. `make web-install`; `graphify update .`; `graphify affected` on `BrainMemoryPage`, `BrainGraphPage`, `MemoryFeed`, `MemoryGraph`, `TimelineScrubber`, `ProcedureManagement`, `ProcedureCandidatesList`, `MemoryFeedItem`; grep `MindInterim`, `mindLoaders`, `three`, `react-force-graph`, `/mind/graph`, `brain-`. Record in the Handoffs note: (a) differences from plan.md "Blast radius"; (b) whether 186 already created `shared/lib/claim-posture.ts` or `entities/hypothesis`; (c) whether 185 and 195 are on `main`; (d) the impeccable baseline critique of the interim Mind. Stop and report differences to the Spec Architect.

## Phase 1: Backend reads [US1, US3]

- [x] T002 [ENG] [BACKEND] Tests first in a new `core/cognition/ze-memory/tests/test_admin_feed.py` (no test covers `get_memory_feed` today; mock-pool pattern from `test_admin_activity.py`): fact rows carry `claim_kind`, episode rows `None`; `get_entity_detail` facts carry `claim_kind`, `confidence`, `reviewed`, `contradicted`, `provenance`; the neighbours query orders by degree DESC then name and the result has `neighbour_total`. Implement in `ze_memory/admin.py`; add the fields to `MemoryFeedItem`, `FactDigestItem`, `EntityDetailResponse.neighbour_total` (`apps/ze-api/ze_api/api/v0/memory/schemas.py`); extend `apps/ze-api/tests/api/test_routes.py`; a `@pytest.mark.pg` case in `apps/ze-api/tests/pg/test_entity_search_pg.py` (T003's file) with 25 neighbours returns 20 in degree-then-name order and `neighbour_total` 25. `make codegen`; commit the generated files with this task.
- [x] T003 [ENG] [BACKEND] Tests first in `core/cognition/ze-memory/tests/test_admin_graph.py`: `search_entities` SQL (name match, alias match through `jsonb_array_elements_text`, `%`/`_`/`\\` escaped with `ESCAPE`, optional type, degree then name order, limit) with a mock pool; `apps/ze-api/tests/pg/test_entity_search_pg.py` (`@pytest.mark.pg`): seeded entities return by alias, by partial name, by type, and none for no match; route test for `GET /api/v0/memory/entities` (`q` length 1..80 → 422 outside, `limit` 1..50, 401 without key). Implement `ze_memory/admin.py::search_entities` and the `searchEntities` route (response_model, summary, description). `make codegen`; commit.
- [x] T004 [JR] [BACKEND] Tests first in `plugins/ze-personal/tests/test_api_routes.py`: `PersonalPlugin().ui_contributions() == []` and `GET /api/v0/contacts/page` still returns the tree. Remove the override and unused imports in `ze_personal/plugin.py`.

## Phase 2: Shared and entities [US1, US3]

- [x] T005 [ENG] [WEB] Tests first `shared/lib/claim-posture.test.ts` (skip creating it if 186 landed it first; then extend its table with memory-fact kinds `fact`, `identity`, `inference`, `suspicion`): glyph, chip label and plain words per kind; no raw enum output. Implement `shared/lib/claim-posture.ts`, export from `shared/lib`.
- [x] T006 [ENG] [WEB] Tests first `entities/memory-feed-item/lib/belief.test.ts`: a sentence value (3+ words starting with a lowercase word, as the conversation value writer produces: "prefers aisle seats") renders as is; a multi-word proper noun (`works_at` + "Acme Corp Ltd", `lives_in` + "New York City") is not a sentence and joins the predicate ("Works at Acme Corp Ltd"); a short value joins the humanised predicate (`works_at` + "Acme" → "Works at Acme"; `exercise_habit` + "runs" → "Exercise habit runs"); empty value → "A fact Ze holds"; no output contains an underscore key; `sinceLabel`; source words for `provenance` and `agent`. Then `entities/memory-feed-item/ui/BeliefRow.test.tsx`: glyph from `claim_kind` via `shared/lib/claim-posture`, sentence, confidence, source, since, reviewed/contradicted marks, Keep/Drop/Edit call their props, buttons carry the 44 px min-size class (jsdom has no layout; T020 captures check the real size). Implement `lib/belief.ts` and `ui/BeliefRow.tsx`, export both.
- [x] T007 [P] [JR] [WEB] Tests first: `entities/memory-graph/api/useSearchEntitiesQuery.ts` (disabled under 1 char; key `queryKeys.entitySearch(q, type)` = `["entity-search", q, type]`) and `entities/contact/{api/useContactsPageQuery.ts,index.ts}` (key `queryKeys.contactsPage` = `["contacts-page"]`); add both keys to `shared/lib/query-keys.ts`. Implement.

## Phase 3: Beliefs and People [US1, US2, US4]

- [x] T008 [ENG] [WEB] Tests first `widgets/beliefs-feed/ui/BeliefsFeed.test.tsx`: fact rows are `BeliefRow`s and episodes look different; no row contains a raw key; Keep/Drop/Edit call `useReviewFactMutation` with `confirm`/`reject`/`edit` (edit sends the new value) and the row updates; paging by `next_before`; as-of control changes the query and prints the date as a readout with "kinds and confidence as of now"; empty state text from spec. Implement `widgets/beliefs-feed`.
- [x] T009 [P] [JR] [WEB] Tests first `widgets/people/ui/People.test.tsx`: the Contacts tree renders inside a `Module` through `ConnectedPrimitiveTree`; loading, error and empty states. Implement `widgets/people`.

## Phase 4: Entity search and neighbourhood [US3, US5]

- [x] T010 [ENG] [WEB] Tests first `widgets/entity-neighbourhood/lib/radial.test.ts`: same input → same positions; neighbours grouped by predicate in a fixed order and sorted by name; at most 20 shown and "+N more" = `neighbour_total` − shown; empty neighbourhood. Implement `lib/radial.ts`; move `entityActivitySeries.ts` (+ test) here.
- [x] T011 [ENG] [WEB] Tests first `widgets/entity-neighbourhood/ui/EntityNeighbourhood.test.tsx`: field with the centre and capped neighbours (each mark focusable with an accessible name), activity sparkline labelled "last 20 facts and 10 episodes", facts as `BeliefRow`s with Keep/Drop/Edit; phone renders a grouped list instead of the field. Implement.
- [x] T012 [P] [JR] [WEB] Tests first `widgets/entity-search/ui/EntitySearch.test.tsx`: debounced query; result rows (type, name, degree); "No entity named X" keeps the text; select calls `onSelect(id)`. Implement.

## Phase 5: Procedures, page, router, cuts [US1–US5]

- [x] T013 [JR] [WEB] Tests first `widgets/procedures/ui/Procedures.test.tsx`: candidates first with review actions (`features/review-procedure`), then library rows (status in words, version, last invoked) opening detail with `features/procedure-review` controls. Implement `widgets/procedures`.
- [x] T014 [ENG] [WEB] Tests first `pages/mind/ui/MindPage.test.tsx` and `pages/mind-entity/ui/MindEntityPage.test.tsx`: desktop layout and phone order (Beliefs → People → Entity search → Procedures); entity page loads `getEntityDetail`, 404 shows "No entity here" with the search; non-UUID path is not found. Implement both pages.
- [x] T015 [ENG] [WEB] Tests first `app/router/routes.test.tsx`, `shared/config/places.test.ts`, `widgets/app-shell/ui/AppShell.test.tsx`: `/mind` → `MindPage`; `/mind/<uuid>` → `MindEntityPage`; `/mind/graph`, `/brain-graph`, `/doing/procedures`, `/procedures`, `/contacts` → `/mind` in one hop; `/brain-memory` → `/mind`. Update `routes.tsx` (delete `mindLoaders`, remove the `procedures` loader), `places.ts` (change `/procedures` to `/mind`), and `pages/doing/ui/DoingInterim.tsx` (drop the Procedures section; a no-op if 188 already deleted the file).
- [x] T016 [ENG] [WEB] Delete `pages/{brain-memory,brain-graph,procedures}`, `widgets/{memory-feed,memory-graph,timeline-scrubber,procedure-management,procedure-candidates}`, `pages/mind/ui/MindInterim.tsx` (+ tests); remove `react-force-graph-3d`, `three`, `three-spritetext`, `@types/three` from `apps/ze-web/package.json` and the lockfile (`make web-install`). `rtk proxy grep -rn "brain-memory\|brain-graph\|memory-graph\|MindInterim\|from \"three\|react-force-graph" apps/ze-web/src` returns only `/jarvis` hits if any; `make web-build` output has no three chunk. Then, if grep finds no other user of `useOptionalCharts`/`ChartsToggle` (190 removes the costs page), delete `shared/lib/optional-charts.ts`, `shared/ui/primitives/ChartsToggle.tsx` and their exports; otherwise leave them for 190's matching task (whichever floor lands second deletes them).

## Phase 6: Hypotheses (needs 185 on main) [US3]

- [x] T017 [ENG] [WEB] If 186 has not created it: `entities/hypothesis` per 186 T003. Tests first `widgets/entity-neighbourhood/ui/Suspicions.test.tsx`: "I suspect …" lists `listHypotheses?entity_id=` with posture (inference/suspicion), relation in words, evidence labels; Useful / Not relevant / Mute call `setHypothesisFeedback` and a dismissed one can be cleared; the section is absent when the list is empty. Implement and add to `MindEntityPage`.

## Phase 7: Screen context (needs 195 on main) [US1, US3]

- [x] T018 [ENG] [WEB] Tests first: Beliefs publishes `selection` (selected rows) and `visible`; `MindEntityPage` publishes `subject` (`entity`). Implement with `useScreenPublisher`.
- [x] T019 [JR] [WEB] Tests first, one per kind (195 FR-025): `ChatAboutChip` on `BeliefRow` (`fact`, via its `onChatAbout` prop), entity search rows and the entity page header (`entity`), neighbour marks (`entity`), procedure rows (`procedure`), hypothesis rows (`hypothesis`, if Phase 6 landed); every Mind `Module` gets `onChatAbout`. Callbacks by props from the pages.

## Phase 8: Acceptance and docs

- [x] T020 [ENG] [WEB] Gates: `make test-web`, `make typecheck-web`, `make web-build` (no three.js chunk), `make lint`, `make test-py`, `make test-pg` (entity search). Impeccable critique of Mind ≥ 29/40 and ≥ the T001 baseline; detector 0; captures at 1440 and 390 with no console errors. Record in the Handoffs note.
- [x] T021 [DOCS] Update every doc in plan.md "Docs touched".
- [x] T022 [DOCS] `AGENTS.md` phase row 189 and the places fact; `specs/README.md` row 189 → Implemented; spec status.
- [x] T023 [DOCS] Coverage check: `git diff main...HEAD --stat` against "Docs touched"; record in the Handoffs note.

---

## Dependencies

- T001 first. T002, T003, T004 independent. T005–T007 independent (T007 after T003's codegen).
- T006 after T005. T008 after T002, T006. T009 after T007. T010 → T011; T011 after T002, T006. T012 after T007. T013 independent. T014 after T008, T009, T011, T012, T013. T015 after T014. T016 after T015.
- T017 after 185 on `main` and T011. T018, T019 after 195 on `main` and T014.
- T020 after all code that has landed; T021–T023 last.

## Lanes

### Lane ENG (Claude Sonnet, lane lead)

T001–T003, T005, T006, T008, T010, T011, T014–T018, T020. Owns `packages/ze-client/src/generated/*`, `app/router/*`, `shared/config/places.ts`.

### Lane JR (OpenCode junior)

T004, T007, T009, T012, T013, T019.

### Docs (Docs Steward)

T021–T023.
