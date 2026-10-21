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

Offered to any agent (no opt-in) when a runner is wired (conversation turns) and the agent has at least one data read tool (visible tools minus writes, `produces_ui` tools, server tools, delegate, `invoke_procedure`, workspace tools and the script tool itself). Trace rows for the step carry `access: "script"`.

## Inside the sandbox (`ze_tools`)

```python
import ze_tools as z

txs = z.get_transactions(period="this_month")   # one function per data read tool; keyword args from its schema
totals = {}
for t in txs:                                    # results are JSON data (dicts, lists); dates arrive as ISO strings
    m = t.get("merchant_name", "?")
    totals[m] = totals.get(m, 0) + abs(t.get("amount", 0))
top = sorted(totals.items(), key=lambda kv: kv[1], reverse=True)[:5]
z.finish({"top_merchants": top})
```

- A function returns the tool's result as JSON data: a tool that returns a JSON string is parsed to its dict or list; dates and times arrive as ISO strings, UUIDs and decimals as strings; other text stays a string.
- `print` output is discarded (stdout goes nowhere); return what the answer needs with `finish`.
- `propose(tool, **args)` returns `{"tool": ..., "args": {...}}`; up to 10 proposals per script, each must be a write tool the agent has.
- A failed or refused call raises `ze_tools.ToolError(message)`.
- Calling a write tool directly is impossible (it is not in the stub); a forged request for one is refused `writes_must_be_proposed`.
- Without `finish`, the value is `None`.

## Model-facing result

Success: the JSON of the value, capped at 4,000 characters (`… [truncated]` when cut). Proposed writes then appear as ordinary tool calls.

Failure:

```json
{"error": {"kind": "limit", "message": "limit: inner_calls (20)",
  "completed": [{"name": "get_transactions", "success": true}],
  "last_result_shape": "list[dict] keys: id, date, amount, merchant_name, category",
  "stderr_tail": "…last 20 lines…"}}
```

`kind`: `exception`, `limit`, `resource_limit`, `sandbox_unavailable`, `sandbox_busy`, `bad_request`, `source_too_long`, `procedure_not_script`. `last_result_shape` appears on `exception`.

## Ze ↔ sidecar (`WS /scripts`, `Authorization: Bearer <WORKSPACE_API_TOKEN>`)

| Direction | Frame |
|---|---|
| Ze → sidecar | `{"type": "start", "id": "<uuid>", "source": "...", "stub": "...", "timeout_seconds": 30}` |
| sidecar → Ze | `{"type": "call", "seq": 1, "tool": "get_transactions", "args": {...}}` |
| Ze → sidecar | `{"type": "reply", "seq": 1, "ok": true, "value": [...]}` or `{"type": "reply", "seq": 1, "ok": false, "error": "..."}` |
| Ze → sidecar | `{"type": "cancel"}` |
| sidecar → Ze | `{"type": "end", "status": "ok" \| "exception" \| "timeout" \| "killed" \| "bad_request" \| "busy" \| "unavailable" \| "resource_limit", "value": ..., "writes": [...], "stderr_tail": "...", "exception": "..."}` |

The sidecar refuses the handshake with close code 1008 when the token is missing or wrong, or when no token is configured. It closes the socket after `end`. A second connection while a script runs receives `end` with `busy`. WS `max_size` is 2 MiB on both sides. `GET /stat` gains `scripts_busy: bool` and `scripts_isolated: bool` (rule verified and `/workspace` closed; a failed per-script probe sets it false and ends that script `unavailable`).

## Pipe protocol (sandbox ↔ sidecar)

One JSON object per line. Requests: `{"seq": n, "tool": "...", "args": {...}}` (at most 256 KB per line). Replies: `{"seq": n, "ok": bool, "value"|"error": ...}` (at most 1 MiB; a larger result is replied as `ok: false, error: "result_too_large"`). Finish: `{"finish": value, "writes": [...]}` (at most 1 MiB; last line wins; `writes` entries must be `{tool: str, args: dict}`). A line over its cap, invalid JSON, or wrong keys end the script with `bad_request`. Probe breach: `{"isolation_breach": "<what>"}` ends it `unavailable`.

## Trace

Script step row: `name: "run_tool_script"`, `access: "script"`, `call_id`, `script: {source, source_cut, outcome, limit, source_hash, procedure_id}`. Inner rows and proposed-write rows: `parent_call_id` = the step's `call_id`, listed right after the step (depth-first). Synthetic proposed-write call ids are `<model call id>_w<i>`, limited to `[A-Za-z0-9_-]` and 64 characters.
