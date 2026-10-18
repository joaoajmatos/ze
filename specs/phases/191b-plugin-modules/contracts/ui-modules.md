# Contract: UI manifest and modules

## `GET /api/v0/ui/manifest` (`getUiManifest`)
```json
{ "modules": [{ "id": "ze_news.sources", "plugin": "ze_news", "label": "Sources", "icon": "newspaper",
                "slot": "mind.entity", "priority": 100 }],
  "presets": [{ "id": "ze_news.whats_new", "plugin": "ze_news", "label": "What's new in my sources?",
                "icon": "newspaper", "prompt": "What's new in my sources?", "priority": 100 }],
  "settings_sections": [{ "id": "ze_news.settings", "plugin": "ze_news", "label": "News", "icon": "newspaper",
                          "settings_operation_id": "getNewsSettings", "priority": 100 }] }
```

## `GET /api/v0/ui/modules/{module_id}` (`getUiModule`)
Query: `subject_kind` (`entity` | `workflow_run` | `none`), `subject_id`, `subject_label`, `entity_type`, `parent_id`.
- 200 `{ "module_id": "ze_news.sources", "applies": true, "components": [ …191a primitives… ], "ui_version": "2.0" }`
- 200 `{ "module_id": "…", "applies": false, "components": [], "ui_version": "2.0" }`
- 404 unknown module; 422 subject kind not valid for the slot; 502 `{ "detail": "News could not load." }` or `"News sent a view Ze cannot show."`; 504 `{ "detail": "News took too long." }`.

## Refresh
`{ "type": "refresh", "screen": "module:ze_news.sources" }` refetches every subject's copy of that module.

## Web routes
`/news` → `/ask`. No plugin page route; old top-level plugin paths show not found.
