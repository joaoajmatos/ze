# Research: Voice Input Transport (B3)

## R1. Measuring the recording length on the server
- **Decision**: ffprobe in two steps, with ffmpeg installed in the ze-api image. Step 1 is `format=duration`. Step 2, when step 1 prints `N/A`, is a packet scan (`-select_streams a:0 -show_entries packet=pts_time,duration_time`), returning the last `pts_time + duration_time`. Each step forces the demuxer from the validated type (`-f`), sets `-protocol_whitelist pipe`, and has a 10 s timeout.
- **Rationale**: Clarification Q3 requires a server-side length. MediaRecorder WebM (Chrome, Firefox) carries no Duration and no cues: `format=duration` prints `N/A` from a pipe (reproduced in review: a 3 s libopus WebM gave `N/A`; the packet scan gave 2.994 + 0.02). Fragmented MP4 (Safari's MediaRecorder) probes from a pipe. A progressive MP4 with `moov` at the end does not. It is rejected as unreadable rather than written to disk, and the spec states that edge case. The image installs only `libgomp1` today (`apps/ze-api/Dockerfile`), so the existing `to_mp3` already fails in production.
- **Alternatives**: decoding the whole file (`ffmpeg -i pipe:0 -f null -`, slower than the packet scan); writing a temp file for every probe (disk writes for every upload); a pure-Python parser (partial coverage); trusting the client (rejected by Q3).

## R2. Formats
- **Decision**: accept `audio/webm`, `audio/ogg`, `audio/mp4`, `audio/m4a`/`audio/x-m4a`, `audio/wav`/`audio/x-wav`, with any codec parameter. The model takes mp3, wav, ogg, flac and m4a directly (`_TRANSCRIBE_FORMATS`). WebM is converted to mp3 by `to_mp3`.
- **Rationale**: Chrome and Firefox record `audio/webm;codecs=opus`, Safari records `audio/mp4`. `normalise_audio_format` maps mp4 to m4a.

## R3. Where the transcript lives between upload and send
- **Decision**: an in-process registry in ze-api (`app.state`) with a 10-minute TTL, keyed by a random hex id.
- **Rationale**: FR-004 forbids storing audio and requires the turn to read the duration and transcript without trusting the client. A single-user, single-instance deployment needs nothing shared. A restart loses references, and turns that name them run as text (spec edge case).
- **Alternatives**: a table (persistence for a 10-minute value); signing the transcript into a client token (lets the client carry text the server must still compare; more code for no gain).

## R4. Carrying the voice reference on the message
- **Decision**: `context.voice.transcription_id` on the existing `message` frame context, read by a small helper in `ws/turns.py` from the raw wire dict. `ScreenContext` only adds `voice` to its known keys. It does not carry the reference, so a voice-only context stays empty, adds no Screen stage to the trace, and is not persisted as screen context (review V-3).
- **Rationale**: there is one frame and one parser (`ScreenContext.from_wire`, lenient), and the 195 send path already merges this context.
- **Alternatives**: a new frame type (a second send path; violates 187 SC-001's single send path).

## R5. Edited flag
- **Decision**: computed on the server: `text.strip() != stored_transcript.strip()`.
- **Rationale**: the client's claim is not trusted (spec story 1, scenario 3); a case or space-only change still counts as edited, except leading and trailing whitespace.

## R6b. Upload size enforcement
- **Decision**: a path-scoped ASGI check refuses a `Content-Length` over 10 MB plus 64 KB of multipart overhead with 413 before Starlette parses the body; the handler also stops reading past 10 MB (chunked uploads).
- **Rationale**: Starlette spools the multipart body to a temporary file before the route runs, so an in-handler cap alone does not bound what an authenticated client can push to disk (review V-4).

## R6c. Subprocess safety
- **Decision**: the demuxer is forced from the validated type, `-protocol_whitelist pipe` is set, the probe has a 10 s timeout and the conversion 30 s, a timed-out process is killed, and `to_mp3` raises `AudioUnreadableError` (it raised a bare `RuntimeError`).
- **Rationale**: untrusted bytes must not choose a demuxer or protocol, and a hung ffprobe must not hold the request.

## R6. Cost tracking
- **Decision**: `transcribe_audio` sets the flow and agent context (`transcription`, `whisper`) exactly as the `preprocess` branch did, so `CostTracker` records it under the transcription flow. `duration_seconds` is passed for audio pricing (`audio_seconds`).
