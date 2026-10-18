# Data Model: Plugin Modules in Slots (191b)

No storage change.

## UiContribution (ze-plugin)

| Field | Kinds | Notes |
|---|---|---|
| id, plugin, label, icon, priority | all | ids unique; lists sorted by (priority, id) |
| kind | — | `module` \| `preset` \| `settings_section`; anything else fails startup |
| slot | module | `mind.entity` \| `doing.run` \| `governance.connections` |
| provider | module | async `(ModuleSubject) -> ModuleResult`; not serialized |
| prompt | preset | 1–300 chars; label ≤ 40 |
| settings_operation_id | settings_section | unchanged |

Removed: `path`, `page_operation_id`, `show_in_mobile_nav`, the `nav` kind, `CORE_RESERVED_NAV_PATHS`.

## ModuleSubject

| Slot | kind | Fields |
|---|---|---|
| mind.entity | entity | id, label, entity_type |
| doing.run | workflow_run | id (execution), parent_id (workflow) |
| governance.connections | none | — |

## ModuleResult

`applies: bool`, `components: list[dict]` (191a primitives).

## Manifest

`modules[]` (id, plugin, label, icon, slot, priority), `presets[]` (id, plugin, label, icon, prompt, priority), `settings_sections[]` (unchanged).
