# Feature Specification: Plugins in Places (W7)

**Feature Branch**: `191-web-plugins-in-places`

**Created**: 2026-10-17 (refined through `/speckit-specify` 2026-10-18)

**Status**: Draft

**Input**: User description: "Plugins in Places (W7)": Maestro brief 2026-10-17, phase W7; overhaul plan sections a (capability map: Contacts → Mind, Reminders → World, News → Ask preset + Governance settings) and e (Phase W7). The capability map was accepted with the overhaul plan ("go with the recommendations").

**Governed by**: `PRODUCT.md` (plugins contribute screens at runtime through the UI manifest), `specs/arch/plugin-domain-vocabulary.md`, phases 47/63 (plugin framework, UI contributions), 66 (primitive UI), 183 (five places and the redirect table), 187 (Try chips, restyled renderer), 190 (plugin settings in Governance › Connections).

**Depends on**: 187 (Ask: Try chips and the restyled renderer) and 189 (Mind › People). 186 already absorbed Reminders, 189 Contacts, and 190 plugin settings.

**Doctrine function served**: governance (one app frame: plugins extend places instead of adding organs to the nav).

**Owning packages** (for planning): ze-plugin (contribution types and validation), ze-api (manifest), plugin ze-news, ze-web. No migration.

## Context

Plugins declare UI contributions in a manifest the web app reads at runtime: navigation entries with a server-driven page, and settings sections. The five places now own the app frame (183), and 186, 189 and 190 moved Reminders, Contacts and plugin settings into places. One plugin page is left: News, shown at a top-level route outside the places. The web app still has a catch-all top-level route for any plugin page. This phase ties every plugin page to a place, turns News into an Ask preset, and closes the top-level plugin route.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Plugin pages live inside a place (Priority: P1)

A plugin that contributes a page names the place it belongs to. Its page shows as a section of that place, built from HUD modules like the rest of the app, never as its own nav item. Old links to the plugin's top-level path land on the new location.

**Why this priority**: it is the rule that keeps the app to five places as plugins grow.

**Independent Test**: with a fixture plugin that contributes a page in Mind, the page renders as a Mind section with one module per top-level element; the old top-level path redirects there; a contribution without a place makes startup fail with a plain error that names the plugin.

**Acceptance Scenarios**:

1. **Given** a plugin contributing a page with place `mind` and path `p`, **When** the user opens Mind, **Then** a section for it appears and opens at `/mind/p`, rendered as modules.
2. **Given** that plugin, **When** the user opens `/p`, **Then** they land on `/mind/p` in one hop.
3. **Given** a plugin page contribution with no place, or a place outside the five, **When** Ze starts, **Then** startup fails with a typed configuration error naming the contribution.
4. **Given** two contributions with the same place and path, **When** Ze starts, **Then** startup fails as duplicate nav paths do today.

---

### User Story 2 - News becomes an Ask preset (Priority: P2)

The News plugin no longer has a page. It adds a Try chip in Ask, "What's new in my sources?", that asks Ze in the normal way. Its settings stay in Governance › Connections.

**Why this priority**: it applies the accepted capability map. News answers a question; it is not a place to browse.

**Independent Test**: with News enabled, the manifest carries one preset and one settings section and no page. The Try chips show the preset after the core chips, and tapping it sends its prompt on the selected thread. With News disabled, the chip is gone.

**Acceptance Scenarios**:

1. **Given** News is enabled, **When** Ask loads, **Then** "What's new in my sources?" appears after the core Try chips.
2. **Given** the user taps it, **When** the turn runs, **Then** it is an ordinary turn with the preset's prompt, marked as a preset in the screen context.
3. **Given** the News page route and its page descriptor, **When** this phase lands, **Then** both are gone (pre-v1 hard cut), and `/news` redirects to Ask.
4. **Given** News is disabled, **When** Ask loads, **Then** no News chip appears.

---

### User Story 3 - Plugin settings are verified in place (Priority: P3)

Plugin settings sections render and save from Governance › Connections. Phase 190 built this; this phase only checks it against the final manifest.

**Why this priority**: regression guard only.

**Independent Test**: the manifest's settings sections render in Connections and a save dispatches the section's operation.

**Acceptance Scenarios**:

1. **Given** the News settings section, **When** the user changes and saves a setting in Governance › Connections, **Then** the plugin's settings operation runs and the saved value shows.

### Edge Cases

- No plugin contributes a page (the state after News moves): the places show no plugin sections, and the place-aware page route is still covered by the fixture plugin's tests.
- A plugin contributes a preset but no page: only the chip appears.
- More plugin presets than chip slots: chips beyond the limit are not shown, and the order is stable (contribution priority, then id).
- An old bookmark to a removed plugin path that no plugin now claims lands on not-found, not a blank page.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Page contributions MUST declare a place, one of the five (world, ask, doing, mind, governance). Startup MUST fail with a typed configuration error when it is missing or invalid.
- **FR-002**: The UI manifest MUST carry each page contribution's place and each preset contribution, and the generated web client MUST be regenerated.
- **FR-003**: A new preset contribution kind MUST carry a label and a prompt. Ask MUST show presets as Try chips after the core chips, at most two plugin chips, in contribution priority order, sending through the single send path with the preset marked.
- **FR-004**: The web app MUST render each plugin page as a section of its place at `/<place>/<path>`, with one HUD module per top-level element. The old top-level path MUST redirect to it in one hop.
- **FR-005**: The top-level catch-all plugin route and any plugin nav mapping outside places MUST be removed (pre-v1 hard cut). The News page route, its page descriptor and its nav contribution MUST be removed; `/news` MUST redirect to Ask.
- **FR-006**: The core reserved nav paths list MUST be updated to the five places and their known section paths, so a plugin cannot claim them.
- **FR-007**: Docs MUST describe page contributions with a place and the preset kind (extending-Ze guide, frontend, native interface), and README screenshots MUST be refreshed.

### Key Entities

- **Page contribution**: plugin, id, label, place, path, page operation, priority.
- **Preset contribution**: plugin, id, label, prompt, priority.
- **Settings contribution**: unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Manifest tests cover every installed plugin's contributions, plus a fixture plugin with a page in each of two places.
- **SC-002**: No route renders a plugin page outside the five places (a route test fails if a top-level plugin path renders a page).
- **SC-003**: The Python plugin and manifest suites, the web suites, typecheck and lint pass.

## Assumptions

- The News preset prompt is a plain question routed like any typed question (to the news agent by routing). No new composed-answer type is added for News.
- Two plugin chips is enough for now. Only News contributes one.
- Plugin settings stay as 190 built them; this phase adds no settings behaviour.
- Finance and other plugins gain no UI here (plugins mature later).
