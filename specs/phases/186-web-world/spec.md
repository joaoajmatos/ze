# Feature Specification: World (W2)

**Feature Branch**: `186-web-world`

**Created**: 2026-10-17

**Status**: Implemented (2026-10-17)

**Input**: Maestro brief 2026-10-17, phase W2; overhaul plan sections a (World), b.1, e (Phase W2). Reserved phase 176 "Today surface" was dropped by the user on 2026-10-17 (relayed by the Maestro: "World covers it"); this phase is where that intent lives. No phase uses the number 176.

**Governed by**: `DESIGN.md` (field chart, leader line, honesty visuals, One Alarm Rule), `PRODUCT.md` principles 1–3, `specs/arch/pre-v1-hard-cuts.md`. User decisions 1 (World is home), 3 (priority folded into World, drag to pin), 8 (phone).

**Depends on**: 183 (shell, on `main`), 184 (goal progress, `failure_summary`, notification `target_parent_id`), 185 (budget, `confidence_prior`, `drift_deadline`, reminders, hypotheses, notification filters) and 195 (screen-context store, `chatAbout`, `Module.onChatAbout`, `ChatAboutChip`). The floor starts when all four are on `main`.

**Doctrine functions served**: executive function (what is open, slipping, promised; what needs the user) and governance (decisions in one place, interruption budget visible).

---

## Clarifications

### Session 2026-10-17 (planning against the code)

Binding for the plan; each one follows the code or the honesty rule.

