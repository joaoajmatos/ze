# Contract: OpenRouter Server Tools (196)

## Request (agent → OpenRouter)

Only these entries may appear in a request's `tools` array as server tools, and only when the agent declared them:

```json
{"type": "openrouter:web_search"}
{"type": "openrouter:web_fetch", "parameters": {"engine": "openrouter", "max_uses": 5, "max_content_tokens": 8000}}
```

## Startup

An agent declaring `openrouter:<anything else>` fails `validate_registry`:

```
AgentConfigError: Agent 'x' declares server tool 'openrouter:shell', which Ze does not allow. Allowed: openrouter:web_fetch, openrouter:web_search.
```

## Reply handling

| OpenRouter returns | Ze records |
|---|---|
| tool call named an allowed server tool (any `openrouter:`/`openrouter_` spelling) | read `ToolCall` under the canonical name, success, tool message `[search complete]` or `[page fetch complete]` |
| tool call with a server-tool-shaped name not allowed | `ToolCall(success=False, error="unexpected_server_tool")`, warning log, tool message `[error: unexpected_server_tool]` |
| `usage.server_tool_use: {"web_search_requests": 2, "web_fetch_requests": 1}` | `TurnTelemetry.server_tools += {"web_search": 2, "web_fetch": 1}` |

## Trace

`MessageTrace.server_tools` / `MessageTraceResponse.server_tools` / final `trace_update.server_tools`:

```json
"server_tools": {"web_search": 2, "web_fetch": 1}
```

Empty object when nothing was reported. The web Tools instrument draws `Web search ×2` and `Read page ×1`; unknown kinds by key.
