# Contract: getUiManifest

`GET /api/v0/ui/manifest` (`getUiManifest`, API key):
```json
{
  "pages": [{ "id": "x.notes", "plugin": "x", "kind": "page", "label": "Notes", "icon": "note",
              "place": "mind", "path": "notes", "page_operation_id": "getXNotesPage", "priority": 100 }],
  "presets": [{ "id": "ze_news.whats_new", "plugin": "ze_news", "kind": "preset",
                "label": "What's new in my sources?", "icon": "newspaper",
                "prompt": "What's new in my sources?", "priority": 100 }],
  "settings_sections": [{ "id": "ze_news.settings", "plugin": "ze_news", "kind": "settings_section",
                          "label": "News", "icon": "newspaper", "settings_operation_id": "getNewsSettings", "priority": 100 }]
}
```
Validation (startup, `AgentConfigError` naming the contribution id):
- `kind` is one of `page`, `preset`, `settings_section`; anything else raises.
- page: `place` in the five, `path` matches `^[a-z0-9][a-z0-9-]{0,39}$`, `page_operation_id` set; `(place, path)` unique.
- preset: `label` 1–40 characters, `prompt` 1–300 characters; no place.
- ids unique. Each list is sorted by `(priority, id)`.

Web routes: `/<place>/plugin/<path>` (World `/plugin/<path>`); `/news` → `/ask`. There is no top-level `/:pluginPath` route; an old top-level plugin path falls to the `*` not-found route.

Refresh: a `{"type": "refresh", "screen": S}` frame for a plugin page carries the page id as `S` (for example `x.notes`). `refreshKeysForScreen` matches `S` against `manifest.pages[].id` and invalidates `queryKeys.pluginPage(id)`. Paths are not unique across places, so the web app never matches a refresh by path. No plugin sends a refresh frame today.
Removed: `nav`, `show_in_mobile_nav`, `GET /api/v0/news/page` (`getNewsPage`).
