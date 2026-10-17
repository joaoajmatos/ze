# ze-web frontend architecture

The React web client (`apps/ze-web`) uses [Feature-Sliced Design](https://feature-sliced.design/) (FSD). Spec: [specs/phases/082-ze-web-fsd/spec.md](../specs/phases/082-ze-web-fsd/spec.md).

## Layers

![Layer stack showing ze-web's six Feature-Sliced Design layers in strict one-way import order, from shared at the foundation up to app at the top](diagrams/docs/frontend-layers.svg)

<sub>[Interactive version](diagrams/docs/frontend-layers.html)</sub>

<details>
<summary>Table</summary>

| Layer | Purpose | Name by | Example |
|-------|---------|---------|---------|
| `shared` | UI kit, utilities, API wiring — no business logic | — | `shared/ui` (primitives + layout), `shared/api/ws-client` |
| `entities` | One business noun: display + read queries | singular noun | `entities/goal` → `GoalCard`, `useGoalsQuery` |
| `features` | One user interaction | verb phrase | `features/export-user-data` |
| `widgets` | Composite screen sections | UI block role | `widgets/goals-overview` |
| `pages` | Thin route entry — composes widgets | route segment | `pages/goals` |
| `app` | Bootstrap, router, providers | — | `app/router/routes.tsx` |

</details>

**Import rule:** a slice imports only from layers below it, via public `index.ts` exports. Enforced by `make lint-web` (`@feature-sliced/eslint-config`).

## The shell and the five places

The app has five places: World, Ask, Doing, Mind and Governance. `shared/config/places.ts` lists them in order, maps a path to its place (`placeOf`), and holds the path helpers (`goalPath`, `workflowPath`, `askPath`, `settingsDataPath`).

`widgets/app-shell` draws the frame around every place:

- **Top bar:** the dot-matrix brand, the five place tabs, the notification bell and a connection dot.
- **Strip:** the claim legend, today's date and a dot-matrix clock.
- **Left rail:** the Presence module with the orb. The place fills the column beside it.
- **Ask bar:** sticky at the bottom of every place except Ask. Typing there opens the Ask overlay (see [native-interface.md](native-interface.md#ask-from-any-screen)).
- **Phone width (1023 px and below):** one column, a compact Presence, and a bottom bar with the five places as icons and labels. The Ask bar sits above it.

Tokens, type and every shell class live in `shared/styles/ze.css`. Fonts (Saira, Michroma, JetBrains Mono) are self-hosted under `public/fonts/`. The HUD building blocks (`Module`, `Meter`, `Control`, `CommandChip`, `DotMatrix`, `SectionTabs`, and the orb under `hud/presence/`) live in `shared/ui/hud/`. The palette (Orchid, Ultraviolet, Amethyst) is a user setting in Governance. `main.tsx` applies the stored choice before the first render. [DESIGN.md](../DESIGN.md) is the design source of truth.

### Presence

`entities/presence` holds a pure reducer, `nextPresence(state, event, now)`, and `usePresence(activeThreadId)`. The orb follows only real signals for the thread selected in Ask:

| Orb state | Signal |
|-----------|--------|
| `idle` | Connected, nothing in flight. The idle orb watches the pointer and keyboard focus like a curious pet: it follows, peers, glances at new things, startles on a fast flick, blinks when it switches target, and dozes after a minute. Reduced motion turns the gaze off. |
| `listening` | The Ask bar has focus and text |
| `thinking` | A `typing` frame, or the thread is marked thinking, until the first token |
| `speaking` | `token` frames for the thread |
| `done` | The `message` frame that closes the turn, for one second |
| `error` | The WebSocket is closed. The phrase reads "Offline". |

Replayed messages, other threads and frames with no thread never move the orb. `attention`, `acting` and `assembling` exist in the reducer (`set_world_signal`), but no place sends them yet.

### Old routes and interim places

Old paths redirect to their place and keep params, query and hash. The table is `redirects` in `places.ts`.

| Old path | New path |
|----------|----------|
| `/loops` | `/` |
| `/priority` | `/world/priority` |
| `/goals`, `/goals/:id` | `/doing/goals`, `/doing/goals/:id` |
| `/workflows`, `/workflows/:id` | `/doing/workflows`, `/doing/workflows/:id` |
| `/skills`, `/procedures`, `/workspace` | `/doing/skills`, `/doing/procedures`, `/doing/workspace` |
| `/brain-memory`, `/brain-graph` | `/mind`, `/mind/graph` |
| `/costs`, `/data`, `/settings` | `/governance`, `/governance/data`, `/governance/settings` |

Until each place has its own design, it hosts the old pages as sections behind a row of tabs. One file per place holds the sections: `pages/world/ui/WorldInterim.tsx` (phase 186 replaces it), `pages/ask/ui/AskInterim.tsx` (187), `pages/doing/ui/DoingInterim.tsx` (188), `pages/mind/ui/MindInterim.tsx` (189) and `pages/governance/ui/GovernanceInterim.tsx` (190). A page cannot import another page, so `app/router/routes.tsx` passes each interim file the loaders for its sections. Plugin pages still use `/:pluginPath` (phase 191 places them).

## Adding a new screen

Example: finance overview at `/finance`. Plugin screens normally arrive through the UI manifest. A core screen belongs to one of the five places.

1. **`entities/transaction/`** — `TransactionRow`, `useTransactionsQuery` wrapping `@myguyze/ze-client`
2. **`widgets/finance-overview/`** — composes the entity list
3. **`pages/finance/`** — `FinancePage` that renders `<FinanceOverview />`
4. **`app/router/routes.tsx`** — add the route under its place, or add a section to that place's interim file
5. **`shared/config/places.ts`** — add a path helper if other screens link to it

To ask Ze about a screen, call `askAbout({ text, context })` from `features/ask-bar`.

Each slice exposes a public API through `index.ts`. Internal `ui/`, `api/`, `model/` folders are private to the slice.

Core-owned screens include `/skills` (`pages/skills` + `widgets/skill-management`) and `/workspace` (`pages/workspace`). See [skills.md](skills.md) and [workspace.md](workspace.md).

## Extending an existing domain

Example: goal detail view at `/doing/goals/:goalId`.

1. Add `entities/goal/ui/GoalDetail.tsx` and optionally `useGoalQuery(id)`
2. Add `widgets/goal-detail/` composing the entity + any action features
3. Add `pages/goal-detail/` thin page
4. Register the nested route in `app/router/routes.tsx` (no nav entry needed if reached from a list)

Do not put route-specific logic in entities — entities are reusable across screens.

## Adding a user action

Example: confirm recurring expense.

1. Create `features/confirm-recurring/` with hook or handler in `api/`
2. Use it from the widget that owns the UI (e.g. `widgets/finance-overview`)
3. Export through `features/confirm-recurring/index.ts`

Features import from `entities` and `shared` only — never from `widgets` or `pages`.

## Reply feedback and Retry

Three slices serve the thumbs up, thumbs down, and Retry controls on assistant replies:

- **`entities/message-feedback/`** — `useMessageFeedbackQuery` (one batch call for the visible assistant ids) and `useSetMessageFeedbackMutation` (optimistic, reverts on error, sends a client UUID idempotency key).
- **`features/reply-feedback/`** — `ReplyActions`: the thumb buttons with `aria-pressed` and accessible names.
- **`features/retry-reply/`** — `RetryButton` and `useRetryReply`: send the `retry` WebSocket frame and handle `message_superseded` and the `error` codes. A disabled Retry shows its reason as visible text.

`entities/message` cannot import a feature. `MessageBubble` therefore takes an `actions` slot, and `widgets/chat-workspace` mounts `ReplyActions` and `RetryButton` into it for stored assistant messages only. `widgets/trace-panel/ui/FeedbackSection.tsx` shows the rating history and the retry links. See [native-interface.md](native-interface.md#reply-feedback-and-retry).

## Quiet hours and the notification bell

`widgets/quiet-hours-settings/` renders the quiet-hours form under Settings › Notifications. It reads `entities/quiet-hours/` (`useQuietHoursQuery`, `useUpdateQuietHoursMutation` over the generated `getQuietHours` / `updateQuietHours`), prefills the timezone from `Intl.DateTimeFormat().resolvedOptions().timeZone` when the server value is null, and places each 422 field error from `detail[].loc` under the matching input.

`widgets/notification-bell/ui/NotificationBell.tsx` labels a held item "Held for quiet hours" and a suppressed one "Not pushed: daily limit", and shows no label for any other delivery.

## Shared abstractions

- **`shared/ui/layout/ListPage`** — standard list screen shell (header, skeleton, error, empty, children)
- **`shared/lib/query-keys.ts`** — TanStack Query key factory; extend when adding REST resources
- **`shared/config/places.ts`** — the five places, the old-route redirect table and the path helpers; `app/router/routes.tsx` builds the routes from it
- **Plugin routes** — plugins add nav items, settings sections, and pages at runtime through `GET /api/v0/ui/manifest` (`entities/ui-manifest`, rendered by `pages/plugin-page`)

## API and types

- REST and WebSocket types: `@myguyze/ze-client` (generated — never raw URL strings)
- Server-driven UI: `@myguyze/ze-ui`, `@myguyze/ze-ui/react`
- Entity query hooks wrap `@myguyze/ze-client` + `shared/lib/queryKeys`

## Shared UI

`shared/ui/` is the single UI slice:

| Subfolder | Contents |
|-----------|----------|
| `primitives/` | Generic building blocks (shadcn-style `Button`, `Input`, `Sheet`) |
| `layout/` | Ze screen patterns (`ListPage`, `PageHeader`, `EmptyState`, …) |

Import from the public API: `import { Button, ListPage } from "@/shared/ui"`.

## Configuration

`shared/config/app-config.ts` stores the server URL and API key in `localStorage`. Set them during onboarding or in Settings. No `VITE_*` env vars.

## Commands

```bash
make web          # dev server :5173
make web-build    # production build
make test-web     # vitest
make lint-web     # ESLint (FSD boundaries)
```

## Testing

Colocated `*.test.tsx` next to the module. Run from repo root: `make test-web`.
