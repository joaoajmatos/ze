# Research: Voice Input Transport (B3)

## R1. Measuring the recording length on the server
- **Decision**: `ffprobe -show_entries format=duration` on the uploaded bytes (stdin), with ffmpeg installed in the ze-api image.
- **Rationale**: Clarification Q3 says a recording whose length cannot be told is rejected, so the length must come from the server. ffprobe reads WebM, Ogg, MP4 and WAV headers in one call. The engine already shells out to ffmpeg (`to_mp3`), but the image does not install it (`apps/ze-api/Dockerfile` installs only `libgomp1`), so conversion fails in production today.
- **Alternatives**: a pure-Python container parser (mutagen-style): another dependency, and WebM from MediaRecorder often lacks a duration header, which ffprobe handles by scanning. Trusting the client's length: rejected by Q3.

## R2. Formats
- **Decision**: accept `audio/webm`, `audio/ogg`, `audio/mp4`, `audio/m4a`/`audio/x-m4a`, `audio/wav`/`audio/x-wav`, with any codec parameter. The model takes mp3, wav, ogg, flac and m4a directly (`_TRANSCRIBE_FORMATS`). WebM is converted to mp3 by `to_mp3`.
- **Rationale**: Chrome and Firefox record `audio/webm;codecs=opus`, Safari records `audio/mp4`. `normalise_audio_format` maps mp4 to m4a.

## R3. Where the transcript lives between upload and send
- **Decision**: an in-process registry in ze-api (`app.state`) with a 10-minute TTL, keyed by a random hex id.
- **Rationale**: FR-004 forbids storing audio and requires the turn to read the duration and transcript without trusting the client. A single-user, single-instance deployment needs nothing shared. A restart loses references, and turns that name them run as text (spec edge case).
- **Alternatives**: a table (persistence for a 10-minute value); signing the transcript into a client token (lets the client carry text the server must still compare; more code for no gain).

## R4. Carrying the voice reference on the message
- **Decision**: `context.voice.transcription_id` on the existing `message` frame context (`WsScreenContext`), beside `workspace_placed` and `compose`, which are also non-screen fields there.
- **Rationale**: there is one frame and one parser (`ScreenContext.from_wire`, lenient), and the 195 send path already merges this context.
- **Alternatives**: a new frame type (a second send path; violates 187 SC-001's single send path).

## R5. Edited flag
- **Decision**: computed on the server: `text.strip() != stored_transcript.strip()`.
- **Rationale**: the client's claim is not trusted (spec story 1, scenario 3); a case or space-only change still counts as edited, except leading and trailing whitespace.

## R6. Cost tracking
- **Decision**: `transcribe_audio` sets the flow and agent context (`transcription`, `whisper`) exactly as the `preprocess` branch did, so `CostTracker` records it under the transcription flow. `duration_seconds` is passed for audio pricing (`audio_seconds`).
