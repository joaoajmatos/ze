# Data Model: OpenRouter Server Tools (196)

No migration. All changes are in-process types or fields of `messages.trace` JSON.

**WebFetchConfig** (ze-agents, frozen dataclass): `engine: str = "openrouter"`, `max_uses: int = 5`, `max_content_tokens: int = 8000`. Invalid values (wrong type, `max_uses < 1`, `max_content_tokens < 500`) fall back to the default with a warning.

**ServerToolConfig** (ze-agents, frozen dataclass): `web_fetch: WebFetchConfig`. `from_config(config: dict)` reads `openrouter.server_tools.web_fetch`.

**SERVER_TOOLS** (ze-agents): `{"openrouter:web_search": builder, "openrouter:web_fetch": builder}`. The only allowlist.

**RawCapture** (ze-core, per model call): `sources: list[Source]`, `server_tools: Counter[str]` (kind = reported key minus `_requests`).

**TurnTelemetry** (187b recorder) addition: `server_tools: Counter[str]`, `add_server_tools(counts: dict[str, int])`.

**MessageTrace** addition: `server_tools: dict[str, int]`, default `{}`. Same field on `MessageTraceResponse` and the final `trace_update` frame.

**config.yaml** addition:

```yaml
openrouter:
  server_tools:
    web_fetch:
      engine: openrouter        # openrouter | auto | native | exa | firecrawl | parallel
      max_uses: 5               # fetches per model request
      max_content_tokens: 8000  # longer pages are truncated by OpenRouter
```
