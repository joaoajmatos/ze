# Contract: voice and ambience UI seams

These are the signatures the contract step lands; lanes `voice` and `ambience` fill them in.

## Server (from 192, unchanged)
- `transcribeVoice` (`POST /api/v0/voice/transcriptions`, multipart `file`) → `{ transcript, duration_s, transcription_id }`; errors per 192's contract (503 means voice is off on this server).
- WS `message` frame: `context.voice = { transcription_id }`. The server computes `input.edited`.

## entities/presence
```ts
type PresenceEvent = … | { type: "voice_recording" } | { type: "voice_transcribing" } | { type: "voice_idle" };
interface PresenceState { …; voice: "none" | "recording" | "transcribing" }
presenceActions.voice(state: "none" | "recording" | "transcribing"): void
```

## shared/ui/hud/presence
```ts
<Orb … level?: () => number />                        // read per frame while listening; never under reduced motion
<Presence … headSlot?: ReactNode level?: () => number />
export function smoothLevel(prev: number, raw: number): number   // attack 0.5, release 0.12
```

## features/ask-bar
```ts
<AskBar onSubmit disabledReason renderMic?: (blocked: string | null) => ReactNode renderVoiceStatus?: () => ReactNode />
useAskOverlay: { voiceId: string | null; setVoiceTranscript(text: string, id: string): void }
OutboxItem: { …; voiceId?: string }   // its context carries voice: { transcription_id }
```
On Ask, AskBar's submit adds `voice: { transcription_id: voiceId }` to the explicit context. Elsewhere, the store's `submit` puts it in the outbox context. `close` returns an unsent outbox's text and `voiceId` to the bar.

## features/voice-input (index)
```ts
export function VoiceMic(props: { blocked: string | null }): JSX.Element
export function VoiceStatus(): JSX.Element
export function useHoldToTalk(enabled: boolean): void
export const useVoiceInput: UseBoundStore<…VoiceInputState & { start(); stop(); retry(); dismiss() }>
export function registerTranscript(cb: (text: string, transcriptionId: string) => void): () => void
export function currentLevel(): number   // 0 unless recording
```

## features/ambience (index)
```ts
export function AmbienceToggle(): JSX.Element
```

## Router
No `jarvis` route and no redirect: `/jarvis` renders not found.
