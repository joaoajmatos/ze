# Contract: confirmation frames (WebSocket `/ws`)

Hard cut (pre-v1): the top-level `prompt`, `editable`, `proposed` fields of `confirm_request` are removed. The JSON schemas in `ze_api/api/schemas.py` and the generated `@myguyze/ze-client` `ws.ts` are regenerated in the same change.

## Server → client: `confirm_request`

```json
{
  "type": "confirm_request",
  "id": "8d0f…",                 // request_id (pending_confirmations key, 113)
  "thread_id": "…",
  "kind": "write",               // "write" | "budget" | "held" | "prompt"
  "round": 1,                    // 1..3 within the turn ("write" only)
  "title": "Ze needs your OK",   // short heading, code-built
  "items": [
    {
      "item_id": "c1",
      "agent": "calendar",
      "tool": "delete_event",
      "effect_phrase": "delete a calendar event",
      "summary": "Dentist — today 15:00",
      "conflict": null,          // 144 text when a reviewed constraint needs the OK
      "editable_field": null,    // e.g. "body" for send_email
      "proposed_text": null      // current value of the editable field
    }
  ],
  "source": null,                // "held" only: {"kind": "workflow"|"goal", "name": "Weekly summary"}
  "expires_at": "2026-10-15T20:15:00Z",
  "actions": [
    {"label": "Approve all", "value": "approve", "style": "primary"},
    {"label": "Deny all", "value": "deny", "style": "secondary"}
  ]
}
```

`kind: "budget"` has one item with `tool: null`, `effect_phrase` "continue past today's spend limit" and `summary` "$4.10 of $4.00".

`kind: "prompt"` is a confirmation with no parked writes: goal gates (Proceed/Stop/Redirect), goal suggestions, the workspace reset, and `AppInterface.send_confirmation`. `round` is 1, `items` is `[]`, `title` is the producer's prompt, and `actions` are the producer's own buttons. An `approve`/`deny` value comes back as a `confirm` frame; any other value (e.g. `goal_plan:yes:<id>`) comes back as `{"type": "action", "payload": "<value>", "thread_id": …}`. The stored row keeps `{kind, round, items, title, actions}`, so a reconnect replays the same frame. All producers build it with `build_prompt_frame` (`ze_api/api/websocket/frames.py`).

Items show the effect in the imperative ("delete a calendar event"). One helper, `effect_imperative(effect_phrase)`, converts the declared past-tense phrase using a regular "-ed" rule plus an explicit irregular map (sent → send, ran → run, …). A test runs it over every registered `effect_phrase`; a phrase it cannot convert fails the test, and the author adds it to the map.

## Client → server: `confirm`

```json
{"type": "confirm", "id": "8d0f…", "choice": "approve", "edits": {"c2": "new body text"}}
{"type": "confirm", "id": "8d0f…", "choice": "deny"}
```

- `choice`: `approve` | `deny` (the old `edit` choice is gone; edits ride on `approve`).
- `edits` keys must be `item_id`s with a non-null `editable_field`; others are rejected with `{"type": "error", "detail": "invalid edit"}` and nothing runs.
- A `confirm` for an unknown, expired or superseded `id` → `{"type": "error", "detail": "No pending confirmation."}`; nothing runs.

## Server → client: `confirm_cancel`

Unchanged: `{"type": "confirm_cancel", "id": "…"}` when a confirmation is superseded, expired or answered elsewhere (e.g. a held write answered from the notification).

## Replay

On connect, open `pending_confirmations` rows for the thread and open `held_writes` rows are replayed as `confirm_request` frames (today's replay, extended to holds).
