# Data Model: Voice Input Transport (B3)

No tables. In-memory and trace shapes only.

## Transcription (ze-core `voice.py`, returned by `transcribe_audio`)
| Field | Type | Rule |
|---|---|---|
| text | str | stripped; may be empty |
| duration_s | float | from the two-step probe (research R1); 0 < d ≤ 120 |

## Registry entry (ze-api `voice/registry.py`)
| Field | Type | Rule |
|---|---|---|
| transcription_id | str | `uuid4().hex`, 32 chars |
| text | str | as transcribed |
| duration_s | float | |
| created_at | datetime (UTC) | expires at +10 min; swept on access; at most 100 entries, oldest dropped |

## VoiceInput (ze-agents `interface/types.py`, on `RawInput.voice`)
| Field | Type | Rule |
|---|---|---|
| duration_s | float | from the registry |
| edited | bool | server-computed (research R5) |

## InputTrace (ze-core `conversation/messages/types.py`, `MessageTrace.input`)
| Field | Type | Rule |
|---|---|---|
| modality | str | `voice` (only voice turns carry the section) |
| duration_s | float \| None | |
| edited | bool \| None | |
Never the transcript text (clarification Q2). Read back by the message store's trace parser (`input` absent on old rows → `None`).

## Removed
`RawInput.audio`, `RawInput.audio_mime`, `AgentState.audio_data`, `AgentState.audio_mime`, `invoke_raw(audio_data=, audio_mime=)`.
