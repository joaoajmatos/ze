# Feature Specification: Voice Input Transport (B3)

**Feature Branch**: `192-voice-transport`

**Created**: 2026-10-17 (refined through `/speckit-specify` 2026-10-18)

**Status**: Draft

**Input**: User description: "Voice Input Transport (B3)": Maestro brief 2026-10-17, backend floor B3; overhaul plan section d, gap 5, and section c (Voice); user decision 6 ("Voice: input only in this overhaul (W8); spoken output later").

**Governed by**: phase 10 (multimodal input), `specs/arch/pre-v1-hard-cuts.md`, `SECURITY.md` (size limits, single user, API key).

**Depends on**: nothing unfinished. Must land before 193 (W8, the web voice control). Runs in parallel with the web phases.

**Doctrine function served**: perception (a new input channel into the same turn).

**Owning packages** (for planning): ze-core (transcription helper, the old audio path cut, trace field), ze-api (route, message context), ze-web regenerated client only. No migration: the trace is stored as JSON on `messages`.

## Context

The engine can already turn audio into text: when a turn's raw input carries audio bytes, the first graph step transcribes them with the configured speech model and marks the turn as voice. Nothing in the API fills that input today. The WebSocket `message` frame carries text only; the audio path was built for Telegram, which has since been removed. The web app also needs the transcript back before the turn runs, so the user can correct what Ze heard (overhaul plan section c). This phase replaces the dead audio-in-the-turn path with one voice path: transcribe first, let the user correct, then send an ordinary text turn marked as voice.

## Clarifications

### Session 2026-10-18 (user answers through the Maestro: all recommended)

- Q: Can a voice note be sent without the correction step? → A: No. Always transcribe, show the text, the user sends it.
- Q: What does the trace keep from a voice turn? → A: Modality, duration and an edited flag only; never the raw transcript.
- Q: If the server cannot tell a recording's length? → A: Reject it as unreadable ("I couldn't make out the recording").
- Q: Drop the language field? → A: Yes, drop it.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Transcribe, correct, then send (Priority: P1)

The user records a short voice note in the web app. Ze returns what it heard within a few seconds. The user fixes any mistake in the text and sends it as a normal message. Ze treats the turn as a voice turn and records, on the reply's trace, that it came from voice, how long the recording was, and whether the user edited the transcript.

**Why this priority**: it is the whole feature. Without it 193 has nothing to call, and voice input stays dead.

**Independent Test**: upload a recording to the transcription endpoint with a fake speech model, then send a message that carries the returned transcription reference. The reply's trace shows modality voice, the duration and `edited` true or false.

**Acceptance Scenarios**:

1. **Given** a supported recording (WebM, Ogg, MP4/M4A or WAV) of at most 10 MB and 120 seconds, **When** the client uploads it, **Then** it receives the transcript, the duration in seconds and a transcription reference.
2. **Given** a transcription reference from the last 10 minutes, **When** the user sends a message that names it (edited or not), **Then** the turn runs as a voice turn and the reply's trace records modality voice, the duration, and whether the sent text differs from the transcript.
3. **Given** a message that names an unknown or expired reference, **When** it is sent, **Then** the turn runs as an ordinary text turn and the trace records no voice section (the client's claim is not trusted).

---

### User Story 2 - Failures are plain and recoverable (Priority: P1)

When a recording cannot be used, the user is told why in plain words and can try again without recording again.

**Why this priority**: voice that fails silently breaks trust on the first try.

**Independent Test**: route tests for each failure with the fake speech model.

**Acceptance Scenarios**:

1. **Given** an unsupported file type, **When** it is uploaded, **Then** the response is "unsupported media type" with the accepted types listed.
2. **Given** a file over 10 MB or longer than 120 seconds, **When** it is uploaded, **Then** the response says "too large" (over 10 MB) or "too long" (over 2 minutes), with the limit in words.
3. **Given** the speech model fails or returns nothing, **When** a supported file is uploaded, **Then** the response is "I couldn't make out the recording" as an upstream failure, and nothing is stored.

---

### User Story 3 - Voice costs are tracked (Priority: P2)

Each transcription is counted in Ze's spend like any other model call, so Governance › Spend includes voice.

**Why this priority**: honesty about spend; small.

**Independent Test**: a transcription records one cost entry under the transcription flow.

**Acceptance Scenarios**:

1. **Given** a successful transcription, **When** spend is listed, **Then** one entry appears under the transcription flow with the speech model's name.

---

### Edge Cases

- A recording in a format the speech model does not accept directly is converted on the server first. If conversion fails, the user gets the "couldn't make out" failure, not a crash.
- A recording whose length cannot be determined (no length metadata and it cannot be decoded) is rejected as unreadable with the "couldn't make out" failure.
- An empty or silent recording returns an empty transcript. The client shows "Ze heard nothing" and does not send a message (193).
- The same reference sent twice: the second turn is also voice. The reference stays valid until it expires and is not consumed.
- A server restart drops unexpired references. Turns that name them run as text (Story 1, scenario 3).
- The connection-level API key protects the route like every other REST route.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The system MUST accept a recording upload of WebM, Ogg, MP4/M4A or WAV audio, at most 10 MB and at most 120 seconds, and return the transcript, the duration in seconds and a transcription reference.
- **FR-002**: The system MUST reject other types, oversized files, over-long recordings and recordings whose length cannot be read with distinct plain errors that state the limit or the accepted types. A server that lacks the audio tools MUST answer "Voice input is not available on this server".
- **FR-003**: The system MUST transcribe with the same speech model the engine uses today (the configured `whisper` model), and record the call in spend under the transcription flow.
- **FR-004**: The system MUST NOT store audio. The transcription reference MUST map, in memory and for 10 minutes, to the transcript and duration, so a later turn can record them without trusting the client.
- **FR-005**: A message that names a live transcription reference MUST run as a voice turn. Its trace MUST carry an input section: modality, duration in seconds, and whether the sent text differs from the transcript. The raw transcript MUST NOT be kept on the trace.
- **FR-006**: The old path that carries audio bytes inside a turn MUST be removed: raw-input audio fields, the graph state audio fields and the first step's audio branch. Image captioning in that step stays. Pre-v1 hard cut: one voice path.
- **FR-007**: The generated web client MUST expose the transcription call, and the message context MUST accept the voice reference in its schema.
- **FR-008**: Public docs MUST describe the transcription route, the voice message context and the speech-model configuration.

### Key Entities

- **Transcription**: the result of one upload: transcript, duration, reference, creation time; held in memory for 10 minutes; never persisted.
- **Voice input trace**: part of a reply's trace: modality, duration, edited.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Route tests cover success and each failure (unsupported type, too large, too long, speech model failure) with a fake speech model; the default test suites make no network call to a model.
- **SC-002**: After the cut, nothing in the engine or API carries audio bytes through a turn (no audio fields in raw input, graph state or the first step).
- **SC-003**: A voice turn's trace shows modality, duration and edited for 100% of turns that name a live reference, and for none that name an unknown one.
- **SC-004**: All Python suites and lint pass.

## Assumptions

- The speech model does not report a language, so the response carries none. The language field from the earlier draft is dropped.
- Duration is measured on the server from the uploaded file (container metadata or a decode). The client's claim is never used for the 120-second limit.
- The server image gains the audio tools needed to measure length and convert browser formats. Planning found the ze-api image has none today, so the engine's existing conversion step would fail in production. A server without them answers "Voice input is not available on this server".
- References live in one process. A single-user, single-instance deployment makes that enough.
- Spoken replies, streaming transcription and wake words are out of scope (user decision 6).
