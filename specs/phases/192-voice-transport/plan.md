# Implementation Plan: Voice Input Transport (B3)

**Branch**: `192-voice-transport` | **Date**: 2026-10-18 (revised after Gauge's review V-1..V-9) | **Spec**: [spec.md](./spec.md)

**Input**: spec.md with the 2026-10-18 clarifications (user: all recommended), `main` at ab334b60.

## Summary

There will be one voice path: transcribe first, then the user corrects the text, then an ordinary text turn runs marked as voice.

- **Route.** `POST /api/v0/voice/transcriptions` (`transcribeVoice`) takes a recording. It checks the type and the size (a `Content-Length` pre-check before parsing, then a cap on the read). It measures the length on the server in two steps: the container's duration, then a packet scan, because MediaRecorder WebM carries no duration. Unreadable or over 120 s is rejected. It transcribes with the configured `whisper` model under the `transcription` cost flow and returns the transcript, the duration and a reference.
- **Reference.** It lives in a bounded in-process registry on the ze-api container for 10 minutes. A message whose context names a live reference becomes a voice turn. The reference is read by a small helper in `ws/turns.py`, not by `ScreenContext`. The trace carries `input { modality, duration_s, edited }`, and `edited` is computed on the server. The message store parses `input` back on read.
- **Hard cut.** The dead audio-in-the-turn path is removed: `RawInput.audio`/`audio_mime`, the graph state audio fields and the `preprocess` audio branch.
- **Image.** The ze-api image gains `ffmpeg`, which it lacks today.

## Technical Context

**Language/Version**: Python 3.12.
**Primary Dependencies**: FastAPI `UploadFile` (`python-multipart` is in `uv.lock`; the workspace and data upload routes use it); `ffmpeg`/`ffprobe` binaries (new in the ze-api image; a developer prerequisite, documented beside yt-dlp in `docs/ingestion.md`'s system-binaries section and linked from `docs/configuration.md`).
**Storage**: none. No migration: the trace is JSONB on `messages`; the registry is in memory.
**Testing**: pytest; fake `transcribe` client; patched subprocess for unit tests; one real-ffprobe test (`@pytest.mark.slow`, skipped when the binary is absent) over a non-seekable WebM fixture made with `ffmpeg … -f webm pipe:1`, and a fragmented MP4 fixture.
**Target Platform**: Linux container (Fly/docker-compose) and macOS dev.
**Project Type**: web service (backend only; ze-web regenerated client only).
**Performance Goals**: a 10 s recording transcribed in under 5 s end to end on a normal connection (193 SC-003). The probe adds under 200 ms on the duration path and under 500 ms on the packet-scan fallback for a 120 s WebM.
**Constraints**:
- **Size.** 10 MB, enforced twice: a `Content-Length` pre-check returns 413 before multipart parsing (an ASGI check scoped to this path), and the handler stops reading past the cap. A chunked request with no length is bounded by the handler cap only. Starlette may still spool up to the cap to a temporary file, which is deleted when the request ends.
- **Length.** 120 s, from the server probe.
- **Storage.** No audio is kept.
- **Subprocesses.** Each run is forced to the demuxer named by the validated type (`-f webm|ogg|mp4|wav`), with `-protocol_whitelist pipe`, and has a timeout: 10 s for the probe and 30 s for the conversion. On timeout the process is killed.
- **Auth.** The API key protects the route.

**Scale/Scope**: single user, single instance.

## Constitution Check

| Principle | Check |
|---|---|
| I Spec-first | spec with clarifications; plan, research, data model, contract, quickstart, checklists, tasks. |
| II Single-user | No per-user scoping; the registry is process-wide. |
| III Layered packages | Audio tools and the transcription helper in ze-core (`openrouter/audio.py`, `voice.py`); `VoiceInput` in ze-agents beside `RawInput`; route, registry, the length guard and WS wiring in ze-api. `ScreenContext` only learns that `voice` is a known key. No plugin is touched. |
| IV Typed Python | Dataclasses `VoiceInput`, `InputTrace`, `Transcription`. Errors are `ZeError` subclasses under `VoiceInputError`: `AudioTooLongError` (length), `AudioUnreadableError`, `AudioToolMissingError`, `TranscriptionFailedError`. `to_mp3`'s bare `RuntimeError` becomes `AudioUnreadableError`. |
| V Tests | Fail-first; no real model in default suites; the real-ffprobe test is slow-marked. |
| VI Persistence | No schema change. |
| VII One gateway | `OpenRouterClient.transcribe`. |
| VIII Hard cuts | Audio fields and the `preprocess` audio branch deleted; no shim. |

Gate: pass.

## Blast radius

From `graphify affected` (after `graphify update .`) and `rtk proxy grep`:

| Symbol | Callers | Change |
|---|---|---|
| `RawInput.audio`, `.audio_mime` | only `ze_core/container.py:99-102` passes them; every other caller builds `RawInput(text=...)` (`invoke_retry_turn`, `make_graph_input_from_raw_text`, ws `turns.py`, eval router, `wiring/container.py`, `wiring/workflow_graph.py`, `ze_automation/bootstrap.py`) | Deleted; `RawInput.voice` added. |
| `AgentState.audio_data`, `.audio_mime` | `preprocess`, `make_graph_input`, `tests/orchestration/test_state_serde.py:193-194` | Deleted; `voice_input` added. |
| `preprocess` audio branch | graph; `tests/orchestration/nodes/test_preprocessing.py:29,57` | Deleted; image captioning kept. |
| `make_graph_input` (`turn.py:34-40`) | the single state builder | Modality `voice` and `voice_input` when `raw.voice`. `input_modality` is read only for `image` (`memory.py:252`, `context.py:318`), so `voice` changes no other behaviour. |
| `_normalise_audio_format`, `_to_mp3` (`client.py`) | `transcribe`, `preprocess` | Moved to `openrouter/audio.py`; `to_mp3` raises `AudioUnreadableError`, with a timeout. |
| `record_trace` (`nodes/trace.py:77`) | graph | Sets `MessageTrace.input`. |
| `_parse_trace` (`conversation/messages/store.py:285-345`) | `get_trace`, `get_traces`, history hydration, REST `getMessageTraces` | Parses `input` (V-2); old rows without it parse as `None`. |
| `ScreenContext.from_wire` `known` keys (`ze_agents/screen.py:112-125`) | ws `turns.py`, retry | Gains `voice` so no warning is added. `ScreenContext` fields, `is_empty`, `to_wire` and `resolve_screen` are unchanged (V-3). |
| `handle_message` (`ws/turns.py:39`) | `ws/endpoint.py` | Reads `container.transcription_registry` (the container is already an argument). |
| `handle_retry` (`ws/turns.py:527-537`) | retry frames | Unchanged: a retry replays the stored text as a text turn (spec edge case, V-3). |
| `ZeContainer` (`ze_api/wiring/container.py`) | endpoint, routes | Gains `transcription_registry`. |
| `MessageTraceResponse`, `WsTraceUpdateFrame`, `WsScreenContext` | trace REST, native interface, send path | Gain `input`, and `voice` on the context. |
| `apps/ze-api/Dockerfile` | image | `ffmpeg`. |

## Design

### ze-agents

- `interface/types.py`: `VoiceInput(duration_s: float, edited: bool)`; `RawInput.voice: VoiceInput | None = None`; the audio fields are removed.
- `errors.py`: `VoiceInputError(ZeError)` and the six subclasses above.
- `screen.py`: `"voice"` added to the `known` key set only. The wire key belongs to the voice helper, not to the screen context.

### ze-core

- **`openrouter/audio.py`:**
  - `normalise_audio_format` and `to_mp3`, moved. `to_mp3` gets an `-f` from the mime, `-protocol_whitelist pipe` and a 30 s timeout, and raises `AudioUnreadableError`.
  - `probe_duration(data, container_format) -> float`, in two steps, each with `-f <container_format> -protocol_whitelist pipe` and a 10 s timeout:
    1. `ffprobe -v error -show_entries format=duration -of csv=p=0 pipe:0`. A positive number is returned.
    2. On `N/A`, empty or non-numeric output: `ffprobe -v error -select_streams a:0 -show_entries packet=pts_time,duration_time -of csv=p=0 pipe:0`, returning the last packet's `pts_time + duration_time`.
    
    No packets, or a non-zero exit on both steps, raises `AudioUnreadableError`. A missing binary raises `AudioToolMissingError`. A timeout kills the process and raises `AudioUnreadableError`.
  - The container format comes from the validated mime: `webm`, `ogg`, `mp4` (for mp4 and m4a) or `wav`.
- **MP4.** Safari's MediaRecorder writes fragmented MP4, which probes from a pipe. A progressive MP4 with `moov` at the end also probes from a pipe (checked in review, 5.0 s); the packet scan covers anything else.
- **`voice.py`:** `Transcription(text, duration_s)` and `async transcribe_audio(client, data, mime, *, model, max_seconds=120) -> Transcription`. Steps:
  1. Probe; over the limit raises `AudioTooLongError` before any model call.
  2. Set the flow and agent context (`transcription`, `whisper`).
  3. Call `client.transcribe(data, mime, model=model, duration_seconds=d)` (the client normalises and converts).
  
  An empty reply returns `""`. Any model error raises `TranscriptionFailedError`, and the cause (status, class) is logged as `voice_transcription_failed`.
- **`conversation/turn.py`:** `make_graph_input` sets `input_modality = "voice"` and `voice_input = {"duration_s", "edited"}` when `raw.voice` is set, else `None`. It resets each turn like the screen keys.
- **`conversation/messages/types.py`:** `InputTrace(modality, duration_s=None, edited=None)`; `MessageTrace.input`.
- **`conversation/messages/store.py`:** `_parse_trace` reads `input`, filtering to the known fields; it is `None` when absent.
- **`orchestration/nodes/trace.py`:** `record_trace` sets `input` for voice turns. The transcript is never on the trace.
- **`container.py`:** `invoke_raw`'s audio kwargs are deleted.

### ze-api

- **`api/v0/voice/router.py`:** `POST /voice/transcriptions`, `operation_id="transcribeVoice"`, `response_model=TranscriptionResponse`, summary, description, `require_api_key`. Steps:
  1. Validate the type before `;` against `audio/webm`, `audio/ogg`, `audio/mp4`, `audio/m4a`, `audio/x-m4a`, `audio/wav`, `audio/x-wav`.
  2. Read in 1 MB chunks up to 10 MB.
  3. Call `transcribe_audio` with `models.whisper` (fallback `MODEL_WHISPER`).
  4. Register the result.

  Errors map as follows:
  - 413: size over 10 MB (raised by the route and the length guard) or `AudioTooLongError` ("too long… 2 minutes").
  - 415: unsupported type.
  - 422: `AudioUnreadableError`.
  - 502: `TranscriptionFailedError` ("I couldn't make out the recording"; the cause is logged).
  - 503: `AudioToolMissingError` (logged as `voice_ffmpeg_missing`).
  - A missing `file` part or a non-multipart body: a plain 422 "Send the recording as a file named file." through a route-scoped handler, not FastAPI's list-shaped detail.
- **`api/v0/voice/limits.py`:** an ASGI middleware scoped to `/api/v0/voice/transcriptions`. A `Content-Length` over 10 MB plus a 64 KB multipart allowance returns 413 before the body is read. It is registered in `ze_api/main.py` beside the existing middleware.
- **`ze_api/voice/registry.py`:** `TranscriptionRegistry(clock, ttl=600, max_entries=100)`. `register` returns a 32-character hex id and drops the oldest entry past the cap. `lookup` returns `(text, duration_s)` or `None`. Expired entries are swept on each call.
- **`ze_api/wiring/container.py`:** `self.transcription_registry = TranscriptionRegistry(...)`. The route reads it via `request.app.state.container`; `handle_message` reads `container.transcription_registry`.
- **`api/ws/turns.py`:** `_voice_input(context_wire, text, registry) -> VoiceInput | None` reads `context.voice.transcription_id` (a string of at most 64 characters) from the raw wire dict. A live id builds `RawInput(text=text, voice=VoiceInput(d, edited=text.strip() != stored.strip()))`. An unknown or expired id logs `ws_voice_ref_unknown` and the turn stays text. `ScreenContext` handling is unchanged.
- **Schemas:** `api/ws/schemas.py` gets `WsVoiceRef` on `WsScreenContext.voice` (the wire shape the generated client sends), `InputTraceResponse`, and `input` on `WsTraceUpdateFrame`. `api/v0/messages/{schemas,router}.py` get `input`.
- **`Dockerfile`:** `ffmpeg` added to the apt line.
- `make codegen`.

## Project Structure

### Documentation (this feature)

```text
specs/phases/192-voice-transport/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md, tasks.md
├── contracts/transcribe-voice.md
└── checklists/{requirements.md,security.md}
```

### Source Code

```text
core/contracts/ze-agents/ze_agents/{interface/types.py,screen.py,errors.py}
core/engine/ze-core/ze_core/openrouter/{audio.py (new),client.py}
core/engine/ze-core/ze_core/voice.py (new)
core/engine/ze-core/ze_core/conversation/{turn.py,messages/types.py,messages/store.py}
core/engine/ze-core/ze_core/orchestration/{state.py,nodes/preprocessing.py,nodes/trace.py}
core/engine/ze-core/ze_core/container.py
apps/ze-api/ze_api/api/v0/voice/{__init__,router,schemas,limits}.py (new) ; apps/ze-api/ze_api/api/v0/__init__.py ; apps/ze-api/ze_api/main.py
apps/ze-api/ze_api/voice/registry.py (new) ; apps/ze-api/ze_api/wiring/container.py
apps/ze-api/ze_api/api/ws/{turns,schemas}.py ; apps/ze-api/ze_api/api/v0/messages/{schemas,router}.py
apps/ze-api/Dockerfile ; packages/ze-client/src/generated/*
```

## Docs touched

- `docs/architecture.md`: lines ~61-62 and ~175 ("Normalize audio/image input" → image only); ~692 and ~700-701 (the "Voice note" row: transcription route then a text turn); the REST table gains `transcribeVoice`.
- `docs/configuration.md` (~177): `whisper` is used by the transcription route; link to the ffmpeg prerequisite.
- `docs/ingestion.md`: the system-binaries section (where yt-dlp is documented, ~203) gains ffmpeg/ffprobe.
- `docs/native-interface.md`: the route, `context.voice`, the trace `input`.
- `docs/package-architecture.md` (~163) and `core/engine/ze-core/README.md` (~29): module tables gain `voice.py` and `openrouter/audio.py`.
- `docs/testing.md`: the slow real-ffprobe test.
- `AGENTS.md`: phase row 192, the graph-flow line ("preprocess (image → caption)"), and `ze_core/voice.py` in the layout tree if it lists module files; `specs/README.md` row 192.

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first; T002–T004):
- **ze-agents:** `VoiceInput`, `RawInput.voice`, the voice errors, and `"voice"` in the screen `known` keys.
- **ze-core:** `InputTrace` and `MessageTrace.input`, plus `_parse_trace` reading `input` (V-2). `voice.py` stub.
- **ze-api schemas:** `TranscriptionResponse`, `InputTraceResponse`, `WsVoiceRef`, and `input` on both trace models.
- **Route stub:** returns 501, registered.
- `make codegen`.
- **Fixtures:** a non-seekable WebM (`ffmpeg -f lavfi -i sine=duration=3 -c:a libopus -f webm pipe:1`), a fragmented MP4 (`-movflags frag_keyframe+empty_moov`), a 1 s WAV, the generator script beside them, `fake_transcribe_client`, and `ffprobe_stub`.

| Lane | Model / role | Owns (disjoint) | Tasks | Starts after | Reviewer |
|---|---|---|---|---|---|
| lead | Sonnet ENG lead | `ze_agents/{screen.py,errors.py}`, `ze_agents/interface/types.py` (until handover), `ze_core/conversation/messages/{types.py,store.py}`, `ze_core/voice.py` (stub until handover), `api/v0/messages/{schemas,router}.py`, `api/ws/schemas.py`, `api/v0/voice/schemas.py`, `api/v0/__init__.py`, `packages/ze-client/src/generated/*`, fixtures; merges, the post-merge test clean-up (T013 edits api-lane tests after merge) and gates | T001–T004, T013, T014 | - | Gauge |
| core | Sonnet ENG | `ze_core/openrouter/{audio.py,client.py}`, `ze_core/voice.py` (body), `ze_core/conversation/turn.py`, `ze_core/orchestration/{state.py,nodes/preprocessing.py,nodes/trace.py}`, `ze_core/container.py`, `ze_agents/interface/types.py` (audio-field removal after handover), and their tests | T005–T008 | contract step | floor Reviewer |
| api | Sonnet ENG | `api/v0/voice/{router,limits}.py`, `ze_api/main.py` (middleware line), `ze_api/voice/registry.py`, `ze_api/wiring/container.py` (registry line), `api/ws/turns.py`, `apps/ze-api/Dockerfile`, and their tests | T009–T012 | contract step | floor Reviewer |
| docs | Haiku DOCS | the files in "Docs touched" | T015–T017 | T013 | floor Reviewer |

**Rules**: one lane per file at a time. `ze_core/voice.py` and `ze_agents/interface/types.py` pass from `lead` to `core` after the contract step. Lane `api` codes against the `transcribe_audio` stub signature and patches it until `core` merges. `lead` merges `core`, then `api`. There is no JR lane: every task crosses a contract or wraps a subprocess.

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| `ffmpeg` in the image | Server-side length (clarification Q3) and WebM conversion; the image has neither tool today. | A pure-Python parser (partial coverage, a new dependency); the client's length (rejected). |
| Two-step probe | MediaRecorder WebM has no duration header; `format=duration` prints `N/A` (reproduced in review). | Rejecting WebM (breaks Chrome and Firefox); trusting the client. |
| Path-scoped length guard | Starlette spools the multipart body before the handler runs, so an in-handler cap alone does not bound disk use. | A global body limit (would cap other routes). |
| Bounded in-process registry | The turn must know the transcript without trusting the client (FR-004). | A table (persistence for a 10-minute value). |
