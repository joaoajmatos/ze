# Implementation Plan: Plugin Modules in Slots (191b)

**Branch**: `191b-plugin-modules` | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md with the 2026-10-18 clarifications (user: all recommended); `main` e4d57414; 191a's contract (typed actions, `ui_version`, fallback, slot primitives).

## Summary

- **Contributions.** `UiContribution.kind` becomes `module | preset | settings_section`. The page kind, `path`, `page_operation_id`, `show_in_mobile_nav` and `CORE_RESERVED_NAV_PATHS` are cut. A module declares a `slot` (`mind.entity`, `doing.run`, `governance.connections`) and a Python `provider`, the plugin's read operation: `async (subject) -> ModuleResult(applies, components)`.
- **One core route.** ze-api serves `GET /api/v0/ui/modules/{module_id}` (`getUiModule`). It resolves the slot's subject from Ze's own records, calls the module's provider under a 3 s timeout, and validates the tree: the 191a schema, every tool action bound to an agent of the contributing plugin, and every claim posture licensed (tone and label recomputed in core). It returns the tree with `ui_version`. Plugins write no REST route for a module.
- **Refresh emitter.** `ze_sdk.ui.request_module_refresh(interface, module_id)` sends `{"type": "refresh", "screen": "module:<id>"}`; News calls it after a fetch that stored new articles.
- **Manifest.** It returns `modules`, `presets` and `settings_sections`.
- **Web slots.** One `widgets/plugin-module` slot component fetches each module for its slot and subject. It refetches on place load, on a `refresh` frame with `screen: "module:<id>"`, and every 60 s while visible, and shows a loading line, a plain failure line, or nothing when the module does not apply. Slots are mounted in the Mind entity page, the Doing workflow run page and Governance › Connections. Ask's Try chips add up to two plugin presets.
- **News.** It contributes the preset "What's new in my sources?", a `mind.entity` module "Sources" (articles with a tag equal to the topic entity's name), and its settings section. The page, `getNewsPage` and `ui/page.py` are deleted; `/news` redirects to `/ask`.
- **Leftover cuts.** ze-personal's `getContactsPage` and `ui/page.py`, the `plugin` place value (WS screen context, `ze_agents/screen.py`, `places.ts`), and `queryKeys.pluginPage` are deleted.
- **Fixture plugin.** A test plugin contributes one module per slot plus a preset, and proves each slot on both sides.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 5, React 19, TanStack Query 5.
**Primary Dependencies**: none new.
**Storage**: none; no migration. News reads `news_articles` by tag through a new store method.
**Testing**: pytest (contribution validation, the module route with fake providers, the news provider); vitest (slot component states, refresh and visibility polling, each place mounting its slot, Try chips presets).
**Target Platform**: Linux container + browser.
**Project Type**: web service + web app.
**Constraints**: plugins import only `ze_sdk.*`; no plugin script in the browser; a module never delays its place; FSD.
**Scale/Scope**: one real plugin (News) and one fixture plugin; three module slots plus presets.

## Constitution Check

| Principle | Check |
|---|---|
| I Spec-first | spec, clarifications, plan, research, data model, contract, quickstart, tasks. |
| III Layered packages | Types and validation in ze-plugin, re-exported by `ze_sdk.ui`; the module route in ze-api; ze-news imports `ze_sdk.ui` only. |
| IV Typed Python | `UiContribution`, `ModuleSubject`, `ModuleResult` dataclasses; `AgentConfigError` on invalid contributions; Pydantic only in ze-api schemas. |
| V Tests | Fail-first; the fixture plugin covers each slot. |
| VIII Hard cuts | The page kind and its fields, `CORE_RESERVED_NAV_PATHS`, `pages/plugin-page`, the top-level `:pluginPath` route, the News page route and builder; no redirects except `/news` → `/ask` (in the existing redirect table). |

Gate: pass.

## Blast radius

From `git grep` on `main` e4d57414 (T001 re-runs `graphify affected` after 191a lands):

| Symbol | Callers | Change |
|---|---|---|
| `UiContribution`, `UiManifest`, `collect_ui_contributions`, `filter_ui_manifest_by_openapi`, `CORE_RESERVED_NAV_PATHS` (`ze_plugin/ui.py`) | `ze_sdk/ui.py:2,10`, `ze_news/plugin.py:148-170`, `wiring/agents.py:224-232` (`build_ui_manifest` logs `nav=`), `wiring/container.py:768-769` (`ui_nav`), `core/contracts/ze-plugin/tests/test_ui.py` | New kinds and fields; `UiManifest(modules, presets, settings_sections)`; the filter keeps only the settings operation check. |
| `UiManifestResponse`, `UiContributionSchema` (`api/v0/system/schemas.py:48-49`) | `getUiManifest` | Mirror the domain; `make codegen`. |
| `getNewsPage`, `ze_news/ui/page.py`, `ze_news/api/schemas.PluginPageResponse` (page use) | `ze_news/api/routes.py:17-33`, `apps/ze-api/tests/api/test_openapi_export.py:11,27`, `apps/ze-api/tests/test_plugin_routes.py:28`, `packages/ze-client/src/sdk-dispatch.test.ts`, news tests | Deleted (settings route stays); tests point at `getNewsSettings`. |
| `getContactsPage` (`ze_personal/api/routes.py:24-35`), `ze_personal/ui/page.py`, ze-personal's `PluginPageResponse` copy | nothing since 189 removed the Contacts nav; `shared/lib/query-keys.test.ts:41` expects `["plugin-page", …"contacts"]` | Deleted with its tests and that expectation. News keeps its `PluginPageResponse` for the settings route (191a adds `ui_version` to it). |
| The `plugin` place: `WsScreenContext.place` Literal (`api/ws/schemas.py:227`), `PLACES` (`ze_agents/screen.py:25`), the comment at `places.ts:23`, `queryKeys.pluginPage` (`shared/lib/query-keys.ts:28`) | screen context, query keys | Removed; `make codegen` regenerates the client type. |
| `AppInterface` (`ze_agents/interface`), `NativeAppInterface` (`interface/native.py`) | plugins via `ze_sdk.ui` | New `send_refresh(screen)` broadcast used by `request_module_refresh`. |
| `NewsFetchJob.run` (`ze_news/jobs/fetch.py:72-82`) | scheduler | Calls `request_module_refresh(interface, "ze_news.sources")` when `upsert` stored new articles. |
| Web `manifest.nav` | `pages/plugin-page/ui/PluginPage.tsx`, `shared/lib/query-keys.ts` (`refreshKeysForScreen`) | `pages/plugin-page` deleted; `refreshKeysForScreen` handles `module:<id>`. |
| Router `:pluginPath` (`app/router/routes.tsx`) | router | Deleted; the `*` route shows not found. |
| `widgets/connections/ui/Connections.tsx:81` (`settings_sections`) | Governance | Unchanged list; gains the `governance.connections` module slot. |
| `pages/mind-entity/ui/MindEntityPage.tsx` | router | Mounts the `mind.entity` slot under the neighbourhood. |
| `pages/doing-workflow/ui/DoingWorkflowPage.tsx` (188) | router | Mounts the `doing.run` slot in the selected run's view. |
| `widgets/try-chips` (187: chips array, `chips[Number(e.key) - 1]`, `disabled`) | `pages/ask` | `presets: { id, label, prompt }[]`, appended to the chips array so numbering, keys and `disabled` continue. |

## Design

### ze-plugin (`ui.py`)

- `Slot = Literal["mind.entity", "doing.run", "governance.connections"]`.
- `ModuleSubject(kind: Literal["entity", "workflow_run", "none"], id: str | None, label: str | None, entity_type: str | None, parent_id: str | None)`, always built by ze-api from its own records, never from client text.
- `ModuleResult(applies: bool, components: list[dict])`, where components are serialized 191a primitives.
- `UiContribution(id, plugin, kind: Literal["module", "preset", "settings_section"], label, icon, slot=None, provider=None, prompt=None, settings_operation_id=None, priority=100)`. `provider` is an async callable `(ModuleSubject) -> ModuleResult`; it is excluded from serialization.
- `collect_ui_contributions` raises `AgentConfigError` naming the contribution when:
  - the kind is unknown;
  - a module has no slot, an unknown slot, or no provider;
  - a preset has no prompt (1–300 characters) or a label over 40 characters;
  - a settings section has no operation id;
  - an id repeats.
  
  Lists are sorted by `(priority, id)`.
- `UiManifest(modules, presets, settings_sections)`; `filter_ui_manifest_by_openapi` checks only settings operation ids.
- `get_module(manifest, module_id)` for the route.
- Providers read their stores at call time (never captured when `ui_contributions()` runs, before `startup()`); a provider whose store is not ready returns `applies=False`.
- `request_module_refresh(interface, module_id)` (re-exported by `ze_sdk.ui`): calls `interface.send_refresh(f"module:{module_id}")`, guarded so a failure is logged and never raised.

### ze-api

- `GET /api/v0/ui/modules/{module_id}` (`getUiModule`, API key), query `subject_kind`, `subject_id`, `parent_id` (the workflow id for a run):
  - unknown module id → 404;
  - the subject kind does not match the slot (`mind.entity` → entity, `doing.run` → workflow_run, `governance.connections` → none) → 422;
  - the subject is resolved server-side: an entity through the memory graph store (label and entity type from the record), a run through the workflow store (`get_execution(workflow_id, execution_id)`); an unknown subject → 404;
  - otherwise `asyncio.wait_for(provider(subject), 3.0)`:
    - success → 200 `{ "module_id", "applies", "components", "ui_version" }` after validation: the 191a schema; every `ToolAction` names an agent registered by the contributing plugin and a tool in that agent's list; every `claim` is a (ClaimKind, Provenance) pair the shared vocabulary allows (T001 names the function; if none exists, lead adds `is_licensed_posture` from the existing tables), with any provider-set tone or label dropped and recomputed in core (`claim_tone`). Any failure → 502 with detail "<Plugin> sent a view Ze cannot show.";
    - timeout → 504 with detail "<Plugin> took too long.";
    - exception → 502 with detail "<Plugin> could not load."
  
  A failure is logged (`ui_module_failed`). Schemas `UiModuleResponse`, `UiManifestResponse` (`modules`, `presets`, `settings_sections`).
- The tool-action binding and the posture-pair check live in `ze_plugin/ui_validate.py` as `validate_plugin_tree(plugin, components)` (re-exported by `ze_sdk.ui`), so both sides can call it: the core module route calls it, and then also recomputes tone and label (ze-api has ze-components). Plugin settings come from each plugin's own REST route, which core does not see, so News's settings route calls `validate_plugin_tree` before returning and raises on failure, and a fixture-plugin test proves the News settings tree passes it. The spec's guarantee for settings trees is therefore "validated by the plugin through the shared check, and tested"; core enforces module trees.
- A plugin's agents: the registered agents whose class `__module__` starts with one of the plugin's `agent_module_paths()` (so `ze_news.agents.agent` → `news`). A plugin that registers no agent can emit only navigate, ask and compose actions in its trees.
- `NativeAppInterface.send_refresh(screen)` broadcasts `{ "type": "refresh", "screen": screen }` to the connected client.
- `build_ui_manifest` and the container log the new fields.

### ze-news

- `NewsStore.by_tag(tag, limit=8)`: articles with `tags && ARRAY[$1]` (exact, using the GIN index, the same key the signal path uses to create the topic entity), newest first.
- `ui_contributions()` returns three contributions:
  - the preset `ze_news.whats_new` (label and prompt "What's new in my sources?", icon `newspaper`);
  - the module `ze_news.sources` (slot `mind.entity`, label "Sources"). Its provider reads the store at call time and returns `applies=False` when the store is not ready, for entity types other than `topic`, or when nothing matches, else a `claim_list`: one item per article with title, source and date, posture `fact`/`live_search` set by code, and the action `navigate` to nothing; the article link is shown as text;
  - `ze_news.settings` (unchanged).
- Deleted: `getNewsPage`, `ui/page.py`, its tests, and the page cases in `tests/test_api_routes.py`.
- `NewsFetchJob` is built before startup without an interface (`plugin.py:74`); `startup(container)` binds it with `job.bind_interface(container.interface)`. After a run whose `upsert` returned new articles it calls `request_module_refresh(interface, "ze_news.sources")`; with no interface bound it skips the refresh, with no error.
- `eval/calibration/routing.jsonl` row `single-news-sources-en` ("What's new in my sources?" → `news`), checked offline with `make calibrate-routing ARGS=--check-sets` (a live run costs credits and is not a gate). The preset sends `{ origin: "preset" }` with no `compose`, so nothing reroutes it: the screen note records the origin and normal routing picks news.

### ze-web

- `entities/ui-manifest`: `modulesForSlot(manifest, slot)`, `presets(manifest)`; `useUiModuleQuery(moduleId, subject)` (query key `uiModule(id, subjectKey)`).
- `widgets/plugin-module`: `PluginModuleSlot({ slot, subject })` renders, per module in the slot (priority order), a `Module` titled with the contribution label:
  - loading → "Loading <label>…";
  - error → the server's detail line;
  - `applies: false` → nothing;
  - otherwise → `ConnectedPrimitiveTree` with 191a's `usePrimitiveActions`.
  
  Visibility: an `IntersectionObserver` sets `refetchInterval` to 60 000 ms while the module is on screen, else off (no background refetch). It renders nothing when the slot has no modules.
- `shared/lib/query-keys.ts`: `refreshKeysForScreen("module:<id>")` returns `[uiModule(id)]` (prefix match over subjects).
- Mounts (one line each): `MindEntityPage` (subject from the entity detail), `DoingWorkflowPage` (subject: the selected execution and its workflow), `Connections` (subject none, after the settings sections).
- `widgets/try-chips`: the `presets` prop is appended to the chips array (at most two), so index labels, keys (preset ids; core chips get fixed ids) and `disabled` continue; each sends `onSend(prompt, { origin: "preset" })`. `pages/ask` passes `presets(manifest)`.
- Router: delete the top-level `:pluginPath` route and `pages/plugin-page`; `places.ts` adds `/news` → `/ask`.
- Fixture: `apps/ze-web/src/test/fixtures/manifest.ts` with one module per slot, one preset and one settings section.

## Project Structure

### Documentation (this feature)

```text
specs/phases/191b-plugin-modules/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md, tasks.md
├── contracts/ui-modules.md
└── checklists/{requirements,slots}.md
```

### Source Code

```text
core/contracts/ze-plugin/ze_plugin/ui.py ; packages/ze-sdk/ze_sdk/ui.py
apps/ze-api/ze_api/api/v0/system/{schemas,ui}.py ; apps/ze-api/ze_api/api/v0/ui_modules/ (new route) ; wiring/{agents,container}.py
core/contracts/ze-plugin/tests/fixture_plugin.py (new test helper)
plugins/ze-news/ze_news/{plugin.py,store.py,api/routes.py,ui/page.py (deleted)} ; eval/calibration/routing.jsonl
packages/ze-client/src/generated/*
apps/ze-web/src/entities/ui-manifest/ ; widgets/{plugin-module (new),try-chips,connections}/ ; pages/{mind-entity,doing-workflow,ask}/ ; pages/plugin-page/ (deleted)
apps/ze-web/src/app/router/routes.tsx ; shared/config/places.ts ; shared/lib/query-keys.ts
```

## Docs touched

- `docs/extending-ze.md`: the plugin UI model (modules, slots, providers, presets, settings); the page kind removed.
- `docs/frontend.md`: slots in the places, `PluginModuleSlot`, the refresh rule, presets in Try chips, `/news` redirect.
- `docs/native-interface.md`: the manifest shape, `getUiModule`, the `module:<id>` refresh screen.
- `packages/ze-sdk/README.md` and `core/contracts/ze-plugin/README.md` if they document `UiContribution`.
- `AGENTS.md`: phase row 191b; the Learned Workspace Facts line on plugin UI (`ui_contributions()` → modules in slots, presets, settings; no pages). `specs/README.md` row 191b.

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first; T002–T004):
- **ze-plugin:** the contribution types and validation, `ModuleSubject`/`ModuleResult`, and the `ze_sdk.ui` re-export.
- **ze-api:** the manifest and module route with its schemas, the log fields, and `make codegen`.
- **Callers:** the tests that name `getNewsPage` are switched.
- **Web:** `entities/ui-manifest` selectors and `useUiModuleQuery`; a `PluginModuleSlot` stub with the final props; the router and `places.ts` changes; `refreshKeysForScreen`.
- **Fixtures:** the Python fixture plugin and the web fixture manifest.
- **News:** its page contribution is deleted in this step so startup passes; lane `news` adds the preset and module.

