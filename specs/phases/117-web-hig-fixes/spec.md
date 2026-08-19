# Feature Specification: Web UI HIG Audit Fixes

**Feature Branch**: `117-web-hig-fixes`

**Created**: 2026-08-19

**Status**: Draft

**Input**: User description: "Fix the UI/UX and correctness issues found in today's Apple HIG design audit of ze-web, covering the app shell/navigation, Settings page, the contextual chat overlay, and the chat send/receive loop."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Chat always resolves to a visible outcome (Priority: P1)

A person sends a message to Ze. The assistant finishes processing and stores a
response, but right now the composer can stay locked on a "thinking" state and
the message never appears on screen — the only way to see the reply is to
reload the whole app. After the fix, every sent message ends in a state the
person can see: either the reply appears, or a clear failure/retry state
appears, within a bounded time.

**Why this priority**: Chat is the core, most-used surface of the app. A
message that silently vanishes into an infinite loading state makes the
product feel broken and erodes trust in every other feature.

**Independent Test**: Send a message in a fresh chat session and leave the
tab alone (no manual reload). Confirm that within a bounded wait the reply
renders, or a retry/error affordance appears — never an indefinitely
spinning indicator with a locked composer.

**Acceptance Scenarios**:

1. **Given** a person has sent a message and Ze has finished generating a
   reply, **When** the reply is ready, **Then** it appears in the
   conversation and the composer unlocks, without the person needing to
   reload the page.
2. **Given** a person has sent a message and the reply cannot be delivered
   to the open session for any reason, **When** a bounded wait time elapses,
   **Then** the person sees a clear "something went wrong, retry" state
   instead of an indefinite "thinking" indicator.
3. **Given** a reply was missed by the live connection, **When** the person
   reopens or refreshes the conversation, **Then** the reply is present
   (no data loss — only the live delivery needs fixing).

---

### User Story 2 - Every destination stays reachable at any window size (Priority: P1)

At medium window widths (tablet-sized, or a desktop window resized
narrower), the navigation sidebar collapses to icons only, and several
whole sections (Goals, Workflows, Memory, Graph, Usage, Data, Skills,
Workspace, Contacts, News, Reminders) become completely unreachable — there
is no label, no expand control, and no other way to get to them at that
width. After the fix, a person can reach every navigation destination at
every supported window size.

**Why this priority**: A navigation dead-end silently removes access to
most of the app for anyone working at a common window size. This isn't a
degraded experience, it's a missing one.

**Independent Test**: Resize the app window to a mid-range width (roughly
tablet-sized) and confirm every navigation destination reachable at full
desktop width is still reachable — via icon click, tooltip-assisted click,
flyout, or any other discoverable path — with zero destinations that
require widening the window first.

**Acceptance Scenarios**:

1. **Given** the window is at a medium width where the sidebar shows icons
   only, **When** a person interacts with a grouped section's icon,
   **Then** they can reach every item in that group (not just see the
   group icon).
2. **Given** the window is at a medium width, **When** a person looks at
   the collapsed sidebar, **Then** every icon communicates what it leads to
   (e.g. on hover or focus) before they click it.
3. **Given** a person is already on a page only reachable through a
   collapsed group, **When** the window is at medium width, **Then** the
   sidebar still indicates which section is active.

---

### User Story 3 - The contextual assistant panel can always be closed (Priority: P1)

Opening the floating contextual chat panel (via the launcher button or a
keyboard shortcut) currently offers no visible close control, and the
Escape key does not dismiss it. After the fix, a person always has an
obvious, discoverable way to close the panel.

**Why this priority**: A panel that can't be dismissed traps the person's
attention and blocks interaction with the rest of the app — this is a hard
usability failure, not a cosmetic one.

**Independent Test**: Open the contextual panel by any means, then close it
using only an on-screen control, and separately using the Escape key.
Confirm both close the panel from any page.

**Acceptance Scenarios**:

1. **Given** the contextual panel is open, **When** a person looks at it,
   **Then** they can see an obvious close control without hovering or
   guessing.
2. **Given** the contextual panel is open, **When** a person presses
   Escape, **Then** the panel closes.
