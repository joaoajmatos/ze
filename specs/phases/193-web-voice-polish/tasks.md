# Tasks: Voice and Polish (W8)

**Input**: [spec.md](./spec.md) (clarifications 2026-10-18), [plan.md](./plan.md) (Lane Plan), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/voice-ui.md](./contracts/voice-ui.md), [quickstart.md](./quickstart.md).

**Tests**: required. **Fail-first**: write the test, run it, see it fail for the stated reason, then implement.

**Build gate**: start when 187 (Ask) and 192 (transcription) are on `main`, and 186, 188, 189 and 190 have landed (the critique covers every place). 191 is parked and is not a dependency.

## Format: `[ID] [P?] [Lane] [Story] Description`

- **[Lane]**: `[L:lead]`, `[L:voice]`, `[L:ambience]`, `[L:cut]`, `[L:polish]`, `[L:docs]` (plan.md Lane Plan).
- **[Story]**: US1 speak/correct/send, US2 ambience, US3 critique, US4 cut.

**Crew**: Sonnet `lead`, `voice`, `polish`; Haiku JR `ambience`, `cut`; Haiku `docs`. Contract step first; `voice`, `ambience` and `cut` then run in parallel; `lead` merges them; `polish` runs after; `docs` last. Tick a task's checkbox in the commit that finishes it.

**Rules**: FSD (`pages → widgets → features → entities → shared`; features never import features; the shell wires them through props and slots); DESIGN.md modules and 44 px targets (asserted by class in tests); reduced motion respected; `localStorage` only in try/catch; `git add <paths>`, never `-A` or `stash`. Browser APIs (`MediaRecorder`, `navigator.mediaDevices`, `AudioContext`) are faked in tests, never called for real.

---

## Phase 1: Setup

- [ ] T001 [L:lead] Branch from `main` (29f7f307 or later) with 187, 192 and 186–190 merged. `make web-install`; `graphify update .`; `graphify affected` on `AskBar`, `useAskOverlay`, `nextPresence`, `presenceActions`, `Orb`, `Presence`, `AppShell`, `JarvisApp`. Check that:
  - the generated client exports `transcribeVoice` and `WsScreenContext` has `voice?: { transcription_id: string }`;
  - `AskBar` still renders the disabled mic `Control` ("Voice input arrives later");
  - `pages/jarvis` has no importer outside itself and `routes.tsx`;
  - which `pages/*/ui/*Interim.tsx` files remain, and whether anything imports them;
  - how the generated `transcribeVoice` returns errors (`{ data, error, response }` with `response.status`), and the `OutboxItem`/`submit`/`ack`/`close` lines in `ask-overlay.ts`.

  Record differences from plan.md "Blast radius" in the Handoffs note; stop and report differences to the Spec Architect (Lintel).

---

## Phase 2: Foundational (contract step, lane `lead`)

- [ ] T002 [L:lead] Tests first:
  - `entities/presence/model/presence.test.ts`: `voice` survives an unrelated event (`baseOf` and `BASE` copy it); `voice_recording` → orb `listening`, phrase "listening", even with a turn thinking or a world signal; `voice_transcribing` → `thinking`, phrase "transcribing"; `voice_idle` returns to the derived state; offline still wins over voice;
  - `shared/ui/hud/presence/level.test.ts`: `smoothLevel(0, 1)` is 0.5; `smoothLevel(1, 0)` is 0.88; the output stays in 0–1;
  - `shared/ui/hud/presence/presence.test.tsx` (extend): `headSlot` renders inside `presence-head`; with reduced motion the `level` getter is never called; in `listening` with motion allowed, one animation frame (mocked rAF) calls it once.

  Implement `presence.ts`, `store.ts` (`presenceActions.voice`), `level.ts`, `Orb.tsx` (`level`, scaling the listening gather and brightness by `1 + 0.6 * smoothed`), `Presence.tsx` (`headSlot`, `level`).
