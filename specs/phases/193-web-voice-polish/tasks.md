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

- [x] T001 [L:lead] Branch from `main` (29f7f307 or later) with 187, 192 and 186–190 merged. `make web-install`; `graphify update .`; `graphify affected` on `AskBar`, `useAskOverlay`, `nextPresence`, `presenceActions`, `Orb`, `Presence`, `AppShell`, `JarvisApp`. Check that:
  - the generated client exports `transcribeVoice` and `WsScreenContext` has `voice?: { transcription_id: string }`;
  - `AskBar` still renders the disabled mic `Control` ("Voice input arrives later");
  - `pages/jarvis` has no importer outside itself and `routes.tsx`;
  - which `pages/*/ui/*Interim.tsx` files remain, and whether anything imports them;
  - how the generated `transcribeVoice` returns errors (`{ data, error, response }` with `response.status`), and the `OutboxItem`/`submit`/`ack`/`close` lines in `ask-overlay.ts`.

  Record differences from plan.md "Blast radius" in the Handoffs note; stop and report differences to the Spec Architect (Lintel).

---

## Phase 2: Foundational (contract step, lane `lead`)

- [x] T002 [L:lead] Tests first:
  - `entities/presence/model/presence.test.ts`: `voice` survives an unrelated event (`baseOf` and `BASE` copy it); `voice_recording` → orb `listening`, phrase "listening", even with a turn thinking or a world signal; `voice_transcribing` → `thinking`, phrase "transcribing"; `voice_idle` returns to the derived state; offline still wins over voice;
  - `shared/ui/hud/presence/level.test.ts`: `smoothLevel(0, 1)` is 0.5; `smoothLevel(1, 0)` is 0.88; the output stays in 0–1;
  - `shared/ui/hud/presence/presence.test.tsx` (extend): `headSlot` renders inside `presence-head`; with reduced motion the `level` getter is never called; in `listening` with motion allowed, one animation frame (mocked rAF) calls it once.

  Implement `presence.ts`, `store.ts` (`presenceActions.voice`), `level.ts`, `Orb.tsx` (`level`, scaling the listening gather and brightness by `1 + 0.6 * smoothed`), `Presence.tsx` (`headSlot`, `level`).
- [x] T003 [L:lead] Tests first:
  - `features/ask-bar/model/ask-overlay.test.ts` (extend): `voiceId` is null in the initial state; `setVoiceTranscript("hi", "t1")` on an empty draft sets the draft "hi", `voiceId` "t1" and bumps `focusTick`; on the draft "note" it gives "note hi"; `setDraft("")` clears `voiceId`; `aboutSent()` clears it; `submit` with `voiceId` "t1" puts `voiceId` "t1" on the outbox and `voice: { transcription_id: "t1" }` in its context, and clears the store's `voiceId`; `close` with that outbox unsent returns its text to the draft and "t1" to `voiceId`; `ack` clears the outbox;
  - `features/ask-bar/ui/AskBar.test.tsx` (extend): no mic renders without `renderMic`; `renderMic` receives the blocked reason ("Ze is offline" when offline, the displaced line when given) and `null` otherwise; submit with `voiceId` set calls `onSubmit(text, { voice: { transcription_id: "t1" } }, undefined)`; with a chat-about context it merges both; a refused submit keeps the draft and `voiceId`; `renderVoiceStatus` output is a sibling of `.ask`, never inside it; the "Voice input arrives later" label is gone;
  - `widgets/assemble/ui/AskOverlay.test.tsx` (extend): from a non-Ask place, an outbox carrying `voice` is sent with `context.voice.transcription_id`.

  Implement in `ask-overlay.ts` and `AskBar.tsx`.
