# Ze — Native App Interface

Ze's native interface connects the React web app (`ze-web`) to the backend (`ze-api`)
over a persistent WebSocket. When the app is not connected, Ze falls back to
**ntfy push notifications**.

**Module:** `ze_api/interface/native.py` · `ze_api/api/ws.py`  
**WebSocket endpoint:** `GET /ws`

---

## Overview

![Architecture diagram of the native interface: the React app talks to NativeAppInterface over a bidirectional WebSocket, which always persists outbound messages to MessageStore and falls back to NtfyNotifier only when the client is offline.](diagrams/docs/native-interface.svg)

<sub>[Interactive version](diagrams/docs/native-interface.html)</sub>

`NativeAppInterface` is the `AppInterface` implementation for the native client. It
saves every outbound message to `MessageStore` (for unread replay on reconnect), pushes
it to the active WebSocket connection if one exists, and falls back to ntfy if the
client is offline.

**One connection at a time.** A new WebSocket connection displaces the previous one
with close code `4000`.

---

## Authentication

Pass the API key either as a bearer header or a query parameter:

```
Authorization: Bearer <ZE_API_KEY>
# or
GET /ws?token=<ZE_API_KEY>
```

The server closes connections without a valid key with code `4001`.

---

## Connection sequence

On connect, the server:

1. Closes any previous connection with code `4000`.
2. Fetches all unread messages from `MessageStore` and replays them as
   `{"type": "message", ...}` frames.