- **The `/jarvis` reference fakes three values; World never ports them.** It plots a missing confidence at 0.5 (`c.confidence ?? 0.5`), draws the decay trail from an invented staleness curve, and hard-codes drift deadlines and reminders. World takes deadlines from `LoopListItem.drift_deadline` (185), reminders from `listReminders` (185), and draws the trail only from `confidence_prior` → `confidence` (185). A concern with no confidence (stuck goals, relationships, unlinked reminders) sits in a "not a claim" lane at the top of its time band, never at a guessed height.
- **The field shows what `PriorityView` ranks, plus reminders.** The snapshot ranks open loops, stuck goals (`list_stuck`) and recent hypotheses (`list_recent`, confirmed ones included), and relationships. Healthy active goals are not concerns: Doing now shows them, not the field. A goal on the field is a stuck goal (hollow mark, slipped). Hypotheses join against `listHypotheses?state=all&limit=200`. Relationship items have no record route, so their readout is title and rank only.
- **Gates have no REST route.** The goal executor's gate notification carries the actions `goal:approve:<gate_id>`, `goal:stop:<gate_id>`, `goal:redirect:<gate_id>`, answered by an `action` WS frame (`ze_api/api/ws/goal_actions.py`). Needs you lists a gate from the goal row (184 `gate_id`, `gate_title`, `gate_open_since`) and sends the matching frame on the session thread (`useSession().threadId`, the thread the overlay uses). Proceed / Stop: the server posts its assistant message ("Approved - Ze will continue …") into that thread and sends `refresh` (screen `goals`); a failure comes back as an `error` frame on that thread; there is no ack. The row is disabled from the send until the goals refetch drops the gate, and an `error` frame on that thread within 15 s shows the module error line and re-enables it (the server does not guard a double approve). Redirect: sends `goal:redirect:<gate_id>` on the session thread (the server then treats the next message on that thread as the redirect instruction, `turns.py`), then opens the overlay on that thread with the gate as subject and the bar focused, so the user's next message is the instruction. Redirect does not close the gate: its in-flight state ends at the first `message` frame on that thread (the server's "Send your instructions …" reply) or an `error` frame; the row then reads "Waiting for your instructions" with Proceed and Stop still enabled.
- **Needs you has four kinds:** held writes (`listHeldWrites`, `decideHeldWrite`), open gates (above), suspected loops (`confirmLoop`, `dropLoop`), and confirmations waiting in a chat (`usePendingConfirms`, kinds `budget` and `write`: Approve / Deny through `useConfirmation`, plus Open to go to that thread). Chat confirmations come only from the pending store, which lives in client memory and is rebuilt from the server's replay of `pending_confirmations` on connect.
- **Loop lifecycle stays reachable.** Deleting the old Loops page removes Close and Drop for active and drifting loops; World puts Close ("done") and Drop on the field readout and the loops-rail row for those loops (not in Needs you).
- **"Acting" is shown only for what is running now.** A workflow whose latest execution is `running` lights an `acting` ring. Goals expose no "executing now" field, so an active goal does not light one.
- **"While you were away" starts at the viewer's last visit**, kept in `localStorage` (`ze.world.lastSeenAt`, per viewer; wrapped in try/catch). Storage always holds the last time World was in front of the user: `lastSeenAt = now` is written on every hide, on `pagehide` and on unmount. `since` is kept in memory per visit: read from storage on mount, and moved only when a new visit starts (World visible again after at least 5 minutes hidden, `since` = the hide time). A quick tab switch writes storage but keeps the list; reopening after closing the tab uses the stored time. With no stored value it shows the last 24 hours. It lists `listNotifications?since=` (185 matches `COALESCE(delivered_at, created_at)`) and the proactive job runs since then.
- **Held-write links open World.** `notificationHref` sends `held_write`, `open_loop`, `reminder` and `hypothesis` targets to `/?focus=<kind>:<id>`; World selects that item (row highlighted, field mark selected). The bell's held-write list and its `?confirm=` handling are deleted.
- **World does not refresh on its own today for loops:** loops are written after a turn (`write_memory`) with no `refresh` frame. World invalidates its queries on every `message` frame and on `notification` frames, and refetches on window focus. The goals `refresh` screen also invalidates the priority snapshot and workflow executions, and loop transitions invalidate every loop key and the snapshot.

## Overview

World is the home at `/`: the state of the user's life as Ze holds it, in one look, with what slipped and what needs a decision first. It replaces the interim World sections from 183 (the old Loops and Priority pages), the Reminders plugin page and the bell's held-writes list. It is not an agenda: every module answers what Ze understands (claims with kind, source, confidence), what it is doing about it, or what it needs from the user.

## Modules (desktop three-column; phone order below)

- **Presence** (left rail top): orb driven by 183's reducer plus World signals: `attention` when anything slipped (drifting loop, stuck goal, failed run), with the leader line from the orb to the slipped mark; `acting` rings per running goal or workflow (max 3).
- **Needs you** (left rail): gates, held writes, suspected loops, budget pauses. One row per decision with its one or two actions (Yes, track it / Drop; Approve / Deny; Approve / Open). Cream, never coral. Reuses the claim-card intents from 184.
- **Doing now** (left rail): active goals with progress (184), the next workflow run, runs this week ok/failed (latest executions per workflow, capped at 10 workflows), and a running execution if any.
- **The Field** (hero): time left × how sure (DESIGN.md "The field chart"), marks by claim kind, coral slipped band, NOW line, dotted trail from 185 `confidence_prior` to the current confidence (none when the prior is null), reminders as deadlines on their loop (`loop.reminder_id`; unlinked reminders as their own marks; `overdue` reminders sit in the slipped band), callout on hover/focus, readout on select. "Why this order" readout per item from the priority snapshot (computed vs displayed rank, override, pinned) with drag/keyboard to reorder and pin (`submitPriorityOverride`, `unpinPriorityOverride`).
- **The Sentence + CTA** (hero head): one sentence in Ze's voice built from counts ("Two promises slipped. I am watching 11 concerns.") and a "What's slipping?" command chip that opens Ask with `context.compose = "slipping"` (184).
- **Loops · confidence** (right rail): rows with glyph, state tick, sparkline, mono readout, dim second line ("Drifting · email · 3d ago").
- **Touched · 7 d** (right rail): loops, goals and workflows changed in the last seven days.
- **While you were away** (right rail): notifications and job runs since the last visit with one action each, via `notificationHref` and the 184 target table; budget used/max and next slot from 185.

## User Scenarios & Testing *(mandatory)*

1. **The user sees what slipped first (P1).** With seed data containing two drifting loops, the Sentence names two slipped, the slipped band holds two coral marks, the orb is in `attention`, and the leader line ends on the most overdue mark's centre (not its label). Test: field placement unit tests (bands, lanes, label collision) and a capture.
2. **The user decides from World (P1).** Approving a held write, answering a gate and confirming or dropping a suspicion from Needs you call the existing mutations / `action` frame and remove the row on success; failures show the module error state. Test: mutation tests per intent.
3. **Posture is honest everywhere (P1).** Glyph, chip, meter and sparkline agree for told, inferred, suspected, goal and slipped; no raw enums (`awaiting_gate`, `user_declared`) render. Test: posture → visual mapping table test shared by field, rows and cards.
4. **Sources failing are named (P1).** When the priority snapshot reports `sources_failed`, the hero head prints "N sources down: …" and only dependent modules show their error state. Test: fake snapshot with `sources_failed: ["hypothesis"]`.
5. **Reorder with a reason (P2).** Drag or keyboard (Space to lift, arrows, Space to drop) reorders; "Why this order" shows computed vs displayed rank and the pin. Test: override submission payload and keyboard path.
6. **Phone (P1).** At 390 px: Presence → Sentence + CTA → ranked list grouped by band (Slipped, This week, Later, No deadline; no plot) → Needs you → Doing now → Loops → the rest; the slipped row pulses instead of a leader line.

States: loading draws module frames with dim labels and no numbers; empty field = bare grid + "Nothing tracked yet. Tell me what you are working on."; offline disables every write control with "Ze is offline".

## Requirements *(mandatory)*

- **FR-001**: `pages/world` with widgets `world-field`, `needs-you`, `doing-now`, `loops-rail`, `touched`, `away`; entities `loop`, `priority-item`, `goal`, `workflow`, `confirmation` (held writes, existing), `notification`, and new `reminder` and `hypothesis` (from 185) with query hooks in `entities/<name>/api/`; a `useWorld` composition hook in `pages/world/model` carrying `sources_failed` (entities cannot import each other, so the join lives in the page and widgets get props).
- **FR-002**: The field and leader line port `pages/jarvis/hud/FieldChart.tsx` and `LeaderLine.tsx` with real data (`pages/jarvis/model/world.ts` mapping logic becomes `entities`/`widgets` lib code with tests); px-true chart type; 26/60 unit hit radius; desktop only.
- **FR-003**: Presence `attention` and `acting` signals are dispatched from World data through 183's `set_world_signal`.
- **FR-004**: The WS `notification`, `confirm_request` and `refresh` frames invalidate the right queries (extend `features/invalidate-on-ws-refresh`).
- **FR-005**: Hard cuts: `pages/loops`, `pages/priority`, `widgets/loop-review`, `widgets/priority-snapshot`, `pages/world/ui/WorldInterim.tsx`, the `/world/priority` route and its redirect target (old `/priority` now redirects to `/`), the Reminders plugin nav/page mapping (plugin page route for reminders resolves to World), the held-writes list inside `NotificationBell` (the bell keeps the unread count and opens World › While you were away), and the Reminders plugin's `ui_contributions` page descriptor plus `getRemindersPage` route in `ze-calendar` once World renders reminders from 185 (backend task in this phase).
- **FR-005a**: Screen context (phase 195): World publishes into the screen-context store: the field selection (selected marks as `selection` refs), the selected readout item as `subject`, the visible marks and rows as `visible`, and the focused module. Every module and component built here wires "Chat about this" (callbacks passed down by props from widgets, 195 FR-024) (`onChatAbout` on `Module`; `ChatAboutChip` on field marks, loop rows, Needs-you rows and While-you-were-away rows), with a test per kind (195 FR-025).
- **FR-006**: Acceptance per the plan: impeccable critique ≥ 29/40; detector 0 on touched slices; captures at 1440 and 390 with no console errors and 44 px targets; 60 fps scroll probe on the field.

## Success Criteria *(mandatory)*

- **SC-001**: Every value on World traces to an API field; values the API lacks are absent (spot check list in the floor's Handoffs note).
- **SC-002**: A decision can be made from World for each of the four kinds.
- **SC-003**: `make test-web`, `make typecheck-web`, `make web-build`, lint, and `make test-py` for the ze-calendar cut pass.

## Out of Scope

- Ask canvas and trace (187), Doing detail pages (188), Mind (189), Governance settings (190), voice (193).

## Owning packages

ze-web (all modules); ze-calendar (delete the reminders page descriptor and route after World renders reminders); no migration.