3. **Given** the panel was opened by the floating launcher, **When** it is
   later opened again via the keyboard shortcut, **Then** the same close
   behaviors work identically both times.

---

### User Story 4 - The contextual panel never blocks a page's primary controls (Priority: P2)

On small (mobile-width) screens, the floating launcher for the contextual
panel currently sits on top of the last visible row's primary action button
(for example, covering "Run now" on a workflow row). After the fix, the
launcher never visually or interactively blocks another control.

**Why this priority**: This is a direct interaction collision on the
smallest, most space-constrained layout — a specific, frequently-reachable
action becomes unusable without scrolling around the obstruction.

**Independent Test**: On a small screen, scroll a list (Goals, Workflows,
or similar) to its end and confirm the last row's primary action is fully
visible and clickable without the floating launcher overlapping it.

**Acceptance Scenarios**:

1. **Given** a list of items is scrolled to its last visible row on a small
   screen, **When** the floating launcher is present, **Then** it does not
   overlap that row's primary action control.
2. **Given** the floating launcher is visible, **When** a person scrolls
   any page, **Then** the launcher never permanently obscures interactive
   content beneath it.

---

### User Story 5 - The contextual panel always names the right page (Priority: P2)

The contextual panel labels itself after the page it was opened from (e.g.
"Ze · Workflows") when triggered by the floating launcher, but shows a
stale, incorrect label (e.g. "Ze · Chat") when triggered by the keyboard
shortcut from a different page. After the fix, the panel's label always
matches the page it was actually opened from, regardless of how it was
triggered.

**Why this priority**: A mislabeled panel misrepresents what the person is
about to ask about, which can lead to confusing or wrongly-scoped
responses — a correctness issue, but one with a workaround (people can
still use the panel).

**Independent Test**: From several different pages, open the panel once
via the floating launcher and once via the keyboard shortcut. Confirm the
label matches the current page every time, for both trigger methods.

**Acceptance Scenarios**:

1. **Given** a person is on any page other than Chat, **When** they open
   the contextual panel with the keyboard shortcut, **Then** the panel's
   label names that page, not "Chat".
2. **Given** a person navigates to a different page while the panel is
   closed, **When** they next open the panel, **Then** the label reflects
   the page they are currently on.

---

### User Story 6 - The Settings page uses the space it's given (Priority: P2)

On a wide window (a typical laptop or desktop display), the Settings page
currently renders as a narrow, fixed-width column pinned to the left edge,
leaving most of the window empty. After the fix, Settings makes reasonable
use of the available width instead of looking unfinished or broken on a
wide display.

**Why this priority**: This doesn't block any task, but it's a visible
polish gap on a page every person visits, and it stands out badly next to
other pages (like Data) that already adapt well to window width.

**Independent Test**: Open Settings at a typical laptop width and again at
a very wide desktop width. Confirm the layout expands to use the space
sensibly at both sizes rather than staying pinned to a narrow column.

**Acceptance Scenarios**:

1. **Given** the window is wide, **When** a person opens Settings,
   **Then** the content is not confined to a narrow strip with large
   amounts of unused space beside it.
2. **Given** the window is resized narrower, **When** the layout adjusts,
   **Then** the transition remains legible and doesn't break at any width
   in between.

---

### User Story 7 - Icon-only navigation controls are usable with assistive technology (Priority: P3)

When the sidebar shows icons without visible text labels (at medium window
widths), those icons currently have no accessible name for screen readers
or other assistive technology. After the fix, every icon-only control
announces what it does regardless of whether its text label is visually
shown.

**Why this priority**: This affects a specific but real group of people
(screen reader and voice-control users) and is a straightforward,
self-contained accessibility fix.

**Independent Test**: Using a screen reader (or an accessibility inspector)
at a window width where the sidebar shows icons only, confirm every
navigation control announces a meaningful name.

**Acceptance Scenarios**:

1. **Given** the sidebar shows icons only, **When** an assistive technology
   user navigates to a nav control, **Then** it announces the destination's
   name, not just "button" or "link".

---

### User Story 8 - Mobile navigation stays easy to scan as more sections are added (Priority: P3)

