# Tasks: Plugin Modules in Slots (191b)

**Input**: [spec.md](./spec.md) (clarifications 2026-10-18), [plan.md](./plan.md) (Lane Plan), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/ui-modules.md](./contracts/ui-modules.md), [quickstart.md](./quickstart.md).

**Tests**: required. **Fail-first**: write the test, run it, see it fail for the stated reason, then implement.

**Build gate**: 191a on `main`; 187 (Try chips) and 189 (Mind entity page) landed; 188 (Doing workflow page) landed or landing (see the Lane Plan rule).

## Format: `[ID] [P?] [Lane] [Story] Description`

- **[Lane]**: `[L:lead]`, `[L:news]`, `[L:web]`, `[L:docs]` (plan.md Lane Plan).
- **[Story]**: US1 modules in slots, US2 News, US3 no plugin pages, US4 settings.

**Crew**: Sonnet `lead`, `news`, `web`; Haiku `docs`. Contract step first; `news` and `web` then run in parallel; `lead` merges `news`, then `web`. Tick a task's checkbox in the commit that finishes it.

**Rules**: plugins import only `ze_sdk.*`; FSD; a module never delays its place; `git add <paths>`, never `-A` or `stash`.

---

## Phase 1: Setup

- [ ] T001 [L:lead] Branch from `main` with 191a merged. `make install && make web-install`; `graphify update .`; `graphify affected` on `UiContribution`, `UiManifest`, `collect_ui_contributions`, `filter_ui_manifest_by_openapi`, `CORE_RESERVED_NAV_PATHS`, `PluginPage`, `refreshKeysForScreen`, `TryChips`, `MindEntityPage`, `DoingWorkflowPage`, `Connections`. Grep `manifest.nav`, `ui_manifest.nav`, `ui_nav`, `show_in_mobile_nav`, `page_operation_id`, `getNewsPage`, `news/page`, `build_news_page`, `PluginPageResponse`. Confirm: how a plugin's registered agents are known at runtime (for the tool-action binding); the function in `ze_agents/claims.py` or `ze_components/claims.py` that says which (ClaimKind, Provenance) pairs are allowed (if none, lead adds `is_licensed_posture` in T002); where plugin settings responses can be validated by core; the memory graph and workflow store lookups for the subject; whether 188's `DoingWorkflowPage` is on `main`; and the final `TryChips` chips array and props. Record differences from plan.md "Blast radius" in the Handoffs note; stop and report differences to the Spec Architect (Lintel).

---

## Phase 2: Foundational (contract step, lane `lead`)

- [ ] T002 [L:lead] Tests first:
  - `core/contracts/ze-plugin/tests/test_ui.py` (rewrite): each of these raises `AgentConfigError` naming the id:
    - the kinds `nav`, `page` and `foo`;
    - a module without a slot, with an unknown slot, or without a provider;
    - a preset without a prompt, with a prompt over 300 characters, or with a label over 40;
    - a settings section without an operation id;
    - a duplicate id.
    
    Lists are sorted by `(priority, id)`. `UiManifest` has `modules`, `presets` and `settings_sections`, and `provider` is not serialized. `filter_ui_manifest_by_openapi` drops a settings section with a missing operation and keeps modules and presets.
  - `apps/ze-api/tests/api/test_ui_manifest.py`: the response shape per [the contract](./contracts/ui-modules.md).
  - `apps/ze-api/tests/api/test_ui_modules.py`, with fake providers and a fixture plugin from `core/contracts/ze-plugin/tests/fixture_plugin.py`:
    - success returns 200 with `ui_version`;
    - `applies: false` passes through;
    - an unknown id is 404;
    - a subject kind that does not match the slot is 422;
    - a provider that raises is 502 "<Plugin> could not load.";
    - a provider over 3 s (fake clock) is 504 "<Plugin> took too long.";
    - an invalid tree is 502 "<Plugin> sent a view Ze cannot show.";
    - each failure logs `ui_module_failed`;
    - a module tree whose `ToolAction` names another plugin's agent, or a tool outside the named agent's list, is 502 "<Plugin> sent a view Ze cannot show."; the same tree in a settings response is refused;
    - a tree with an unlicensed posture pair is refused; a provider-set tone or label is replaced by the core-derived one;
    - the subject is resolved server-side: an unknown entity or run id is 404, and the provider receives the record's label and entity type (a forged `subject_label` query parameter is ignored);
    - `request_module_refresh(interface, "x.facet")` calls `send_refresh("module:x.facet")`, and a failing interface is logged, not raised; `NativeAppInterface.send_refresh` sends the `refresh` frame.

  Implement `ze_plugin/ui.py` (delete the page kind, `path`, `page_operation_id`, `show_in_mobile_nav`, `CORE_RESERVED_NAV_PATHS`), the `ze_sdk/ui.py` re-export (lines 2 and 10), the `api/v0/system` schemas and route description, the new `api/v0/ui_modules` route, and the log fields in `wiring/agents.py:224-232` and `wiring/container.py:768-769`. Delete News's page contribution in `ze_news/plugin.py` so startup passes (lane `news` adds the preset and module). Delete ze-personal's `getContactsPage` (`api/routes.py:24-35`), `ui/page.py`, its `PluginPageResponse` copy and their tests. Remove the `plugin` place from `WsScreenContext.place` (`api/ws/schemas.py:227`) and `PLACES` (`ze_agents/screen.py:25`). Add `AppInterface.send_refresh`, `NativeAppInterface.send_refresh` and `ze_sdk.ui.request_module_refresh`. Point `apps/ze-api/tests/api/test_openapi_export.py:11,27`, `apps/ze-api/tests/test_plugin_routes.py:28` and `packages/ze-client/src/sdk-dispatch.test.ts` at `getNewsSettings`. Run `make codegen`; commit the generated client with the task.
