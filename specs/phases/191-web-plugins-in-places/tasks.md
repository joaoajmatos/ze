# Tasks: Plugins in Places (W7)

**Input**: [spec.md](./spec.md) (clarifications 2026-10-18), [plan.md](./plan.md) (Lane Plan), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/ui-manifest.md](./contracts/ui-manifest.md), [quickstart.md](./quickstart.md).

**Tests**: required. **Fail-first**: write the test, run it, see it fail for the stated reason, then implement.

**Build gate**: start when 187 (Ask, Try chips) and 189 (Mind) are on `main`. 188 may land before or after: lane `web` touches one line in its page and rebases if needed.

## Format: `[ID] [P?] [Lane] [Story] Description`

- **[Lane]**: `[L:lead]`, `[L:news]`, `[L:web]`, `[L:docs]` (plan.md Lane Plan).
- **[Story]**: US1 pages in places, US2 News preset, US3 settings verified.

**Crew**: Sonnet `lead`, `news`, `web`; Haiku `docs`. Contract step first; `news` and `web` then run in parallel; `lead` merges `news` then `web`. Tick a task's checkbox in the commit that finishes it.

**Rules**: FSD (`pages → widgets → features → entities → shared`; widgets take callbacks by props); DESIGN.md modules and 44 px targets (asserted by class in tests); plugins import only `ze_sdk.*`; `git add <paths>`, never `-A` or `stash`.

---

## Phase 1: Setup

- [ ] T001 [L:lead] Branch from `main` with 187 and 189 merged. `make install && make web-install`; `graphify update .`; `graphify affected` on `UiContribution`, `UiManifest`, `collect_ui_contributions`, `filter_ui_manifest_by_openapi`, `PluginScreen`, `PluginPage`, `refreshKeysForScreen`, `TryChips`; grep `manifest.nav\|\.nav\b\|show_in_mobile_nav\|CORE_RESERVED_NAV_PATHS\|getNewsPage\|build_news_page`. Record differences from plan.md "Blast radius" (and where 187 put `TryChips` and its props) in the Handoffs note; stop and report differences to the Spec Architect (Lintel).

---

## Phase 2: Foundational (contract step, lane `lead`)

- [ ] T002 [L:lead] Tests first:
  - `core/contracts/ze-plugin/tests/test_ui.py` (rewrite the nav cases):
    - a page without `place`, with an unknown place, without `path`, or without `page_operation_id` raises `AgentConfigError` naming the id;
    - the same `(place, path)` twice raises; the same path in two places passes;
    - a preset without `prompt`, with a label over 40 characters, or with a prompt over 300 characters raises;
    - lists are sorted by `(priority, id)`;
    - `UiManifest` has `pages`, `presets` and `settings_sections`;
    - `filter_ui_manifest_by_openapi` drops pages whose operation is missing and keeps presets.
  - `apps/ze-api/tests/api/test_ui_manifest.py`: the response shape per [the contract](./contracts/ui-manifest.md).

  Implement `ze_plugin/ui.py` (delete `CORE_RESERVED_NAV_PATHS` and `show_in_mobile_nav`), check the `ze_sdk/ui.py` re-export, update the `api/v0/system/schemas.py` mirror and the `ui.py` route description, and update any ze-api wiring that names `nav`. Run `make codegen` and commit the generated client with the task.
- [ ] T003 [L:lead] Tests first in `app/router/routes.test.tsx` and `shared/config/places.test.ts`:
  - each place has a `<place>/plugin/:pluginPath` route (World: `plugin/:pluginPath`), matched before `ask/:threadId` and `mind/:entityId`;
  - `/:pluginPath` renders `PluginRedirect`;
  - `/news` redirects to `/ask`;
  - `refreshKeysForScreen` matches a page by path from `manifest.pages`.

  Implement in `routes.tsx` (a `PluginRedirect` stub import from `pages/plugin-page`), `places.ts` and `query-keys.ts`. Add `apps/ze-web/src/test/fixtures/manifest.ts`: pages in Mind (`notes`) and Doing (`queue`), one preset, one settings section.

**Checkpoint**: lanes start.

---

## Phase 3: User Story 1 - Plugin pages live inside a place (P1) 🎯 MVP