| Lane | Model / role | Owns (disjoint) | Tasks | Starts after | Reviewer |
|---|---|---|---|---|---|
| lead | Sonnet ENG lead | `ze_plugin/ui.py`, `ze_sdk/ui.py`, `api/v0/system/*`, `api/v0/ui_modules/*`, `wiring/{agents,container}.py`, `packages/ze-client/src/generated/*` and `sdk-dispatch.test.ts`, the ze-api tests naming the manifest or `getNewsPage`, `entities/ui-manifest/*`, `app/router/*`, `shared/config/places.ts`, `shared/lib/query-keys.ts`, the fixtures, `ze_agents/interface/*` and `ze_agents/screen.py`, `api/ws/schemas.py`, `interface/native.py` (`send_refresh`), the ze-personal Contacts page deletion, the deletion of `pages/plugin-page` and `widgets/plugin-screen`'s page-only parts, the one-line removal of News's page contribution; merges, gates | T001–T004, T010, T011 | 191a on `main` | Gauge |
| news | Sonnet ENG | `plugins/ze-news/**` (except the contract-step line), `eval/calibration/routing.jsonl` row | T005 | contract step | floor Reviewer |
| web | Sonnet ENG | `widgets/{plugin-module,try-chips}/*`, `widgets/connections/ui/Connections.tsx`, `pages/{mind-entity,doing-workflow,ask}/*`, their tests | T006–T009 | contract step | floor Reviewer |
| docs | Haiku DOCS | the files in "Docs touched" | T012–T014 | T011 | floor Reviewer |

**Rules**: one lane per file at a time; the contract step's one-line edit in `ze_news/plugin.py` lands before lane `news` starts. `pages/doing-workflow` comes from 188: until 188 lands, the run slot is proven in tests only (against the fixture), and the mount is added to 188's landing checklist in the Handoffs note so it is not lost. There is no JR lane.

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| A provider callable plus one core route, instead of a plugin REST operation per module | One response schema, a timeout and validation in one place, and no plugin needs FastAPI to show a module. The plugin still owns the read (clarification Q5). | A per-module plugin route (duplicates the response schema per plugin; no shared timeout or validation). |
| Visibility-gated 60 s polling | Clarification Q5; avoids polling modules off screen. | Always-on polling (wasted requests on long pages). |
