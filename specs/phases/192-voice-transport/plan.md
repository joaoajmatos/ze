# Implementation Plan: Voice Input Transport (B3)

**Branch**: `192-voice-transport` | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md with the 2026-10-18 clarifications (user: all recommended), `main` at ab334b60.

## Summary

There will be one voice path: transcribe first, then the user corrects the text, then an ordinary text turn runs marked as voice.

- A new REST route `POST /api/v0/voice/transcriptions` (`transcribeVoice`) takes a recording. It checks type and size, probes the length on the server (unreadable or over 120 s is rejected), and transcribes with the configured `whisper` model under the `transcription` cost flow. It returns the transcript, the duration and a reference.
- The reference lives in an in-process registry for 10 minutes. A message whose context names a live reference becomes a voice turn. Its trace carries `input { modality, duration_s, edited }`, and `edited` is computed on the server by comparing the sent text with the stored transcript.
- The dead audio-in-the-turn path is cut: `RawInput.audio`/`audio_mime`, the graph state audio fields and the `preprocess` audio branch.
- The ze-api image gains `ffmpeg`. Browser recordings (WebM, MP4) need conversion and a length probe, and the image has neither tool today.

## Technical Context

**Language/Version**: Python 3.12.
**Primary Dependencies**: FastAPI `UploadFile` (`python-multipart` is already in `uv.lock`; the workspace upload route uses it), `ffmpeg`/`ffprobe` binaries (new in the ze-api Docker image; a developer prerequisite locally).
**Storage**: none. There is no migration: the trace is JSONB on `messages`, and the registry is in memory.
**Testing**: pytest; fake `transcribe` client; `asyncio.create_subprocess_exec` patched for ffprobe/ffmpeg; FastAPI `TestClient` for the route.
**Target Platform**: Linux container (Fly/docker-compose) and macOS dev.
**Project Type**: web service (backend only; ze-web regenerated client only).
**Performance Goals**: a 10 s recording transcribed in under 5 s end to end on a normal connection (193 SC-003); the probe adds under 200 ms.
**Constraints**: 10 MB upload cap, read in chunks and aborted past the cap; 120 s cap from the server probe; no audio kept (the bytes stay in memory for the request only); the API key on the route.
**Scale/Scope**: single user, single instance.

## Constitution Check

| Principle | Check |
|---|---|
| I Spec-first | spec.md with clarifications; plan, research, data model, contract, quickstart and tasks here. |
| II Single-user | No per-user scoping; the registry is process-wide. |
| III Layered packages | Transcription helper and audio tools in ze-core (`openrouter/audio.py`, `voice.py`); `VoiceInput` in ze-agents (`interface/types.py`, beside `RawInput`); route, registry and WS wiring in ze-api only. No plugin touched. |
| IV Typed Python | `VoiceInput`, `InputTrace`, `Transcription` dataclasses; errors `UnsupportedAudioError`, `AudioTooLargeError`, `AudioUnreadableError`, `AudioToolMissingError`, `TranscriptionFailedError` as `ZeError` subclasses; Pydantic only in ze-api schemas. |
| V Tests | Fail-first tasks; no real model or ffmpeg in default suites. |
| VI Persistence | No schema change. |
| VII One gateway | Transcription uses the injected `OpenRouterClient.transcribe`. |
| VIII Hard cuts | Audio fields and the `preprocess` audio branch deleted, no shim; tests that feed `audio_data` deleted or rewritten. |

Gate: pass (pre- and post-design).

## Blast radius

From `graphify affected` (after `graphify update .`) on `RawInput`, `preprocess`, `transcribe`, `make_graph_input`, plus `rtk proxy grep -rn "audio_data\|audio_mime\|raw.audio"`:

| Symbol | Callers | Change |
|---|---|---|
| `RawInput.audio`, `.audio_mime` (`ze_agents/interface/types.py`) | `ze_core/container.py` (`invoke_raw` kwargs `audio_data`, `audio_mime`), `conversation/turn.py` (`make_graph_input`). Text-only callers: `invoke_retry_turn`, `make_graph_input_from_raw_text`, ze-api ws `turns.py`, eval router, `wiring/container.py`, `wiring/workflow_graph.py`, `ze_automation/bootstrap.py` | Fields deleted; `RawInput.voice: VoiceInput | None` added. Text-only callers are unchanged. |
| `AgentState.audio_data`, `.audio_mime` (`orchestration/state.py`) | `preprocess`, `make_graph_input`, `tests/orchestration/test_state_serde.py` | Deleted; `voice_input: dict | None` added. |
| `preprocess` audio branch (`orchestration/nodes/preprocessing.py:35-49`) | graph | Deleted; image captioning kept; the audio cases in `tests/orchestration/nodes/test_preprocessing.py` deleted. |
| `make_graph_input` (`conversation/turn.py:34`) | `invoke_raw_turn` and its tests (`test_make_graph_input_*`, `test_preset_graph`, `test_partial_trace_update_carries_the_screen`) | Modality `voice` when `raw.voice`; `voice_input` reset each turn like the screen keys. |
| `_normalise_audio_format`, `_to_mp3` (`openrouter/client.py`) | `OpenRouterClient.transcribe`, `preprocess` (deleted import) | Moved to `openrouter/audio.py` (public names); `transcribe` imports them. |
| `record_trace` (`orchestration/nodes/trace.py:77`) | graph | Builds `MessageTrace.input` from state. |
| `MessageTrace` (`conversation/messages/types.py`) | message store, trace REST, WS `trace_update` | Gains `input: InputTrace | None`. |
| `MessageTraceResponse` (`api/v0/messages/schemas.py`), `WsTraceUpdateFrame` (`api/ws/schemas.py`) | trace REST route, native interface | Gain `input`. |
| `WsScreenContext` (`api/ws/schemas.py`), `ScreenContext.from_wire` (`ze_agents/screen.py`) | ws `turns.py` | Gain `voice` / `voice_ref`, parsed leniently. |
| `apps/ze-api/Dockerfile` | image | `ffmpeg` added to apt. |

