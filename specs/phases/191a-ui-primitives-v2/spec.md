# Feature Specification: UI Primitives v2 (191a)

**Feature Branch**: `191a-ui-primitives-v2`

**Created**: 2026-10-18

**Status**: Implemented

**Input**: User description (2026-10-18, phase 191 reopened): "Plugins are data and behavior sources... I dont know if they should contribute complete pages... they could contribute visual components and/or primitives that can be used to render information." Then: "I like that. And maybe this also involves improving our ze ui and or ze components." The agreed plugin UI model (Maestro scratchpad `191-plugin-ui-model.md`, summarized in `PRODUCT.md` › Plugin UI model) splits the work: 191a improves the primitives and their contract; 191b lets plugins place modules in slots the places offer.

**Governed by**: `PRODUCT.md` (Plugin UI model), `DESIGN.md` (modules, posture tones, 44 px targets), phases 45/66 (server-driven primitives), 118 (charts), 181 (write confirmation), 184 (claim posture, set only by code).

**Depends on**: nothing unfinished. It runs in parallel with the web place phases; 191b depends on it.

**Doctrine function served**: governance (every action a screen offers goes through the same gates as chat; what Ze shows is code-set and honest).

**Owning packages** (for planning): ze-components (descriptors), @myguyze/ze-ui (contract, validation, renderer), ze-api (the action route), ze-web (the action host and the gallery). No migration.

## Context

Ze draws structured UI from server-built trees of primitives. Agents build them with render tools; code builds them for composed answers and plugin settings. Three things stop this from carrying plugin UI:

- **Actions are strings.** A button's action is free text the web app interprets: `rest:<operation>` calls a REST route directly, which skips the write-confirmation gate every chat write goes through; `msg:<text>` sends a chat message; goal actions match a pattern. Nothing types or checks them.
- **The tree is brittle.** A tree with one primitive the web app does not know fails validation as a whole, and the renderer draws nothing for an unknown type. A plugin cannot add a view without a web release in lockstep.
- **The set has gaps.** Places and plugin modules need an entity facet, rows of stats, a posture-aware list, a small series, a keyed table with row actions, a timeline and a card with actions. Some exist in part; some do not.

## Clarifications

### Session 2026-10-18 (user answers through the Maestro: all recommended)

- Q: Which tools may a primitive's action call? → A: Any tool owned by the producer of the tree (the plugin or agent), run on the server through the normal tool path: gates, the constraint veto and the trace apply; an irreversible write asks first.
- Q: May agents draw the new primitives in chat? → A: Stat rows, keyed tables and sparklines only. Entity facet, posture-aware list and card-with-actions stay code-built.
- Q: Where does the gallery live? → A: A development-only route, absent from production builds.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - An action on a screen asks first, like chat does (Priority: P1)

A primitive's button that changes something (cancel a reminder, mark a source read) runs the same tool Ze would run in chat, through the same confirmation: an irreversible change asks first, a denial leaves things as they were, and the action ledger records it.

**Why this priority**: today a plugin screen can call a write route directly, with no confirmation and no trace. This closes that hole before plugins get more surfaces.

**Independent Test**: render a tree whose button names an irreversible tool; pressing it shows the confirmation; approving runs the tool once; denying runs nothing; a button that names a REST operation no longer validates.

**Acceptance Scenarios**:

1. **Given** a button whose action calls a reversible write tool, **When** the user presses it, **Then** the tool runs once and the user sees the outcome.
2. **Given** a button whose action calls an irreversible write tool, **When** the user presses it, **Then** the confirmation appears first, and the tool runs only on approval.
3. **Given** a button whose action asks Ze something, **When** the user presses it, **Then** the question is sent on the selected thread as an ordinary turn.
4. **Given** a button whose action opens a place, **When** the user presses it, **Then** the app navigates there without a turn.
5. **Given** a newly built tree with a string action (`rest:…`, `msg:…`, a bare text), **When** it is validated, **Then** validation fails with a plain error naming the action (pre-v1 hard cut). A tree stored before this phase (no version) is shown best effort: its old buttons are disabled with the line "This older button no longer works.", and its text always shows.
6. **Given** a tool action naming a tool that does not exist, is not in the named agent's tools, is not a write tool, or has not opted in to screen actions, **When** the user presses it, **Then** nothing runs and a plain line says the action is not available.
7. **Given** a pending screen confirmation, **When** the user sends a new message on that thread, reconnects, or the server restarts, **Then** the confirmation is replaced ("Okay, I didn't …"), shown again, or answered "That request expired." respectively, and an approval never runs twice.

