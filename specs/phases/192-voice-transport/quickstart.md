# Quickstart: Voice Input Transport (B3)

## Prerequisites
- `ffmpeg` installed locally (`brew install ffmpeg`); the Docker image installs it.
- `make db-up && make dev`.

## Automated checks
- `make test-core` and `make test` (route, registry, turns, trace): all pass with no network.
- `make test-py`, `make lint`.

## Manual validation against `make dev`
1. `curl -H "Authorization: Bearer $ZE_API_KEY" -F "file=@sample.webm;type=audio/webm" localhost:8000/api/v0/voice/transcriptions` → 200 with transcript, duration and id. See [contract](./contracts/transcribe-voice.md).
2. Send a WS `message` with `context.voice.transcription_id` set to that id and a slightly changed text → the reply's trace (`GET /api/v0/messages/traces?ids=…`) shows `input: { modality: "voice", edited: true }`.
3. Repeat with an unknown id → no `input` section.
4. Upload a `.txt` as `text/plain` → 415; a 3-minute WAV → 413 "too long"; a truncated file → 422.
5. Governance › Spend (or `GET /api/v0/costs`) shows a `transcription` entry.
