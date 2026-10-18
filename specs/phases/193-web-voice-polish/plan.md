# Implementation Plan: Voice and Polish (W8)

**Branch**: `193-web-voice-polish` | **Date**: 2026-10-18 | **Spec**: [spec.md](./spec.md)

**Input**: spec.md with the 2026-10-18 clarifications (user: all recommended). Code read on `main` 29f7f307 (187 landed); 192's contract at `specs/phases/192-voice-transport/contracts/transcribe-voice.md`.

## Summary

- **Voice input.** A new `features/voice-input` slice records with `MediaRecorder`, measures the input level with an `AnalyserNode`, and uploads to 192's `transcribeVoice`. The transcript fills the Ask bar, and the bar's next send carries `context.voice.transcription_id`, both on Ask and through the overlay outbox on every other place. The server computes `edited` by comparing the sent text with the stored transcript (192), so the client sends only the id. Presence gains voice states, and the orb takes a level getter it reads inside its animation frame (no re-render per frame). Hold `v` to talk outside text fields.
- **Ambience.** The prototype's drone moves to `features/ambience`, with a toggle in the Presence head, a per-browser preference, start only on a gesture, no auto-start under reduced motion, and ducking while recording.
- **Cut.** `pages/jarvis`, its route and tests, its `.impeccable/surfaces` notes, the prototype palette-key test, and any leftover `*Interim.tsx` with no importer are deleted. `/jarvis` gets no redirect (hard cut; the `*` route shows not found).
- **Polish.** Every place is critiqued to at least 30/40 and walked by keyboard and under reduced motion; captures go in the Handoffs note. DESIGN.md is refreshed through `/impeccable document`.

## Technical Context

**Language/Version**: TypeScript 5, React 19, Zustand, TanStack Query 5.
**Primary Dependencies**: none new. Browser APIs: `MediaRecorder`, `getUserMedia`, Web Audio (`AudioContext`, `AnalyserNode`).
**Storage**: `localStorage` key `ze.ambience` (`"on"`/`"off"`), read and written in try/catch.
**Testing**: vitest + Testing Library, with fakes for `MediaRecorder`, `navigator.mediaDevices`, `AudioContext` and the SDK call; pure functions (mime choice, level mapping, level smoothing, presence derivation) tested directly.
**Target Platform**: desktop and phone browsers (Chrome/Edge/Firefox record WebM or Ogg Opus, Safari records MP4/AAC).
**Project Type**: web app only. No backend, no migration.
**Constraints**: FSD (pages → widgets → features → entities → shared; features never import features, so `widgets/app-shell` wires voice, ask-bar and ambience together through props and slots); DESIGN.md modules, 44 px targets, reduced motion.
**Scale/Scope**: one recording at a time; at most 115 s (192 refuses over 120 s); Opus at 64 kbit/s keeps a full recording near 1 MB, far under 192's 10 MB limit.

## Constitution Check

| Principle | Check |
|---|---|
| I Spec-first | spec, clarifications, plan, research, data model, contract, quickstart, tasks. |
| III Layered packages | ze-web only; FSD layers respected (see Constraints). |
| V Tests | Fail-first per task; browser APIs faked. |
| VIII Hard cuts | The prototype, its route, notes, test and leftover interim files are deleted, with no redirect. The disabled mic placeholder is replaced, not kept beside the new one. |

Gate: pass.

## Blast radius

`git grep` on `187-web-ask-assemble` (graphify is re-run in T001 on the branch with 187, 192 and 186–190 merged):

