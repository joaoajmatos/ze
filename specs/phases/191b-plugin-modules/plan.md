# Implementation Plan: Plugin Modules in Slots (191b)

**Branch**: `191b-plugin-modules` | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md with the 2026-10-18 clarifications (user: all recommended); `main` e4d57414; 191a's contract (typed actions, `ui_version`, fallback, slot primitives).

## Summary

- **Contributions.** `UiContribution.kind` becomes `module | preset | settings_section`. The page kind, `path`, `page_operation_id`, `show_in_mobile_nav` and `CORE_RESERVED_NAV_PATHS` are cut. A module declares a `slot` (`mind.entity`, `doing.run`, `governance.connections`) and a Python `provider`, the plugin's read operation: `async (subject) -> ModuleResult(applies, components)`.
- **One core route.** ze-api serves `GET /api/v0/ui/modules/{module_id}` (`getUiModule`). It calls the module's provider with the slot's subject under a 3 s timeout and returns the tree with `ui_version`. Plugins write no REST route for a module.
- **Manifest.** It returns `modules`, `presets` and `settings_sections`.
- **Web slots.** One `widgets/plugin-module` slot component fetches each module for its slot and subject. It refetches on place load, on a `refresh` frame with `screen: "module:<id>"`, and every 60 s while visible, and shows a loading line, a plain failure line, or nothing when the module does not apply. Slots are mounted in the Mind entity page, the Doing workflow run page and Governance › Connections. Ask's Try chips add up to two plugin presets.
- **News.** It contributes the preset "What's new in my sources?", a `mind.entity` module "Sources" (articles whose tags match the entity), and its settings section. The page, `getNewsPage` and `ui/page.py` are deleted; `/news` redirects to `/ask`.
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
| `ze_personal/api/routes.py` (`PluginPageResponse`) | — | T001 checks whether it is reachable; 191b leaves it unless it is a page route (then deleted). |
| Web `manifest.nav` | `pages/plugin-page/ui/PluginPage.tsx`, `shared/lib/query-keys.ts` (`refreshKeysForScreen`) | `pages/plugin-page` deleted; `refreshKeysForScreen` handles `module:<id>`. |
| Router `:pluginPath` (`app/router/routes.tsx`) | router | Deleted; the `*` route shows not found. |
| `widgets/connections/ui/Connections.tsx:81` (`settings_sections`) | Governance | Unchanged list; gains the `governance.connections` module slot. |
| `pages/mind-entity/ui/MindEntityPage.tsx` | router | Mounts the `mind.entity` slot under the neighbourhood. |
| `pages/doing-workflow/ui/DoingWorkflowPage.tsx` (188) | router | Mounts the `doing.run` slot in the selected run's view. |
| `widgets/try-chips` (187: chips array, `chips[Number(e.key) - 1]`, `disabled`) | `pages/ask` | `presets: { id, label, prompt }[]`, appended to the chips array so numbering, keys and `disabled` continue. |

## Design

### ze-plugin (`ui.py`)

- `Slot = Literal["mind.entity", "doing.run", "governance.connections"]`.
- `ModuleSubject(kind: Literal["entity", "workflow_run", "none"], id: str | None, label: str | None, entity_type: str | None, parent_id: str | None)`.
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

### ze-api

- `GET /api/v0/ui/modules/{module_id}` (`getUiModule`, API key), query `subject_kind`, `subject_id`, `subject_label`, `entity_type`, `parent_id` (each optional, validated per kind):
  - unknown id → 404;
  - the subject kind does not match the slot (`mind.entity` → entity, `doing.run` → workflow_run, `governance.connections` → none) → 422;
  - otherwise `asyncio.wait_for(provider(subject), 3.0)`:
    - success → 200 `{ "module_id", "applies", "components", "ui_version" }`, with components validated against the 191a schema; an invalid tree → 502 with detail "<Plugin> sent a view Ze cannot show.";
    - timeout → 504 with detail "<Plugin> took too long.";
    - exception → 502 with detail "<Plugin> could not load."
  
  A failure is logged (`ui_module_failed`). Schemas `UiModuleResponse`, `UiManifestResponse` (`modules`, `presets`, `settings_sections`).
- `build_ui_manifest` and the container log the new fields.

### ze-news

- `NewsStore.by_tag(tag, limit=8)`: articles whose `tags` contain the tag (case-insensitive), newest first.
- `ui_contributions()` returns three contributions:
  - the preset `ze_news.whats_new` (label and prompt "What's new in my sources?", icon `newspaper`);
  - the module `ze_news.sources` (slot `mind.entity`, label "Sources"). Its provider returns `applies=False` for entity types other than `topic` or when nothing matches, else a `claim_list`: one item per article with title, source and date, posture `fact`/`live_search` set by code, and the action `navigate` to nothing; the article link is shown as text;
  - `ze_news.settings` (unchanged).
- Deleted: `getNewsPage`, `ui/page.py`, its tests, and the page cases in `tests/test_api_routes.py`.
- `eval/calibration/routing.jsonl` row `single-news-sources-en` ("What's new in my sources?" → `news`).

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
| lead | Sonnet ENG lead | `ze_plugin/ui.py`, `ze_sdk/ui.py`, `api/v0/system/*`, `api/v0/ui_modules/*`, `wiring/{agents,container}.py`, `packages/ze-client/src/generated/*` and `sdk-dispatch.test.ts`, the ze-api tests naming the manifest or `getNewsPage`, `entities/ui-manifest/*`, `app/router/*`, `shared/config/places.ts`, `shared/lib/query-keys.ts`, the fixtures, the deletion of `pages/plugin-page` and `widgets/plugin-screen`'s page-only parts, the one-line removal of News's page contribution; merges, gates | T001–T004, T010, T011 | 191a on `main` | Gauge |
| news | Sonnet ENG | `plugins/ze-news/**` (except the contract-step line), `eval/calibration/routing.jsonl` row | T005 | contract step | floor Reviewer |
| web | Sonnet ENG | `widgets/{plugin-module,try-chips}/*`, `widgets/connections/ui/Connections.tsx`, `pages/{mind-entity,doing-workflow,ask}/*`, their tests | T006–T009 | contract step | floor Reviewer |
| docs | Haiku DOCS | the files in "Docs touched" | T012–T014 | T011 | floor Reviewer |

**Rules**: one lane per file at a time; the contract step's one-line edit in `ze_news/plugin.py` lands before lane `news` starts. `pages/doing-workflow` comes from 188: if 188 has not landed when 191b starts, lane `web` mounts the run slot after it lands and records it. There is no JR lane.

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| A provider callable plus one core route, instead of a plugin REST operation per module | One response schema, a timeout and validation in one place, and no plugin needs FastAPI to show a module. The plugin still owns the read (clarification Q5). | A per-module plugin route (duplicates the response schema per plugin; no shared timeout or validation). |
| Visibility-gated 60 s polling | Clarification Q5; avoids polling modules off screen. | Always-on polling (wasted requests on long pages). |
