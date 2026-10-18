# Contract: Programmatic Tool Use (197)

## Model-facing tool

```json
{"type": "function", "function": {
  "name": "run_tool_script",
  "description": "Run a short Python script that calls your read tools through the ze_tools module and returns only what the answer needs. Use it for three or more reads, loops, joins or counting. Call finish(result, writes=[propose(tool, **args), ...]) at the end; writes run after the script under the usual confirmation rules. Give either source or procedure_id.",
  "parameters": {"type": "object", "properties": {
    "source": {"type": "string", "description": "Python 3.12 source"},
    "procedure_id": {"type": "string", "description": "id of an approved script procedure to rerun"}
  }}
}}
```

Offered only when the agent sets `script_tools = True`, a runner is wired (conversation turns), and the agent's visible read tools number at least two.

## Inside the sandbox (`ze_tools`)

```python
import ze_tools as z

goals = z.list_goals(status="active")          # one function per visible read tool; keyword args from its schema
people = z.list_contacts()
stale = [p for p in people if p["last_contact_days"] > 30]
z.finish({"goals": len(goals), "stale": [p["name"] for p in stale][:5]},
         writes=[z.propose("archive_email", message_id="m1")])
```

- A function returns the tool's result as JSON data, or a string when the tool returns text.
- A failed or refused call raises `ze_tools.ToolError(message)`.
- Calling a write tool directly is impossible (it is not in the stub); a forged request for one is refused `writes_must_be_proposed`.
- Without `finish`, the value is `None`.

## Model-facing result

Success: the JSON of the value, capped at 4,000 characters (`… [truncated]` when cut). Proposed writes then appear as ordinary tool calls.

Failure:

```json
{"error": {"kind": "limit", "message": "limit: inner_calls (20)",
  "completed": [{"name": "list_goals", "success": true}],
  "stderr_tail": "…last 20 lines…"}}
```

`kind`: `exception`, `limit`, `sandbox_unavailable`, `sandbox_busy`, `bad_request`, `source_too_long`, `procedure_not_script`.

## Ze ↔ sidecar (`WS /scripts`, `Authorization: Bearer <WORKSPACE_API_TOKEN>`)

| Direction | Frame |
|---|---|
| Ze → sidecar | `{"type": "start", "id": "<uuid>", "source": "...", "stub": "...", "timeout_seconds": 30}` |
| sidecar → Ze | `{"type": "call", "seq": 1, "tool": "list_goals", "args": {...}}` |
| Ze → sidecar | `{"type": "reply", "seq": 1, "ok": true, "value": [...]}` or `{"type": "reply", "seq": 1, "ok": false, "error": "..."}` |
| Ze → sidecar | `{"type": "cancel"}` |
| sidecar → Ze | `{"type": "end", "status": "ok" \| "exception" \| "timeout" \| "killed" \| "bad_request" \| "busy", "value": ..., "writes": [...], "stderr_tail": "...", "exception": "..."}` |

The sidecar closes the socket after `end`. A second connection while a script runs receives `end` with `busy`. `GET /stat` gains `scripts_busy: bool` and `scripts_isolated: bool`.

## Pipe protocol (sandbox ↔ sidecar)

One JSON object per line. Requests: `{"seq": n, "tool": "...", "args": {...}}`. Replies: `{"seq": n, "ok": bool, "value"|"error": ...}`. Finish: `{"finish": value, "writes": [...]}` (last line wins). Anything that is not valid JSON with these keys ends the script with `bad_request`.

## Trace

Script step row: `name: "run_tool_script"`, `call_id`, `script: {source, source_cut, outcome, limit, source_hash, procedure_id}`. Inner rows and proposed-write rows: `parent_call_id` = the step's `call_id`.
