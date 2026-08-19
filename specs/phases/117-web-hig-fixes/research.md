# Research: Web UI HIG Audit Fixes

Each unknown below was investigated by reading the relevant `apps/ze-web`
source and, where practical, reproducing the behavior live against a running
dev backend + seeded data. Findings are recorded as Decision / Rationale /
Alternatives so implementation doesn't re-derive them from scratch.

## Unknown 1 — Root cause of the stuck "Ze is thinking..." state (User Story 1, FR-001/FR-002)

**Decision**: Treat this as a live-delivery reliability problem to be
root-caused as the first implementation task for User Story 1, with a
polling-fallback safety net as the guaranteed fix regardless of root cause.

**Rationale**: Live reproduction confirmed the backend completes the full
pipeline (routing → agent execution → response persisted) and the reply is
retrievable via `GET /api/v0/messages` immediately after — but the open
session's typing indicator and locked composer never cleared without a full
page reload. Reading `useChatWorkspace.ts` shows the mechanism that *should*
prevent this: `threadId` is a stable, client-generated UUID
(`ze-<uuid>`, persisted in `localStorage` by `entities/session/model/session-store.ts`)
established before any message is sent, and `useFrame("message", ...)` compares
the incoming frame's `thread_id` against it, only clearing the typing state
(`stopThinking()`) on a match. Ruled out: a `null`/unset client thread ID
racing the server-assigned one (thread IDs are always client-generated and
stable, not server-assigned). Not yet confirmed: whether the frame's
`thread_id` genuinely mismatches in the failing case, whether the WS
connection silently drops without the `isConnected` state reflecting it, or
whether the `useFrame` subscription is transiently detached (e.g. a
remount race in `ChatWorkspace`/`ContextOverlay`, both of which call
`useChatWorkspace`) at the moment the frame arrives.

**Alternatives considered**:
- *Ship only a client-side timeout+poll fallback, skip root-causing*:
  rejected as the sole fix — it would mask the bug rather than fix it, and
  the spec (FR-001/FR-002) requires the reply to arrive promptly, not just
  eventually via a poll. Kept as a *safety net* alongside the real fix, not
  a replacement for it.
- *Assume it's server-side and patch `ze_api/interface/native.py`
  unconditionally*: rejected — no server-side evidence was found (the
  backend logs show successful completion and persistence); changing the
  server without confirming the client-side mismatch first risks fixing
  nothing.

**First implementation task for this story**: instrument (temporarily, e.g.
via console logging or a debugger breakpoint) the `useFrame("message", ...)`
handler's `frameThread`/`threadId` comparison during a live repro, to confirm
whether the frames are mismatched, missing entirely, or received-but-ignored
for another reason, before writing the fix.

## Unknown 2 — Whether the contextual panel's dismiss controls are actually missing (User Story 3)

**Decision**: The dismiss code already exists (`ContextOverlay.tsx`) — both
an Escape-key handler and a visible close control (`X` on mobile,
"Collapse" `ChevronDown` on desktop) are wired to the same `close()` action
in both `MobileChatSheet` and `DesktopChatWidget`. The originally-observed
"no way to dismiss" behavior does not match what the code does, and a
follow-up live re-test could not cleanly reproduce the original failure
(see Unknown 3 — the launcher itself was unreliable to open in the re-test,
which may have been the actual cause of the original observation: the panel
was never confirmed open when Escape "didn't close" it).

**Rationale**: Re-reading `ContextOverlay.tsx:86-90` (mobile) and
`ContextOverlay.tsx:200-204` (desktop) shows `document.addEventListener("keydown", ...)`
handlers that call `close()` on `Escape`, present in both variants. The
`DesktopChatWidget` header also renders an explicit `aria-label="Collapse"`
button wired to `close`.

**Revised scope for User Story 3**: implementation should (a) confirm via a
clean repro whether Escape/close genuinely fail once the panel is reliably
open, and (b) regardless of that finding, address the discoverability gap —
the desktop button's label "Collapse" does not clearly communicate "this
dismisses the panel" the way "Close" or an `X` icon would (the mobile sheet
already correctly uses `X` + `aria-label="Close"`; the desktop widget should
match that pattern for consistency and clarity, per FR-005).

**Alternatives considered**:
- *Assume the original audit note was simply wrong and drop User Story 3*:
  rejected — even if the keyboard/click dismiss mechanism turns out to work
  once reliably reproduced, the desktop "Collapse" labeling is a genuine,
  independently-confirmable discoverability gap worth fixing on its own.