- [ ] T003 [L:lead] Tests first:
  - `features/ask-bar/model/ask-overlay.test.ts` (extend): `voiceId` is null in the initial state; `setVoiceTranscript("hi", "t1")` on an empty draft sets the draft "hi", `voiceId` "t1" and bumps `focusTick`; on the draft "note" it gives "note hi"; `setDraft("")` clears `voiceId`; `aboutSent()` clears it; `submit` with `voiceId` "t1" puts `voiceId` "t1" on the outbox and `voice: { transcription_id: "t1" }` in its context, and clears the store's `voiceId`; `close` with that outbox unsent returns its text to the draft and "t1" to `voiceId`; `ack` clears the outbox;
  - `features/ask-bar/ui/AskBar.test.tsx` (extend): no mic renders without `renderMic`; `renderMic` receives the blocked reason ("Ze is offline" when offline, the displaced line when given) and `null` otherwise; submit with `voiceId` set calls `onSubmit(text, { voice: { transcription_id: "t1" } }, undefined)`; with a chat-about context it merges both; a refused submit keeps the draft and `voiceId`; `renderVoiceStatus` output is a sibling of `.ask`, never inside it; the "Voice input arrives later" label is gone;
  - `widgets/assemble/ui/AskOverlay.test.tsx` (extend): from a non-Ask place, an outbox carrying `voice` is sent with `context.voice.transcription_id`.

  Implement in `ask-overlay.ts` and `AskBar.tsx`.
- [ ] T004 [L:lead] Contract stubs and wiring. Create `features/voice-input/index.ts` and `features/ambience/index.ts` exporting the signatures in [the contract](./contracts/voice-ui.md). The stubs: `VoiceMic` renders a disabled 44 px `Control` labelled "Speak to Ze (hold V)", `VoiceStatus` renders an empty `role="status"` line, `useHoldToTalk` does nothing, `useVoiceInput` is a Zustand store with status `idle` and no-op actions, `registerTranscript` stores the callback and returns an unregister, `currentLevel` returns 0, and `AmbienceToggle` renders a 44 px `Control` with `aria-pressed="false"`. Tests first:
  - `widgets/app-shell/ui/AppShell.test.tsx` (extend): the Ask bar shows the mic from `VoiceMic`; the Presence head shows the ambience toggle; a callback registered through `registerTranscript`, when called with ("hello", "t1"), puts "hello" in the bar; closing the overlay while the voice store says `recording` calls `stop`; navigating to another place while recording does not call `stop`;
  - the voice status line renders above the bar (outside `.ask`);
  - `app/router/routes.test.tsx`: no `jarvis` route exists (remove the mock at line 36 and the test at 82-84), and `/jarvis` renders not found;
  - `shared/config/places.test.ts:35`: `placeOf("/jarvis")` is null and no redirect entry names it.

  Implement the wiring in `AppShell.tsx` per plan.md and remove the route in `routes.tsx:57-58`. No redirect.

**Checkpoint**: lanes start.

---

## Phase 3: User Story 1 - Speak, correct, send (P1) 🎯 MVP

- [ ] T005 [P] [L:voice] [US1] Tests first `features/voice-input/lib/mime.test.ts` and `lib/level.test.ts`:
  - `pickMime` returns `audio/webm;codecs=opus` when everything is supported, `audio/ogg;codecs=opus` without WebM, `audio/mp4` with only MP4, and `null` with none; `extensionFor` gives `webm`, `ogg`, `m4a`;
  - `levelFromSamples`: all zeros → 0; a full-scale square wave → 1; an RMS of 0.01 (−40 dBFS) → 0.4; output clamped to 0–1.

  Implement both.
