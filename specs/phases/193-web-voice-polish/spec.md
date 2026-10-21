# Feature Specification: Voice and Polish (W8)

**Feature Branch**: `193-web-voice-polish`

**Created**: 2026-10-17 (refined through `/speckit-specify` 2026-10-18)

**Status**: Implemented

**Input**: User description: "Voice and Polish (W8)": Maestro brief 2026-10-17, phase W8; overhaul plan sections c (Voice) and e (Phase W8); `direction-gmunk.md` ("it is also important to also have the voice orb, the ambience"); user decision 6 (voice input only; spoken output later).

**Governed by**: `DESIGN.md` (orb `listening` state, motion, reduced motion, 44 px targets), 183 (Ask bar with the disabled mic), 187 (Ask, single send path), 192 (transcription endpoint and voice context).

**Depends on**: 187 (Ask) and 192 (transcription). It runs after 186–191, because it closes the overhaul with a critique of every place.

**Doctrine functions served**: perception (voice input) and governance (the final honesty and accessibility pass across all places).

**Owning packages** (for planning): ze-web only. No backend, no migration.

## Context

Two things close the web overhaul. First, voice input. The Ask bar has had a disabled mic since 183 ("Voice input arrives later"), and 192 adds a transcription service that returns what Ze heard before the turn runs. Second, polish. The prototype (`/jarvis`) still carries the ambient sound and the last pieces the places were built from. It and its notes go, the design document is refreshed, and every place gets a final critique.

## Clarifications

### Session 2026-10-18 (user answers through the Maestro: all recommended)

- Q: Where does the ambience toggle live? → A: In the Presence module's head, beside the orb.
- Q: Push-to-talk from the keyboard? → A: Hold `v` to talk, only when no text field has focus; the mic button toggles anywhere.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Speak, correct, send (Priority: P1)

The user presses the mic in the Ask bar and talks. While they talk, the orb listens and visibly follows their voice level. When they stop, the orb shows Ze transcribing. The text lands in the Ask bar, focused and editable. The user fixes anything Ze misheard and sends it like a typed message. Ze knows the message came from voice and whether it was edited.

**Why this priority**: the voice orb is part of the direction the user set ("the voice orb, the ambience"). It is the only new capability in this phase.

**Independent Test**: with a mocked recorder and a mocked transcription call, press mic, feed levels, stop. The orb receives the levels, the transcript fills the bar, and sending carries the voice reference and the edited flag.

**Acceptance Scenarios**:

1. **Given** microphone permission, **When** the user presses the mic, **Then** recording starts, the orb enters listening and its gather follows the input level, and the mic shows a stop state with the elapsed time.
2. **Given** a recording, **When** the user stops it, **Then** Presence shows "transcribing", then the transcript fills the Ask bar, focused, with the caret at the end.
3. **Given** a transcript in the bar, **When** the user sends (edited or not), **Then** the message goes through the single send path with the voice reference, and the trace records whether the text was edited.
4. **Given** a recording reaches 115 seconds, **When** the limit is hit, **Then** recording stops on its own and transcription starts. A countdown shows for the last 10 seconds. (The client stops short of the service's 2-minute limit, because a recording's measured length can run slightly past the moment it stopped.)
5. **Given** transcription fails in a way that may pass on a second try (the recording could not be read, the speech model failed, or the network dropped), **When** the error returns, **Then** the bar shows the service's plain line with Retry, which re-sends the same recording without recording again. **Given** the recording is too large, too long or of a type the service refuses, **Then** the bar shows that line with Record again instead of Retry.
6. **Given** microphone permission is denied or no microphone exists, **When** the user presses the mic, **Then** a plain line says why, and the mic stays disabled with that reason as its label.
7. **Given** an empty transcript, **When** it returns, **Then** the bar shows "Ze heard nothing" and nothing is sent.

---

### User Story 2 - Ambience is a choice (Priority: P2)

A quiet ambient drone can be switched on. It is off by default, remembered per browser, and never starts by itself.

**Why this priority**: part of the stated direction, small, and it lets the prototype go.

**Independent Test**: toggle on, then off; reload and the choice is kept; with reduced motion set, a remembered "on" does not auto-start until the user presses play.

**Acceptance Scenarios**:

1. **Given** a fresh browser, **When** the app loads, **Then** no sound plays and the toggle reads off.
2. **Given** the user turns it on, **When** they reload, **Then** the toggle reads on, and sound starts only after the first user gesture (browser autoplay rules).
3. **Given** reduced motion, **When** the app loads with ambience remembered on, **Then** it does not start until the user presses the toggle.

---

### User Story 3 - Every place passes the final critique (Priority: P1)

