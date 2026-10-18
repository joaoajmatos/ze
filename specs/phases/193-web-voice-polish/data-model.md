# Data Model: Voice and Polish (W8)

Client state only. No backend entity, no migration.

## VoiceInputState (`features/voice-input/model/store.ts`)

| Field | Type | Notes |
|---|---|---|
| status | `"idle" \| "recording" \| "transcribing" \| "failed" \| "unavailable"` | |
| startedAt | number \| null | `Date.now()` at start; elapsed shown as `m:ss` |
| reason | string \| null | the plain line when `unavailable` |
| failure | `{ kind: "retryable" \| "rerecord", detail: string }` \| null | set when `failed`; `detail` is the server's line |
| notice | `"heard_nothing"` \| null | cleared on the next start or after 6 s |
| pending | `{ blob: Blob, mime: string }` \| null | kept from stop until a transcript arrives or the user dismisses; Retry re-uploads it |

Transitions: idle → recording (start) → transcribing (stop, button, 115 s, key release, overlay close, window blur during a hold) → idle (transcript, or `notice` when empty) or failed (unreadable) or unavailable (503). failed (retryable) → transcribing (retry) or idle (dismiss); failed (rerecord) → recording (record again) or idle (dismiss). Any start failure → unavailable. A hold under 300 ms → idle with `pending` null.

## Presence additions (`entities/presence`)

| Field | Type | Notes |
|---|---|---|
| voice | `"none" \| "recording" \| "transcribing"` | recording → orb `listening`, phrase "listening"; transcribing → orb `thinking`, phrase "transcribing"; ranks right after offline |

## Ask overlay additions (`features/ask-bar`)

| Field | Type | Notes |
|---|---|---|
| voiceId | string \| null | 192's `transcription_id`; in `INITIAL`; cleared on send and when the draft is emptied; copied into `OutboxItem.voiceId` by the overlay `submit` and returned to the bar by `close` with the unsent text |

## Ambience preference

`localStorage["ze.ambience"]`: `"on"` or `"off"`; absent or unreadable means off.
