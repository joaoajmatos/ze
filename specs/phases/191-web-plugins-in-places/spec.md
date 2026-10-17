# Feature Specification: Plugins in Places (W7)

**Feature Branch**: `191-web-plugins-in-places`

**Created**: 2026-10-17

**Status**: Draft (spec level; plan and tasks follow once scheduled)

**Input**: Maestro brief 2026-10-17, phase W7; overhaul plan sections a (capability map: Contacts → Mind, Reminders → World, News → Ask preset + Governance settings), e (Phase W7).

**Governed by**: `PRODUCT.md` (plugins contribute screens at runtime through `GET /api/v0/ui/manifest`), `specs/arch/plugin-domain-vocabulary.md`, phase 47/63 (plugin framework, UI contributions), 66 (primitive UI).

**Depends on**: 187 (restyled `PrimitiveRenderer`), 189 (Mind › People). 186 already absorbed Reminders.

**Doctrine function served**: governance (one app frame; plugins extend places instead of adding organs to the nav).

---

## Overview

Plugins declare nav entries and pages in the UI manifest. After the five places land, a plugin page must render inside a place, as HUD modules, never as a separate nav item. This phase adds a `place` to manifest nav contributions, maps every current plugin into a place, and renders manifest pages through one widget.

## User Scenarios & Testing *(mandatory)*

1. **No plugin page renders outside the five places (P1).** Each manifest nav entry declares `place` (`world` | `ask` | `doing` | `mind` | `governance`) and appears as a section in that place; `/:pluginPath` redirects to `/<place>/<pluginPath>`.
2. **Server-driven pages render as modules (P1)** through `widgets/plugin-screen` restyled (module per top-level primitive).
3. **Plugin settings operations dispatch from Governance › Connections (P2).**
4. **News becomes an Ask preset (P2)**: the News plugin contributes a preset chip ("What's new in my sources?") instead of a page; its settings live in Governance.

## Requirements *(mandatory)*

- **FR-001**: `ze_plugin` UI contribution type gains `place` (required for nav entries; validated at manifest build; a plugin without it fails startup with a typed error). The News contribution is updated in its plugin. (Reminders and Contacts no longer contribute nav entries: 186 renders reminders in World and deletes the Reminders page, 189 renders contacts in Mind › People and deletes the Contacts entry.)
- **FR-002**: Manifest REST (`getUiManifest`) carries `place`; `make codegen`.
- **FR-003**: Optional `preset` contribution kind (label + `context` payload, e.g. `compose` values or a plain prompt) rendered as Ask Try chips; News uses it.
- **FR-004**: Hard cuts: `entities/ui-manifest` `pluginNavRoutes` top-level mapping, the `/:pluginPath` top-level route (redirect only), any remaining plugin nav code; the News page descriptor if replaced by the preset.
- **FR-005**: Docs Steward: `docs/frontend.md`, `docs/native-interface.md`, `docs/extending-ze.md` (plugin UI contributions with `place`), README screenshots refreshed.

## Success Criteria *(mandatory)*

- **SC-001**: Manifest mapping tests cover every installed plugin.
- **SC-002**: `make test-py` (plugin contributions), `make test-web`, `make typecheck-web`, lint pass.

## Out of Scope

- New plugin features; finance redesign (plugins mature later).

## Owning packages

ze-plugin (contribution type), ze-api (manifest), plugin ze-news, ze-web; no migration.
