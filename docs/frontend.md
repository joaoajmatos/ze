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
| `entities` | One business noun: display + read queries | singular noun | `entities/goal` → `boardOrder`, `useGoalsQuery` |
| `features` | One user interaction | verb phrase | `features/export-user-data` |
| `widgets` | Composite screen sections | UI block role | `widgets/goals-board` |
| `pages` | Thin route entry — composes widgets | route segment | `pages/doing` |
| `app` | Bootstrap, router, providers | — | `app/router/routes.tsx` |

</details>

**Import rule:** a slice imports only from layers below it, via public `index.ts` exports. Enforced by `make lint-web` (`@feature-sliced/eslint-config`).

## The shell and the five places

The app has five places: World, Ask, Doing, Mind and Governance. `shared/config/places.ts` lists them in order, maps a path to its place (`placeOf`), and holds the path helpers (`goalsPath`, `workflowsPath`, `goalPath`, `workflowPath`, `askPath`, `settingsDataPath`).

`widgets/app-shell` draws the frame around every place:

- **Top bar:** the dot-matrix brand, the five place tabs, the notification bell and a connection dot.
- **Strip:** the claim legend, today's date and a dot-matrix clock.
- **Left rail:** the Presence module with the orb and an ambience toggle in its head. The place fills the column beside it.
- **Ask bar:** sticky at the bottom of every place, Ask included. A paperclip hands Ze a file through the workspace, and a mic records your voice (see [Voice input](#voice-input)). On Ask the bar sends to the selected thread. On every other place it opens the Ask overlay (see [native-interface.md](native-interface.md#ask-from-any-screen)).
- **Displaced window:** when another window takes the connection, every place shows "Ze is open in another window" with a Use here control. The orb rests, the connection dot says "Open in another window", and the Ask bar is disabled with that reason.
- **Phone width (1023 px and below):** one column, a compact Presence, and a bottom bar with the five places as icons and labels. The Ask bar sits above it.

Tokens, type and every shell class live in `shared/styles/ze.css`. Fonts (Saira, Michroma, JetBrains Mono) are self-hosted under `public/fonts/`. The HUD building blocks (`Module`, `Meter`, `Control`, `CommandChip`, `DotMatrix`, `SectionTabs`, and the orb under `hud/presence/`) live in `shared/ui/hud/`. The palette (Orchid, Ultraviolet, Amethyst) is a user setting in Governance. `main.tsx` applies the stored choice before the first render. [DESIGN.md](../DESIGN.md) is the design source of truth.

### Presence

`entities/presence` holds a pure reducer, `nextPresence(state, event, now)`, and `usePresence(activeThreadId)`. The orb follows only real signals for the thread selected in Ask:

| Orb state | Signal |
|-----------|--------|
| `idle` | Connected, nothing in flight. The idle orb watches the pointer and keyboard focus like a curious pet: it follows, peers, glances at new things, startles on a fast flick, blinks when it switches target, and dozes after a minute. Reduced motion turns the gaze off. |
| `listening` | The Ask bar has focus and text, or the mic is recording. While recording, the orb gathers and brightens with your voice level. |
| `thinking` | A `typing` frame, or the thread is marked thinking, until the first token. Also "transcribing" while a recording uploads. |
| `speaking` | `token` frames for the thread |
| `done` | The `message` frame that closes the turn, for one second |
| `error` | The WebSocket is closed. The phrase reads "Offline". A window another window displaced stays `idle`. |

Replayed messages, other threads and frames with no thread never move the orb. `attention`, `acting` and `assembling` exist in the reducer (`set_world_signal`), but no place sends them yet.

### Ask

Ask is the Assemble canvas. The try chips and the conversations list are portalled into the shell rail under the orb (World does the same with Needs you), so the canvas and the trace take the page. On a phone they follow the conversation. A reply is a sentence plus one module per top-level component, flown out of the orb 80 ms apart (opacity only under reduced motion). Five slices make it work:

- **`entities/conversation`** keeps one state per thread: messages, the turn phase (`idle`, `awaiting`, `thinking`, `speaking`, `paused`, `failed`), streaming text, the last outcome, and an attention flag. A pure reducer (`reduce`) applies the seven conversation frames. The `/ask` page and the overlay read the same store, so they always show the same thread.
- **`features/turn-stream`** mounts `TurnFrameHandler` once in the shell. It feeds the reducer, keeps the sessions rail flags and the orb in step, acknowledges unread replies, and runs the delivery watchdog (120 s of silence, then a history reload, then "Ze did not answer"). A turn paused on a confirmation never fails. `sendTurn` is the one place a message leaves the client. `frame-registry.ts` lists every `useFrame` call site with its reason, and a test fails when one is missing.
- **`widgets/assemble`** draws the `Canvas` (exchanges, modules, pin and dismiss, Resend), places confirmations and Retry, and holds the trace rail and the Ask overlay.
- **`features/trace-state`** keeps partial and final traces. It merges stages and tool rows the server sends and reads no client clock.
- **`@myguyze/ze-ui`** takes a `classNames` map and a `renderHeadline` slot, so chat modules and plugin screens share the HUD look without app CSS in the package.

"Why?" on a reply opens its trace at the section the trace can prove: Routing for a preset reply, Tools (render and show rows marked) otherwise. Message components carry no call index, so it cannot name the exact call.

The trace is a rail of instruments, drawn only from `MessageTrace` and `trace_update`: a Signal path (one tick per stage, placed by the server's start offset, so a reply opened from history shows the same times as a live one; a second run after a confirmation sits after a gap labelled with the wait), Routing (a bar labelled by what produced it), Memory (relevance across, extraction confidence up), Tools (one lane per agent), Judgments (grouped by where the answer was used), Reversal (what a retry undid), and readouts (turn total, active time, tool time, tokens, cost and context fill from the trace's `usage`; "est." marks a price or window the server had to guess). Judgment gauges mark the bar that decided; a surface with no bar reads "uncalibrated". Tool rows are keyed by `call_id`, so a live row and its committed row are one. Missing data reads "not recorded".

### Voice input

The mic in the Ask bar records your voice and puts the text in the bar for you to correct before you send it. `features/voice-input` owns it. The shell wires it to the bar and to Presence, because features never import each other.

- **Record.** Press the mic, or hold `V` while no text field has focus. The orb listens, and the mic shows the elapsed time. Press again, or release `V`, to stop. A hold shorter than 300 ms is dropped. Closing the Ask overlay stops a recording and transcribes it. Changing place does not.
- **Limit.** A recording stops by itself at 115 seconds. The mic counts down from 105 seconds, and the status line says "10 seconds left" once.
- **Transcribe.** The recording goes to `POST /api/v0/voice/transcriptions`. Presence reads "transcribing". The text lands in the bar, focused, with the caret at the end. An empty transcript shows "Ze heard nothing" and sends nothing.
- **Send.** The next send carries `context.voice.transcription_id`, from Ask and from the overlay on every other place. The server compares the sent text with the transcript and records whether you edited it on the trace. The client sends no flag of its own. An unsent message keeps its voice reference when it returns to the bar.
- **Failures.** The status line shows the server's own plain line. It offers Retry (same recording, no new take) when a second try can work, and Record again when the recording is too large, too long or in a format the server refuses. A browser-side problem (permission blocked, no microphone, no recording support) shows its line with Try again. A server that has no voice support (503, or an older server that answers 404) leaves the mic disabled until you reload.
- **Browsers.** Chrome and Edge record WebM, Firefox WebM or Ogg, Safari MP4. All use Opus or AAC at 64 kbit/s, so a full recording is about 1 MB.

### Ambience

The toggle in the Presence head plays a quiet synthesized drone. It is off by default and the browser remembers your choice (`localStorage` key `ze.ambience`). A remembered "on" starts at your first click or key press, because browsers block sound before a gesture. With reduced motion set, a remembered "on" reads off until you press the toggle. The drone goes silent while you record, so it never reaches the transcript.

### Old routes

Old paths redirect to their place and keep params, query and hash. The table is `redirects` in `places.ts`.

| Old path | New path |
|----------|----------|
| `/loops` | `/` |
| `/news` | `/ask` |
| `/priority`, `/reminders`, `/world` | `/` |
| `/goals` | `/doing#goals` |
| `/goals/:id` | `/doing/goals/:id` |
| `/workflows` | `/doing#workflows` |
| `/workflows/:id` | `/doing/workflows/:id` |
| `/skills` | `/doing#skills` |
| `/doing/goals`, `/doing/workflows`, `/doing/skills` | `/doing` with the matching hash |
| `/brain-memory`, `/brain-graph`, `/mind/graph`, `/procedures`, `/doing/procedures`, `/contacts` | `/mind` |
| `/costs` | `/governance` |
| `/data`, `/governance/data` | `/governance#data` |
| `/settings`, `/governance/settings` | `/governance#connections` |
| `/workspace`, `/doing/workspace` | `/governance#files` |

The prototype route is gone and has no redirect: an old prototype link shows the not-found page.

A redirect entry can carry a `hint`. `RedirectTo` then replaces the incoming hash with the hint and keeps the query. An entry can also carry a `hintMap`, which lets an old hash win (`#your-data` becomes `#data`).

### World

World is the home at `/` (`pages/world`, phase 186). It shows what Ze holds, what it does about it, and what it needs from you. Every value comes from an API field. A value the API lacks is absent: a goal, a person or a reminder has no confidence, so it never gets a made-up one, and the decay trail draws only from a recorded `confidence_prior`.

`useWorld` (`pages/world/model`) joins the queries the page needs: the priority snapshot, loops (open and closed), goals, workflows with their latest runs, held writes, reminders, hypotheses, notifications and job runs since the last visit, the attention budget, and the confirmations pending in chat. It hands each widget its data by props. A query that fails sets the error state of its own module only. The page prints "N sources down" when the priority snapshot names failed sources.

| Module | Widget | Shows |
|--------|--------|-------|
| The Field | `widgets/world-field` | Time left across, how sure up. Marks by claim kind, a coral Slipped band, a NOW line, a dotted trail from the prior confidence, a readout with "Why this order", and drag or keyboard reorder and pin. On a phone it is a ranked list by band. |
| Needs you | `widgets/needs-you` | Held writes, goal checkpoints (Proceed, Stop, Redirect), suspected loops and confirmations waiting in a chat, each with its action. Cream, never coral. |
| Doing now | `widgets/doing-now` | Active goals with progress, the next run, runs this week, a running run and a failed run's summary. |
| Loops · confidence | `widgets/loops-rail` | Open loops with a sparkline, a readout and Close and Drop. |
| Touched · 7 d | `widgets/touched` | Loops, goals and workflows changed in the last seven days. |
| While you were away | `widgets/away` | Notifications and job runs since your last visit, and the push budget. |

- **Slipped** wins over the deadline: a drifting loop, a stuck goal, an overdue reminder and a loop whose linked reminder is overdue all sit in the Slipped band. The orb holds `attention` while anything slipped or a run failed, and the leader line ends on the most overdue mark (desktop, motion allowed).
- **Last visit.** `localStorage` key `ze.world.lastSeenAt` holds the last time World was in front of you. "While you were away" counts from the start of the visit: a hide of five minutes or more starts a new one.
- **Gates** have no REST route. `features/answer-gate` sends `goal:approve|stop|redirect:<gate_id>` as an `action` frame on the session thread and waits for the goals data to drop the gate, or for an `error` frame within 15 seconds. Another payload family can use the same sender.
- **Held writes** use one `HeldWriteCard` (`features/respond-to-confirmation`). A write with an editable field opens the full confirmation card.
- **Links.** `/?focus=<kind>:<id>` selects one item (`loop`, `goal`, `hypothesis`, `reminder`, `held_write`). `focusHref` and `notificationHref` in `shared/lib` build them.
- **Refresh.** A `message` frame invalidates the World queries. A `notification` frame also invalidates the budget and the key of its target. A `refresh` frame for `goals` invalidates goals, the priority snapshot and workflow executions.
- **Screen context.** The page publishes the focused module, the selected mark and the visible rows. The selected mark's readout, loop rows, Needs-you rows and Away rows offer "Chat about this". A module has no record of its own, so it carries no chip.

The notification bell no longer lists held writes. A `held_write` notification opens World with the item selected.

### Doing

Doing answers what runs without you, what it did, and what it waits for (`pages/doing`, phase 188). It has three routes:

| Route | Page | Content |
|-------|------|---------|
| `/doing` | `pages/doing` | The index: five anchored modules |
| `/doing/goals/:goalId` | `pages/doing-goal` | One goal |
| `/doing/workflows/:workflowId` | `pages/doing-workflow` | One workflow |

The index modules, in phone order:

| Module | Widget | Shows |
|--------|--------|-------|
| Needs you | `widgets/doing-needs-you` | Planned goals to start, open gates and held writes. Cream. |
| Goals | `widgets/goals-board` | One row per goal, from the goal list. Stuck goals come first, in coral. Finished goals sit under "Finished (n)". |
| Workflows | `widgets/workflows-board` | Schedule in words, next run and last result. Failed rows are coral. Run now starts a workflow. |
| Runs | `widgets/runs` | Recent workspace runs, the live output of a running one, and Cancel. |
| Skills | `widgets/skills-queue` | Skills waiting for review first, then the on and off list. |

Rules that apply across Doing:

- **Gates and held writes.** Gate actions go through `features/answer-gate` (the same sender World uses). Held writes use `HeldWriteCard` (`features/respond-to-confirmation`).
- **Coral is for unattended failures.** A run is coral only when an unattended run failed or timed out. A cancelled or refused run is never coral. A failed workflow execution is coral.
- **Plain words.** Statuses, origins and summaries show as plain words. Command output appears verbatim in a monospace box.
- **Runs stay fresh.** While a run is in progress, the Runs list and the workspace status refresh every 5 seconds. A run without an id or a start time shows no Cancel button.
- **Ask about it.** Each goal, workflow, run, skill, gate and held write offers "Chat about this".

On a phone the modules stack in the order Needs you, Goals, Workflows, Runs, Skills. The detail pages use one column, and the gate comes first.

### Mind

Mind shows what Ze believes. `/mind` holds four modules: Beliefs, People, Find an entity and Procedures. `/mind/:entityId` shows one entity.

- **Beliefs** (`widgets/beliefs-feed`): each fact is a `BeliefRow` with a glyph for its claim kind, a plain sentence, confidence, source and age. Keep, Edit and Drop review it in place. An "As of" date shows the feed as it stood then; kind and confidence stay current.
- **People** (`widgets/people`): the Contacts page (`getContactsPage`), rendered through `ConnectedPrimitiveTree`. The entity page also hosts the `mind.entity` plugin slot under the neighbourhood.
- **Find an entity** (`widgets/entity-search`): a server search by name or alias (`searchEntities`). There is no whole-graph view.
- **Entity page**: a small radial field of up to 20 neighbours (`widgets/entity-neighbourhood`), an activity chart, the entity's facts, and an "I suspect…" list of hypotheses with Useful, Not relevant and Mute.
- **Procedures** (`widgets/procedures`): candidates to review first, then the library.

The claim posture table (glyph, chip word, plain words per state) lives in `shared/lib/claim-posture.ts`. Beliefs publish their visible and selected rows to screen context, the entity page publishes its entity as the subject, and rows carry "Chat about this".

Every place has its own page: World, Ask, Doing, Mind and Governance. `/doing` holds the Doing modules and its two detail pages. Plugins add no pages (see Plugin modules under Shared abstractions).


## Governance

`/governance` answers "is Ze behaving?" on one page (`pages/governance`, phase 190). Each module is a widget, labelled by the question it answers:

| Module | Widget | Shows |
|--------|--------|-------|
| Am I spending normally? | `widgets/spend` | Last 7 days' daily average against the 30-day average, the anomaly count, per-flow totals and a `SeriesSpark` over 30 days |
| What can interrupt me? | `widgets/attention` | Pushes used of the daily maximum, the next slot, held pushes, recent push outcomes and the quiet-hours form |
| What does Ze hold, and can I take it? | `widgets/data` | Data domains in plain words, export, import and delete-all behind a typed confirmation |
| How do I reach Ze? | `widgets/connections` | Server URL and key with a test, plugin settings, the palette and "Forget this server" |
| What is in Ze's workspace? | `widgets/files` | A read-only file tree and the workspace status |

On a phone the modules stack as Attention, Spend, Connections, Data, Files. The page publishes the focused module for screen context. It keeps the last focused module until another takes focus, and a click on plain text does not change it.

Spend averages divide by the days since the first spend inside the 30-day window, up to 30, so a new install does not read as a spike. Today's partial day counts as a whole day. The connection test calls the public `/version` route, then one authenticated route, so it can tell "reachable" from "key rejected". `SeriesSpark` (`shared/ui/hud`) draws a series; `Spark` draws a two-point change.

## Adding a new screen

Example (hypothetical — the app has no finance screen): a finance overview at `/finance`. Plugin screens normally arrive through the UI manifest. A core screen belongs to one of the five places.

1. **`entities/transaction/`** — `TransactionRow`, `useTransactionsQuery` wrapping `@myguyze/ze-client`
2. **`widgets/finance-overview/`** — composes the entity list
3. **`pages/finance/`** — `FinancePage` that renders `<FinanceOverview />`
4. **`app/router/routes.tsx`** — add the route under its place
5. **`shared/config/places.ts`** — add a path helper if other screens link to it

To ask Ze about a screen, call `askAbout({ text, context })` from `features/ask-bar`. To tell Ze what the page shows, call `useScreenPublisher` from `entities/screen-context` with the page's subject, selection and visible refs. The store builds the snapshot that every send attaches. To let the user chat about a record, pass `onChatAbout` to `Module`, or place a `ChatAboutChip` on a component without a frame. A widget calls `useChatAbout` and passes the callback down by props, because features and entities never import `features/ask-bar` from each other.

Each slice exposes a public API through `index.ts`. Internal `ui/`, `api/`, `model/` folders are private to the slice.

Skill review lives on Doing (`widgets/skills-queue`). The workspace file map lives in Governance. See [skills.md](skills.md) and [workspace.md](workspace.md).

## Extending an existing domain

Example: goal detail view at `/doing/goals/:goalId`.

1. Add `useGoalDetailQuery(id)` in `entities/goal/api/`
2. Add a widget such as `widgets/milestone-field/` for each module of the view
3. Add `pages/doing-goal/` to compose the widgets
4. Register the nested route in `app/router/routes.tsx` (no nav entry needed if reached from a list)

Do not put route-specific logic in entities — entities are reusable across screens.

## Primitive actions and the gallery

A server-built tree puts typed actions on its buttons. `features/primitive-tree/api/usePrimitiveActions.ts` maps each kind: `ask` sends a turn on the selected thread, `navigate` goes to a place route (anything else shows a notice), `compose` sends a preset turn, and `tool` sends a `ui_action` frame and shows the `ui_action_result` line as a notice. A second press while one is pending is ignored. Stored trees without a version render as legacy.

In development, `/dev/primitives` renders every fixture from `packages/ze-ui/fixtures/`. A production build does not include the route.

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
- **`features/retry-reply/`** — `RetryButton` and `useRetryReply`: send the `retry` WebSocket frame and refresh feedback and traces when the store changes. A disabled Retry shows its reason as visible text.

`widgets/assemble` mounts the thumbs on the latest reply and in the trace head, and `RetryControl` mounts `RetryButton` for the latest reply only. `useRetryReply` sends the `retry` frame; the conversation store applies `message_superseded`, `message_rollback` and the retry `error` codes, and `RetryControl` shows the outcome in words. See [native-interface.md](native-interface.md#reply-feedback-and-retry).

## Quiet hours and the notification bell

`widgets/attention/` renders the quiet-hours form in Governance, under "What can interrupt me?". It reads `entities/quiet-hours/` (`useQuietHoursQuery`, `useUpdateQuietHoursMutation` over the generated `getQuietHours` / `updateQuietHours`) and the nudge cap and held count from `entities/notification/` (`useAttentionBudgetQuery` over `getAttentionBudget`), prefills the timezone from `Intl.DateTimeFormat().resolvedOptions().timeZone` when the server value is null, and places each 422 field error from `detail[].loc` under the matching input.

`widgets/app-shell/ui/NotificationBell.tsx` labels a held item "Held for quiet hours" and a suppressed one "Not pushed: daily limit", and shows no label for any other delivery.

## Shared abstractions

- **`shared/ui/layout/`** — screen states: `EmptyState`, `ErrorState`, `ListSkeleton`, `NoticeBanner`, `ZeErrorBoundary`, `RedirectHintTarget`
- **`shared/lib/page-header.tsx`** — `PageHeader`
- **`shared/lib/query-keys.ts`** — TanStack Query key factory; extend when adding REST resources
- **`shared/config/places.ts`** — the five places, the old-route redirect table and the path helpers; `app/router/routes.tsx` builds the routes from it
- **Plugin modules** — a plugin adds no page. It contributes modules, Ask presets and settings sections through `GET /api/v0/ui/manifest` (`entities/ui-manifest`). `widgets/plugin-module` (`PluginModuleSlot`) fills a slot a place offers: `mind.entity` on the entity page, `doing.run` on a workflow run, `governance.connections` in Connections. Each module loads its tree from `GET /api/v0/ui/modules/{module_id}` (`getUiModule`) on place load, on a `refresh` frame with `screen: "module:<id>"`, and every 60 seconds while visible. A failed module shows one plain line and the rest of the place is unaffected; a module that does not apply shows nothing. Plugin presets appear after the core chips in Ask's Try chips, at most two. `/news` redirects to `/ask`, and an old top-level plugin path shows not found.

## API and types

- REST and WebSocket types: `@myguyze/ze-client` (generated — never raw URL strings)
- Server-driven UI: `@myguyze/ze-ui`, `@myguyze/ze-ui/react`
- Entity query hooks wrap `@myguyze/ze-client` + `shared/lib/query-keys`

## Shared UI

`shared/ui/` is the single UI slice:

| Subfolder | Contents |
|-----------|----------|
| `primitives/` | Generic building blocks (shadcn-style `Button`, `Input`, `Slider`, plus `SearchBar`, `FilterChips`, `ViewToggle`, `SortSelect`) |
| `layout/` | Screen states (`EmptyState`, `ErrorState`, `ListSkeleton`, `NoticeBanner`, error boundary) |
| `hud/` | The HUD building blocks (`Module`, `Meter`, `Control`, `DotMatrix`, `SeriesSpark`, the orb) |

Import from the public API: `import { Button, EmptyState } from "@/shared/ui"`.

## Configuration

`shared/config/app-config.ts` stores the server URL and API key in `localStorage`. Set them during onboarding or in Governance › Connections. No `VITE_*` env vars.

## Commands

```bash
make web          # dev server :5173
make web-build    # production build
make test-web     # vitest
make lint-web     # ESLint (FSD boundaries)
```

## Testing

Colocated `*.test.tsx` next to the module. Run from repo root: `make test-web`.