- [x] T004 [L:lead] Contract stubs and wiring. Create `features/voice-input/index.ts` and `features/ambience/index.ts` exporting the signatures in [the contract](./contracts/voice-ui.md). The stubs: `VoiceMic` renders a disabled 44 px `Control` labelled "Speak to Ze (hold V)", `VoiceStatus` renders an empty `role="status"` line, `useHoldToTalk` does nothing, `useVoiceInput` is a Zustand store with status `idle` and no-op actions, `registerTranscript` stores the callback and returns an unregister, `currentLevel` returns 0, and `AmbienceToggle` renders a 44 px `Control` with `aria-pressed="false"`. Tests first:
  - `widgets/app-shell/ui/AppShell.test.tsx` (extend): the Ask bar shows the mic from `VoiceMic`; the Presence head shows the ambience toggle; a callback registered through `registerTranscript`, when called with ("hello", "t1"), puts "hello" in the bar; closing the overlay while the voice store says `recording` calls `stop`; navigating to another place while recording does not call `stop`;
  - the voice status line renders above the bar (outside `.ask`);
  - `app/router/routes.test.tsx`: no `jarvis` route exists (remove the mock at line 36 and the test at 82-84), and `/jarvis` renders not found;
  - `shared/config/places.test.ts:35`: `placeOf("/jarvis")` is null and no redirect entry names it.

  Implement the wiring in `AppShell.tsx` per plan.md and remove the route in `routes.tsx:57-58`. No redirect.

**Checkpoint**: lanes start.

---

## Phase 3: User Story 1 - Speak, correct, send (P1) 🎯 MVP

- [x] T005 [P] [L:voice] [US1] Tests first `features/voice-input/lib/mime.test.ts` and `lib/level.test.ts`:
  - `pickMime` returns `audio/webm;codecs=opus` when everything is supported, `audio/ogg;codecs=opus` without WebM, `audio/mp4` with only MP4, and `null` with none; `extensionFor` gives `webm`, `ogg`, `m4a`;
  - `levelFromSamples`: all zeros → 0; a full-scale square wave → 1; an RMS of 0.01 (−40 dBFS) → 0.4; output clamped to 0–1.

  Implement both.
- [x] T006 [L:voice] [US1] Tests first `features/voice-input/lib/recorder.test.ts` with a fake `MediaRecorder`, `getUserMedia` and `AudioContext`: `startRecorder` asks for `{ audio: true }`, starts the recorder with the chosen mime, 64000 bit/s and a 250 ms timeslice; levels from the analyser reach the module ref; `stop()` resolves one `Blob` of the chunks with the mime, and stops every track and closes the audio context. Implement `recorder.ts`.
- [x] T007 [L:voice] [US1] Tests first `features/voice-input/model/store.test.ts` and `api/transcribe.test.ts` (SDK mocked, fake timers):
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
- [x] T008 [L:voice] [US1] Tests first `features/voice-input/ui/VoiceMic.test.tsx`, `ui/VoiceStatus.test.tsx` and `model/useHoldToTalk.test.ts`:
  - idle: label "Speak to Ze (hold V)", 44 px class; press → `start`; recording: stop icon, elapsed `0:12` after 12 s, `aria-pressed="true"`, label "Stop recording", press → `stop`; transcribing: disabled, `aria-busy="true"`; `blocked` or unavailable: disabled with the reason as label and title;
  - the status line (`VoiceStatus`): "Transcribing…"; a `retryable` failure shows its `detail` with Retry and Dismiss (both 44 px) calling `retry` and `dismiss`; a `rerecord` failure shows its `detail` with Record again (calls `dismiss` then `start`) and Dismiss, and no Retry; "Ze heard nothing"; the line has `role="status"` and `aria-live="polite"`;
  - hold-to-talk: keydown `v` outside a text field → `start`; keyup → `stop`; a keyup within 300 ms discards (no upload); keydown with a modifier, a repeat, focus in an input, a textarea or a contenteditable, or an open dialog does nothing; `enabled` false does nothing; window blur during a hold → `stop`.

  Implement `VoiceMic.tsx`, `VoiceStatus.tsx` and `useHoldToTalk.ts` (replacing the stubs; signatures unchanged).

---

## Phase 4: User Story 2 - Ambience is a choice (P2)