## Unknown 3 — Reliability of opening the contextual panel launcher (relates to User Story 3 and User Story 4)

**Decision**: Flag as a related but distinct implementation investigation,
folded into User Story 3's scope rather than spun out as an 11th story,
since it's the same component (`DesktopChatWidget`'s FAB) and the same root
audit line (the launcher/panel interaction is unreliable).

**Rationale**: During plan-phase re-verification, repeated precise clicks on
the floating launcher button (confirmed via zoomed screenshots to be
correctly positioned and rendered, not clipped or overlapped by another
element) did not reliably open the panel. The launcher is wrapped in a
framer-motion `motion.div` with `drag` enabled
(`ContextOverlay.tsx:209-214`) — wrapping a primary click target in a
draggable container is a known source of intermittent tap/click
suppression in gesture libraries (the drag recognizer can consume the
pointer sequence before a tap is registered). This is a plausible
explanation for both the original "can't dismiss" observation (if the panel
in fact never opened) and general user-facing flakiness clicking the
launcher.

**Alternatives considered**:
- *Treat this purely as a browser-automation artifact and ignore it*:
  rejected — drag-vs-tap conflicts in framer-motion are a well-documented,
  real-world failure mode, not exclusive to automated clicking; worth a
  deliberate check (e.g. constraining the drag activation distance, or
  separating the drag handle from the click target as the desktop panel's
  *header* already does once open) rather than assuming it's tooling noise.

**First implementation task for this story**: reproduce with real
mouse interaction (not just automation) to confirm or rule out the
drag/tap conflict; if confirmed, apply framer-motion's documented pattern
for combining `drag` and `onTap` (e.g. `dragListener={false}` with a
separate drag handle, matching how the expanded panel already separates its
header drag handle from its close button).

## Unknown 4 — Why the Settings page looked left-pinned despite using `mx-auto` (User Story 6)

**Decision (revised after DOM inspection)**: There was no broken ancestor.
Runtime inspection (`getBoundingClientRect`/`getComputedStyle` on the live
page) showed `SettingsWorkspace.tsx`'s root div genuinely centered —
`marginLeft`/`marginRight` were equal (402px each at a 1568px viewport) —
`mx-auto` was working correctly the whole time. The original "left-pinned"
read from the live audit was a misjudgment: a `max-w-sm` (384px) column
centered inside a ~1192px content region reads as "stuck over on the left"
relative to where the sidebar ends, even though it's mathematically
centered on the content region as a whole. The actual defect is exactly
what FR-009 already says: the column is simply too **narrow** for a wide
window, not mispositioned.

**Fix applied**: widened the root container (`max-w-sm` → `max-w-4xl`) and
wrapped the Connection section and plugin-contributed settings sections
(e.g. News) in a `grid grid-cols-1 lg:grid-cols-2` layout so they sit side
by side on wide screens and stack on narrow ones — the two-column pattern
suggested in the original audit, now applied directly rather than guessed
at. The destructive/full-width sections (Your data, Reset configuration)
stay full-width below the grid, unchanged.

**Alternatives considered**:
- *Chase a non-existent ancestor bug*: this was the original plan
  (see the struck-through hypothesis this replaces) — dropped once
  `getComputedStyle` showed centering was already correct; would have
  wasted implementation time looking for a bug that wasn't there.
- *Just bump `max-w-sm` to a slightly wider single column without a grid*:
  rejected — doesn't use the space as well as a two-column layout when
  there's a second section (News) that has genuine content to show, and
  doesn't match the Data page's already-established two-column precedent.

## Unknown 5 — Where to place the AI-disclosure reminder (User Story 9, FR-011)

**Decision**: Place it as a persistent, low-emphasis caption directly above
or below the message composer (`ChatInput`), visible on every chat surface
(main chat page and the `ContextOverlay` panel), rather than only on the
empty state.

**Rationale**: A composer-adjacent caption is always visible regardless of
conversation state (empty or has history), matches the common,
low-friction industry pattern the audit referenced, and requires touching
only the shared `ChatInput` component rather than duplicating the copy
across every empty-state variant (main chat empty state, mobile sheet,
desktop widget).

**Alternatives considered**:
- *Empty-state only*: rejected — disappears once a conversation has
  messages, which is most of the time a person is actually reading
  AI-generated content.
- *Per-message disclaimer*: rejected as noisy — the guideline calls for an
  unobtrusive, one-time-visible reminder, not per-message repetition.