- [ ] T003 [L:lead] Tests first:
  - `entities/ui-manifest/model/select.test.ts`: `modulesForSlot(manifest, "mind.entity")` returns that slot's modules in order; an empty or absent manifest gives `[]`; `presets(manifest)` returns the presets;
  - `entities/ui-manifest/api/useUiModuleQuery.test.ts`: the query key includes the module id and subject, and the request passes the subject query fields;
  - `shared/lib/query-keys.test.ts`: `refreshKeysForScreen("module:x.facet")` returns the `uiModule("x.facet")` prefix key; `queryKeys.pluginPage` and the `contacts` plugin-page expectation (line 41) are gone;
  - `app/router/routes.test.tsx`: no top-level `:pluginPath` route; `/notes` renders not found; `/news` redirects to `/ask` (in `shared/config/places.test.ts` too).

  Implement in `entities/ui-manifest`, `query-keys.ts` (delete `pluginPage`), `routes.tsx` and `places.ts` (drop the `plugin` comment at line 23). Add `widgets/plugin-module/index.ts` with the `PluginModuleSlot({ slot, subject })` stub (renders nothing), and `apps/ze-web/src/test/fixtures/manifest.ts` (one module per slot, one preset, one settings section).
- [ ] T004 [L:lead] Delete `pages/plugin-page` (route, page and tests) and `widgets/plugin-screen`'s page-header use if nothing else needs it (`PluginSettingsSection` keeps working); run `make test-web` and `make typecheck-web`.

**Checkpoint**: lanes start.

---

## Phase 3: User Story 2 - News (P1)

- [ ] T005 [P] [L:news] [US2] Tests first:
  - `plugins/ze-news/tests/test_store_by_tag.py` (mocked pool): `by_tag("climate")` issues an exact `tags && ARRAY[$1]` match (no `lower()`), newest first, at most 8;
  - `plugins/ze-news/tests/test_plugin_ui.py`: `ui_contributions()` returns the preset `ze_news.whats_new` (label and prompt "What's new in my sources?"), the module `ze_news.sources` (slot `mind.entity`, label "Sources") and the settings section when enabled, and nothing when disabled;
  - the sources provider: `applies=False` before `startup()` has created the store (not an exception), for an entity type other than `topic`, and when no article matches; otherwise a `claim_list` with one item per article (title, source, date), posture `fact`/`live_search` set by code, and the tree validates against the 191a schema;
  - `GET /api/v0/news/page` is gone (not in the OpenAPI export) and `getNewsSettings` still works;
  - `NewsFetchJob.run`: when `upsert` returns new articles, `request_module_refresh(interface, "ze_news.sources")` is called once; with no new articles it is not called.

  Implement `NewsStore.by_tag`, the contributions and provider in `plugin.py` (the provider reads `self._store` at call time), and pass the interface to `NewsFetchJob` in `startup()`. Delete `getNewsPage`, `ui/page.py`, `tests/test_ui_page.py` and the page cases in `tests/test_api_routes.py`. Add the row `{"id": "single-news-sources-en", "lang": "en", "prompt": "What's new in my sources?", "gold_agent": "news", "gold_multi": false}` to `eval/calibration/routing.jsonl` and run `make calibrate-routing ARGS=--check-sets` (offline only).