The bottom navigation bar on small screens already fits more destinations
than the core app defines, once additional sections from installed
add-ons are included — currently 8 items, with no room to add more without
becoming even more cramped. After the fix, the mobile navigation stays
comfortable to scan and tap as the set of available sections grows.

**Why this priority**: Not currently broken, but at risk of degrading
further as more sections get added — worth addressing proactively rather
than waiting for it to become unusable.

**Independent Test**: With the full current set of sections enabled on a
small screen, confirm the navigation bar stays comfortably tappable and
legible, with a clear place for further items to go without shrinking
existing ones.

**Acceptance Scenarios**:

1. **Given** more navigation destinations are available than comfortably
   fit in the bottom bar, **When** a person views it on a small screen,
   **Then** the most-used destinations remain easy to tap and the rest are
   reachable through a clear "more" pathway rather than all being squeezed
   in at reduced size.

---

### User Story 9 - People can react to and trust assistant responses (Priority: P3)

Right now, an assistant reply offers no way to give quick feedback (good or
bad) or ask for another attempt, and nothing in the chat reminds people
that responses are AI-generated and may be wrong. After the fix, each
response offers a lightweight way to react or retry, and the chat surface
sets a clear, unobtrusive expectation that responses can contain mistakes.

**Why this priority**: Neither gap blocks a task, but both affect whether
people trust and get better results from the assistant over time —
appropriate to address once the higher-severity breakages are fixed.

**Independent Test**: Open a conversation with at least one assistant
reply and confirm a feedback/retry option is available on it, and confirm
a visible, unobtrusive reminder about AI-generated content is present
somewhere in the chat surface.

**Acceptance Scenarios**:

1. **Given** an assistant reply is visible, **When** a person hovers or
   focuses it, **Then** they can give positive or negative feedback, or
   ask for the response to be retried.
2. **Given** a person is using the chat surface, **When** they look at the
   composer area or a new conversation's empty state, **Then** they see a
   brief, unobtrusive note that responses are AI-generated and may contain
   errors.

---

### User Story 10 - Small interface polish across navigation and content (Priority: P4)

A handful of minor rough edges: mobile navigation labels render smaller
than comfortably readable, a back-navigation control has a cramped tap
target, and some list items (workflow names, status labels) display raw
internal identifiers instead of human-readable text. After the fix, these
are cleaned up.

**Why this priority**: Individually minor and non-blocking; bundled
together as low-effort polish to pick up alongside the higher-priority
fixes in the same areas of the app.

**Independent Test**: Inspect mobile nav label legibility, tap comfortably
on the back-navigation control, and browse a list containing
seed/auto-generated items to confirm names and statuses read as
human-friendly text rather than raw internal identifiers.

**Acceptance Scenarios**:

1. **Given** a person is on a small screen, **When** they read the bottom
   navigation labels, **Then** the text is comfortably legible at a
   standard reading distance.
2. **Given** a person is viewing a detail page reached via breadcrumb,
   **When** they tap/click the "back" control, **Then** it responds
   reliably without requiring a highly precise tap.
3. **Given** a workflow or goal was created without an explicit
   human-readable name, **When** it displays in a list, **Then** its title
   and status are shown in readable form rather than as a raw internal
   identifier.

---

### User Story 11 - A visual identity that reads as Ze's own, not a template (Priority: P3)

The app today reads as generic: a flat black background with one accent
color and a single unpaired body typeface is one of the most common
default looks in AI-assisted products, and nothing in the interface
reflects what actually makes Ze distinctive. Separately from the audit's
correctness/accessibility findings, this story captures a deliberate
visual direction — "Open Sky" — that builds on a motif the app already has
(a faint drift of stars behind the chat empty state) rather than
discarding it, and applies it consistently: warmer, hue-tinted neutrals
instead of flat greyscale, a real display typeface reserved for the
wordmark and headings, a dedicated data/mono face for timestamps and
technical labels, and one signature motion moment (a single pulsing point
replacing the generic three-dot "typing" indicator) that echoes the star
motif instead of being a generic spinner. The existing accent color, pill
button shapes, and uppercase button-label convention are kept unchanged —
this is a retint and a typographic decision, not a rebrand.

