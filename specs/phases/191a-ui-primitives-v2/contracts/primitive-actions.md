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
Lines: success → the tool's `done_phrase` or "Done."; failure → "Couldn't <effect>." (never raw error text); refusal → "That action is not available."; busy → `code: "busy"`; deny, timeout or supersede → "Okay, I didn't <effect>."; a `confirm` for an unknown id → "That request expired."

Only WRITE tools that declare `ui_action=True` can be named. This frame is separate from the existing `action` frame, which answers prompt-frame choices (goal gates, suggestions).

## Version
Every transport with newly built `components` carries `"ui_version": "2.0"`. Unknown types render through the fallback. A tree with no version (stored before 191a) or `1.x` renders as legacy: string-action buttons disabled ("This older button no longer works."); if it cannot render, only that tree shows "This older view can't be shown."