- [ ] T006 [L:voice] [US1] Tests first `features/voice-input/lib/recorder.test.ts` with a fake `MediaRecorder`, `getUserMedia` and `AudioContext`: `startRecorder` asks for `{ audio: true }`, starts the recorder with the chosen mime, 64000 bit/s and a 250 ms timeslice; levels from the analyser reach the module ref; `stop()` resolves one `Blob` of the chunks with the mime, and stops every track and closes the audio context. Implement `recorder.ts`.
- [ ] T007 [L:voice] [US1] Tests first `features/voice-input/model/store.test.ts` and `api/transcribe.test.ts` (SDK mocked, fake timers):
  - start → `recording`, `presenceActions.voice("recording")`; stop → `transcribing`, then the registered callback gets (transcript, id) and the status is `idle`;
  - 115 s after recording actually began (fake timers and a faked `performance.now`; `getUserMedia` resolving 5 s after `start()` does not eat the budget), it stops and transcribes on its own; with ticks delayed (a throttled tab), it still stops at the first tick past 115 s of elapsed time; at 104 s the mic shows elapsed time, from 105 s the seconds left;
  - `currentLevel()` is 0 when not recording, even with a stale level in the module ref;
  - an empty or whitespace transcript sets `notice: "heard_nothing"`, calls no callback, and the notice clears after 6 s or at the next start;
  - each status, read from `response.status` of the mocked `{ data, error, response }` result: 422, 502, 500 and a network failure (no response) → `failed` with `failure.kind` `retryable`, `detail` the server's line (or "I couldn't make out the recording." with none), `pending` kept, and `retry()` uploads the same blob (same object) without recording; 413 and 415 → `failure.kind` `rerecord` with the server's line, and `retry()` does nothing; a 413 with a plain-text body falls back to "The recording is too large. Record a shorter one.", a 415 to "This recording format isn't supported.", a 503 to "Voice input is not available on this server."; `dismiss()` → `idle`, `pending` null;
  - a 503 → `unavailable`, reason the server's line ("Voice input is not available on this server.");
  - start failures: `NotAllowedError` → "Microphone access is blocked. Allow it in the browser's site settings."; `NotFoundError` or no `mediaDevices` → "No microphone found."; no `MediaRecorder` or `pickMime` null → "This browser can't record audio.";
  - start while `transcribing` does nothing;
  - `transcribe` sends a `File` named `recording.<ext>` with the mime as its type.

  Implement `store.ts` (replacing the stub's no-ops; the exported signatures do not change) and `transcribe.ts`.
- [ ] T008 [L:voice] [US1] Tests first `features/voice-input/ui/VoiceMic.test.tsx`, `ui/VoiceStatus.test.tsx` and `model/useHoldToTalk.test.ts`:
  - idle: label "Speak to Ze (hold V)", 44 px class; press → `start`; recording: stop icon, elapsed `0:12` after 12 s, `aria-pressed="true"`, label "Stop recording", press → `stop`; transcribing: disabled, `aria-busy="true"`; `blocked` or unavailable: disabled with the reason as label and title;
  - the status line (`VoiceStatus`): "Transcribing…"; a `retryable` failure shows its `detail` with Retry and Dismiss (both 44 px) calling `retry` and `dismiss`; a `rerecord` failure shows its `detail` with Record again (calls `dismiss` then `start`) and Dismiss, and no Retry; "Ze heard nothing"; the line has `role="status"` and `aria-live="polite"`;
  - hold-to-talk: keydown `v` outside a text field → `start`; keyup → `stop`; a keyup within 300 ms discards (no upload); keydown with a modifier, a repeat, focus in an input, a textarea or a contenteditable, or an open dialog does nothing; `enabled` false does nothing; window blur during a hold → `stop`.

  Implement `VoiceMic.tsx`, `VoiceStatus.tsx` and `useHoldToTalk.ts` (replacing the stubs; signatures unchanged).

---

## Phase 4: User Story 2 - Ambience is a choice (P2)

- [ ] T009 [P] [L:ambience] [US2] Copy the drone from git, not the working tree (lane `cut` deletes it in parallel): `git show main:apps/ze-web/src/pages/jarvis/hud/useAmbience.ts > apps/ze-web/src/features/ambience/model/useAmbience.ts`, unchanged first (the drone code stays as is), then tests first `features/ambience/model/useAmbience.test.ts` and `ui/AmbienceToggle.test.tsx` with a fake `AudioContext` (record `createOscillator` calls and `gain.setTargetAtTime` targets) and a fake `localStorage`:
  - fresh: `on` false, no `AudioContext` created;
  - starting calls `ctx.resume()` on the new context (Safari);
  - toggle → an `AudioContext` is created, `localStorage["ze.ambience"]` is `"on"`; toggle again → master gain target 0 and `"off"`;
  - stored `"on"`: nothing starts on mount; the first `pointerdown` on `window` starts it; with reduced motion (`useReducedMotion` mocked true) a `pointerdown` does not start it, but the toggle press does;
  - `localStorage` throwing on read or write: off, no crash;
  - while the presence `voice` is `"recording"` (set through `presenceActions.voice`), the master gain target is 0; back to `"none"`, the target is 0.16;
  - `AmbienceToggle`: 44 px class, `aria-pressed` follows `on`, label "Ambience on" / "Ambience off", icons `Volume2` / `VolumeX`.

  Implement the preference, arming and ducking in `useAmbience.ts`, and `AmbienceToggle.tsx` (replacing the stub; signature unchanged). Do not touch `pages/jarvis` (lane `cut` deletes it). If a test cannot be met as written, stop and report to `lead`.

---

## Phase 5: User Story 4 - The prototype and leftovers are gone (P2)

- [ ] T010 [P] [L:cut] [US4] Delete `apps/ze-web/src/pages/jarvis/` (all files), `apps/ze-web/.impeccable/surfaces/apps-ze-web-src-pages-jarvis.md` and `apps-ze-web-src-pages-home.md`, and the "does not read the prototype key" case in `apps/ze-web/src/shared/lib/palette.test.ts` (line 26, `jarvis.palette.v2`). For each `apps/ze-web/src/pages/*/ui/*Interim.tsx` that T001 listed: if `git grep -n "<Name>"` finds no importer outside the file and its test, delete both; otherwise leave it and report it to `lead`. Then run `make typecheck-web` and `make test-web`; both pass. `git grep -niE "jarvis" -- apps/ze-web/src apps/ze-web/.impeccable/surfaces` returns nothing (DESIGN.md is lane `polish`'s; `.impeccable/plan/` is exempt history).

---

## Phase 6: Merge, then User Story 3 - Every place passes the final critique (P1)

- [ ] T011 [L:lead] Merge `voice`, `ambience`, `cut`. Gates: `make test-web`, `make typecheck-web`, `make web-build`, `make lint`. Run quickstart steps 1–9 (including 3a and 3b) against `make dev-full` and record the results in the Handoffs note (SC-003 timing included). At 390 wide, check that the Ask bar does not change height when the voice status line appears.
- [ ] T012 [L:polish] [US3] For World, Ask, Doing (index, goal detail, workflow detail), Mind and Governance: run `/impeccable critique` and fix until each scores ≥ 30/40 with the detector clean; walk each by keyboard (every control reachable, visible focus ring, no trap) and with reduced motion during a running turn (no cascade, sweep or orb motion beyond opacity); capture each at 1440 and 390 with no console errors. Each fix keeps or adds a test where it changes behaviour. Also remove leftover style mappings from 186–190 (FR-006): CSS rules in `shared/styles` and old-page class mappings that no source file references, listed in the Handoffs note before deletion. This also closes two deferrals: 187's Ask critique (its own bar was 29/40; this task's 30/40 covers it) with a reduced-motion capture of Ask during a running turn, and 195's "Chat about this" chip capture (chip visible on a module, overlay open with suggestions, at 1440 and 390). Record scores, findings fixed and capture paths per place in the Handoffs note. A finding that needs a product decision goes to the Spec Architect, not into code.
- [ ] T013 [L:polish] [US4] `/impeccable document` to refresh `DESIGN.md`: Navigation and Components match the shipped places and primitives (Presence with the ambience toggle, the Ask bar mic and its states); replace lines 161-162 with the text in plan.md's blast radius and remove any other `jarvis` mention. `git grep -niE "jarvis" -- DESIGN.md` returns nothing.

---

## Phase 7: Docs

- [ ] T014 [P] [L:docs] `docs/frontend.md`: voice input (the mic, hold V, the states and failure lines, `context.voice.transcription_id`, the server-side edited flag), ambience (toggle, preference, reduced motion, ducking), `/jarvis` removed. Follow the doc-style skill.
- [ ] T015 [P] [L:docs] README screenshots refreshed from T012's captures; `AGENTS.md` phase row 193 and the Learned Workspace Facts line on places (the prototype is gone; interim pages gone if T010 deleted them); `specs/README.md` row 193 → Implemented; spec status.
- [ ] T016 [L:docs] Coverage check: `git diff main...HEAD --stat` against plan.md "Docs touched"; record in the Handoffs note.

---

## Dependencies & Execution Order

- T001 → T002 → T003 → T004 (contract) → lanes.
- `voice`: T005 → T006 → T007 → T008. `ambience`: T009. `cut`: T010.
- T011 after the three lanes; T012 and T013 after T011; T014–T015 after T013; T016 last.

## Parallel Example

```text
After the contract step:
  voice:    T005 → T006 → T007 → T008
  ambience: T009
  cut:      T010
Then lead T011, then polish T012 | T013, then docs.
```

## Implementation Strategy

- MVP = US1 (voice) on the contract step. US2 and US4 are small and run beside it. US3 is the overhaul's acceptance bar and runs last over the merged tree.
