# Data Model: Web UI HIG Audit Fixes

This feature introduces no new persisted entities and no schema changes. The
"entities" below are UI-state concepts already implemented in `apps/ze-web`,
documented here only to the extent this feature adds or changes fields on
them. Everything not listed is unchanged.

## Chat message delivery state (User Story 1)

Already modeled per-thread in the `useWsStore` Zustand store
(`thinkingThreads`, `typingTextThreads`) and per-message in
`entities/message`. No new fields are anticipated; the fix is expected to be
in *how reliably* the existing `message` WS frame transitions this state,
plus a bounded-wait fallback. If the root-cause investigation (research.md,
Unknown 1) surfaces a genuine need for a new field (e.g. a client-side
"delivery attempt" timestamp to drive a timeout), it belongs on the
in-memory `useWsStore` thread state, not on the persisted `Message` type —
no backend/database change either way.

## Navigation destination (User Story 2, User Story 7, User Story 8)

Already modeled as `NavRouteMeta` (`shared/config/nav-routes.ts`): `path`,
`label`, `icon`, `index?`, `showInMobileNav?`. This feature adds no new
fields to the type. What changes is:
- Reachability: `NavGroup` must expose its `children` (currently gated
  `hidden lg:...`) at the `md` breakpoint too (User Story 2).
- Accessible name: icon-only rendering of a `NavRouteMeta` must carry an
  `aria-label` derived from its existing `label` field — no schema change,
  a rendering-completeness fix (User Story 7).
- Mobile overflow grouping: the merged mobile nav list (`mobileNavRoutes` +
  plugin-contributed items from the UI manifest) needs a presentation-layer
  "primary vs. overflow" split once the merged count exceeds the
  comfortable tab-bar limit — this is a UI grouping decision applied at
  render time, not a new persisted field on `NavRouteMeta` (User Story 8).

## Contextual assistant panel state (User Story 3, 4, 5)

Already modeled in `useOverlayStore` (`features/open-context-overlay`):
`open`, `screen`, `entityId?`, `prefillMessage?`, `overlayThreadId`. This
feature does not add fields; it fixes:
- `screen` being set correctly regardless of trigger method (keyboard
  shortcut vs. floating launcher) — a bug in *how* `screen` gets set when
  triggered via `cmd+k` from `AppShell.tsx`, not a shape change to the
  store (User Story 5).
- The launcher's position/interaction reliability so it never visually
  collides with another control's primary action (User Story 4) — a
  layout/z-index concern, not a data concern.

## List item display name/status (User Story 10, FR-014)

Workflow and goal list items already carry a `title`/`name` field
(server-populated) and a `status` enum value. This feature adds a
presentation-layer humanization step — title-casing/space-inserting a raw
snake_case name when no explicit display title was set, and mapping status
enum values (e.g. `awaiting_gate`) through a display-label lookup — applied
where these are rendered (`pages/workflows`, `pages/goals`, status chip
components). No change to the underlying stored value; the humanization is
formatting-only and must not be persisted back.
