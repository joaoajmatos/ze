# Quickstart: Voice and Polish (W8)

## Automated
- `make test-web`, `make typecheck-web`, `make web-build`, `make lint`.
- `git grep -niE "jarvis" -- apps/ze-web/src apps/ze-web/.impeccable/surfaces DESIGN.md` returns nothing.

## Manual against `make dev-full` (192 on main, ffmpeg installed)
1. Press the mic, say "remind me to call Ana tomorrow" for about 10 s, press stop. The orb listens and follows your voice; Presence reads "transcribing"; the text lands in the Ask bar, focused, within 5 s (SC-003). Send it: the trace panel shows a voice input; edit a word first and it shows edited.
2. Hold `v` (focus outside the bar), speak, release: the same flow. A quick tap of `v` does nothing.
3. Let a recording run: from 105 s the mic counts down, and at 115 s it stops and transcribes by itself (192 accepts it).
3a. On World, press the mic, speak, send from the overlay: the trace shows a voice input (the outbox carried the reference). Close the overlay before it sends: the text and the reference return to the bar.
3b. On a real iPhone or Mac Safari: record and send; the recording is MP4 and 192 measures and transcribes it.
4. Stop the backend's ffmpeg (or point at a server without it): the mic reads "Voice input is not available on this server." and stays disabled.
5. Block the microphone in site settings and press the mic: "Microphone access is blocked…", mic disabled with that label.
6. Record silence: "Ze heard nothing"; nothing is sent.
7. Simulate a failed upload (devtools offline after stop): "I couldn't make out the recording." with Retry; back online, Retry transcribes the same recording. A refused type or size (mock a 415 or 413) shows the server's line with Record again, not Retry.
8. Ambience: off on a fresh profile; turn on, reload, it starts at your first click; with reduced motion set, it waits for the toggle; it goes silent while recording.
9. `/jarvis` shows not found.
10. Critique each place (≥ 30/40), walk each by keyboard and with reduced motion, capture at 1440 and 390; record in the Handoffs note.
