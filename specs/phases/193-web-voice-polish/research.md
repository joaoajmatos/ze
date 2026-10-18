# Research: Voice and Polish (W8)

## R1. Recording format
- **Decision**: prefer `audio/webm;codecs=opus`, then `audio/ogg;codecs=opus`, then `audio/mp4`, chosen with `MediaRecorder.isTypeSupported`; 64 kbit/s; 250 ms timeslice.
- **Rationale**: these are what Chrome/Edge (WebM), Firefox (WebM or Ogg) and Safari (fragmented MP4) record. All are on 192's accepted list (codec parameters allowed), and 192 measures WebM and fragmented MP4 durations by packet scan. 120 s at 64 kbit/s is about 1 MB.
- **Alternatives**: WAV through an AudioWorklet (10× larger, more code); a recorder library (new dependency for no gain).

## R2. Level metering
- **Decision**: an `AnalyserNode` on the same stream, RMS of the time-domain samples mapped from −60..−10 dBFS to 0..1, written to a module ref, read by the orb in its own frame.
- **Rationale**: no React state per frame; the orb already runs a rAF loop.
- **Alternatives**: the level in Zustand or the presence store (re-renders every frame).

## R3. Edited flag
- **Decision**: the client sends only `context.voice.transcription_id`; 192 compares the sent text with the stored transcript and writes `input.edited` on the trace.
- **Rationale**: 192's contract already does this, and a client-side flag could disagree with the server.

## R4. Where voice lives in FSD
- **Decision**: a new feature slice `features/voice-input`; `widgets/app-shell` wires it into `AskBar` through `renderMic` and into the ask-overlay store through `registerTranscript`.
- **Rationale**: features may not import features. The shell is already the place that wires the Ask bar to the send path.
- **Alternatives**: voice inside `features/ask-bar` (one slice doing two jobs; ambience would still need a slot in Presence).

## R5. Push-to-talk key
- **Decision**: hold `v` (clarification Q2) with no modifiers, outside text fields and dialogs; a hold under 300 ms is discarded.
- **Rationale**: a tap would otherwise upload a fraction of a second and come back "heard nothing" or 422.

## R6. Ambience autoplay
- **Decision**: a remembered "on" arms the drone; the first `pointerdown`/`keydown` starts it. Under reduced motion only a press of the toggle starts it.
- **Rationale**: browsers block audio before a gesture; the spec forbids auto-start under reduced motion.

## R7. The `/jarvis` link
- **Decision**: add `/jarvis` to the existing redirect table → `/` (spec US4 scenario 1).
- **Rationale**: the table is the one mechanism for old routes since 183; it is not a new shim.

## R8. Critique bar
- **Decision**: `/impeccable critique` per place, ≥ 30/40 and a clean detector; `/impeccable document` for DESIGN.md.
- **Rationale**: the same tooling 186–190 used for their 29/40 gates, one point higher here (spec US3).
