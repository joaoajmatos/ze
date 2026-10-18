# Research: Plugins in Places (W7)

## R1. URL for a plugin page
- **Decision**: `/<place>/plugin/<path>` (World: `/plugin/<path>`).
- **Rationale**: `/ask/:threadId`, `/mind/:entityId` and `/doing/goals/:id` already take the second segment; a fixed `plugin` segment avoids collisions without per-place reserved lists.
- **Alternatives**: `/<place>/<path>` with reserved paths per place (drifts whenever a place adds a route).

## R2. Kind names
- **Decision**: rename `nav` → `page`; add `preset`. Drop `show_in_mobile_nav`.
- **Rationale**: since 183 there is no plugin nav; the contribution is a page that lives in a place. Pre-v1 hard cut.

## R3. Where a place shows its plugin pages
- **Decision**: a "From plugins" module per place (`widgets/plugin-entries`), rendered only when the place has pages.
- **Rationale**: no tab system exists inside the places after 186–190 (they are module pages); a module matches DESIGN.md and costs one line per page.

## R4. Old top-level links
- **Decision**: the `/:pluginPath` catch-all becomes `PluginRedirect` (manifest lookup → place URL, else not found); `/news` is a static redirect to `/ask` in `places.ts`.
- **Rationale**: one hop for bookmarks (FR-004); News has no page any more (clarification Q3).

## R5. News preset
- **Decision**: a plain prompt routed normally (clarification Q2); no compose type.
