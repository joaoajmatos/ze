# Contract: OpenRouter Server Tools (196)

## Request (agent → OpenRouter)

Only these entries may appear in a request's `tools` array as server tools, and only when the agent declared them:

```json
{"type": "openrouter:web_search"}
{"type": "openrouter:web_fetch", "parameters": {"engine": "openrouter", "max_uses": 5, "max_content_tokens": 8000}}
```

`web_fetch` has no domain list (user decision 2026-10-18, risk accepted); `max_uses` is the configured cap. The OpenRouter client raises `OpenRouterError("server tool not allowed: <type>")` before sending if any `openrouter:*` type is outside the allowlist.

## Startup

An agent declaring `openrouter:<anything else>` fails `validate_registry`:

```
AgentConfigError: Agent 'x' declares server tool 'openrouter:shell', which Ze does not allow. Allowed: openrouter:web_fetch, openrouter:web_search.
```

## Reply handling

| OpenRouter returns | Ze records |
|---|---|
| tool call named an allowed server tool (any `openrouter:`/`openrouter_` spelling) | read `ToolCall` under the canonical name, success, tool message `[search complete]` or `[page fetch complete]` |
| tool call with a server-tool-shaped name not allowed (bare `openrouter` included) | `ToolCall(success=False, error="unexpected_server_tool", result="[error: unexpected_server_tool]")`, trace access `unknown`, warning log, tool message `[error: unexpected_server_tool]` |
| returned server tool call with arguments (agent loop) | `ToolCallTrace.target` = `args.url` / `args.query`; merged as status `requested`; never a `Source` |
| fetch result record (`url`, `status`, `retrieved_at`) in the body (tee) | record `(web_fetch, url, status)`; merged as `completed` or `failed`; a non-failed record is a `Source` |
| `usage.server_tool_use: {"web_search_requests": 2, "web_fetch_requests": 1}` (last value per response, once) | `TurnTelemetry.server_tools += {"web_search": 2, "web_fetch": 1}` (`web_fetch_requests` expected; confirmed by T025) |

## Trace

`MessageTrace.server_tools` / `MessageTraceResponse.server_tools` / final `trace_update.server_tools`:

```json
"server_tools": {"web_search": 2, "web_fetch": 1},
"server_tool_targets": [
  {"kind": "web_search", "target": "postgres 18 release notes", "status": "requested", "length": 25, "cut": false},
  {"kind": "web_fetch", "target": "https://example.com/a", "status": "completed", "length": 21, "cut": false}
],
"server_tool_targets_dropped": 0,
"server_tool_unreported": {"web_search": 1}
```

Empty object when nothing was reported. The web Tools instrument draws `Web search ×2` and `Page fetch ×1` (unknown kinds by key), adds the partial mark when `telemetry_partial` is true, lists each target under the counts ("Page fetch · https://…", "… · failed", "Web search · …", cut targets with their length), "+n more" for dropped entries, "Ze cannot see which searches were run (1 of 2 shown)" for each unreported kind, and draws no separate row for `openrouter:*` tool calls.