---

### User Story 2 - An unknown view degrades to a readable table (Priority: P1)

When the server sends a primitive the web app does not know yet, the rest of the tree still renders, and the unknown part shows its fields as a plain table with a short note, instead of vanishing or breaking the whole view.

**Why this priority**: it lets the server add a view without breaking older clients, and it makes a mistake visible instead of silent.

**Independent Test**: a tree with one known and one unknown primitive renders the known one normally and the unknown one as a two-column table of its fields; a tree with a malformed known primitive still fails with a plain error.

**Acceptance Scenarios**:

1. **Given** a tree with an unknown primitive type, **When** it renders, **Then** the known primitives render and the unknown one shows as a table of its scalar fields with a note naming the type.
2. **Given** an unknown primitive with nested children, **When** it renders, **Then** its known children render inside the fallback.
3. **Given** a known primitive with a missing required field, **When** the tree is validated, **Then** it fails with a plain error that names the primitive and the field.
4. **Given** a tree marked with a newer minor version than the client's, **When** it renders, **Then** it renders with the fallback for unknown types. **Given** a tree with no version or a 1.x version (stored before this phase), **When** it renders, **Then** it renders best effort (unknown types fall back; string-action buttons are disabled), and if it still cannot be shown, only that tree is replaced by "This older view can't be shown." while the message text renders.

---

### User Story 3 - The primitives places and plugins need exist (Priority: P2)

The set covers what the places' slots need: an entity facet (a titled group of facts about one thing, with sources), stat rows (label, value, change), a posture-aware list (items that each carry how sure Ze is), a small series (sparkline), a keyed table (rows with stable keys and row actions), a timeline, and a card with actions. Each follows the design system, carries claim posture set by code where it shows a claim, and works at phone width.

**Why this priority**: 191b's slots render with these; without them every plugin would bend a table to its needs.

**Independent Test**: each primitive renders its fixture in every state (empty, normal, long text, phone width, posture tones) and passes its contract test.

**Acceptance Scenarios**:

1. **Given** an entity facet with facts and sources, **When** it renders, **Then** each fact shows its posture tone and its source.
2. **Given** a stat row with a change, **When** it renders, **Then** the value and the change direction are readable without color alone.
3. **Given** a keyed table with row actions, **When** a row's action is pressed, **Then** it runs the typed action for that row's key.
4. **Given** any primitive that shows a claim, **When** an agent's render tool supplies a posture, **Then** the posture is dropped and the code-set posture is used (as today).
5. **Given** an audit of the existing primitives, **When** this phase lands, **Then** each slot need above maps to exactly one primitive, and primitives no caller uses are removed.

---

### User Story 4 - One contract, one gallery (Priority: P2)

The primitive contract is defined once and checked on both sides with the same example trees. A gallery in development builds shows every primitive in every state, so a design or contract change is seen before it ships.

**Why this priority**: two hand-kept definitions drift; a shared fixture set is the cheapest guard.

**Independent Test**: changing a primitive's field on the server side without regenerating the client contract fails a test; every primitive has at least one fixture, and the gallery shows each one.

**Acceptance Scenarios**:

1. **Given** the shared fixture set, **When** the server and client contract tests run, **Then** both accept every valid fixture and reject every invalid one with the same field named.
2. **Given** a new primitive added on the server, **When** its fixture is missing, **Then** a test fails.
3. **Given** a development build, **When** the gallery is opened, **Then** every primitive shows in each of its fixture states.