**Why this priority**: Doesn't block any task and isn't a correctness or
accessibility defect, so it sits behind the P1/P2 fixes — but it's cheap
to apply at the token level (most of the interface inherits color and
type from a small number of shared design tokens) and meaningfully changes
how considered the app feels, which matters for a product meant to feel
like a personal, trusted assistant rather than an interchangeable
dashboard.

**Independent Test**: Compare the chat empty state, a page title in the
top bar, and the "thinking" indicator before and after — confirm the
background and text neutrals read as intentionally tinted rather than
flat grey/black, confirm the wordmark and page titles render in the
display typeface, and confirm the typing indicator is the single pulsing
point rather than three static dots.

**Acceptance Scenarios**:

1. **Given** a person opens the app, **When** they land on the chat empty
   state, **Then** the background and neutral text colors read as part of
   one considered palette (not flat black/white/grey), and the "Ze"
   wordmark renders in the chosen display typeface.
2. **Given** Ze is generating a response, **When** the person watches the
   indicator, **Then** they see the single pulsing signature moment, not a
   generic three-dot ellipsis.
3. **Given** a person looks at any page title, section heading, or
   timestamp/status value, **Then** headings use the display typeface,
   body copy stays on the existing body typeface, and technical/tabular
   values (timestamps, schedules, raw IDs) use the dedicated data
   typeface — never a mix that looks accidental.
4. **Given** the existing accent color, pill radii, and uppercase button
   labels, **When** this direction is applied, **Then** none of those are
   changed — only neutrals, typography, and the one signature motion
   moment.

---

### Edge Cases

- What happens if the live connection drops entirely while a reply is
  in flight — does the person still see the reply once the connection (or
  the page) recovers, without needing to know to reload manually?
- What happens if a person opens the contextual panel, then resizes the
  window from small to wide (or the reverse) — does it stay open, closed,
  or dismissible consistently across the resize?
- What happens if a person navigates away from a page while the contextual
  panel triggered from that page is still open — does the label update, or
  does the panel close?
- What happens when someone has no navigation add-ons installed at all —
  does the medium-width collapsed sidebar and the mobile tab bar still
  behave correctly with only the core set of destinations?
- What happens when someone gives feedback on a response and then asks for
  a retry — do both actions remain available, or does one supersede the
  other?
- What happens at the exact boundary widths between window-size ranges
  (e.g. right at the edge between "medium" and "wide")? The layout must
  not flicker or leave a destination unreachable exactly at the boundary.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST ensure every sent chat message reaches a
  visible terminal state (reply shown, or a clear failure/retry state)
  without requiring the person to manually reload the app.
- **FR-002**: The system MUST NOT lose a completed reply — if live delivery
  to the open session fails, the reply MUST still be retrievable the next
  time the conversation is opened or refreshed.
- **FR-003**: The system MUST make every navigation destination reachable
  at every supported window width, including widths where the sidebar
  shows icons without visible text labels.
- **FR-004**: Icon-only navigation controls MUST expose an accessible name
  usable by assistive technology, independent of whether a text label is
  visually rendered.
- **FR-005**: The contextual assistant panel MUST provide a visible,
  discoverable close control at all times it is open.
- **FR-006**: The contextual assistant panel MUST close when the person
  presses the Escape key, from any page and any trigger method.
- **FR-007**: The contextual assistant panel's launcher and the panel
  itself MUST NOT visually or interactively obscure another control's
  primary action, at any supported screen width.
- **FR-008**: The contextual assistant panel MUST label itself after the
  page the person is currently on, regardless of whether it was opened via
  the floating launcher or the keyboard shortcut.
- **FR-009**: The Settings page MUST adapt its layout to make reasonable
  use of the available window width, rather than remaining a fixed-width
  column regardless of window size.
- **FR-010**: The mobile bottom navigation MUST remain comfortably tappable
  and legible as the number of available navigation destinations grows,
  via an overflow/"more" pathway rather than shrinking every item
  indefinitely.
