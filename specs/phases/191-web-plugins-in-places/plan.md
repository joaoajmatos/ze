# Implementation Plan: Plugins in Places (W7)

**Branch**: `191-web-plugins-in-places` | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md with the 2026-10-18 clarifications (user: all recommended), `main` at ab334b60 (186, 189 and 190 landed; 187 building; 188 building).

## Summary

The plugin UI contract gains `place` and a `preset` kind. The `nav` kind is renamed `page`, since nothing is nav any more. Startup fails if a page has no valid place.

- **Manifest.** It returns `pages`, `presets` and `settings_sections`.
- **News.** It drops its page, route and page builder, and contributes the preset "What's new in my sources?" plus its existing settings section.
- **Web.** A plugin page renders inside its place at `/<place>/plugin/<path>` as HUD modules, one per top-level element. Each place lists its plugin pages in a small entries module that renders only when the place has pages. The old top-level `/:pluginPath` route is deleted (old plugin paths fall to not-found), and `/news` redirects to `/ask`. Ask's Try chips gain up to two plugin presets.

## Technical Context

**Language/Version**: Python 3.12; TypeScript 5, React 19, TanStack Query 5.
**Primary Dependencies**: none new.
**Storage**: none; no migration.
**Testing**: pytest (contribution validation, manifest route, news plugin); vitest (routes, plugin page, entries module, Try chips presets) with a fixture plugin manifest.
**Target Platform**: Linux container + browser.
**Project Type**: web service + web app.
**Constraints**: FSD (pages → widgets → features → entities → shared); DESIGN.md modules; 44 px targets; plugins import only `ze_sdk.*`.
**Scale/Scope**: one plugin contributes UI today (News), so the place-aware page path is covered by a fixture plugin (clarification Q1).

## Constitution Check

| Principle | Check |
|---|---|
| I Spec-first | spec, clarifications, plan, research, data model, contract, quickstart, tasks. |
| III Layered packages | Contribution types in ze-plugin, re-exported by `ze_sdk.ui`. ze-news imports `ze_sdk.ui` only; the manifest route lives in ze-api. |
| IV Typed Python | `UiContribution` dataclass with `place: Place | None`, `prompt: str | None`; `AgentConfigError` on invalid contributions (the existing typed error). |
| V Tests | Fail-first per task. |
| VIII Hard cuts | `nav` → `page` rename, `CORE_RESERVED_NAV_PATHS` deleted, the manifest field `nav` → `pages`, the News page route and builder deleted, the top-level plugin page route deleted; no redirect shim. |

Gate: pass.

## Blast radius

`graphify affected` and grep on `main` ab334b60:

| Symbol | Callers | Change |
|---|---|---|
| `UiContribution` (`ze_plugin/ui.py`), re-exported by `ze_sdk.ui` (`ze_sdk/ui.py:2,10` also re-exports `CORE_RESERVED_NAV_PATHS`) | `ze_news/plugin.py` (`:160` passes `show_in_mobile_nav`), `collect_ui_contributions`, `filter_ui_manifest_by_openapi`, `core/contracts/ze-plugin/tests/test_ui.py`, `apps/ze-api/tests/api/test_ui_manifest.py` | `kind` becomes `Literal["page", "settings_section", "preset"]`; adds `place`, `prompt`. |
| `CORE_RESERVED_NAV_PATHS` | `collect_ui_contributions` | Deleted. Uniqueness becomes per `(place, path)`. |
| `UiManifest` (`nav`, `settings_sections`) | `ZeContainer.ui_manifest`, `UiManifestResponse.from_domain`, `wiring/agents.py:224-231` (`build_ui_manifest` logs `nav=`), `wiring/container.py:768` (`ui_nav=len(ui_manifest.nav)`; 192 and 194 also edit this file, so rebase on whichever lands first) | Becomes `pages`, `presets`, `settings_sections`. |
| `filter_ui_manifest_by_openapi` | container wiring | Filters pages by `page_operation_id` and settings by `settings_operation_id`; presets pass. |
| `UiContributionSchema`, `UiManifestResponse` (`api/v0/system/schemas.py`) | `getUiManifest` | Mirror the domain; `make codegen`. |
| News page operation in tests | `apps/ze-api/tests/api/test_openapi_export.py:11,27` and `apps/ze-api/tests/test_plugin_routes.py:28` (name `getNewsPage` / `/news/page`), `packages/ze-client/src/sdk-dispatch.test.ts` (dispatches `getNewsPage`), `features/primitive-tree/api/usePluginScreenActions.test.ts:51-64` | Point each at a remaining operation (`getNewsSettings`) or the fixture page operation. |
| `getNewsPage` route, `ze_news/ui/page.py` `build_news_page`, `PluginPageResponse` use for the page | `ze_news/api/routes.py`, `plugins/ze-news/tests/test_api_routes.py`, `test_ui_page.py` | Deleted; the settings route stays. |
| `manifest.nav` (web) | `pages/plugin-page/ui/PluginPage.tsx:28`, `shared/lib/query-keys.ts:75` (`refreshKeysForScreen`) | Become `manifest.pages`; the refresh lookup matches the page **id** (paths repeat across places; see the contract). |
| `placeOf` (`shared/config/places.ts`) | `AppShell` (`widgets/app-shell`, `onAsk`), place frame, strip | `placeOf("/plugin/x")` returns World (today the `plugin` segment returns null). New `isPluginPath(pathname)`; `AppShell` sets `onAsk` only when the place is Ask **and** the path is not a plugin path, so `/ask/plugin/x` opens the overlay. |
| `manifest.settings_sections` | `widgets/connections/ui/Connections.tsx:81` | Unchanged name. |
| `:pluginPath` route (`app/router/routes.tsx:61`) | router | Deleted; the `*` route covers old paths. New child routes `<place>/plugin/:pluginPath` for each place. |
| `PluginScreen` (`widgets/plugin-screen`) | `PluginPage`, `PluginSettingsSection` (in Connections) | Restyled: one `Module` per top-level element; the header hook removed (the place frame owns the title). |
| `widgets/try-chips` (187: `chips` array, `chips[Number(e.key) - 1]`, `disabled` prop, keys by `chip.text`) | `pages/ask` | Takes `presets: { id, label, prompt }[]`; plugin chips are appended to the same `chips` array, so numbering and keys continue (3–4 or 4–5); React keys become a stable id (core chips get fixed ids); `disabled` applies to all. |
| The five place pages (`pages/{world,ask,doing,mind,governance}`) | router | Each renders `PluginEntries place="…"` (one line each). |

