# Quickstart: Plugin Modules in Slots (191b)

## Automated
- `make test-plugin`, `make test` (ze-api), `make test-news`, `make test-web`, `make typecheck-web`, `make web-build`, `make lint`.
- `rtk proxy grep -rn "manifest.nav\|ui_manifest.nav\|ui_nav\|show_in_mobile_nav\|CORE_RESERVED_NAV_PATHS\|getNewsPage\|news/page\|build_news_page\|getContactsPage\|build_contacts_page\|page_operation_id\|plugin-page\|pluginPage" core apps plugins packages` returns nothing, and no place list contains `"plugin"` (`api/ws/schemas.py`, `ze_agents/screen.py`, `places.ts`).
- `make calibrate-routing ARGS=--check-sets` passes (offline).

## Manual against `make dev-full`
1. Ask shows "What's new in my sources?" after the core chips, numbered after them; pressing it runs a turn the news agent answers (trace Routing section). The chip comes from the manifest built at startup: after toggling News, restart and reload.
2. Open a Mind topic entity that recent articles are tagged with: a "Sources" module lists them; a person entity shows no Sources module. Trigger a news fetch (`refresh_news`): the open module refreshes without a reload.
3. Stop the database briefly (or make the provider raise in a dev build): the module shows "News could not load." and the rest of the entity page is unchanged.
4. Governance › Connections still renders and saves News settings.
5. `/news` lands on `/ask`; `/notes` shows not found.
6. Open a Doing workflow run: the `doing.run` slot mounts (fixture plugin in a dev build).