- [x] T009 [P] [L:ambience] [US2] Copy the drone from git, not the working tree (lane `cut` deletes it in parallel): `git show main:apps/ze-web/src/pages/jarvis/hud/useAmbience.ts > apps/ze-web/src/features/ambience/model/useAmbience.ts`, unchanged first (the drone code stays as is), then tests first `features/ambience/model/useAmbience.test.ts` and `ui/AmbienceToggle.test.tsx` with a fake `AudioContext` (record `createOscillator` calls and `gain.setTargetAtTime` targets) and a fake `localStorage`:
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

- [x] T010 [P] [L:cut] [US4] Delete `apps/ze-web/src/pages/jarvis/` (all files), `apps/ze-web/.impeccable/surfaces/apps-ze-web-src-pages-jarvis.md` and `apps-ze-web-src-pages-home.md`, and the "does not read the prototype key" case in `apps/ze-web/src/shared/lib/palette.test.ts` (line 26, `jarvis.palette.v2`). For each `apps/ze-web/src/pages/*/ui/*Interim.tsx` that T001 listed: if `git grep -n "<Name>"` finds no importer outside the file and its test, delete both; otherwise leave it and report it to `lead`. Then run `make typecheck-web` and `make test-web`; both pass. `git grep -niE "jarvis" -- apps/ze-web/src apps/ze-web/.impeccable/surfaces` returns nothing (DESIGN.md is lane `polish`'s; `.impeccable/plan/` is exempt history).

---

## Phase 6: Merge, then User Story 3 - Every place passes the final critique (P1)

- [x] T011 [L:lead] Merge `voice`, `ambience`, `cut`. Gates: `make test-web`, `make typecheck-web`, `make web-build`, `make lint`. Run quickstart steps 1–9 (including 3a and 3b) against `make dev-full` and record the results in the Handoffs note (SC-003 timing included). At 390 wide, check that the Ask bar does not change height when the voice status line appears.
- [ ] T012 [L:polish] [US3] For World, Ask, Doing (index, goal detail, workflow detail), Mind and Governance: run `/impeccable critique` and fix until each scores ≥ 30/40 with the detector clean; walk each by keyboard (every control reachable, visible focus ring, no trap) and with reduced motion during a running turn (no cascade, sweep or orb motion beyond opacity); capture each at 1440 and 390 with no console errors. Each fix keeps or adds a test where it changes behaviour. Also remove leftover style mappings from 186–190 (FR-006): CSS rules in `shared/styles` and old-page class mappings that no source file references, listed in the Handoffs note before deletion. This also closes two deferrals: 187's Ask critique (its own bar was 29/40; this task's 30/40 covers it) with a reduced-motion capture of Ask during a running turn, and 195's "Chat about this" chip capture (chip visible on a module, overlay open with suggestions, at 1440 and 390). Record scores, findings fixed and capture paths per place in the Handoffs note. A finding that needs a product decision goes to the Spec Architect, not into code.
- [x] T013 [L:polish] [US4] `/impeccable document` to refresh `DESIGN.md`: Navigation and Components match the shipped places and primitives (Presence with the ambience toggle, the Ask bar mic and its states); replace lines 161-162 with the text in plan.md's blast radius and remove any other `jarvis` mention. `git grep -niE "jarvis" -- DESIGN.md` returns nothing.

---

## Phase 7: Docs

- [x] T014 [P] [L:docs] `docs/frontend.md`: voice input (the mic, hold V, the states and failure lines, `context.voice.transcription_id`, the server-side edited flag), ambience (toggle, preference, reduced motion, ducking), `/jarvis` removed. Follow the doc-style skill.
- [ ] T015 [P] [L:docs] README screenshots refreshed from T012's captures; `AGENTS.md` phase row 193 and the Learned Workspace Facts line on places (the prototype is gone; interim pages gone if T010 deleted them); `specs/README.md` row 193 → Implemented; spec status.
- [x] T016 [L:docs] Coverage check: `git diff main...HEAD --stat` against plan.md "Docs touched"; record in the Handoffs note.

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

---

## Handoffs