## Design

### ze-plugin (`ui.py`)

- `Place = Literal["world", "ask", "doing", "mind", "governance"]`.
- `UiContribution(id, plugin, kind: Literal["page", "settings_section", "preset"], label, icon, path=None, place=None, page_operation_id=None, settings_operation_id=None, prompt=None, priority=100)`. `show_in_mobile_nav` is deleted, since there is no plugin nav.
- `collect_ui_contributions` validates and raises `AgentConfigError` naming the contribution. The rules:
  - **page:** requires `place` in `Place`, `path` (lowercase slug), and `page_operation_id`; `(place, path)` is unique.
  - **preset:** requires `prompt` (1–300 characters) and `label` (at most 40 characters); there is no place.
  - **settings_section:** unchanged.
  - **ids:** unique, as today.
  
  - **kind:** anything other than `page`, `preset`, `settings_section` raises.
  - **path:** `^[a-z0-9][a-z0-9-]{0,39}$`.
  
  Each list is sorted by `(priority, id)`.
- `UiManifest(pages, presets, settings_sections)`.

### ze-api

- `UiContributionSchema` and `UiManifestResponse` mirror the domain (`pages`, `presets`, `settings_sections`), and the route description is updated. `make codegen`.

### ze-news

- `ui_contributions()` returns the preset (`id="ze_news.whats_new"`, label "What's new in my sources?", prompt "What's new in my sources?", icon `newspaper`) and the settings section.
- Delete `GET /news/page` (`getNewsPage`), `ui/page.py` and their tests; `PluginPageResponse` stays for settings.

### ze-web