- [ ] T005 [P] [L:web] [US1] Tests first `entities/ui-manifest/model/select.test.ts`: `pagesForPlace(manifest, "mind")` returns only Mind pages in priority order; an empty or absent manifest returns `[]`. Implement in `entities/ui-manifest/model/select.ts`; export from the index.
- [ ] T006 [L:web] [US1] Tests first `pages/plugin-page/ui/PluginPage.test.tsx`:
  - `/mind/plugin/notes` renders `PluginScreen` for that entry;
  - `/doing/plugin/notes` (a wrong place) shows not found;
  - an unknown path shows not found;
  - `PluginRedirect` at `/notes` navigates to `/mind/plugin/notes` with `replace`, shows the loading line while the manifest loads, and shows not found for an unknown path.

  Implement `PluginPage` (reading `:place` from the route) and `PluginRedirect`.
- [ ] T007 [L:web] [US1] Tests first `widgets/plugin-screen/ui/PluginScreen.test.tsx` (extend): each top-level primitive renders in its own `Module` with an `A·NN` index; the empty, error and invalid-tree states remain; no page-header hook call. Implement the restyle.
- [ ] T008 [L:web] [US1] Tests first `widgets/plugin-entries/ui/PluginEntries.test.tsx`: it renders nothing for a place without pages; for Mind, a "From plugins" module with one row per page (icon, label, 44 px class) linking to `/mind/plugin/<path>`; World links use `/plugin/<path>`. Implement, then add `<PluginEntries place="…" />` to `pages/{world,ask,doing,mind,governance}` (one line each; a test per page asserting the module mounts with the fixture).

---

## Phase 4: User Story 2 - News becomes an Ask preset (P2)

- [ ] T004 [P] [L:news] [US2] Tests first `plugins/ze-news/tests/test_plugin_ui.py`: `ui_contributions()` returns exactly the preset (`ze_news.whats_new`, label and prompt "What's new in my sources?") and the settings section when enabled, and nothing when disabled; `GET /api/v0/news/page` is gone (404 / not in the OpenAPI export); `getNewsSettings` still works. Delete `ze_news/ui/page.py`, the `getNewsPage` route, and `tests/test_ui_page.py` plus the page cases in `tests/test_api_routes.py`. Implement the preset in `plugin.py`.
- [ ] T009 [L:web] [US2] Tests first in `widgets/try-chips/ui/TryChips.test.tsx` (extend) and `pages/ask/ui/AskPage.test.tsx` (extend):
  - plugin presets render after the core chips, at most two, in order;
  - keys 4–5 send them under the same focus rule as keys 1–3;
  - each calls `onSend(prompt, { origin: "preset" })`;
  - no presets → no extra chips;
  - the Ask page passes `manifest.presets`.

  Implement.

---

## Phase 5: User Story 3 - Plugin settings verified in place (P3)

- [ ] T010 [L:web] [US3] Test only, `widgets/connections/ui/Connections.test.tsx` (extend) with the T003 fixture: the settings section renders and a save dispatches its operation. No implementation change is expected. If one is needed, report it to the Spec Architect.

---

## Phase 6: Polish and cross-cutting

- [ ] T011 [L:lead] Merge `news`, then `web`. `make codegen` if a schema moved. Gates: `make test-py`, `make test-web`, `make typecheck-web`, `make web-build`, `make lint`. `rtk proxy grep -rn "manifest.nav\|show_in_mobile_nav\|CORE_RESERVED_NAV_PATHS\|getNewsPage\|build_news_page" core apps plugins packages` returns nothing.
- [ ] T012 [L:lead] Run [quickstart.md](./quickstart.md) against `make dev-full`, with captures of Ask (News chip) and of Mind with the fixture page at 1440 and 390, no console errors; record in the Handoffs note.
- [ ] T013 [P] [L:docs] `docs/extending-ze.md` (contribution kinds, `place`, `preset`, reserved paths removed), `docs/frontend.md`, `docs/native-interface.md` (manifest shape), `packages/ze-sdk/README.md` if it documents `UiContribution`; doc-style skill.
- [ ] T014 [P] [L:docs] README screenshots refreshed (from T012's captures); `AGENTS.md` phase row 191 and the plugin-UI Learned Workspace Facts line; `specs/README.md` row 191 → Implemented; spec status.
- [ ] T015 [L:docs] Coverage check: `git diff main...HEAD --stat` against plan.md "Docs touched"; record in the Handoffs note.

---

## Dependencies & Execution Order

- T001 → T002 → T003 (contract) → lanes.
- `news`: T004. `web`: T005 → T006, T007, T008; T009; T010.
- T011 after both lanes; T012 after T011; T013–T014 after T011; T015 last.

## Parallel Example

```text
After the contract step:
  news: T004
  web:  T005 → T006 | T007 | T008, then T009, T010
```

## Implementation Strategy

- MVP = US1 (pages in places, with the fixture plugin) plus the contract. US2 is the user-visible change (the News chip). US3 is a regression guard.