### Edge Cases

- A tool action pressed twice quickly runs once (the button locks until the outcome, as buttons do today).
- A tool action while disconnected shows the "not connected" line and runs nothing.
- An action pressed on a tree that came from history (an old message) still runs through the gates; a tool that no longer exists reports "not available".
- A fallback table for an unknown type shows at most 12 fields and never shows nested objects as raw text.
- Long values wrap; nothing overflows at phone width.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Primitive actions MUST be typed: ask (send a question on the selected thread), tool (run a named tool with arguments), navigate (open a place route), and compose (run a composed-answer preset). String actions MUST be removed (pre-v1 hard cut).
- **FR-002**: A tool action MUST run on the server through the same tool path as chat, including the write-confirmation gate and the constraint veto, and MUST be recorded in the action ledger. The browser MUST never call a plugin's REST operation as a primitive action.
- **FR-003**: A tool action MUST name an agent and one of that agent's tools; the tool MUST be a write tool that opted in to screen actions. Anything else MUST be refused with a plain line. (The server cannot tell which tree a press came from; the opt-in keeps arbitrary one-click writes unreachable.)
- **FR-003a**: Agents' render tools MUST offer stat rows, keyed tables and sparklines; entity facet, posture-aware list and card-with-actions MUST be code-built only.
- **FR-004**: Every newly sent tree MUST carry a contract version. The client MUST render a same-major tree with unknown types through the fallback; a tree with no version or an older major version MUST render best effort as legacy, never failing the message it belongs to. A version MUST never be stamped onto a stored tree at read time.
- **FR-005**: An unknown primitive type MUST render as a table of its scalar fields with a note naming the type, with its known children rendered inside; it MUST never fail the rest of the tree.
- **FR-006**: The primitive set MUST cover: entity facet, stat rows, posture-aware list, series (sparkline), keyed table with row actions, timeline, and card with actions. An audit MUST map each need to one primitive and remove unused primitives.
- **FR-007**: Claim posture MUST remain set by code only on every primitive that shows a claim.
- **FR-008**: The contract MUST be defined once on the server and generated for the client; a shared fixture set MUST be validated by both sides, and every primitive MUST have at least one fixture.
- **FR-009**: A development-only gallery MUST show every primitive in each fixture state.
- **FR-010**: No plugin-supplied script MUST ever run in the browser; plugins contribute only data and descriptors.
- **FR-011**: Docs MUST describe the primitive set, typed actions, the version and fallback rules, and the gallery (ze-ui and ze-components READMEs, frontend, extending-Ze guide).

- **FR-012**: A screen confirmation MUST be replaced when a new turn starts on its thread, shown again after a reconnect, answered "That request expired." when unknown, time out with "Okay, I didn't …", and run at most once.
- **FR-013**: The outcome line MUST come from the tool's declared phrases, never from raw error text.

### Key Entities

- **Primitive**: a typed descriptor (type, fields, optional children, optional code-set posture).
- **Primitive action**: kind (ask, tool, navigate, compose) and its payload (question text; agent, tool name and arguments; route; preset id).
- **Contract version**: major and minor numbers carried by each tree.
- **Fixture**: a named example tree, valid or invalid, shared by server and client tests and the gallery.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No primitive action can change data without passing the write-confirmation gate (a test presses every action kind on every primitive that has actions).
- **SC-002**: A tree with an unknown primitive renders everything else in 100% of fixture cases.
- **SC-003**: Every slot need named in FR-006 has a primitive with fixtures in all its states.
- **SC-004**: The server and client contract tests agree on every shared fixture.
- **SC-005**: The suites, typecheck and lint pass.

## Assumptions

- Plugin modules, slots and the manifest change are 191b; this phase gives them their vocabulary.
- The existing claim posture rules (184) carry over unchanged.
- The gallery is a development tool, not a user-facing place.