| Symbol / file | Callers | Change |
|---|---|---|
| `AskBar` (`features/ask-bar/ui/AskBar.tsx`) | `widgets/app-shell/ui/AppShell.tsx` | The disabled mic `Control` is replaced by a `renderMic(blocked)` prop. `submit` merges `{ voice: { transcription_id } }` into the explicit context when the store holds a voice id. |
| `useAskOverlay` (`features/ask-bar/model/ask-overlay.ts`: `OutboxItem` :4-10, `INITIAL` :52, `submit` :65-69, `ack` :84-90, `close` :92-93) | AskBar, AppShell, AboutPanel, TryChips, `widgets/assemble/ui/AskOverlay.tsx` (sends `outbox.context`) | Gains `voiceId` (in `INITIAL`), `setVoiceTranscript(text, id)`. `submit` copies `voiceId` into `OutboxItem.voiceId` and merges `voice: { transcription_id }` into the outbox context, then clears `voiceId`; `close` returns an unsent outbox's text and its `voiceId` to the bar; `setDraft("")` clears `voiceId`. |
| `PresenceEvent`, `PresenceState`, `nextPresence` (`entities/presence/model/presence.ts`), `presenceActions` (`store.ts`) | AppShell, AskBar, turn-stream | Adds `voice: "none" \| "recording" \| "transcribing"` and the events `voice_recording`, `voice_transcribing`, `voice_idle`; derive puts voice right after offline. |
| `Orb` (`shared/ui/hud/presence/Orb.tsx`) | `Presence` | New optional prop `level?: () => number` read inside the frame while listening; ignored under reduced motion. |
| `Presence` (`shared/ui/hud/presence/Presence.tsx`) | AppShell | New props `headSlot?: ReactNode` (the ambience toggle) and `level?: () => number`. |
| `AppShell` (`widgets/app-shell/ui/AppShell.tsx`) | router | Wires `VoiceMic` into `renderMic`, `useHoldToTalk`, the transcript into the bar, the overlay-close stop, `AmbienceToggle` into `headSlot`, and the level getter into `Presence`. |
| `pages/jarvis/*` (`JarvisApp`, `JarvisShell`, `hud/{FieldChart,useAmbience}`, `model/*`, `views/WorldView`) | `app/router/routes.tsx:57-58`, `routes.test.tsx:36,82-84`, `shared/config/places.test.ts:35`, `shared/lib/palette.test.ts:26` ("does not read the prototype key") | Deleted; route and tests removed; no redirect; the palette test case deleted (the key it guards against no longer exists anywhere). |
| `.impeccable/surfaces/apps-ze-web-src-pages-{jarvis,home}.md` | none (design notes) | Deleted. |
| `pages/ask/ui/AskInterim.tsx`, `pages/doing/ui/DoingInterim.tsx` (on `main` today) | their place pages until 187/188 land | Deleted only if nothing imports them when 193 starts (187 and 188 plan to delete them). |
| `DESIGN.md:161-162` | docs | Becomes: "Source of truth for the web app (`apps/ze-web`). Every token below is a CSS custom property in `apps/ze-web/src/shared/styles/ze.css`; the five places are the reference implementation." |
| `WsScreenContext` (generated) | `sendTurn` | Must carry `voice` after 192's codegen; T001 checks. |

## Design

### entities/presence

- `PresenceState.voice: "none" | "recording" | "transcribing"` (base `"none"`).
- Events: `{ type: "voice_recording" }`, `{ type: "voice_transcribing" }`, `{ type: "voice_idle" }`.
- `derive`: offline → error; then `voice === "recording"` → `listening`, phrase "listening"; `voice === "transcribing"` → `thinking`, phrase "transcribing"; then the existing order (done, turn, ask text, world signal, idle).
- `presenceActions.voice(state)` dispatches the matching event.

### shared/ui/hud/presence

- `Orb` prop `level?: () => number` (0–1). In each frame while the state is `listening` and motion is allowed, `smoothLevel(prev, raw)` (attack 0.5, release 0.12 per frame) scales the listening program's gather and brightness by `1 + 0.6 * level`. Under reduced motion the getter is never called. `smoothLevel` is a pure export in `presence/level.ts`.
- `Presence` passes `level` to the orb and renders `headSlot` in `presence-head` after the clock.

