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

- [ ] T001 [L:lead] Branch from `main` with 187 and 189 merged. `make install && make web-install`; `graphify update .`; `graphify affected` on `UiContribution`, `UiManifest`, `collect_ui_contributions`, `filter_ui_manifest_by_openapi`, `PluginScreen`, `PluginPage`, `refreshKeysForScreen`, `TryChips`; grep `manifest.nav\|\.nav\b\|ui_nav\|show_in_mobile_nav\|CORE_RESERVED_NAV_PATHS\|getNewsPage\|news/page\|build_news_page`. Re-read the landed `widgets/try-chips/ui/TryChips.tsx` and `widgets/app-shell/ui/AppShell.tsx` (`onAsk`). Record differences from plan.md "Blast radius" (and any change to `TryChips`' chips array, key handling or props) in the Handoffs note; stop and report differences to the Spec Architect (Lintel).

---

## Phase 2: Foundational (contract step, lane `lead`)

- [ ] T002 [L:lead] Tests first:
  - `core/contracts/ze-plugin/tests/test_ui.py` (rewrite the nav cases):
    - a page without `place`, with an unknown place, without `path`, with a path that fails `^[a-z0-9][a-z0-9-]{0,39}$` (`Notes`, `-x`, `a/b`, 41 characters), or without `page_operation_id` raises `AgentConfigError` naming the id;
    - an unknown `kind` (for example `nav`) raises;
    - the same `(place, path)` twice raises; the same path in two places passes;
    - a preset without `prompt`, with a label over 40 characters, or with a prompt over 300 characters raises;
    - lists are sorted by `(priority, id)`;
    - `UiManifest` has `pages`, `presets` and `settings_sections`;
    - `filter_ui_manifest_by_openapi` drops pages whose operation is missing and keeps presets.
  - `apps/ze-api/tests/api/test_ui_manifest.py`: the response shape per [the contract](./contracts/ui-manifest.md).

  Also update the callers that name the old shape or the News page operation: `apps/ze-api/tests/api/test_openapi_export.py:11,27` and `apps/ze-api/tests/test_plugin_routes.py:28` (use `getNewsSettings`), `packages/ze-client/src/sdk-dispatch.test.ts` (dispatch a remaining operation).

  Implement `ze_plugin/ui.py` (delete `CORE_RESERVED_NAV_PATHS` and `show_in_mobile_nav`), drop both from `ze_sdk/ui.py` (lines 2, 10), update the `api/v0/system/schemas.py` mirror and the `ui.py` route description, and rename the log fields in `wiring/agents.py:224-231` (`nav=` → `pages=`, add `presets=`) and `wiring/container.py:768` (`ui_nav` → `ui_pages`; 192 and 194 edit this file too, so rebase on whichever lands first). `ze_news/plugin.py:160` passes `show_in_mobile_nav` on its `nav` contribution, so startup would fail: the contract step deletes that contribution (keeping the settings section) and lane `news` adds the preset in T004. This is the only contract-step edit in a `news` file; it lands before the lane starts. Run `make codegen` and commit the generated client with the task.
- [ ] T003 [L:lead] Tests first in `app/router/routes.test.tsx`, `shared/config/places.test.ts`, `shared/lib/query-keys.test.ts` and `widgets/app-shell/ui/AppShell.test.tsx`:
  - with `matchRoutes`, `/mind/plugin/notes`, `/ask/plugin/notes`, `/doing/plugin/notes`, `/governance/plugin/notes` and `/plugin/notes` each match the plugin route (not `mind/:entityId`, `ask/:threadId`, or the `doing/*` / `governance/*` splats);
  - `/notes` (an old top-level plugin path) matches the `*` not-found route; no `:pluginPath` route exists at the top level;
  - `/news` redirects to `/ask`;
  - `placeOf("/plugin/x")` is World; `placeOf("/ask/plugin/x")` is Ask; `isPluginPath` is true for both and false for `/ask/123`;
  - `AppShell` on `/ask/plugin/x`: the shell has no `on-ask` class and submitting the Ask bar opens the overlay;
  - `refreshKeysForScreen("x.notes", fixture)` returns `queryKeys.pluginPage("x.notes")`; a page path (`notes`) returns `undefined`.

  Implement in `routes.tsx` (child routes import `PluginPage` from `pages/plugin-page`; delete the top-level `:pluginPath` route), `places.ts` (`placeOf`, `isPluginPath`, the `/news` redirect), `query-keys.ts` and `AppShell.tsx` (`onAsk`). Add `apps/ze-web/src/test/fixtures/manifest.ts`: pages `x.notes` in Mind (`notes`) and `x.queue` in Doing (`queue`), each with a fixture page operation id (`getXNotesPage`, `getXQueuePage`; not in the generated client, so tests that load the page mock the dispatcher), one preset, one settings section.

**Checkpoint**: lanes start.

---

## Phase 3: User Story 1 - Plugin pages live inside a place (P1) 🎯 MVP

- [ ] T005 [P] [L:web] [US1] Tests first `entities/ui-manifest/model/select.test.ts`: `pagesForPlace(manifest, "mind")` returns only Mind pages in priority order; an empty or absent manifest returns `[]`. Implement in `entities/ui-manifest/model/select.ts`; export from the index.
- [ ] T006 [L:web] [US1] Tests first `pages/plugin-page/ui/PluginPage.test.tsx`:
  - `/mind/plugin/notes` renders `PluginScreen` for that entry;
  - `/doing/plugin/notes` (a wrong place) shows not found;
  - an unknown path shows not found;
  - the loading line shows while the manifest loads.

  Implement `PluginPage` (reading `:place` from the route). Also point `features/primitive-tree/api/usePluginScreenActions.test.ts:51-64` at the fixture page operation instead of `getNewsPage`.
- [ ] T007 [L:web] [US1] Tests first `widgets/plugin-screen/ui/PluginScreen.test.tsx` (extend): each top-level primitive renders in its own `Module` with an `A·NN` index; the empty, error and invalid-tree states remain; no page-header hook call. Implement the restyle.
- [ ] T008 [L:web] [US1] Tests first `widgets/plugin-entries/ui/PluginEntries.test.tsx`: it renders nothing for a place without pages; for Mind, a "From plugins" module with one row per page (icon, label, 44 px class) linking to `/mind/plugin/<path>`; World links use `/plugin/<path>`. Implement, then add `<PluginEntries place="…" />` to `pages/{world,ask,doing,mind,governance}` (one line each; a test per page asserting the module mounts with the fixture).

---

## Phase 4: User Story 2 - News becomes an Ask preset (P2)

- [ ] T004 [P] [L:news] [US2] Tests first `plugins/ze-news/tests/test_plugin_ui.py`: `ui_contributions()` returns exactly the preset (`ze_news.whats_new`, label and prompt "What's new in my sources?") and the settings section when enabled, and nothing when disabled; `GET /api/v0/news/page` is gone (404 / not in the OpenAPI export); `getNewsSettings` still works. Delete `ze_news/ui/page.py`, the `getNewsPage` route, and `tests/test_ui_page.py` plus the page cases in `tests/test_api_routes.py`. Implement the preset in `plugin.py`. Add the row `{"id": "single-news-sources-en", "lang": "en", "prompt": "What's new in my sources?", "gold_agent": "news", "gold_multi": false}` to `eval/calibration/routing.jsonl`.
- [ ] T009 [L:web] [US2] Tests first in `widgets/try-chips/ui/TryChips.test.tsx` (extend) and `pages/ask/ui/AskPage.test.tsx` (extend):
  - plugin presets (`{ id, label, prompt }`) render after the core chips, at most two, in order;
  - their index labels and keys continue the visible numbering: 3–4 with no active goal, 4–5 with one; the key past the last chip does nothing;
  - React keys are ids (two presets with the same label render without a key warning);
  - `disabled` disables plugin chips and their keys too;
  - each calls `onSend(prompt, { origin: "preset" })` (the label is shown, the prompt is sent);
  - no presets → no extra chips;
  - the Ask page passes `manifest.presets`.

  Implement.

---

## Phase 5: User Story 3 - Plugin settings verified in place (P3)

- [ ] T010 [L:web] [US3] Test only, `widgets/connections/ui/Connections.test.tsx` (extend) with the T003 fixture: the settings section renders and a save dispatches its operation. No implementation change is expected. If one is needed, report it to the Spec Architect.

---

## Phase 6: Polish and cross-cutting

- [ ] T011 [L:lead] Merge `news`, then `web`. `make codegen` if a schema moved. Gates: `make test-py`, `make test-web`, `make typecheck-web`, `make web-build`, `make lint`. `rtk proxy grep -rn "manifest.nav\|ui_manifest.nav\|ui_nav\|show_in_mobile_nav\|CORE_RESERVED_NAV_PATHS\|getNewsPage\|news/page\|build_news_page\|PluginRedirect" core apps plugins packages` returns nothing.
- [ ] T012 [L:lead] Run [quickstart.md](./quickstart.md) against `make dev-full` (the News chip's turn must route to the news agent per the trace panel; if it does not, report to the Spec Architect before changing routing), with captures of Ask (News chip) and of Mind with the fixture page at 1440 and 390, no console errors; record in the Handoffs note.
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