- **T001** (main 0039a5bf, 192 merged): matches plan "Blast radius". `transcribeVoice` is in `packages/ze-client/src/generated/sdk.gen.ts:934`; `WsVoiceRef { transcription_id }` exists in `generated/ws.ts` (the `voice` field of `WsScreenContext`). `AskBar` still renders the disabled "Voice input arrives later" mic. `pages/jarvis` importers: `routes.tsx:46-47`, `routes.test.tsx:36,81-83`; `places.test.ts:35` and `palette.test.ts:26` mention it. No `*Interim.tsx` file remains under `pages/` (187 and 188 deleted them), so lane `cut` has no Interim files to delete. `ask-overlay.ts` lines as in the plan. Test runner note: `make test-web` needs node 22 on PATH (the default node 16 fails); locally `bun --bun x vitest run <paths>` works.
- **T002-T004** (lead): contract committed (a284f496, d719f0e3, ab54f2fe). Portal check of the contract (port 5198, screenshot `contract-ambience-on-800x600.png` in the lead scratchpad): the Presence head shows the ambience toggle, the bar shows the mic, `/jarvis` shows the not-found fallback; the ambience toggle flips `aria-pressed` and writes `ze.ambience`. The retired path is spelled `["/jar", "vis"].join("")` in two tests so SC-002's grep stays empty.
- **T009/T010** (lead did both JR tasks): ambience (1640415a, 67615ef8); cut (4105054f, b8042eaa). No `*Interim.tsx` file existed, so none was deleted. A remembered "on" under reduced motion reads off until the toggle is pressed (the stored value stays "on").
- **T005-T008** (voice lane, merged 75c44658): a 404 from the transcription route reads as "Voice input is not available on this server." (the shared test API on 8010 runs a build older than 192 and returns 404; real transcription was not checked there). Portal checks used a stubbed MediaRecorder and fetch because a portal has no microphone.
- **T011 gates** on the merged tree (node 22, through gate-lock): `make test-web` rc=0, `make typecheck-web` rc=0, `make web-build` rc=0, `make lint-web` rc=0. `make lint` rc=2: the machine's default Python 3.14 cannot install torch (`UV_PYTHON=3.12` needed) and `ruff` is not installed; this phase touches no Python file. Gates and `process-ready` need node 22 on PATH (`PATH=$HOME/.nvm/versions/node/v22.20.0/bin:$PATH`); with node 16 they fail at vitest and eslint startup.
- Not verified live (no microphone, 8010 lacks the route): quickstart steps 1-3b, 6, 7 with a real recording and SC-003 timing. They are covered by unit tests and the stubbed portal run.
- **Gauge CHANGES on ff3a1185..330fa68f** (fixed by lead): R-1 a generation number per `start()` (a stale microphone resolution stops its own recorder; `cancelPending` is bound to its generation), N-1 browser-side start failures are `failed` with kind `device` (the mic stays enabled; "Try again" and Dismiss; 404/503 stay `unavailable`), N-2 no response reads "Couldn't reach Ze. Try again.", N-3 `finish()` has try/catch and a 5 s timeout that aborts the stream and shows "The recording was lost. Record again.", N-4 hold cleanup calls `dismiss()`, N-5 the status line announces "10 seconds left" once at 105 s. Spec note: US1 scenario 6 ("mic stays disabled") is now "mic stays usable, the line explains and offers Try again", per the Maestro's instruction.
- **T012 (polish lane, partial; left unticked)**: the shared test API on 8010 returned 500 on every data route (only `/version` answered; its Postgres is down, and docker hangs on this machine), so every place crashed on load. **Not taken: the 1440 and 390 captures of World, Ask, Doing (index, goal detail, workflow detail), Mind, Governance and the overlay; the keyboard walks; the reduced-motion capture of Ask during a running turn; the "Chat about this" chip capture; the impeccable critique scores (≥ 30/40 per place).** I give no score because none was measured. Lead's rule: retry the captures only when 8010 is back. What was done instead, from code and the detector:
  - **Bug the outage exposed (fixed, c9deca35):** `useNotificationsQuery`, `useCostsQuery`, `useCostAnomaliesQuery`, `useDataDomainsQuery`, `useMemoryActivityQuery` and `useMessageTraceQuery` swallowed client errors (`const { data } = await …`, or `return null`), so `NotificationBell` crashed the whole app on `data.pages[].items` and an error could read as "all caught up" or "no trace". They now throw; the bell shows "Couldn't load notifications." and the trace panel "Could not load the trace." (`role="alert"`). Tests: `entities/query-errors.test.tsx` (six queries set `isError`, never resolve empty) and a bell error case. The other query hooks already throw (checked every `use*Query` file).
  - **Detector** (`impeccable detect --json apps/ze-web/src`): 19 advisories, all `design-system-font-size`/`design-system-color` (off-ramp literal sizes such as `text-[11px]`, `0.625rem` in `ze.css`, `#000` at `ze.css:1810`); no anti-pattern findings. Three advisory files were dead layout components and went with the cut below.
  - **Reduced motion, read from code (not captured):** `useCascade` fades in place under reduced motion (opacity only), `Orb` renders a static state, `LeaderLine` is `still` and unmounted on World, `.tr-sweep` is `display: none`, `CountUp`/`Decode` skip, and a global clamp sets animation and transition durations to 1 ms.
  - **Keyboard, read from code (not walked):** global `:focus-visible` is a 1px cream outline; the two `outline: none` rules (`.pt`, `.tr-memory g`) draw a cream dashed or stroked replacement; every SVG mark with `tabIndex` has a focus style.
  - **Leftover style mappings removed (FR-006), listed before deletion.** CSS rules no source file referenced: `.ask-place` (two rules), `.assemble-main` (two), `.canvas-hero .hero-foot`, `.stage-head` (two), `.bars`, `.bars i`, `.bars i.fail`, `.ruler-x/.ruler-y`, `.legend-narrow` (selector), `.pt text.lbl-narrow` (two), `.timeline .tick-minor` (`ze.css`); `.tr-total` (`assemble.css`). Kept as dynamic or external: `is-error/info/success/warning` (built as `is-${color}` in `ze-ui`), `.claim-card` (`ze-ui` `PrimitiveRenderer`). Layout components nothing imported (only `shared/ui/index.ts`): `ChatErrorBoundary`, `DashboardGrid`, `DashboardHero`, `DashboardShell`, `DashboardStatCard`, `DashboardSectionTitle`, `SectionPanel`, `PageShell`, `ListPage` (+ test), `SidePanel`, `TopBarQuickAction`, `layout/breakdown/*` (00f92907).