- **FR-011**: Each assistant chat reply MUST offer a lightweight way to
  give positive or negative feedback and to request a retry. The chat
  surface (e.g. near the composer or a new conversation's empty state)
  MUST also present a brief, unobtrusive reminder that responses are
  AI-generated and may contain errors.
- **FR-012**: Mobile bottom-navigation labels MUST be rendered at a size
  that is comfortably legible at typical reading distance.
- **FR-013**: The breadcrumb "back" control MUST provide a click/tap target
  large enough for comfortable, reliable activation.
- **FR-014**: List items (workflow titles, status labels, and similar)
  MUST display a human-readable form of their name and status rather than
  a raw internal identifier, when no explicit display name was set.
- **FR-015**: The interface's neutral colors (background and muted/body
  text) MUST be a deliberately tinted palette rather than flat
  black/white/grey, applied via shared design tokens so the change
  propagates consistently rather than per-component.
- **FR-016**: A dedicated display typeface MUST be used for the wordmark,
  page titles, and section headings; body copy MUST remain on the existing
  body typeface; a dedicated monospace/data typeface MUST be used for
  timestamps, schedules, and other tabular or technical values.
- **FR-017**: The "Ze is thinking" indicator MUST use a single pulsing
  signature visual instead of a generic three-dot ellipsis, and MUST
  respect `prefers-reduced-motion`.
- **FR-018**: This direction MUST NOT change the existing accent color,
  pill button/input shapes, or uppercase button-label convention — scope
  is limited to neutrals, typography, and the one signature motion moment
  (User Story 11, Acceptance Scenario 4).

**Implementation status (2026-08-19)**: FR-015 through FR-017 are applied
at the token/shared-component level — `apps/ze-web/src/app/styles/globals.css`
(retinted `--color-void`/`--color-bone`/`--color-ash`/`--color-smoke`,
added `--font-display` (Space Grotesk) and `--font-mono` (JetBrains Mono)
theme tokens), `entities/message/ui/TypingIndicator.tsx` (pulsing-star
signature, `motion-safe:` gated), and the display typeface applied to the
wordmark (`widgets/chat-workspace/ui/ChatWorkspace.tsx`) and page/section
titles (`shared/ui/layout/TopBar.tsx`, `widgets/app-shell/ui/AppShell.tsx`).
Because color and font are theme tokens, most of the app inherits the
retint automatically; `AppShell.tsx` and `TopBar.tsx` additionally had
their literal `bg-black`/`text-white`/`border-white/*` Tailwind utilities
swapped for the semantic token classes (`bg-background`, `text-foreground`,
`border-border`, …) so those two high-traffic shell components pick up the
palette rather than staying pinned to hardcoded black/white. This sweep
was then completed across the entire `apps/ze-web/src` tree — every
remaining file using literal `text-white`/`bg-black`/`border-white`/`bg-white`
Tailwind utilities (58 files total across `shared/ui`, `shared/effects`,
`entities/*`, `features/*`, `widgets/*`, and `pages/*`) was swept to the
semantic token classes. Zero literal black/white color utilities remain in
the codebase as of this pass (`grep -rlE "text-white|bg-black|border-white|bg-white" src`
returns no matches).

FR-009 (Settings width) and FR-014 (humanized content) were also
implemented in this pass, ahead of their own scheduled priority, because
they directly overlapped with this work: `widgets/settings-workspace/ui/SettingsWorkspace.tsx`
now uses a `max-w-4xl` two-column grid (Connection + plugin-contributed
sections side by side on wide screens) instead of a `max-w-sm` single
column — see research.md Unknown 4 for why the original "left-pinned"
diagnosis was wrong and what the real fix was. A new `shared/lib/humanize.ts`
(`humanizeStatus`, `humanizeIdentifier`) is now applied to goal status
chips and workflow display names, confirmed live turning `awaiting_gate` →
"Awaiting gate" and `lembrete_regar_plantas` → "Lembrete regar plantas".

**Follow-up audit (2026-08-19, same day)**: a self-review against the
original design board found two real gaps the first pass missed —
`shared/ui/layout/PageHeader.tsx` and `shared/ui/layout/DashboardHero.tsx`
(the page-title component and the large stat-number component used by
Data/Usage/etc.) were still rendering in the body typeface, not the
display face. Both now use `font-display`; `DashboardHero`'s large figures
keep a light weight (`font-light`, Space Grotesk 300 added to the font
import) to preserve the airy hero-number look. The board's "sky settles
once" load motion (distinct from the ambient starfield drift) was also
missing from the real `ChatWorkspace` empty state — added as a
`motion-safe:`-gated one-time fade-in. `--font-mono` (JetBrains Mono) turned
out to already be reaching every existing `font-mono` usage across the app
without further edits, since it overrides Tailwind v4's built-in default
`--font-mono` token rather than requiring a new utility class per call
site. Re-verified: `make test-web` 103/103, `bun run lint` unchanged.

