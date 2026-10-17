# Feature Specification: Voice and Polish (W8)

**Feature Branch**: `193-web-voice-polish`

**Created**: 2026-10-17

**Status**: Draft (spec level; plan and tasks follow once scheduled)

**Input**: Maestro brief 2026-10-17, phase W8; overhaul plan sections c (Voice), e (Phase W8); `direction-gmunk.md` ("it is also important to also have the voice orb, the ambience").

**Governed by**: `DESIGN.md` (orb `listening` and `speaking` states, motion, reduced motion), user decision 6 (voice input only).

**Depends on**: 187 (Ask), 192 (B3 transcription endpoint). Runs after 186–191 because it closes the overhaul with a critique of every place.

**Doctrine functions served**: perception (voice input) and governance (the final honesty and accessibility pass across all places).

---

## Overview

Two things close the overhaul. First, voice input: the mic chip in the Ask bar records, the orb listens with the live input level, the recording is transcribed (192), and the transcript lands in the Ask bar for the user to correct before sending. Second, polish: ambience as a Governance toggle, a final impeccable critique of every place, a `DESIGN.md` refresh, and deletion of the prototypes.

## User Scenarios & Testing *(mandatory)*

1. **Speak, correct, send (P1).** Press mic (or hold `v`): the orb goes `listening`, its gather and inner ring follow the input level (Web Audio `AnalyserNode`); stop: "transcribing" phrase; the transcript fills the Ask bar, focused, editable; Enter sends with `context.voice`. Permission denied → a plain message and the mic disabled with the reason.
2. **Ambience is a choice (P2).** Governance › Connections (or a Presence setting) toggles the ambient sound from the prototype's `useAmbience`; off by default; persists per browser; reduced-motion users get no auto-start.
3. **Every place passes the final critique (P1).** Impeccable critique ≥ 30/40 on World, Ask, Doing (index and both details), Mind, Governance; reduced-motion and keyboard paths verified on all five; captures at 1440 and 390 with no console errors.

## Requirements *(mandatory)*

- **FR-001**: `features/voice-input` (MediaRecorder, level meter feeding presence `listening` with amplitude, upload via the generated `transcribeVoice`, retry on failure); the 183 disabled mic control becomes live.
- **FR-002**: `features/ambience` moved from `pages/jarvis/hud/useAmbience.ts`; toggle in Governance.
- **FR-003**: `DESIGN.md` refresh through the impeccable `document` flow (Navigation, Components, the prototype-only notes removed).
- **FR-004**: Hard cuts: `pages/jarvis` (all of it) and its `/jarvis` routes, `apps/ze-web/.impeccable/work/cap` prototypes, any remaining interim file or Tailwind remap left by 186–190.
- **FR-005**: Docs: `docs/frontend.md` (voice, ambience), README screenshots.

## Success Criteria *(mandatory)*

- **SC-001**: Critique ≥ 30/40 on every place, recorded in the floor's Handoffs note.
- **SC-002**: No route or file named `jarvis` or `proto` remains in `apps/ze-web/src`.
- **SC-003**: `make test-web`, `make typecheck-web`, `make web-build`, lint pass.

## Out of Scope

- Spoken output (decision 6).

## Owning packages

ze-web only; no backend, no migration.
