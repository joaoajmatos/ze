# Feature Specification: Plugin Modules in Slots (191b)

**Feature Branch**: `191b-plugin-modules`

**Created**: 2026-10-18

**Status**: Draft

**Input**: User description (2026-10-18, phase 191 reopened): "Plugins are data and behavior sources... I dont know if they should contribute complete pages... they could contribute visual components and/or primitives that can be used to render information." The agreed plugin UI model is summarized in `PRODUCT.md` › Plugin UI model. This phase is its second half; 191a supplies the primitives, typed actions and fallback it builds on.

**Governed by**: `PRODUCT.md` (Plugin UI model; "Ze is not an agenda or notes app; every view answers 'what does Ze understand, and what is it doing about it?'"), `DESIGN.md`, phases 47/63 (plugin framework, UI contributions), 183 (five places), 184 (composed answers, presets), 186–190 (the places), 191a.

**Depends on**: 191a (primitives v2) and the place phases 186–190 (landed or landing). Supersedes the parked 191 "Plugins in Places" design (plugin pages inside places).

**Doctrine function served**: governance (one app frame: plugins extend what places know and show, never add their own screens).

**Owning packages** (for planning): ze-plugin (contribution types and validation), ze-sdk (re-export), ze-api (manifest and module data), plugin ze-news, ze-web (slots in each place). No migration.

## Context

Plugins today can contribute a navigation entry with a whole server-driven page, and a settings section. Only News uses the page. Under the agreed model, a plugin is a source of data and behaviour: it feeds the core contracts (claims, loops, signals, actions, screen resolvers, composed answers, settings), and the five places render what it feeds. When a plugin does need a visual of its own, it contributes a **module**: a title, a data source and a layout of primitives, bound to a **slot** that a place offers. The place decides where the module sits, how dense it is and how it looks. A plugin's "full view" is a composed answer in Ask, summoned by a preset chip.

## Clarifications

### Session 2026-10-18 (user answers through the Maestro: all recommended)

- Q: Does World get a module slot? → A: No. Plugins reach World through claims and loops only.
- Q: How does a module get its data? → A: Each module names a plugin read operation that returns its primitive tree for the slot's subject; it refreshes on place load, on a refresh frame naming the module, and at most every 60 s while visible.
- Q: May plugins add composed-answer types now? → A: Not in 191b; a preset sends a plain prompt.
- Architect decision (recorded so the answer above is not silently reinterpreted): "a plugin read operation per module" is implemented as an in-process provider function that each module declares, served by one core route; the manifest carries no operation id for modules, and the OpenAPI export lists the one core route instead of a route per plugin.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - A plugin's module appears in a place's slot (Priority: P1)

A plugin that knows something about a person, a project or a run contributes a module to the matching slot. The user sees it where it belongs, styled like the rest of the place, not as a separate screen.

**Why this priority**: it is the one new capability; everything else is a cut or a migration.

**Independent Test**: with a fixture plugin that contributes one module to each slot, every slot shows its module in that place, built from primitives, and nothing shows when the plugin is disabled.

**Acceptance Scenarios**:

1. **Given** a module for the Mind entity slot, **When** the user opens an entity the module covers, **Then** the module appears among that entity's facets with its title and primitives.
2. **Given** a module for the Doing run slot, **When** the user opens a run the module covers, **Then** the module appears as a block in that run's view.
3. **Given** a module for the Governance › Connections slot, **When** the user opens Connections, **Then** the module appears as that plugin's card.
4. **Given** a module whose data source fails or times out, **When** the place loads, **Then** the slot shows a plain line naming the plugin and the rest of the place is unaffected.
5. **Given** a module whose data says it does not apply to this entity or run, **When** the place loads, **Then** the slot shows nothing for it.
6. **Given** a module with an action, **When** the user presses it, **Then** it runs through the typed action and the write gates (191a).

---

### User Story 2 - News is a preset, its claims and a sources facet (Priority: P1)

News no longer has a page. Ask shows a "What's new in my sources?" chip that runs an ordinary turn. What News learns reaches the places as claims, and Mind shows a facet listing the sources a topic came from. Its settings stay in Governance › Connections.

**Why this priority**: News is the only plugin with a page today; moving it proves the model and lets the page path be cut.

**Independent Test**: with News enabled, the manifest has a preset, a Mind facet module and a settings section, and no page; the chip runs a turn the news agent answers; the facet shows sources on a topic entity.

**Acceptance Scenarios**:

1. **Given** News enabled, **When** Ask loads, **Then** "What's new in my sources?" appears after the core chips, numbered after them.
2. **Given** the chip is pressed, **When** the turn runs, **Then** it is an ordinary turn whose screen context says it came from a preset, and normal routing sends it to the news agent (guarded by a routing calibration row).
3. **Given** a Mind topic entity whose name equals an article tag, **When** the user opens it, **Then** a "Sources" facet lists the articles with their source and date. A topic whose name differs from every tag (even only in case) shows no Sources facet.
5. **Given** News stores new articles, **When** the fetch finishes, **Then** any open Sources facet refreshes without a reload.
4. **Given** the old News page route, **When** this phase lands, **Then** it is gone, and `/news` redirects to Ask.