---

## Phase 4: User Story 1 - Modules in slots (P1) 🎯 MVP

- [ ] T006 [L:web] [US1] Tests first `widgets/plugin-module/ui/PluginModuleSlot.test.tsx` (fixture manifest; mocked query; mocked `IntersectionObserver`):
  - a slot with no modules renders nothing;
  - each module renders in a `Module` titled with its label, in priority order;
  - the loading line "Loading <label>…" shows while waiting;
  - an error shows the server's detail line, and the other modules in the slot still render;
  - `applies: false` renders nothing for that module;
  - `refetchInterval` is 60 000 while the module is visible and off when it is not;
  - module actions go through 191a's `usePrimitiveActions`;
  - an unknown primitive shows 191a's fallback.

  Implement `PluginModuleSlot`.
- [ ] T007 [L:web] [US1] Tests first, extending `pages/mind-entity/ui/MindEntityPage.test.tsx`, `pages/doing-workflow/ui/DoingWorkflowPage.test.tsx` and `widgets/connections/ui/Connections.test.tsx`, each with the fixture manifest:
  - the Mind entity page mounts the `mind.entity` slot with subject `{ kind: "entity", id, label, entity_type }`;
  - the Doing workflow page mounts the `doing.run` slot with the selected execution as `id` and the workflow as `parent_id` (if 188 has not landed, the mount waits for it: record it on 188's landing checklist in the Handoffs note);
  - Connections mounts the `governance.connections` slot with subject `none`, after the settings sections.

  Implement the one-line mounts.
- [ ] T008 [L:web] [US2] Tests first `widgets/try-chips/ui/TryChips.test.tsx` and `pages/ask/ui/AskPage.test.tsx` (extend):
  - presets render after the core chips, at most two, in order;
  - their index labels and keys continue the visible numbering (3–4 with no active goal, 4–5 with one), and the key past the last chip does nothing;
  - React keys are ids;
  - `disabled` applies to them;
  - pressing one calls `onSend(prompt, { origin: "preset" })`;
  - no presets → no extra chips;
  - the Ask page passes `presets(manifest)`.

  Implement.

---

## Phase 5: User Stories 3 and 4 - No plugin pages; settings verified (P2, P3)

- [ ] T009 [L:web] [US4] Test only, `widgets/connections/ui/Connections.test.tsx` (extend) with the fixture: the settings section renders and a save dispatches its operation. No implementation change is expected; if one is needed, report it to the Spec Architect.

---

## Phase 6: Polish and cross-cutting

- [ ] T010 [L:lead] Merge `news`, then `web`. `make codegen` if a schema moved. Gates: `make test-py`, `make test-web`, `make typecheck-web`, `make web-build`, `make lint`. The quickstart grep returns nothing.
- [ ] T011 [L:lead] Run [quickstart.md](./quickstart.md) against `make dev-full`, with captures of Ask (News chip) and a Mind topic entity with the Sources module at 1440 and 390, no console errors; record them in the Handoffs note.
- [ ] T012 [P] [L:docs] `docs/extending-ze.md`, `docs/frontend.md`, `docs/native-interface.md`, `packages/ze-sdk/README.md` and `core/contracts/ze-plugin/README.md` where they document UI contributions; doc-style skill.
- [ ] T013 [P] [L:docs] README screenshots refreshed from T011's captures; `AGENTS.md` phase row 191b and the plugin-UI Learned Workspace Facts line; `specs/README.md` row 191b → Implemented; spec status.
- [ ] T014 [L:docs] Coverage check: `git diff main...HEAD --stat` against plan.md "Docs touched"; record in the Handoffs note.

---

## Dependencies & Execution Order

- T001 → T002 → T003 → T004 (contract) → lanes.
- `news`: T005. `web`: T006 → T007; T008; T009.
- T010 after both lanes; T011 after T010; T012–T013 after T011; T014 last.

## Parallel Example

```text
After the contract step:
  news: T005
  web:  T006 → T007, then T008, T009
```

## Implementation Strategy

- MVP = US1 (a module in each slot, proven by the fixture plugin) on the contract step. US2 moves News and is what the user sees. US3 is the hard cut done in the contract step. US4 is a regression guard.