## Design

### ze-agents

- `interface/types.py`: `VoiceInput(duration_s: float, edited: bool)`; `RawInput.voice: VoiceInput | None = None`; audio fields removed.
- `errors.py`: the five voice errors under one `VoiceInputError(ZeError)`.
- `screen.py`: `ScreenContext.voice_ref: str | None`, read from `context.voice.transcription_id` (strings of at most 64 characters; anything else is ignored with a warning in the existing warning list).

### ze-core

- `openrouter/audio.py`: `normalise_audio_format` and `to_mp3` (moved), and `probe_duration(data) -> float`, which runs `ffprobe -v error -show_entries format=duration -of csv=p=0 pipe:0`. A missing or non-numeric result raises `AudioUnreadableError`; a missing binary (`FileNotFoundError`) raises `AudioToolMissingError`.
- `voice.py`: `Transcription(text, duration_s)` and `async transcribe_audio(client, data, mime, *, model, max_seconds=120) -> Transcription`. It probes first; over the limit raises `AudioTooLargeError`. It sets the flow and agent context (`transcription`, `whisper`) so the cost tracker records the call. It calls `client.transcribe(data, mime, model=model, duration_seconds=d)` (the client converts formats it cannot send). An empty transcript returns `""`, and any model error raises `TranscriptionFailedError`.
- `conversation/turn.py`: `make_graph_input` sets `input_modality = "voice"` and `voice_input = {"duration_s", "edited"}` when `raw.voice` is set, else `voice_input = None`.
- `conversation/messages/types.py`: `InputTrace(modality: str, duration_s: float | None = None, edited: bool | None = None)`; `MessageTrace.input: InputTrace | None = None`.
- `orchestration/nodes/trace.py`: `record_trace` sets `input` when `input_modality == "voice"`. The transcript text is never on the trace (clarification Q2).
- `container.py`: `invoke_raw`'s `audio_data`/`audio_mime` kwargs are deleted.

### ze-api

- `api/v0/voice/router.py`: `POST /voice/transcriptions`, `operation_id="transcribeVoice"`, `response_model=TranscriptionResponse`, summary, description, `require_api_key`. Steps:
  1. Check `content_type` against `audio/webm`, `audio/ogg`, `audio/mp4`, `audio/x-m4a`, `audio/m4a`, `audio/wav`, `audio/x-wav`. Codec parameters are allowed and compared on the type before `;`.
  2. Read 1 MB chunks up to 10 MB.
  3. Call `transcribe_audio` with the `whisper` model from config (the key `preprocess` used), then register the result.

  Errors map as follows:
  - 415: unsupported type, with the accepted list.
  - 413: "too large", with the limit in words ("over 10 MB" or "over 2 minutes").
  - 422 (`AudioUnreadableError`): "I couldn't make out the recording".
  - 502 (`TranscriptionFailedError`): "I couldn't make out the recording".
  - 503 (`AudioToolMissingError`): "Voice input is not available on this server" (logged as `voice_ffmpeg_missing`).
  
  `schemas.py`: `TranscriptionResponse { transcript, duration_s, transcription_id }`.
- `ze_api/voice/registry.py`: `TranscriptionRegistry` (constructor-injected clock): `register(text, duration_s) -> id` (`uuid4().hex`) and `lookup(id) -> (text, duration_s) | None`, with a 10-minute TTL and expired entries swept on each call. Created in `ze_api/lifespan.py` and set on `app.state.transcription_registry`. The route reads it with a `Depends` helper; ws `turns.py` gets it through the same container/app state path that `connection_manager` uses.
- `api/ws/turns.py`: after `ScreenContext.from_wire`, a `voice_ref` that is found in the registry builds `RawInput(text=text, voice=VoiceInput(duration_s, edited=text.strip() != stored.strip()))`. A ref that is not found keeps the turn as text and writes `ws_voice_ref_unknown`.
- `api/ws/schemas.py`: `WsVoiceRef { transcription_id: str = Field(max_length=64) }` on `WsScreenContext.voice`; `InputTraceResponse`; `input` on `WsTraceUpdateFrame`. `api/v0/messages/schemas.py`: `input` on `MessageTraceResponse`, mapped in `messages/router.py`.
- `Dockerfile`: `ffmpeg` added to the existing apt line.
- `make codegen` regenerates `packages/ze-client`.