`make test-web` (103 tests) and `bun run lint` show no new failures from
this work.

### Key Entities

- **Chat message**: A person's message or an assistant reply within a
  conversation; has a delivery/visibility state (sending, delivered,
  failed) that must always resolve to something the person can see.
- **Navigation destination**: A section of the app reachable from the
  sidebar or bottom navigation; has a name, an icon, and a group; must
  remain reachable and identifiable regardless of window width.
- **Contextual assistant panel**: A page-aware chat overlay that can be
  opened from any page; has an open/closed state, a label naming the page
  it applies to, and a position that must not collide with other on-screen
  controls.
- **List item display name/status**: The human-facing title and status
  text shown for workflows, goals, and similar items; may fall back to a
  raw internal identifier when no display name was explicitly set, which
  this feature requires be humanized before display.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of sent chat messages reach a visible terminal state
  (reply shown or clear failure state) within a bounded wait, with zero
  messages requiring a manual page reload to become visible, across a
  sample of repeated test sends.
- **SC-002**: Every navigation destination available at full desktop width
  is also reachable at every narrower supported window width, verified
  across the full width range with zero unreachable destinations.
- **SC-003**: The contextual panel can be closed via an on-screen control
  and via the Escape key from 100% of pages it can be opened from.
- **SC-004**: Zero instances of the contextual panel or its launcher
  visually overlapping another control's primary action, across all
  supported screen widths.
- **SC-005**: The contextual panel's displayed label matches the
  originating page in 100% of open attempts, regardless of trigger method.
- **SC-006**: On a wide desktop display, the Settings page's used content
  width increases visibly compared to its current fixed-width behavior
  (no longer confined to a narrow left-pinned column).
- **SC-007**: Screen-reader users can identify the destination of every
  icon-only navigation control without needing to expand or widen the
  sidebar first.
- **SC-008**: People can leave feedback or request a retry on an assistant
  reply in one interaction step, without leaving the conversation view.

## Assumptions

- The chat "stuck loading" issue (User Story 1) is a live-delivery problem,
  not a data-loss problem — the assistant's reply is already being
  generated and stored correctly; only its arrival in the currently open
  session is unreliable. Root-causing whether the failure lives in the
  delivery path or the client's handling of it is in scope; changing how
  replies are generated or stored is not.
- "Medium window width" refers to the tablet-and-narrow-desktop range
  where the navigation sidebar currently switches to icons-only, as
  opposed to the fully expanded (wide desktop) or fully collapsed (mobile
  bottom-bar) presentations.
- The bounded wait used to judge whether a chat message has "hung" (User
  Story 1, FR-001) should match existing normal response-time expectations
  for the assistant; this feature does not change how long responses
  normally take, only what the person sees while waiting and afterward.
- Existing navigation destinations, groupings, and the plugin-contributed
  additions to them (Contacts, News, Reminders, etc.) are not being
  redesigned — this feature makes the existing structure reachable and
  legible at every size, not restructured.
- Feedback given on assistant replies (User Story 9) is captured for later
  review; this feature does not specify what happens to that feedback
  afterward (e.g. whether it retrains anything), only that the person can
  give it.
- Humanizing raw identifiers (User Story 10 / FR-014) applies to display
  only; underlying stored identifiers are unchanged.
- The "Open Sky" direction (User Story 11) is primarily a token-level
  change — pages that consume the shared color/type tokens inherit the new
  palette and typography without individual edits. The literal-color sweep
  (raw `black`/`white`/`grey` Tailwind utilities that don't route through
  the tokens) was completed in full across the codebase in this pass rather
  than deferred, since it turned out to be a mechanical, low-risk,
  file-by-file substitution with no behavioral changes — confirmed by
  `make test-web` (103/103 passing) and `bun run lint` (no new errors)
  both before and after.
