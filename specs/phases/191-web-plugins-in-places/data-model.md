# Data Model: Plugins in Places (W7)

No storage. Contract types only.

## UiContribution (ze-plugin `ui.py`, re-exported by `ze_sdk.ui`)
| Field | Type | Rule |
|---|---|---|
| id | str | unique |
| plugin | str | |
| kind | `page` \| `settings_section` \| `preset` | |
| label | str | preset ≤ 40 chars |
| icon | str | |
| place | `world`\|`ask`\|`doing`\|`mind`\|`governance` \| None | required for `page` |
| path | str \| None | required for `page`; lowercase slug; unique per place |
| page_operation_id | str \| None | required for `page` |
| settings_operation_id | str \| None | required for `settings_section` |
| prompt | str \| None | required for `preset`; 1–300 chars |
| priority | int | default 100; lists sorted by (priority, id) |

Removed: `show_in_mobile_nav`, `CORE_RESERVED_NAV_PATHS`.

## UiManifest
`pages`, `presets`, `settings_sections` (replaces `nav`, `settings_sections`).