World, Ask, Doing (index and both detail pages), Mind and Governance each score at least 30/40 on the design critique. Each passes the keyboard path and reduced motion, and each is captured at desktop and phone width with no console errors.

**Why this priority**: the overhaul's acceptance bar. It is one point higher than each place's own phase gate (29/40).

**Independent Test**: the critique runs and the captures are recorded per place in the floor's handoff note.

**Acceptance Scenarios**:

1. **Given** each place, **When** the critique runs, **Then** the score is at least 30/40 and the detector finds nothing.
2. **Given** keyboard only, **When** the user walks each place, **Then** every control is reachable with a visible focus ring and no trap.
3. **Given** reduced motion, **When** each place loads and a turn runs, **Then** no cascade, sweep or orb motion beyond opacity plays.

---

### User Story 4 - The prototype and leftovers are gone (Priority: P2)

Nothing named after the prototype remains in the web app. The design document describes the shipped system, not the prototype.

**Why this priority**: pre-v1 hard cuts; the prototype has done its job.

**Independent Test**: no route, file or import named `jarvis` remains in the web source and no prototype file remains; the design document's prototype-only notes are gone.

**Acceptance Scenarios**:

1. **Given** the cut, **When** the routes are listed, **Then** no `/jarvis` route exists, and an old prototype link shows the not-found page (pre-v1 hard cut; nothing outside the prototype linked to it).
2. **Given** the design refresh, **When** the document is read, **Then** Navigation and Components match the shipped places and primitives, and the prototype asides are removed.

### Edge Cases

- The user switches tab or place while recording: recording continues in the Ask bar's state until stopped. Closing the overlay stops it and transcribes.
- A second press of the mic while transcribing is ignored, and the mic shows busy.
- The browser cannot record any supported format: the mic is disabled with that reason.
- A displaced window (187) cannot record: the mic follows the Ask bar's disabled reason.
- Ambience and a voice recording at the same time: ambience ducks to silence while recording, so it never leaks into the transcript.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The Ask bar's mic MUST record audio in a format the transcription service accepts, show elapsed time, stop on press or at 115 seconds (with a countdown from 105), support hold-`v` to talk when no text field has focus, and upload the recording for transcription.
- **FR-002**: While recording, Presence MUST be listening with the live input level driving the orb, and MUST show "transcribing" while the upload runs.
- **FR-003**: The transcript MUST land in the Ask bar, focused and editable. Sending MUST carry the voice reference through the single send path, from Ask and from the overlay on every other place, and keep it when an unsent message returns to the bar; Ze records whether the sent text differs from the transcript (192 compares them on the server).
- **FR-004**: Failures MUST show plain lines: the service's own line for each refusal; Retry (reusing the same recording) only where a second try can succeed; Record again for too large, too long or unsupported; heard nothing; permission denied; no microphone; unsupported browser; voice off on this server.
- **FR-005**: An ambience toggle in the Presence module's head MUST play the existing quiet drone, off by default, remembered per browser, never auto-starting under reduced motion, ducked while recording.
- **FR-006**: The prototype MUST be removed: every prototype route and file, its surface notes under `.impeccable/surfaces`, and any interim file or leftover style mapping from 186–190.
- **FR-007**: The design document MUST be refreshed through the impeccable document flow (Navigation, Components; prototype-only notes removed).
- **FR-008**: Each place MUST score at least 30/40 on the critique, with keyboard and reduced-motion paths verified and captures at 1440 and 390 recorded.
- **FR-009**: Docs MUST cover voice input and ambience (frontend guide), and README screenshots MUST be refreshed.

### Key Entities

- **Recording**: audio in progress or finished, elapsed time, level stream, state (idle, recording, transcribing, failed, unavailable), and a kept copy of the last recording for Retry.
- **Ambience preference**: on or off, per browser.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Critique of at least 30/40 on every place, recorded in the floor's handoff note.
- **SC-002**: No route, file, import, test or design note named `jarvis` remains in the web source, its `.impeccable/surfaces` notes or the design document, and no prototype file remains. Exempt, as history: `.impeccable/plan/` (the overhaul plan and direction, where "Jarvis" names the product direction) and the phase rows in `AGENTS.md` and `specs/`.
- **SC-003**: A spoken message reaches the Ask bar as editable text in under 5 seconds for a 10-second recording on a normal connection.
- **SC-004**: The web suites, typecheck, build and lint pass.

## Assumptions

- Holding `v` records only when no text field has focus; releasing it stops and transcribes.
- The transcription service's limits (10 MB, 120 seconds, accepted types) are the ones 192 sets. The client stops at 115 seconds and picks a supported format.
- The ambience sound is the prototype's synthesized drone, moved as is.
- Spoken output stays out of scope (user decision 6).
