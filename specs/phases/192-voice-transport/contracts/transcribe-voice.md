# Contract: transcribeVoice and the voice message context

## REST `POST /api/v0/voice/transcriptions` (`operation_id: transcribeVoice`)
- Auth: `Authorization: Bearer <ZE_API_KEY>`.
- Body: `multipart/form-data`, field `file`, content type one of `audio/webm`, `audio/ogg`, `audio/mp4`, `audio/m4a`, `audio/x-m4a`, `audio/wav`, `audio/x-wav` (codec parameters allowed).
- 200 `TranscriptionResponse` (an empty transcript is registered like any other; the client decides not to send it):
  ```json
  { "transcript": "remind me to call Ana", "duration_s": 3.4, "transcription_id": "9f2c…" }
  ```
- Errors (`{ "detail": "<plain line>" }`):
  | Status | When | detail |
  |---|---|---|
  | 413 | over 10 MB (declared or read), or over 120 s | "That recording is too large: the limit is 10 MB." / "That recording is too long: the limit is 2 minutes." |
  | 415 | other type | "Unsupported recording type. Use WebM, Ogg, MP4 or WAV." |
  | 422 | length cannot be determined | "I couldn't make out the recording." |
  | 502 | speech model failed | "I couldn't make out the recording." |
  | 503 | ffmpeg missing on the server | "Voice input is not available on this server." |
  | 422 | no `file` part, or not multipart | "Send the recording as a file named file." |

- A declared `Content-Length` over the limit is refused with the same 413 before the body is read.
- WebM and fragmented MP4 (what browsers record) are measured; a progressive MP4 with its index at the end is refused as unreadable (422).

## WS `message` frame: `context.voice`
```json
{ "type": "message", "text": "remind me to call Ana tomorrow", "thread_id": "…",
  "context": { "voice": { "transcription_id": "9f2c…" } } }
```
- A live id makes the turn a voice turn; an unknown or expired id is ignored (text turn).

## Trace: `input`
On `MessageTraceResponse` and `WsTraceUpdateFrame`:
```json
"input": { "modality": "voice", "duration_s": 3.4, "edited": true }
```
Absent (null) on text turns.
