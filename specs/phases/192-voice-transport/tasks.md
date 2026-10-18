# Tasks: Voice Input Transport (B3)

**Input**: [spec.md](./spec.md) (clarifications 2026-10-18), [plan.md](./plan.md) (Lane Plan; revised after Gauge's review V-1..V-9), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/transcribe-voice.md](./contracts/transcribe-voice.md), [quickstart.md](./quickstart.md), [checklists/security.md](./checklists/security.md).

**Tests**: required (constitution V). **Fail-first**: write the test, run it, see it fail for the stated reason, then implement. No real model call in default suites. Subprocess calls are patched in unit tests. One real-ffprobe test is marked `slow` and skipped when the binary is absent.

**Build gate**: starts now on `main`; runs in parallel with the web floors; must land before 193.

## Format: `[ID] [P?] [Lane] [Story] Description`

- **[Lane]**: `[L:lead]`, `[L:core]`, `[L:api]`, `[L:docs]` (plan.md Lane Plan). A task touches only files its lane owns.
- **[Story]**: US1 transcribe-correct-send, US2 plain failures, US3 cost tracking.

**Crew**: Sonnet `lead`, `core`, `api`; Haiku `docs`. Contract step (T002–T004) first; `core` and `api` then run in parallel in their own worktrees; `lead` merges `core` then `api`. Tick a task's checkbox in the same commit that finishes it.

**Rules for every lane**: `rtk proxy grep` and `graphify affected "<Symbol>" --depth 2` before changing a shared symbol; `ZeError` subclasses only; `get_logger(__name__)`; `git add <paths>`, never `-A` or `stash`.

---

## Phase 1: Setup

- [x] T001 [L:lead] Branch from `main`. `make install`; `graphify update .`; `graphify affected` on `RawInput`, `make_graph_input`, `preprocess`, `transcribe`, `record_trace`, `MessageTrace`, `_parse_trace`, `handle_message`, `ScreenContext`; `rtk proxy grep -rn "audio_data\|audio_mime\|raw.audio\|_normalise_audio_format\|_to_mp3" core apps plugins integrations`. Confirm `python-multipart` resolves and `ffmpeg -version` / `ffprobe -version` work locally. Record differences from plan.md "Blast radius" in the Handoffs note; stop and report differences to the Spec Architect (Lintel).

---

## Phase 2: Foundational (contract step, lane `lead`)

- [x] T002 [L:lead] Tests first:
  - `core/contracts/ze-agents/tests/test_interface_types.py`: `VoiceInput(duration_s, edited)`; `RawInput.voice` defaults to `None`.
  - `core/contracts/ze-agents/tests/test_screen_context.py`: a context with only `voice: {...}` returns no warning, `is_empty` is true, and `to_wire()` has no `voice` key (V-3).
  - `core/contracts/ze-agents/tests/test_errors.py`: `VoiceInputError(ZeError)` with `UnsupportedAudioError`, `AudioTooLargeError`, `AudioTooLongError`, `AudioUnreadableError`, `AudioToolMissingError`, `TranscriptionFailedError`.
  
  Implement in `ze_agents/interface/types.py` (add `VoiceInput` and `RawInput.voice`; the audio fields stay for `core`), `ze_agents/screen.py` (`"voice"` in `known` only) and `ze_agents/errors.py`.
- [x] T003 [L:lead] Tests first:
  - `core/engine/ze-core/tests/conversation/test_message_trace_input.py`:
    - `InputTrace` round-trips through `asdict`, and `MessageTrace.input` defaults to `None`;
    - **store round-trip (V-2)**: `save_trace` then `get_trace` keeps `input` for a voice trace, a text trace keeps `None`, and a stored row without an `input` key parses with `None` (mocked pool returning the JSON).
  - `apps/ze-api/tests/api/test_voice_contract.py`:
    - the OpenAPI export lists `transcribeVoice` with `TranscriptionResponse`;
    - `WsScreenContext` accepts `voice.transcription_id` and rejects one over 64 characters;
    - `MessageTraceResponse` and `WsTraceUpdateFrame` accept `input`.

  Implement:
  - `InputTrace` and `MessageTrace.input` in `conversation/messages/types.py`, and `input` parsing in `_parse_trace` (`conversation/messages/store.py`).
  - The `ze_core/voice.py` stub: `Transcription` and `transcribe_audio(client, data, mime, *, model, max_seconds=120)` raising `NotImplementedError`.
  - `TranscriptionResponse` in `api/v0/voice/schemas.py`, plus `InputTraceResponse`, `WsVoiceRef` and `input` in `api/ws/schemas.py`, and `input` in `api/v0/messages/{schemas,router}.py`.
  - A 501 stub `api/v0/voice/router.py` (final signature, `operation_id="transcribeVoice"`, `response_model`, summary, description, `require_api_key`), registered in `api/v0/__init__.py`.

  Run `make codegen` and commit the generated client with the task.
- [x] T004 [P] [L:lead] Fixtures in `apps/ze-api/tests/fixtures/audio/`, with the generator script `make_fixtures.sh` committed beside them:
  - `stream.webm`, made by `ffmpeg -f lavfi -i sine=duration=3 -c:a libopus -f webm pipe:1 > stream.webm`: non-seekable, no duration;
  - `frag.mp4`, made with `-movflags frag_keyframe+empty_moov`;
  - `stream.ogg`, an Opus clip made with `-c:a libopus -f ogg pipe:1` (Firefox records `audio/ogg`);
  - `one_second.wav`.

  In `core/engine/ze-core/tests/conftest.py`: `fake_transcribe_client`, and `ffprobe_stub(outputs: list[str], missing=False, hang=False)`, which patches `asyncio.create_subprocess_exec` and returns the outputs in order (step 1, step 2). Hand `ze_core/voice.py` and `ze_agents/interface/types.py` to lane `core` (Handoffs note).

**Checkpoint**: contract merged; `core` and `api` start.

---

## Phase 3: User Story 1 - Transcribe, correct, then send (P1) 🎯 MVP

- [x] T005 [P] [L:core] [US1] Tests first `core/engine/ze-core/tests/openrouter/test_audio.py` (stubbed):
  - `normalise_audio_format` maps `audio/webm;codecs=opus` → `webm`, `audio/mp4` → `m4a` and `audio/x-wav` → `wav`.
  - The container format for the probe maps mp4 and m4a → `mp4`.
  - `probe_duration`:
    - returns step 1's `3.400000`; a step-1 output of `0` or a negative number counts as failure and runs step 2 (only a positive number is success);
    - when step 1 prints `N/A`, runs step 2 and returns the last `pts_time + duration_time` (`2.994000,0.020000` → 3.014);
    - raises `AudioUnreadableError` when both steps fail or step 2 returns no packets;
    - raises `AudioToolMissingError` on `FileNotFoundError`;
    - on a hang past the timeout, kills the process and raises `AudioUnreadableError`;
    - passes `-f <container>` and `-protocol_whitelist pipe` to every call.
  - `to_mp3` raises `AudioUnreadableError` on a non-zero exit or a timeout.

  Move `_normalise_audio_format` and `_to_mp3` to `ze_core/openrouter/audio.py` (public names, demuxer, whitelist, timeouts). Add `probe_duration`. `client.py` imports them, and the existing client tests stay green.
- [x] T006 [L:core] [US1] Real-binary check before building on the probe (V-1): `core/engine/ze-core/tests/openrouter/test_audio_real.py`, marked `@pytest.mark.slow` and skipped without `ffprobe`. `probe_duration` returns 3.0 ± 0.1 on each of the T004 fixtures: `stream.webm` and `stream.ogg` (both through the packet scan) and `frag.mp4` (step 1). A WAV labelled as WebM is rejected by the forced demuxer (`AudioUnreadableError`). Run it locally with `make test-core SLOW=1` and record the result in the Handoffs note.
- [x] T007 [L:core] [US1] Tests first `core/engine/ze-core/tests/test_voice.py`:
  - success returns the stripped text and the probed duration, and passes `duration_seconds` and the mime to `client.transcribe`;
  - an empty reply returns `Transcription("", d)`;
  - over `max_seconds` raises `AudioTooLongError` before any model call;
  - a model exception raises `TranscriptionFailedError` and logs `voice_transcription_failed` with the cause class;
  - the flow and agent ContextVars are `transcription` and `whisper` during the call (US3).
  
  Implement `transcribe_audio` in `ze_core/voice.py`.
- [x] T008 [L:core] [US1] Tests first:
  - `tests/conversation/test_make_graph_input.py` (extend): a `RawInput` with `voice` sets `input_modality == "voice"` and `voice_input`; text sets `None`, and the key resets each turn.
  - `tests/orchestration/nodes/test_trace_input.py`: `record_trace` sets `MessageTrace.input` for voice and `None` for text, with no transcript text in the JSON.

  Implement in `conversation/turn.py`, `orchestration/state.py` and `orchestration/nodes/trace.py`. Then the hard cut (SC-002): delete `RawInput.audio`/`.audio_mime`, `AgentState.audio_data`/`.audio_mime`, the `preprocess` audio branch and its import, and `invoke_raw`'s audio kwargs (`ze_core/container.py`), plus the audio cases in `test_preprocessing.py` (lines ~29, ~57) and `test_state_serde.py` (~193-194). `rtk proxy grep -rn "audio_data\|audio_mime\|raw\.audio" core apps plugins integrations` returns nothing. `make test-core` and `make test-agents` pass.
- [x] T009 [P] [L:api] [US1] Tests first `apps/ze-api/tests/voice/test_registry.py` (injected clock): `register` returns a 32-character hex id; `lookup` returns `(text, duration_s)` within 10 minutes and `None` after; expired entries are swept on each call; past 100 entries the oldest is dropped. Implement `ze_api/voice/registry.py`, and add `self.transcription_registry` in `ze_api/wiring/container.py` with a test that the container exposes it.
- [x] T010 [L:api] [US1] Tests first `apps/ze-api/tests/api/test_voice_route.py` (success path, `transcribe_audio` patched until `core` merges): `one_second.wav` as `audio/wav` with the key returns 200 `{transcript, duration_s, transcription_id}`; the id is in `container.transcription_registry`; no key → 401; the model passed is `models.whisper` (fallback `MODEL_WHISPER`); `audio/webm;codecs=opus` is accepted. Implement the route body.
- [x] T011 [L:api] [US1] Tests first `apps/ze-api/tests/api/test_ws_voice_turn.py`, driving `handle_message` with a container whose registry holds an entry (V-5):
  - a frame with a live `context.voice.transcription_id` builds `RawInput(text, voice=VoiceInput(d, edited))` (spy on `invoke_raw_turn`), with `edited` False when the text equals the transcript after stripping whitespace and True otherwise;
  - an unknown or expired id gives a text-only `RawInput`, the log `ws_voice_ref_unknown`, and no user-visible warning;
  - a voice-only context is not stored as `screen_context` on the user message, and `config_extra` has no `screen_context` (V-3);
  - the reference is reusable.

  Implement `_voice_input` in `api/ws/turns.py`.

---

## Phase 4: User Story 2 - Failures are plain and recoverable (P1)

- [x] T012 [L:api] [US2] Tests first in `apps/ze-api/tests/api/test_voice_route.py`, each with the exact `detail` from [the contract](./contracts/transcribe-voice.md) and no registry entry on failure:
  - `text/plain` → 415;
  - a declared `Content-Length` of 11 MB → 413 before the handler runs (the patched `transcribe_audio` is never called, and the middleware answers);
  - a chunked 11 MB body with no length → 413 from the handler's read cap;
  - `AudioTooLongError` → 413 "too long";
  - `AudioUnreadableError` → 422;
  - `TranscriptionFailedError` → 502 (cause logged);
  - `AudioToolMissingError` → 503 and the log `voice_ffmpeg_missing`;
  - no `file` part, or a JSON body → 422 "Send the recording as a file named file." (a string `detail`, not a list).

  Implement the mapping and the missing-part handler in `api/v0/voice/router.py`, and the path-scoped length check in `api/v0/voice/limits.py`, registered in `ze_api/main.py`. Add `ffmpeg` to the apt line in `apps/ze-api/Dockerfile`.

---

## Phase 5: User Story 3 - Voice costs are tracked (P2)

US3 is asserted in T007 (flow and agent ContextVars during the call); the cost tracker records every `complete` call under the current flow.

---

## Phase 6: Polish and cross-cutting

- [x] T013 [L:lead] Merge lane `core`, then lane `api`. After the merge, `lead` edits the api tests to drop their `transcribe_audio` patches, so they run on the real helper with the stubbed probe and fake client. Run `make codegen` if a schema moved. Gates: `make test-py`, `make test-core SLOW=1` (with ffprobe present), `make lint`, `make test-web`.
- [x] T014 [L:lead] Run [quickstart.md](./quickstart.md) against `make dev`: a real Chrome WebM recording, a Safari MP4 recording (or the fragmented fixture), and the failure cases. Build the ze-api image once and run `ffprobe -version` inside it. Record the results in the Handoffs note.
- [x] T015 [P] [L:docs] From the merged diff, following the doc-style skill:
  - `docs/architecture.md` (~61-62, ~175, ~692, ~700-701, and the REST table);
  - `docs/configuration.md` (~177);
  - `docs/native-interface.md` (the route, `context.voice`, trace `input`);
  - `docs/ingestion.md` (system binaries: ffmpeg/ffprobe beside yt-dlp, ~203).
- [x] T016 [P] [L:docs] `docs/package-architecture.md` (~163) and `core/engine/ze-core/README.md` (~29) module tables (`voice.py`, `openrouter/audio.py`); `docs/testing.md` (slow real-ffprobe test); `AGENTS.md` phase row 192, the graph-flow line ("preprocess (image → caption)"), and the layout tree if it lists module files; `specs/README.md` row 192 → Implemented; spec status.
- [ ] T017 [L:docs] Coverage check: `git diff main...HEAD --stat` against plan.md "Docs touched" (the exact line list); record in the Handoffs note.

---

## Dependencies & Execution Order

- T001 → T002, T003, T004 (contract) → lanes.
- `core`: T005 → T006 (real binary) → T007 → T008.
- `api`: T009 → T010 → T012; T011 after T009.
- T013 after both lanes; T014 after T013; T015–T016 after T013; T017 last.

## Parallel Example

```text
After the contract step:
  core: T005 → T006 → T007 → T008
  api:  T009 → T010 → T012, and T011
docs after T013.
```

## Implementation Strategy

- MVP = US1 with the fake client and the real-binary check (T006) early, so the browser WebM path is proven before anything builds on it. US2 hardens the route; US3 is asserted inside T007.
- 193 can code its web voice control against the contract once T003's codegen lands.

---

## Handoffs

- **T001**: grep matches plan "Blast radius" exactly. `make install` needs `UV_PYTHON=3.12`; `make test-web` needs node 22 on PATH (default node 16 fails in vitest startup). `ffprobe format=duration` prints `N/A` from a pipe for WebM, Ogg and WAV; only fragmented MP4 returns a duration, so WAV and Ogg also use the packet scan.
- **T006** (core lane): real-ffprobe slow test, 4 passed (WebM/Ogg through the packet scan, `frag.mp4`, WAV labelled WebM rejected).
- **T013** gates at merge (8b61bed2): `make test-py` rc=0, `make test-core SLOW=1` rc=0, `make lint` rc=0, `make test-web` rc=0 (1012 tests, node 22).
- **T014** (throwaway DB `ze_192_voice`, port 8020, dropped afterwards), `curl` against the real server and real ffprobe:
  - `text/plain` 415; no key 401; 180 s WAV 413 "too long"; 11 MB body 413 "too large"; truncated file and random bytes 422/502 plain line; WAV labelled WebM 422; missing `file` part 422 "Send the recording as a file named file.".
  - WebM (macOS `say` → libopus), Safari-style fragmented MP4, `stream.ogg` and `frag.mp4` all pass the probe and reach the model. The model call returned 502 because the OpenRouter account has less than the $0.50 balance audio requires ("This request requires at least $0.50 in balance for audio"), so a real transcript, quickstart steps 2-3 (WS turn trace) and step 5 (cost entry) were NOT verified live; they are covered by unit tests.
  - Docker: building the full ze-api image (torch, model downloads) was skipped. The Dockerfile's apt line (`libgomp1 ffmpeg`) was run on `python:3.12-slim-bookworm`: `ffprobe version 5.1.9`.
