# Data Model: OpenRouter Server Tools (196)

No migration. All changes are in-process types or fields of `messages.trace` JSON.

**WebFetchConfig** (ze-agents, frozen dataclass): `engine: str = "openrouter"`, `max_uses: int = 5`, `max_content_tokens: int = 8000`. Invalid values (wrong type, `max_uses < 1`, `max_content_tokens < 500`) fall back to the default with a warning.

**ServerToolConfig** (ze-agents, frozen dataclass): `web_fetch: WebFetchConfig`, `fetch_hosts: tuple[str, ...] = ()`. `from_config(config: dict)` reads `openrouter.server_tools.web_fetch`; `with_fetch_urls(text: str) -> ServerToolConfig` returns a copy whose `fetch_hosts` are the hosts of the `http(s)` URLs in `text` (deduplicated, order kept, at most 10). `WebFetchConfig.engine` must be one of `auto`, `native`, `exa`, `openrouter`, `firecrawl`, `parallel`; anything else falls back to `openrouter` with a warning.

**SERVER_TOOLS** (ze-agents): a `MappingProxyType` over `{"openrouter:web_search": builder, "openrouter:web_fetch": builder}`. The only allowlist; read-only at runtime. `web_fetch` is available on a request only when `fetch_hosts` is non-empty.

**RawCapture** (ze-core, per model call): `sources: list[Source]`, `server_tools: Counter[str]` (kind = reported key minus `_requests`); each response body contributes its last `server_tool_use` once.

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
