# Contract: OpenRouter Server Tools (196)

## Request (agent → OpenRouter)

Only these entries may appear in a request's `tools` array as server tools, and only when the agent declared them:

```json
{"type": "openrouter:web_search"}
{"type": "openrouter:web_fetch", "parameters": {"engine": "openrouter", "max_uses": 5, "max_content_tokens": 8000, "allowed_domains": ["example.com"]}}
```

`web_fetch` is sent only on a turn whose user message (`AgentContext.user_turn_text`, never a delegate prompt) contains URLs; `allowed_domains` holds their hosts and `max_uses` is `min(configured cap, distinct pasted URLs)`. The OpenRouter client raises `OpenRouterError("server tool not allowed: <type>")` before sending if any `openrouter:*` type is outside the allowlist.

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
| `usage.server_tool_use: {"web_search_requests": 2, "web_fetch_requests": 1}` (last value per response, once) | `TurnTelemetry.server_tools += {"web_search": 2, "web_fetch": 1}` (`web_fetch_requests` expected; confirmed by T025) |

## Trace

`MessageTrace.server_tools` / `MessageTraceResponse.server_tools` / final `trace_update.server_tools`:

```json
"server_tools": {"web_search": 2, "web_fetch": 1}
```

Empty object when nothing was reported. The web Tools instrument draws `Web search ×2` and `Page fetch ×1` (unknown kinds by key), adds the partial mark when `telemetry_partial` is true, and draws no row for `openrouter:*` tool calls.