---

### User Story 3 - No plugin pages remain (Priority: P2)

The page contribution kind and the top-level plugin route are gone. A plugin that declares a page fails startup with a plain error naming it.

**Why this priority**: the hard cut that keeps the app to five places.

**Independent Test**: a contribution of an unknown or removed kind fails startup; no route renders a plugin page; old top-level plugin paths show not found.

**Acceptance Scenarios**:

1. **Given** a plugin that declares a page or any unknown contribution kind, **When** Ze starts, **Then** startup fails with a typed configuration error naming the contribution.
2. **Given** an old top-level plugin path, **When** the user opens it, **Then** the not-found page shows (`/news` alone redirects to Ask).

---

### User Story 4 - Plugin settings keep working (Priority: P3)

Settings sections render and save in Governance › Connections as 190 built them.

**Why this priority**: regression guard.

**Independent Test**: the News settings section renders and a save runs its operation.

**Acceptance Scenarios**:

1. **Given** the News settings section, **When** the user saves a change, **Then** the plugin's settings operation runs and the saved value shows.

### Edge Cases

- Two plugins contribute to the same slot for the same entity: both modules show, ordered by contribution priority, then id.
- A module's data is slow: the slot shows a loading line; the place never waits for it.
- A plugin is enabled or disabled in config: the manifest is built at startup, so its modules appear or disappear after a restart and a reload.
- A module is asked for before its plugin has finished starting: it shows nothing (not applicable), never a failure line.
- A module's view names a tool of another plugin's agent, or carries a claim posture the shared vocabulary does not allow: Ze refuses the view and shows the plugin's failure line.
- A module renders an unknown primitive: the 191a fallback table shows.
- More plugin presets than chip slots: only the first two by priority show.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Plugin UI contributions MUST be one of: module, preset, settings section. The page kind MUST be removed, and an unknown kind MUST fail startup with a typed configuration error naming the contribution.
- **FR-002**: A module MUST declare a title, the slot it fills, and a plugin read operation that returns a primitive tree for the slot's subject (an entity, a run, or none for the Connections card), or a signal that it does not apply. The slot MUST fetch it on place load, refetch on a refresh frame naming the module, and refetch at most every 60 seconds while visible.
- **FR-003**: The places MUST offer these slots: Mind entity facet, Doing run block, Governance › Connections card, and Ask preset chip. Each place MUST own placement, density and design of its slot.
- **FR-004**: A module's failure, slowness or absence MUST never break or delay the rest of the place; the slot MUST show a plain line for a failure and a loading line while waiting.
- **FR-005**: Module actions MUST use 191a's typed actions and gates; every tool action in a plugin's view MUST name an agent the contributing plugin registered and one of that agent's tools, or the view is refused (Ze enforces this for module views; settings views run the same shared check in the plugin and are tested). Plugins MUST contribute no browser script.
- **FR-005a**: Claim postures in a plugin's view MUST be pairs the shared claim vocabulary allows; Ze derives their tone and label itself and refuses a view with any other posture.
- **FR-005b**: The slot's subject MUST be resolved by Ze from its own records (an entity, a run); an unknown subject is refused.
- **FR-005c**: A plugin MUST be able to ask for its module to be refreshed; News MUST do so after a fetch that stored new articles.
- **FR-006**: The manifest MUST carry modules, presets and settings sections, and the generated client MUST be regenerated.
- **FR-007**: News MUST contribute a preset, a Mind sources facet module and its settings section, and no page; its page route and descriptor MUST be removed; `/news` MUST redirect to Ask.
- **FR-008**: The top-level plugin page route, the reserved-paths list, the mobile-nav flag, the `plugin` place value, and every remaining plugin page route (News's page and ze-personal's Contacts page) MUST be removed (pre-v1 hard cut).
- **FR-009**: A fixture plugin MUST prove each slot in tests.
- **FR-010**: Docs MUST describe the plugin UI model (modules, slots, presets, settings), and `PRODUCT.md` MUST carry a short Plugin UI model section.

### Key Entities

- **Module contribution**: plugin, id, title, slot, data source, priority.
- **Slot**: place, kind (entity facet, run block, connections card, preset chip), and the subject it passes to a module.
- **Preset contribution**: plugin, id, label, prompt, priority.
- **Settings contribution**: unchanged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Each slot shows a fixture module in tests, and a failing module never changes what the rest of its place shows.
- **SC-002**: No route renders a plugin page (a route test fails if one does).
- **SC-003**: The News chip's turn reaches the news agent, and the sources facet shows on a mentioned entity.
- **SC-004**: The suites, typecheck and lint pass.

## Assumptions

- World gets plugin data through claims and loops only (clarification).
- Presets send a plain prompt routed like a typed question; plugin composed-answer types are a later phase (clarification).
- Only News contributes UI today; Finance and others gain none here (plugins mature later).