### features/ask-bar

- `AskBar` props `renderMic?: (blocked: string | null) => ReactNode` (inside `.ask`, one grid cell, the button only) and `renderVoiceStatus?: () => ReactNode` (a sibling above `.ask` in the form, like the attachment chips, so the bar's grid and height never change). Without them nothing renders (the disabled placeholder is gone). `blocked` is the bar's own reason (displaced window or offline).
- `useAskOverlay`: `voiceId: string | null`; `setVoiceTranscript(text, id)` sets the draft (replacing an empty draft, or appending after one space) and the id, then bumps `focusTick` (the existing focus path puts the caret at the end); `setDraft("")` clears `voiceId`; `aboutSent()` clears it.
- `submit` on Ask: `explicit = voiceId ? { ...(explicitContext ?? {}), voice: { transcription_id: voiceId } } : explicitContext`. A chat-about context with `captured_at` keeps its snapshot; `sendTurn` merges as today; a refused send keeps the draft and `voiceId`. On every other place the shell calls the store's `submit`, which carries `voiceId` in the outbox (see the blast radius), so a spoken message sent from World, Doing, Mind or Governance is a voice turn too.

### features/voice-input (new)

- `lib/mime.ts`: `pickMime(isTypeSupported)` returns the first of `audio/webm;codecs=opus`, `audio/ogg;codecs=opus`, `audio/mp4` the browser supports, else `null`; `extensionFor(mime)` → `webm` / `ogg` / `m4a`.
- `lib/level.ts`: `levelFromSamples(Float32Array)`: RMS → dBFS → `clamp((db + 60) / 50, 0, 1)`.
- `lib/recorder.ts`: `startRecorder({ onLevel, mime })` opens `getUserMedia({ audio: true })`, starts `MediaRecorder` (`audioBitsPerSecond: 64000`, 250 ms timeslice), runs an `AnalyserNode` (`fftSize` 1024) on a rAF loop writing the level to a module ref, and returns `stop(): Promise<Blob>`, which stops the recorder, every track and the audio context.
- `api/transcribe.ts`: `transcribe(blob, mime)` calls the generated `transcribeVoice` with `file = new File([blob], "recording.<ext>", { type: mime })` and reads `{ data, error, response }` (the status comes from `response.status`, not the thrown error). It returns `{ transcript, transcriptionId }` or throws `VoiceError { kind, detail }`:
  - `retryable` for 422, 502, any other 5xx except 503, and a network failure (no response); `detail` is the server's line or "I couldn't make out the recording.";
  - `rerecord` for 413 and 415, with the server's line (too large, too long, unsupported);
  - `unavailable` for 503, with the server's line.
- `model/store.ts` (Zustand): `status: "idle" | "recording" | "transcribing" | "failed" | "unavailable"`, `startedAt`, `reason` (why unavailable), `failure: { kind: "retryable" | "rerecord", detail } | null`, `notice` (`"heard_nothing"` or null), `pending: { blob, mime } | null`; actions `start()`, `stop()`, `retry()` (only for `retryable`), `dismiss()`, and `currentLevel()` (reads the module ref, and returns 0 unless the status is `recording`, so a typed "listening" orb never moves with stale levels). Each status change calls `presenceActions.voice(...)`. On a transcript, `onTranscript(text, id)` (registered by AppShell) is called; an empty trimmed transcript sets `notice: "heard_nothing"` and calls nothing. 115 s after start, `stop()` runs on its own; from 105 s the mic shows the seconds left.
- Start failures: `NotAllowedError` → unavailable, "Microphone access is blocked. Allow it in the browser's site settings."; `NotFoundError` or no `mediaDevices` → unavailable, "No microphone found."; `pickMime` null or no `MediaRecorder` → unavailable, "This browser can't record audio." A 503 → unavailable with the server line "Voice input is not available on this server." Unavailable lasts until reload.
- `ui/VoiceMic.tsx` (`{ blocked }`): a 44 px `Control`. Idle: mic icon, label "Speak to Ze (hold V)". Recording: stop icon, mono elapsed `m:ss` (from 105 s, the seconds left), `aria-pressed`, label "Stop recording". Transcribing: `aria-busy`, disabled, label "Transcribing". Unavailable or `blocked`: disabled, the reason as label and title.
- `ui/VoiceStatus.tsx`: the `role="status"`, `aria-live="polite"` line rendered through `renderVoiceStatus`: "Transcribing…"; a `retryable` failure's line with Retry and Dismiss; a `rerecord` failure's line with Record again (dismiss, then start) and Dismiss; "Ze heard nothing" (cleared on the next start or after 6 s).
- `model/useHoldToTalk.ts` (`enabled`): `keydown` of `v` with no modifiers, not repeated, no text field focused, no dialog open, status idle → `start()`; `keyup` of `v` → `stop()`. A hold shorter than 300 ms discards the recording (no upload). Window `blur` during a hold stops and transcribes.

### features/ambience (new)

- `model/useAmbience.ts`: the prototype's drone moved unchanged (oscillators, LFO, low-pass, 0.16 gain), plus:
  - preference: `ze.ambience` read on mount (try/catch, default off) and written on toggle;
  - arming: a remembered "on" starts at the first `pointerdown` or `keydown` on `window`; under reduced motion it waits for a press of the toggle itself; after creating the `AudioContext` it calls `ctx.resume()` (Safari creates it suspended outside the gesture's task);
  - ducking: while the presence `voice` is `recording`, the master gain goes to 0 (`setTargetAtTime`, 0.1 s) and returns to 0.16 after.
- `ui/AmbienceToggle.tsx`: a 44 px `Control` with `aria-pressed`, label "Ambience on" / "Ambience off", lucide `Volume2` / `VolumeX`.

### widgets/app-shell

- `AskBar renderMic={(blocked) => <VoiceMic blocked={blocked} />} renderVoiceStatus={() => <VoiceStatus />}`; `useHoldToTalk(!blocked)`; `registerTranscript((text, id) => useAskOverlay.getState().setVoiceTranscript(text, id))`; when the overlay closes while recording, `stop()`; `Presence headSlot={<AmbienceToggle />} level={currentLevel}`.

### Cut and redirect

- Delete `apps/ze-web/src/pages/jarvis/` and the two surface notes; remove the route (`routes.tsx:57-58`) and its tests (`routes.test.tsx:36,82-84`); `places.test.ts:35` asserts `placeOf("/jarvis")` is null and the route renders not found; delete the `palette.test.ts:26` case. No redirect entry.
- SC-002 grep: `git grep -niE "jarvis" -- apps/ze-web/src apps/ze-web/.impeccable/surfaces DESIGN.md` returns nothing. Exempt as history: `apps/ze-web/.impeccable/plan/` and the phase rows of `AGENTS.md` (655, 659) and `specs/`.

### Polish

- `/impeccable critique` on World, Ask, Doing (index, goal detail, workflow detail), Mind and Governance, each ≥ 30/40 with the detector clean; fixes in place; keyboard walk (every control reachable, visible focus, no trap) and reduced motion (no cascade, sweep or orb motion beyond opacity during a turn); captures at 1440 and 390 with no console errors; results in the Handoffs note.
- `/impeccable document` refreshes `DESIGN.md` (Navigation, Components; prototype asides removed).

## Project Structure

### Documentation (this feature)

```text
specs/phases/193-web-voice-polish/
├── spec.md, plan.md, research.md, data-model.md, quickstart.md, tasks.md
├── contracts/voice-ui.md
└── checklists/requirements.md
```

### Source Code

```text
apps/ze-web/src/entities/presence/model/{presence.ts,store.ts}
apps/ze-web/src/shared/ui/hud/presence/{Orb.tsx,Presence.tsx,level.ts (new)}
apps/ze-web/src/features/ask-bar/{ui/AskBar.tsx,model/ask-overlay.ts}
apps/ze-web/src/features/voice-input/ (new)
apps/ze-web/src/features/ambience/ (new)
apps/ze-web/src/widgets/app-shell/ui/AppShell.tsx
apps/ze-web/src/app/router/routes.tsx ; shared/config/places.ts
apps/ze-web/src/pages/jarvis/ (deleted) ; apps/ze-web/.impeccable/surfaces/*{jarvis,home}.md (deleted)
DESIGN.md
```

## Docs touched

- `docs/frontend.md`: voice input (mic, hold V, failure lines, the voice context), ambience, the `/jarvis` removal.
- `DESIGN.md`: refreshed by the polish lane (FR-007).
- README screenshots refreshed from the polish captures (FR-009).
- `AGENTS.md`: phase row 193; the Learned Workspace Facts line on places (prototype gone). `specs/README.md` row 193.

## Lane Plan (Maestri crew)

**Contract step** (lane `lead`, lands first; T002–T004): presence voice states and events; `Orb` `level` and `Presence` `headSlot`/`level`; `AskBar` `renderMic` and the ask-overlay voice fields; the `features/voice-input` and `features/ambience` public APIs as typed stubs (`VoiceMic`, `useHoldToTalk`, `useVoiceInput` with `registerTranscript`, `currentLevel`; `AmbienceToggle`); the AppShell wiring against those stubs; the `/jarvis` route removed and redirected.

| Lane | Model / role | Owns (disjoint) | Tasks | Starts after | Reviewer |
|---|---|---|---|---|---|
| lead | Sonnet ENG lead | `entities/presence/*`, `shared/ui/hud/presence/*`, `features/ask-bar/*`, `widgets/app-shell/*`, `widgets/assemble/ui/AskOverlay.test.tsx` (the outbox voice test), `app/router/*`, `shared/config/places*`, the stub `index.ts` of both new slices; merges, gates | T001–T004, T011 | - | Gauge |
| voice | Sonnet ENG | `features/voice-input/**` except its `index.ts` signatures | T005–T008 | contract step | floor Reviewer |
| ambience | Haiku JR | `features/ambience/**` except its `index.ts` signatures | T009 | contract step | floor Reviewer |
| cut | Haiku JR | deletion of `pages/jarvis/**`, `.impeccable/surfaces/*{jarvis,home}.md`, unimported `pages/*/ui/*Interim.tsx`; the `shared/lib/palette.test.ts` prototype case | T010 | contract step | floor Reviewer |
| polish | Sonnet ENG | any `apps/ze-web/src/**` file a critique finding or a leftover style mapping needs, after the other lanes merge; `DESIGN.md` | T012, T013 | T011 (lanes merged) | Gauge |
| docs | Haiku DOCS | the files in "Docs touched" except `DESIGN.md` | T014–T016 | T013 | floor Reviewer |

**Rules**: one lane per file at a time. `polish` starts only after `lead` has merged `voice`, `ambience` and `cut`, so its broad ownership never overlaps a running lane. `ambience` and `cut` are Haiku JR because their tasks spell out every test and file. `ambience` copies the drone from git (`git show main:apps/ze-web/src/pages/jarvis/hud/useAmbience.ts`), never from the working tree, so `cut` can delete the directory in parallel. If a JR task needs a decision the task does not state, the JR stops and reports to `lead`.

## Complexity Tracking

| Item | Why | Simpler alternative rejected |
|---|---|---|
| Level getter instead of a level prop | The level changes every frame; a prop would re-render Presence 60 times a second. | Level in the presence store (same re-render cost). |
| Slots (`renderMic`, `headSlot`) instead of imports | FSD forbids feature-to-feature and shared-to-feature imports. | Moving voice into ask-bar (mixes two features; ambience still needs the slot). |