3. If a confirmation was pending when the client disconnected, replays the
   `confirm_request` frame so the user can still approve or cancel (see
   [Confirmation flow](#confirmation-flow)).
4. Begins forwarding new messages in real time.

The client should send `{"type": "ack", "ids": [...]}` frames to mark messages as read.

---

## Frame types

### Client → Server

| Frame | When to send | Description |
|---|---|---|
| `{"type": "ping"}` | Heartbeat | Server replies with `{"type": "pong"}` |
| `{"type": "ack", "ids": ["<uuid>", ...]}` | After displaying messages | Marks messages as read in `MessageStore` |
| `{"type": "message", "text": "...", "thread_id": "...", "context": {...}}` | User sends a message | `thread_id` is optional; `context` is optional screen context |
| `{"type": "retry", "message_id": "<uuid>", "thread_id": "...", "confirmed_plan": ["<entry id>", ...]}` | User presses Retry on the latest reply | Undoes what the reply did, then regenerates it. `confirmed_plan` lists the undo entry ids the person confirmed. Omit it or send `null` when the plan is empty. See [Reply feedback and Retry](#reply-feedback-and-retry). |
| `{"type": "command", "name": "cancel"}` | Cancel pending confirmation | Aborts the awaited graph turn |
| `{"type": "command", "name": "costs"}` | Introspection | Returns a 7-day cost summary message |
| `{"type": "command", "name": "status", "period_days": 1}` | Accountability | Returns an activity narrative (default: past 24 h; set `period_days: 7` for the weekly view) |
| `{"type": "command", "name": "onboarding"}` | Setup | Starts or resumes onboarding |
| `{"type": "command", "name": "reset_preview", "scope": "memory"}` | Reset preview | Returns counts for a reset scope |
| `{"type": "command", "name": "reset", "scope": "memory", "confirm": "RESET"}` | Reset | Executes a scoped reset; requires explicit confirmation |
| `{"type": "component_submit", "session_id": "...", "step_id": "...", "component_id": "...", "values": {...}}` | Interactive component | Submits structured onboarding form/button values |

### Server → Client

| Frame | Description |
|---|---|
| `{"type": "pong"}` | Heartbeat reply |
| `{"type": "typing"}` | Sent immediately after receiving a user message while Ze is processing. May include an optional `"text"` field with a localized progress string (e.g. `"📡 Fetching the latest news..."`). Re-sent mid-turn by agents to update the status and reset the client's 3-second display timer. |
| `{"type": "message", "message": Message}` | Outbound message from Ze (see Message shape below) |
| `{"type": "confirm_request", "id": "...", "prompt": "...", "actions": [...]}` | Capability gate confirmation request |
| `{"type": "confirm_cancel", "id": "..."}` | Confirmation cancelled (timeout or cancel command) |
| `{"type": "message_superseded", "message_id": "...", "replaced_by": "...", "thread_id": "..."}` | A retry replaced `message_id` with `replaced_by`. Sent after the new `message` frame. |
| `{"type": "message_rollback", "message_id": "...", "thread_id": "...", "rollback": {...}}` | The stored rollback record of `message_id` changed. Sent on each state change of a retry. |
| `{"type": "error", "detail": "...", "code": "..."}` | Error from the server (e.g. "busy"). `code` is optional; see [Error codes](#error-codes). |

### Progress messages

The `typing` frame carries an optional `text` field with a localized human-readable
status string. The server sends an initial `{ "type": "typing" }` (no text) as soon
as a user message is received; agents then emit keyed progress messages mid-turn that
re-send the frame with text.

```json
{ "type": "typing", "text": "📡 Fetching the latest news..." }
```

Each `typing` frame resets the client's display timer (default 3 seconds). Long-running
operations (e.g. RSS fetches, web searches) emit multiple frames to keep the indicator
alive.

Clients should render `text` when present and fall back to a generic spinner when absent.
`typingText` is exposed from `useChatSession` for this purpose.

### Message shape

```json
{
  "id": "uuid",
  "role": "assistant",
  "text": "string",
  "components": [],
  "read": false,
  "thread_id": "string or null",
  "created_at": "ISO8601",
  "replaces": "uuid or null",
  "replaced_by": "uuid or null"
}
```

`replaces` is set on a reply that a retry produced. `replaced_by` is set on a reply that a
retry replaced. `rollback` is the stored rollback record of a reply whose retry undid
actions, or `null`. See [Rollback record](#rollback-record).

`components` is a list of server-driven UI component descriptors (from `ze-components`).
The web app renders them below the message text.

Onboarding messages also include an `onboarding` metadata object beside `message`:

```json
{
  "type": "message",
  "message": { "role": "assistant", "text": "Setup", "components": [] },
  "onboarding": { "session_id": "uuid", "completed": false }
}
```

The web app stores this metadata on the message and uses it when form/confirm
components submit `component_submit` frames.

---

## Confirmation flow

When an agent action requires user approval (`confirm` capability mode), the graph
pauses at `await_confirmation`. The server sends:

```json
{
  "type": "confirm_request",
  "id": "request-uuid",
  "prompt": "Ze proposes to send an email to João about...",
  "actions": [
    {"label": "Approve", "payload": "yes"},
    {"label": "Cancel",  "payload": "no"}
  ]
}
```

The client presents this to the user. On user action, the client sends a message:

```json
{"type": "message", "text": "yes", "thread_id": "<original-thread-id>"}
```

The WS handler resumes the LangGraph checkpoint with `graph.ainvoke(None, config)` on
the same `thread_id`.

### Persistence across disconnects

The server saves the `confirm_request` payload to the `pending_confirmations` Postgres
table at the moment it sends the frame. On the next WebSocket reconnect, after
replaying unread messages, the server checks `pending_confirmations` for any
non-expired row and re-sends the `confirm_request` frame. The user can approve or
cancel even if they closed and reopened the app.

Ze clears the row when:
- The user responds (approve or cancel).
- The timeout elapses (see below).

### ntfy push on background

When the app is not connected and a confirmation is required, Ze also pushes an ntfy
notification with the prompt text (urgency `high`) so the user is alerted even with
the app closed.

### Timeout

A `CONFIRM_TIMEOUT_SECONDS` (default: 900 s / 15 min) watchdog runs in the background
from the moment the server sends the `confirm_request`. If the window elapses with no
user response, Ze sends:

```
"I waited for your approval but the window elapsed — let me know if you'd like me to try again."
```

If the turn still has unfinished conductor work, Ze appends an offer to continue that
job as a goal or as a workflow. Ze does not create either until the user accepts.

Ze deletes the `pending_confirmations` row. If the app is still connected the message
appears in-chat; otherwise it goes via ntfy (urgency `low`).

---

## Busy guard

Only one graph invocation runs at a time. If the client sends a second `message` frame
while a previous invocation is still in flight, the server responds:

```json
{"type": "error", "detail": "busy", "code": "busy"}
```

The client should queue or display this as feedback. A `retry` frame uses the same
guard, so Retry cannot start while a turn runs on the thread.

### Error codes

The `error` frame has an optional `code` field.

| `code` | Meaning |
|---|---|
| `busy` | A turn or retry already runs on this thread. |
| `retry_unavailable` | Ze refused the retry before any graph run. The frame also carries `reason_code` and `reason_text`. |
| `retry_partial` | Ze could not undo every action, so it did not regenerate. The frame carries `rolled_back: true` and the `rollback` record. The original reply stays. |
| `retry_failed` | The retry started but did not produce a reply. The frame carries `rolled_back` (`true` when Ze already undid actions) and, when `true`, the `rollback` record. The original reply stays. |

Retry error frames also carry the `message_id` of the reply the person tried to retry.
A `retry_unavailable` frame with `reason_code: "plan_changed"` also carries `plan`, the
recomputed plan, so the client can ask the person again.

---

## Reply feedback and Retry

Each stored assistant reply shows thumbs up, thumbs down, and Retry. The controls appear
on hover and on keyboard focus. On touch screens they are reachable without hover.
Command replies, progress text, and typing frames are not stored messages and get no
controls.

### Rating a reply

Ratings use REST, so they work when the socket is down.

| Route | Purpose |
|---|---|
| `PUT /api/v0/messages/{message_id}/feedback` | Body `{"rating": "up" \| "down" \| "none", "idempotency_key": "<client uuid>"}`. Returns the reply's `FeedbackView`. `none` clears the rating. Repeating a key appends nothing. Returns 404 for an unknown message or a user message. |
| `GET /api/v0/messages/feedback?ids=...` | Up to 100 ids. Returns, per assistant message: `current` rating, `history`, `retry` eligibility, `replaces`, `replaced_by`, and `trace_present`. |

Each change appends one record to the `feedback_records` table. The current rating is the
latest record. Earlier ratings stay as history, and the trace panel shows them. A rating
is evidence about the reply. It is never a fact about the user, and no turn reads it back.

### Retry

Retry regenerates the reply to the same user message. It never repeats a side effect.
The server decides whether Retry is allowed. The client cannot override the decision.

Retry is available for the latest assistant reply of a thread when every write the turn
made can be undone, and no approved confirmation or workspace run happened. A reply that
only read data has an empty plan, and one press retries it. A reply that wrote
something has a plan: the list of undos Retry will run first. Retry then regenerates
the reply and skips memory admission. One policy applies to the new run: irreversible
write tools are refused, and reversible write tools run under the normal gates. If the
model wants an irreversible write, the reply says so in words and offers to do it as a
normal request.

Each plan entry has an `entry_id`, the `tool`, an `effect_phrase`, and an `undo_note`
that says what the undo cannot restore. The `retry` field of the feedback view carries
the plan. The web app shows the plan and asks the person to confirm before it sends
`confirmed_plan`.

When Retry is unavailable, the response carries a `reason_code` and a plain-words
`reason_text` that names what the turn did, for example "This reply set a reminder."
The web app shows the text as visible description text, not only as a tooltip.

| `reason_code` | Why Retry is unavailable |
|---|---|
| `not_latest` | Only the latest reply in a thread can be retried. |
| `not_undoable` | The turn ran a write tool that Ze cannot undo cleanly this time, for example the call failed or it left no undo data. |
| `undo_failed` | An earlier Retry could not undo an action of this reply. Retry stays off so nothing is repeated. |
| `has_irreversible_action` | The turn ran an action that cannot be undone. |
| `confirmed_action` | The person approved a confirmation and the action ran. |
| `workspace_run` | The turn started a workspace run. |
| `trace_unavailable` | The reply has no trace (a command reply, a push, or an older message). |
| `unknown_tool` | The trace predates effect metadata, or a tool was not in the registry. Unknown never means safe. |
| `turn_pending` | The turn waits for a confirmation and has no final reply. |
| `busy` | Ze is already working on the thread. |
| `history_unavailable` | Ze cannot rewind the thread history, so it refuses before it undoes anything. Sent as a request-time refusal. |
| `plan_changed` | The plan the client confirmed no longer matches. The frame carries the new `plan`. Nothing changed. Sent as a request-time refusal. |
| `undo_not_confirmed` | The reply has a plan and the frame did not confirm it. Nothing changed. Sent as a request-time refusal. |
| `disconnected` | Set by the web app when the socket is down. The server never returns it. |

A denied or expired confirmation counts as no action. A failed write call still counts,
because it may have run in part.

### Retry flow

1. The client sends the `retry` frame. When the plan is not empty, the client first asks
   the person to confirm it and puts the entry ids in `confirmed_plan`.
2. The server loads the message and trace and evaluates eligibility again, under the
   thread lock. It recomputes the plan and compares it with `confirmed_plan`. An
   ineligible or mismatched request gets an `error` frame with
   `code: "retry_unavailable"`, and nothing changes.
3. The server appends a `retry_requested` feedback record to the old reply. The record
   stays even if the retry fails.
4. The server undoes the plan entries and sends a `message_rollback` frame each time the
   record changes. If an undo fails, the server stops, sends `error` with
   `code: "retry_partial"`, and the original reply stays.
5. The server sends `typing` frames and rewinds the thread's checkpointed history to
   before the old reply. It runs the graph with the original user text and `retry_mode`.
6. On success the server stores the new reply with `replaces` set, marks the old reply
   superseded, and sends a `message` frame, then a `message_superseded` frame.
7. If a reversible write needs a confirmation, the server sends a `confirmation` frame
   after the `retry` frame, and the retry waits. The `confirm` reply resolves it. An
   approved or denied confirmation that produces a reply supersedes the old reply as in
   step 6. If no reply results, the record state becomes `rolled_back_retry_failed`.
8. On failure the server restores the history and sends `error` with
   `code: "retry_failed"` and `rolled_back`. The original reply stays visible. The
   notice names what Ze undid when `rolled_back` is `true`.

### Rollback record

A retry that undid actions writes a record to the `rollback` field of the old reply. The
record has `state`, `entries`, and `replaced_by`. Each entry has `entry_id`, `tool`,
`effect_phrase`, `outcome` (`undone`, `failed`, or `not_attempted`), `at`, and
`failure_code`. The REST responses and WebSocket frames never expose the undo arguments.

| `state` | Meaning |
|---|---|
| `partial` | An undo failed. Ze did not regenerate. The original reply stays. |
| `rolled_back_awaiting_confirmation` | Ze undid the actions and waits for the person to confirm a new action. |
| `rolled_back_retry_failed` | Ze undid the actions but could not write a new reply. |
| `superseded` | A new reply replaced the old one. |

The server stores the record state `rolled_back_retry_failed` as soon as the undos finish,
before regeneration completes. A client should hide that notice while the feedback view
reports `reason_code: "busy"`. The web app does this.

A superseded reply stays in the database with its trace and feedback. `GET /api/v0/messages`
hides it unless you pass `include_superseded=true`, and later turns never see it.
A retried reply is itself rateable and retryable.

---

## Unread message replay

`MessageStore` (`ze_core/conversation/messages/store.py`) persists all outbound messages (assistant
and Ze's proactive pushes) to Postgres. On WebSocket connect, the server replays all
messages with `read = false` in order before new messages flow. The client marks them
read via `ack` frames.

**REST fallback** — `GET /api/v0/messages` returns the same unread list for scenarios where the
client needs to poll rather than hold a persistent connection.

---

## ntfy push notifications

When no WebSocket connection is active, `NativeAppInterface` also delivers to ntfy
via `NtfyNotifier` (`ze-notifications`). Configure in `.env`:

```
NTFY_BASE_URL=https://ntfy.sh        # or your self-hosted instance
NTFY_TOPIC=ze-your-unique-topic
NTFY_TOKEN=                          # optional auth token for private topics
```

ntfy priority:
- Normal messages → priority 3 (default)
- High-urgency proactive notifications (e.g. workflow failures) → priority 5

If `NTFY_TOPIC` is empty, ntfy delivery is disabled and Ze is WebSocket-only.

---

## Screen context

The `message` frame accepts an optional `context` object for screen-aware responses:

```json
{
  "type": "message",
  "text": "What is this?",
  "context": {
    "screen": "GoalDetail",
    "goal_id": "uuid"
  }
}
```

The context is passed as `screen_context` in the graph config's `configurable` dict,
making it available to agents via `ctx.config`.

---

## Connection manager

The app instantiates `ConnectionManager` (`ze_api/api/ws.py`) once at startup and
stores it on `app.state.connection_manager`. It exposes:

| Method | Description |
|---|---|
| `connect(ws, message_store, confirmation_store=None)` | Accept a new connection; closes the previous one; replays unread messages; replays any pending confirmation |
| `disconnect()` | Clear the active connection |
| `push(message)` | Send a message frame; silently no-ops if disconnected |
| `send_frame(frame)` | Send an arbitrary JSON frame |
| `try_set_busy() → bool` | Claim the invocation slot; returns False if already busy |
| `clear_busy()` | Release the invocation slot |

Never instantiate `ConnectionManager` outside the FastAPI lifespan — there must only
be one instance.
