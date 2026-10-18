# UX and Accessibility Requirements Checklist: Voice and Polish (W8)

**Purpose**: check that the voice, ambience and critique requirements are complete, clear and testable before implementation.
**Created**: 2026-10-18
**Feature**: [spec.md](../spec.md)

## Requirement Completeness

- [x] CHK001 Are the mic's states (idle, recording, transcribing, failed, unavailable) each specified with label, icon and enabled state? [Completeness, Plan §features/voice-input]
- [x] CHK002 Is each failure line specified word for word, with which ones offer Retry? [Completeness, Spec §FR-004, Plan]
- [x] CHK003 Is the behaviour defined when a transcript arrives while the draft already holds text? [Gap → Plan §features/ask-bar: append after one space]
- [x] CHK004 Is what Retry re-sends defined (the same recording, no new recording)? [Clarity, Spec US1-5]
- [x] CHK005 Are the hold-`v` exclusions (modifiers, repeat, text fields, contenteditable, dialogs) all listed? [Completeness, Plan, T008]
- [x] CHK006 Is a very short `v` tap defined (discarded under 300 ms)? [Edge Case, Research R5]

## Requirement Clarity

- [x] CHK007 Is "the orb follows the level" bounded (scale factor, smoothing, reduced-motion behaviour)? [Clarity, Plan §shared/ui]
- [x] CHK008 Is "edited" defined, and is it clear who computes it? [Clarity, Spec §FR-003, Research R3]
- [x] CHK009 Is the 30/40 bar tied to a named tool and per-place list (including both Doing detail pages)? [Measurability, Spec US3, T012]

## Accessibility

- [x] CHK010 Are 44 px targets required for the mic, Retry, Dismiss and the ambience toggle? [Coverage, T008, T009]
- [x] CHK011 Are screen-reader semantics specified (`aria-pressed`, `aria-busy`, `role="status"` line, reason as accessible name)? [Coverage, T008]
- [x] CHK012 Is reduced motion specified for the orb level, the ambience start, and the per-place turn walk? [Coverage, Spec US2-3, US3-3]

## Scenario Coverage

- [x] CHK013 Are permission denied, no microphone, unsupported browser and server-off (503) each a distinct requirement? [Coverage, Plan]
- [x] CHK014 Is recording across place changes, overlay close and window blur defined? [Edge Case, Spec Edge Cases, T004, T008]
- [x] CHK015 Is the expired transcription id (192's 10-minute window) covered? [Edge Case: the turn runs as a text turn per 192's contract; no client behaviour needed]

## Dependencies

- [x] CHK016 Are the dependencies on 192's generated client (`transcribeVoice`, `WsScreenContext.voice`) checked before building? [Dependency, T001]
