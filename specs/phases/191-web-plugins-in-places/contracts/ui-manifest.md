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
Web routes: `/<place>/plugin/<path>` (World `/plugin/<path>`); `/<path>` redirects there; `/news` → `/ask`.
Removed: `nav`, `show_in_mobile_nav`, `GET /api/v0/news/page` (`getNewsPage`).