- `entities/ui-manifest`: types from the generated client; `useUiManifestQuery` unchanged; a selector `pagesForPlace(manifest, place)`.
- `pages/plugin-page`: `PluginPage` reads `:place` and `:pluginPath`, finds the page with that place and path (not found otherwise; the loading line while the manifest loads), and renders `PluginScreen`.
- `widgets/plugin-screen`: restyled to modules (`Module` per top-level primitive, `A·NN` index, label from the element's title or the entry label); `useSetPageHeader` removed. `PluginSettingsSection` usage in Connections is unchanged.
- `widgets/plugin-entries`: `PluginEntries({ place })` renders a `Module` titled "From plugins" with one 44 px row per page (icon, label) linking to `/<place>/plugin/<path>`. It renders nothing when there are none.
- `widgets/try-chips`: a `presets: { id, label, prompt }[]` prop. Plugin chips are appended to the core `chips` array (at most two), so their index and key continue the visible numbering (3–4 without an active goal, 4–5 with one) under the same focus rule and `disabled` state; each calls `onSend(prompt, { origin: "preset" })`. React keys are ids (`core.slipping`, `core.decisions`, `core.goal`, the preset id).
- **Router:**
  - one `<place>/plugin/:pluginPath` child per place (`plugin/:pluginPath` under `/` for World), placed before the dynamic `ask/:threadId` and `mind/:entityId`;
  - the top-level `:pluginPath` route deleted (the `*` route renders not-found);
  - `matchRoutes` tests pin the ranking: `<place>/plugin/:pluginPath` beats `ask/:threadId`, `mind/:entityId`, and the `doing/*` and `governance/*` splats;
  - `places.ts` redirect `/news` → `/ask`;
  - `query-keys.ts`: `refreshKeysForScreen` matches `manifest.pages[].id`.
  - `places.ts`: `placeOf` maps `/plugin/...` to World; `isPluginPath`. `AppShell`: `onAsk` false on plugin paths.
- **Place pages:** each adds `<PluginEntries place="…" />` in its rail or index; Ask passes `presets` to `TryChips`.

## Project Structure

### Documentation (this feature)

```text
specs/phases/191-web-plugins-in-places/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md, tasks.md
├── contracts/ui-manifest.md
└── checklists/requirements.md
```

### Source Code

```text
core/contracts/ze-plugin/ze_plugin/ui.py ; packages/ze-sdk/ze_sdk/ui.py (re-export check)
apps/ze-api/ze_api/api/v0/system/{schemas.py,ui.py} ; apps/ze-api/ze_api/wiring/* (manifest build, if it names nav)
plugins/ze-news/ze_news/{plugin.py,api/routes.py,ui/page.py (deleted)}
packages/ze-client/src/generated/*
apps/ze-web/src/entities/ui-manifest/ ; pages/plugin-page/ ; widgets/{plugin-screen,plugin-entries (new),try-chips}/
apps/ze-web/src/pages/{world,ask,doing,mind,governance}/ui/*Page.tsx (one line each)
apps/ze-web/src/app/router/routes.tsx ; shared/config/places.ts ; shared/lib/query-keys.ts ; widgets/app-shell/ui/AppShell.tsx
eval/calibration/routing.jsonl (one row)
```

## Docs touched

- `docs/extending-ze.md`: UI contributions (`page` with `place`, `preset`, `settings_section`); the reserved-paths rule removed.
- `docs/frontend.md`: plugin pages in places, entries module, `/<place>/plugin/<path>`, presets in Try chips, `/news` redirect.
- `docs/native-interface.md`: the manifest shape.
- `packages/ze-sdk/README.md` if it documents `UiContribution`.
- README screenshots refreshed (FR-007).
- `AGENTS.md`: phase row 191; the Learned Workspace Facts line on plugin UI (`ui_contributions()` → pages in places, presets); `specs/README.md` row 191.

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first; T002–T003):
- **ze-plugin:** `UiContribution` with `place`, `prompt` and the `page`/`preset` kinds; `UiManifest(pages, presets, settings_sections)`, with the validation rules.
- **ze-api:** the schemas.
- `make codegen`.
- **Router and shell:** the child routes, the top-level `:pluginPath` route deleted, the `/news` redirect, `refreshKeysForScreen` on page ids, `placeOf`/`isPluginPath`, and `AppShell`'s `onAsk`.
- **Fixture:** `apps/ze-web/src/test/fixtures/manifest.ts` (two pages in Mind and Doing, one preset, one settings section).

| Lane | Model / role | Owns (disjoint) | Tasks | Starts after | Reviewer |
|---|---|---|---|---|---|
| lead | Sonnet ENG lead | `ze_plugin/ui.py`, `ze_sdk/ui.py`, `api/v0/system/{schemas,ui}.py`, ze-api wiring that builds the manifest, `packages/ze-client/src/generated/*` and `sdk-dispatch.test.ts`, the ze-api tests naming the manifest or `getNewsPage`, `app/router/*`, `shared/config/places.ts`, `shared/lib/query-keys.ts`, `widgets/app-shell/*`, the web fixture; merges, gates | T001–T003, T011, T012 | - | Gauge |
| news | Sonnet ENG | `plugins/ze-news/ze_news/{plugin.py,api/routes.py,ui/page.py}` and their tests, the `eval/calibration/routing.jsonl` news row | T004 | contract step | floor Reviewer |
| web | Sonnet ENG | `entities/ui-manifest`, `pages/plugin-page`, `widgets/{plugin-screen,plugin-entries,try-chips}`, `features/primitive-tree/api/usePluginScreenActions.test.ts`, the five place pages (one line each), and their tests | T005–T009 | contract step | floor Reviewer |
| docs | Haiku DOCS | the files in "Docs touched", plus the screenshot capture run | T013–T015 | T011 | floor Reviewer |

**Rules**: one lane per file, with one exception: the contract step deletes News's `nav` contribution in `ze_news/plugin.py` so startup passes, before lane `news` starts. The place pages belong to other floors (186–190) until those land; lane `web` touches one line in each and rebases when needed. There is no JR lane: each piece crosses a contract or a page layout.

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| `/<place>/plugin/<path>` instead of `/<place>/<path>` | `/ask/:threadId` and `/mind/:entityId` would swallow plugin paths. | Reserving per-place path lists (drifts as places add routes). |
| Keep place-aware pages with no live consumer | User decision (clarification Q1); covered by a fixture plugin. | Cutting plugin pages (rebuild later). |