## Project Structure

### Documentation (this feature)

```text
specs/phases/192-voice-transport/
├── spec.md
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/transcribe-voice.md
├── checklists/requirements.md
└── tasks.md
```

### Source Code

```text
core/contracts/ze-agents/ze_agents/{interface/types.py,screen.py,errors.py}
core/engine/ze-core/ze_core/openrouter/{audio.py (new),client.py}
core/engine/ze-core/ze_core/voice.py (new)
core/engine/ze-core/ze_core/conversation/{turn.py,messages/types.py}
core/engine/ze-core/ze_core/orchestration/{state.py,nodes/preprocessing.py,nodes/trace.py}
core/engine/ze-core/ze_core/container.py
apps/ze-api/ze_api/api/v0/voice/{__init__,router,schemas}.py (new) ; apps/ze-api/ze_api/api/v0/__init__.py
apps/ze-api/ze_api/voice/registry.py (new) ; apps/ze-api/ze_api/lifespan.py
apps/ze-api/ze_api/api/ws/{turns,schemas}.py ; apps/ze-api/ze_api/api/v0/messages/{schemas,router}.py
apps/ze-api/Dockerfile
packages/ze-client/src/generated/*
```

## Docs touched

- `docs/native-interface.md`: the transcription route, `context.voice`, the trace `input` section.
- `docs/configuration.md`: the `whisper` model key; the ffmpeg prerequisite.
- `docs/architecture.md`: the REST table gains `transcribeVoice`; `preprocess` captions images only.
- `README.md` and `CONTRIBUTING.md` (local setup): ffmpeg prerequisite.
- `AGENTS.md`: phase row 192 and the graph-flow line ("preprocess (image → caption)"); `specs/README.md` row 192.

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first; T002–T004):
- **ze-agents:** `VoiceInput` and `RawInput.voice` (the audio fields stay until lane `core` cuts them); the voice errors; `ScreenContext.voice_ref` with its parsing test.
- **ze-core:** `InputTrace` and `MessageTrace.input`.
- **ze-api schemas:** `TranscriptionResponse`, `InputTraceResponse`, `WsVoiceRef`, and `input` on both trace models.
- **Route stub:** returns 501, with the final signature, response model and operation id, registered in `api/v0/__init__.py`.
- **ze-core stub:** `voice.py` with `Transcription` and a `transcribe_audio` signature that raises `NotImplementedError`.
- `make codegen`.
- **Shared fixtures:** `apps/ze-api/tests/fixtures/audio/` (a 1 s WAV and a short WebM) and a `fake_transcribe_client` fixture in `core/engine/ze-core/tests/conftest.py`.

| Lane | Model / role | Owns (disjoint) | Tasks | Starts after | Reviewer |
|---|---|---|---|---|---|
| lead | Sonnet ENG lead | `ze_agents/{interface/types.py,screen.py,errors.py}`, `ze_core/conversation/messages/types.py`, `ze_core/voice.py` (stub only; `core` fills it), `api/v0/messages/{schemas,router}.py`, `api/ws/schemas.py`, `api/v0/__init__.py`, `packages/ze-client/src/generated/*`, shared fixtures; final integration and gates | T001–T004, T013, T014 | - | Gauge |
| core | Sonnet ENG | `ze_core/openrouter/{audio.py,client.py}`, `ze_core/voice.py` (body), `ze_core/conversation/turn.py`, `ze_core/orchestration/{state.py,nodes/preprocessing.py,nodes/trace.py}`, `ze_core/container.py`, `ze_agents/interface/types.py` audio-field removal (handed over by `lead` after the contract step), and their tests | T005–T008 | contract step | floor Reviewer |
| api | Sonnet ENG | `api/v0/voice/{router,schemas}.py` (body), `ze_api/voice/registry.py`, `ze_api/lifespan.py` (registry line), `api/ws/turns.py`, `apps/ze-api/Dockerfile`, and their tests | T009–T012 | contract step | floor Reviewer |
| docs | Haiku DOCS | the files in "Docs touched" | T015–T017 | lanes `core` and `api` merged | floor Reviewer |

**Rules**: one lane per file at a time. `ze_core/voice.py` and `ze_agents/interface/types.py` pass from `lead` to `core` after the contract step and are not edited by `lead` again. Lane `api` codes against the contract `transcribe_audio` signature and patches it in its tests until `core` merges. `lead` merges `core`, then `api`, re-runs `make codegen` if a schema moved, and runs the gates. There is no JR lane: every task crosses a contract or wraps a subprocess, so none is fully specified enough for Haiku.

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| `ffmpeg` in the image | Browsers record WebM (Chrome) or MP4 (Safari). The length must be measured on the server (clarification Q3), and WebM must be converted before the model; the image has no ffmpeg today, so `to_mp3` would fail in production. | A pure-Python parser per container (more code, partial coverage); trusting the client's length (rejected by the clarification). |
| In-process registry | The turn must know the transcript without trusting the client (FR-004). | A table (persistence for a 10-minute value; the spec says nothing is stored). |
