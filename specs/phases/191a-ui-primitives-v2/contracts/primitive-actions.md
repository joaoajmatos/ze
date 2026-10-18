# Contract: typed primitive actions

## Descriptor
```json
{ "type": "button", "label": "Mark read", "style": "secondary",
  "action": { "kind": "tool", "owner": "news", "tool": "mark_source_read", "args": { "source_id": "s-12" } } }
```
Other kinds:
```json
{ "kind": "ask", "text": "What's new in my sources?" }
{ "kind": "navigate", "route": "/mind/ent-42" }
{ "kind": "compose", "compose": "slipping" }
```
A string `action` fails validation.

## WS: client → server
```json
{ "type": "ui_action", "id": "6c1…", "thread_id": "t-1",
  "action": { "kind": "tool", "owner": "news", "tool": "mark_source_read", "args": { "source_id": "s-12" } } }
```
## WS: server → client
- Asks-first write: a normal `confirm_request` (`kind: "write"`, one item); the client answers with the normal `confirm` frame.
- Outcome:
```json
{ "type": "ui_action_result", "id": "6c1…", "thread_id": "t-1", "ok": true, "line": "Marked as read." }
```
Refusals: `ok: false`, `line: "That action is not available."`; a busy thread: `ok: false`, `code: "busy"`; deny or timeout: `ok: false`, `line: "Okay, I didn't mark the source as read."`.

## Version
Every transport with `components` carries `"ui_version": "2.0"`. A client refuses a major version older than its own and renders unknown types through the fallback.