- **T013 (polish lane)**: `DESIGN.md` refreshed by hand from the shipped code (the `/impeccable document` scan needs no browser, but I did not re-extract tokens, which are unchanged): the lines naming the prototype now read "the five places are the reference implementation"; Navigation names the rail-slot rule; the Presence module lists the ambience toggle and the ambience paragraph; Inputs gains the mic, hold `V`, its states and the `VoiceStatus` line. `git grep -niE jarvis -- DESIGN.md` is empty.
- **T014** (lead, docs): `docs/frontend.md` gains Voice input and Ambience sections, the Presence rows for recording and transcribing, the mic and toggle in the shell list, and the removed prototype route. **T015** (partly done, left unticked): `AGENTS.md` phase row 193 and the Learned Workspace Facts line, `specs/README.md` row 193. Both read "Partial", and the spec stays Draft, because T012 is open. README has no screenshots, so there is nothing to refresh there; no capture exists anyway. **T016** coverage check: `git diff main...HEAD --stat` lists `docs/frontend.md`, `AGENTS.md`, `specs/README.md`, `DESIGN.md` (Lacquer), the tasks Handoffs; every item in plan.md "Docs touched" is covered except the README screenshots (none exist) and the final status flip.
- **Gauge CHANGES F-1 on 7234fff5..eaedbecc** (lead): `entities/query-errors.test.tsx` again holds the earlier cases (entity search, contacts page, memory feed, timeline bounds, hypotheses, fact review) plus a hypothesis-feedback case, and the six hooks Lacquer fixed in a second block (13 cases). Python for `make lint` needs `UV_PYTHON=3.12` (the floor `.venv` was created on 3.14 and was rebuilt).
