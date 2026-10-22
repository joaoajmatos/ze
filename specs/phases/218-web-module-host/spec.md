# Feature Specification: Web Module Host — States, Place Signals, One Primitive Host

**Feature Branch**: `218-web-module-host`

**Created**: 2026-10-22

**Status**: Draft

**Depends on**: 206 (Module states read the shared query adapter's error/loading shape; widgets convert after their entity queries do)

**Input**: Architecture review 2026-10-22, candidate C20 ("Module renders its own loading, error and empty states; one primitive-host adapter; one posture vocabulary"). Report: `architecture-review-2026-10-22.html`; floor brief `floor-briefs-2026-10-22.md`, Wave 3.

**Governed by**: `DESIGN.md` (module chrome, copy, `role` usage, 44 px targets, focus rings), phase 184 (ClaimPosture set only by code from the stored record), phase 191a (typed `PrimitiveAction`, `ui_action`), phase 191b (plugin modules in slots, plugin settings sections), phase 195 (screen context and Chat about this), `specs/GLOSSARY.md` (Place, Module).

## Context

The five Places build every Module from the same chrome (`shared/ui/hud/Module.tsx`, 52 lines). That chrome does not know whether its content is loading, failed or empty, so each widget writes the branch itself:

- **Hand-written state branches.** 23 widget and page files read `isError`, and 19 of them hand-write a `role="alert"` line. "Reading…" is hand-written 17 times. Roles drift: some loading lines carry `role="status"`, some carry nothing. `shared/ui/layout/ErrorState.tsx` has exactly one user (`widgets/connections/ui/PluginSettingsSection.tsx`).
- **Repeated Place signals.** Pages pass the same signals down by hand. `offline={offline}` appears 10 times and `onChatAbout={chatAbout}` 17 times. `useWsStore((s) => s.isConnected)` is read separately in `DoingPage.tsx:27` and `DoingGoalPage.tsx:67`, among others.
- **Unshared Part type.** World alone has a `Part<T>` type with data, loading and error (`pages/world/model/useWorld.ts:18-22`). No other Place uses it.
- **Unchecked casts.** Screen refs for `useScreenPublisher` (14 sites) are built with `as WsScreenRef` or `as never`, 30 casts in all, so a wrong ref kind compiles.

The primitive tree renderer (`@myguyze/ze-ui`, `PrimitiveRenderer.tsx`) is deep. Its host side in ze-web is split:

- **Two action vocabularies, two dispatchers.** Typed `PrimitiveAction` goes through `features/primitive-tree/api/usePrimitiveActions.ts`. Card actions go through `useCardActions.ts`. The generated `CardAction.intent` is a closed set (`packages/ze-ui/src/generated/types.gen.ts:225`), but `packages/ze-ui/src/react/context.tsx:5` widens it to `intent: string`.
- **The goal payload is built twice.** The `goal:<verb>:<id>` action payload is built in `useCardActions.ts:41` and again in `features/answer-gate/api/useAnswerGate.ts:58`.
- **The not-connected notice is copied.** "Not connected. Retry when Ze reconnects." is written in five files: `useCardActions`, `usePrimitiveActions`, `useConfirmation`, `useRetryReply` and `useSendTurn`.
- **Plugin settings skip the host.** `PluginSettingsSection.tsx:13-45` builds its own renderer from `parseTree` and `usePrimitiveActions` and skips `ConnectedPrimitiveTree`, so it gets no HUD class map, no card actions and no headline renderer.
- **Two posture wordings.** In chat, ze-ui's `postureLine` (`PrimitiveRenderer.tsx:817-823`) prints raw words, such as "suspicion · suspected · 60%". World and Mind use ze-web's `shared/lib/claim-posture.ts` ("I suspect this", glyphs). The same record reads differently in a claim card and in the field.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Every Module says loading, failed or empty the same way (Priority: P1)

On every Place, a Module whose read is loading shows the same reading line, a failed read shows the same alert line naming what could not be read, and an empty one shows its own empty copy. Assistive tech hears these through consistent roles.

**Why this priority**: This is the most repeated code on the web and the place where accessibility drifts.

**Independent Test**: A Module test renders each state from a Part-like value and checks the copy, the role and focus. Converted widgets keep their existing tests.

**Acceptance Scenarios**:

1. **Given** a Module whose read is loading, **When** it renders, **Then** it shows the reading line with `role="status"`.
2. **Given** a failed read, **When** it renders, **Then** it shows "Couldn't read <what>" with `role="alert"`, plus a retry control where the read can retry.
3. **Given** an empty result, **When** it renders, **Then** it shows the Module's empty copy and no alert.
4. **Given** the client is offline, **When** a Module renders, **Then** controls that need the socket are disabled and say why, the same way on every Place.

---

### User Story 2 — Chat, plugins and World read a claim the same way (Priority: P1)

A claim card in a chat reply, a plugin module, and the World field use the same posture words and glyphs for the same stored record.

**Why this priority**: The doctrine's posture rule (phase 184) is about how a claim reads to the user. Two wordings break it visibly.

**Independent Test**: A fixture claim renders through ze-ui in chat and through the World field. Both show the same words and glyph.

**Acceptance Scenarios**:

1. **Given** a suspected loop at 60% confidence, **When** it renders as a chat claim card and as a World field row, **Then** both read with the same posture phrase and glyph.
2. **Given** a claim with no kind, **When** it renders, **Then** both surfaces fall back to the same plain wording.

---

### User Story 3 — Plugin settings and plugin modules act like core Modules (Priority: P2)

A plugin settings section gets the same HUD styling, card actions, headline and not-connected handling as a primitive tree anywhere else.

**Why this priority**: Plugins add no pages (phase 191b). Their surfaces are only as good as the host they get.

**Independent Test**: Render a plugin settings fixture that contains a card with an action and a headline. The card action dispatches, and the headline uses the HUD renderer.

**Acceptance Scenarios**:

1. **Given** a plugin settings tree with a claim card that has a "confirm_loop" action, **When** the user taps it, **Then** the loop is confirmed through the same path as on World.
2. **Given** the socket is down, **When** the user taps an action that needs it, **Then** the same not-connected notice shows as elsewhere.

---

### User Story 4 — Card actions and goal answers have one typed path (Priority: P2)

Card intents are a closed, typed set. Each goal action payload (approve, stop, redirect, pause, abandon) is built in one place, whether it comes from a card or from the gate answer feature.

**Why this priority**: A new intent or verb becomes one edit, and a typo cannot compile.

**Independent Test**: Type-check fails on an unknown card intent. A unit test covers the goal payload builder for each verb.

**Acceptance Scenarios**:

1. **Given** a card with intent `approve_gate`, **When** it is tapped, **Then** the payload is built by the same function the gate answer uses.
2. **Given** the server adds an intent, **When** the generated types update, **Then** the host fails to compile until the intent is handled.

---

### User Story 5 — Screen refs are typed (Priority: P3)

Each Place publishes its screen context with ref builders that know each ref kind's fields, with no casts.

**Why this priority**: It prevents wrong-kind refs in screen context (phase 195). There is no visible change today.

**Independent Test**: A source search finds zero `as never` and zero `as WsScreenRef` casts on screen refs. The phase 195 screen-context tests still pass.

**Acceptance Scenarios**:

1. **Given** a goal page, **When** it publishes its subject, **Then** the ref comes from a typed builder for goals.

### Edge Cases

- A Module shows several reads, as World's Needs you does. Its state combines them: an error in one read is named without hiding the others' data, matching World's existing `sourcesFailed` behaviour.
- A Module has no read, such as static copy. It renders as today.
- A plugin module fails the server's schema check, which returns 502 or 504 (phase 191b). Its plain line still shows inside the shared failed state.
- Reduced motion: the reading line has no animated spinner.
- Phone width: the state lines wrap within the 16 px gutter.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Module chrome MUST accept a read state (loading, failed, empty or data), the noun for what it reads, and its empty copy. It MUST render the three non-data states with fixed roles: `status` for reading, `alert` for failed, and no live role for empty.
- **FR-002**: The read-state shape MUST be shared, generalising World's `Part`, and built from the phase 206 query adapter's result.
- **FR-003**: Every widget on the five Places that hand-writes a loading, error or empty branch MUST move to FR-001. `ErrorState` MUST be removed or folded into the Module chrome.
- **FR-004**: Place-wide signals (the current time, offline, and Chat about this) MUST come from one Place context that each Place page provides. Widgets MUST NOT receive them as pass-through props.
- **FR-005**: Screen refs MUST be built by typed builders exported from `entities/screen-context`, one per ref kind. Casts on screen refs MUST be removed.
- **FR-006**: One host-actions module in `features/primitive-tree` MUST serve every primitive tree renderer site, including `PluginSettingsSection`, `PluginModuleSlot`, `People`, the Assemble canvas and reply blocks. It owns typed actions, card intents, form submit, the headline renderer and the class map.
- **FR-007**: Card intents MUST keep the generated closed type end to end. The `intent: string` widening in ze-ui's context MUST be removed.
- **FR-008**: The goal action payload MUST be built by one function, owned next to the gate answer feature, and used by the card host.
- **FR-009**: The not-connected notice MUST be one shared message, used by every send that needs the socket.
- **FR-010**: Claim posture wording and glyph choice MUST live in one module. ze-ui and ze-web MUST both use it: either ze-ui exports it, or the host passes a posture renderer the way it passes `renderHeadline`. The plan picks one. The posture value stays code-set from the stored record (phase 184).
- **FR-011**: Copy, roles, focus rings and 44 px targets MUST follow `DESIGN.md`. Any new copy MUST be added to `DESIGN.md` in the same change.

### Key Entities

- **Read state**: what a Module shows: loading, failed (with the noun), empty (with copy), or data.
- **Place context**: the shared signals a Place gives its Modules.
- **Host actions**: the one module that turns primitive and card actions into effects.
- **Posture wording**: the words and glyph for a claim's posture.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Zero widget files hand-write a `role="alert"` read-failure line. Today 19 do.
- **SC-002**: Zero `offline={offline}` and `onChatAbout={chatAbout}` pass-through props. Today there are 10 and 17.
- **SC-003**: Zero casts on screen refs. Today there are 30.
- **SC-004**: One posture wording module. The chat and World fixture test of US2 passes.
- **SC-005**: Each of the five Places renders in the agent's own portal, checked with the `ze-web-verify` skill, with screenshots of a loading, a failed and an empty Module and of a plugin settings card action.
- **SC-006**: All existing ze-web and ze-ui tests pass, and `make typecheck-web` is clean.

## Assumptions

- Phase 206 has landed its query adapter. Widgets convert after their entity does.
- No backend change. Card intents and goal action verbs stay as the server defines them.
- The orb, Presence and the Ask canvas cascade are untouched.

## Out of Scope

- Turn state (phase 205) and query staleness (phase 206).
- New primitives or new card intents.
- Plugin module refresh polling (phase 191b behaviour stays).
