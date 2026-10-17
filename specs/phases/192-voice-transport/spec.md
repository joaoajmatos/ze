# Feature Specification: Voice Input Transport (B3)

**Feature Branch**: `192-voice-transport`

**Created**: 2026-10-17

**Status**: Draft (spec level; plan and tasks follow once scheduled)

**Input**: Maestro brief 2026-10-17, backend floor B3: overhaul plan section d, gap 5; section c (Voice); user decision 6 ("Voice: input only in this overhaul (W8); spoken output later").

**Governed by**: phase 10/19 (multimodal input: the `preprocess` node transcribes `audio_data` through `OpenRouterClient.transcribe`), `specs/arch/pre-v1-hard-cuts.md`, `SECURITY.md` (size limits, single user, API key).

**Depends on**: nothing unfinished. Must land before 193 (W8).

**Doctrine function served**: perception (a new input channel into the same turn).

---

## Overview

The graph already turns audio into text: `invoke_raw_turn` copies `RawInput.audio` and `audio_mime` into `AgentState`, and `preprocess` transcribes them and sets `input_modality = "voice"`. Nothing in ze-api fills those fields: the WebSocket `message` frame carries text only (the path was built for Telegram, removed since). The web app also needs the transcript back before the turn runs, so the user can correct what Ze heard (plan section c).

## User Scenarios & Testing *(mandatory)*

1. **Transcribe, then send (P1).** The client uploads a recording to `POST /api/v0/voice/transcriptions` (multipart, `audio/webm` | `audio/ogg` | `audio/mp4` | `audio/wav`, ≤ 10 MB, ≤ 120 s) and gets `{ transcript, language, duration_s, transcription_id }`. The user edits the text in the Ask bar and sends a normal `message`, with `context.voice = { transcription_id, edited: bool }`. The trace records the modality as voice and whether the user edited the transcript.
2. **Errors are plain (P1).** Unsupported type → 415; too large or too long → 413 with the limit in words; transcription failure → 502 with "I couldn't make out the recording"; the Ask bar keeps the recording and offers Retry.
3. **Costs are tracked (P2).** The transcription call is recorded by the cost tracker under flow `voice` like any other OpenRouter call.

## Requirements *(mandatory)*

- **FR-001**: Route in ze-api (`api/v0/voice/`), `operation_id="transcribeVoice"`, `response_model`, `summary`, `description`; calls a new `ze_core` `transcribe_audio()` helper built on the existing `transcribe` and `_normalise_audio_format`, using the model configured for voice in `config.yaml` (the one `preprocess` uses).
- **FR-002**: No audio is stored; the `transcription_id` is a short-lived in-process key (10 minutes) mapping to transcript, language and duration so the turn can record them on the trace without trusting the client.
- **FR-003**: The `message` frame's `context.voice` is read in `fetch_context` (or `turns.py` when building the raw input) to set `input_modality="voice"` and a `MessageTrace.input` section (`modality`, `edited`, `duration_s`, `language`). `RawInput.audio`/`audio_mime` and the `preprocess` audio branch are deleted (pre-v1: one voice path, the transcription endpoint; image captioning in `preprocess` stays).
- **FR-004**: `make codegen`; `docs/native-interface.md` and `docs/configuration.md` updated.

## Success Criteria *(mandatory)*

- **SC-001**: Route tests with a fake client cover success, 413, 415, 502; no OpenRouter call in default suites.
- **SC-002**: `rtk proxy grep -rn "audio_data" core apps` returns nothing after the cut.
- **SC-003**: `make test-py`, `make lint` pass.

## Out of Scope

- Spoken replies (TTS), streaming transcription, wake words (decision 6).

## Owning packages

ze-core (transcribe helper, `preprocess` cut, trace field), ze-api (route, WS context), ze-web regenerated client only; no migration (the trace is JSONB on `messages`).
