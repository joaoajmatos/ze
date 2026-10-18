# Data Model: OpenRouter Server Tools (196)

No migration. All changes are in-process types or fields of `messages.trace` JSON.

**WebFetchConfig** (ze-agents, frozen dataclass): `engine: str = "openrouter"`, `max_uses: int = 5`, `max_content_tokens: int = 8000`. Invalid values (wrong type, `max_uses < 1`, `max_content_tokens < 500`) fall back to the default with a warning.

**ServerToolConfig** (ze-agents, frozen dataclass): `web_fetch: WebFetchConfig`. `from_config(config: dict)` reads `openrouter.server_tools.web_fetch`. `WebFetchConfig.engine` must be one of `auto`, `native`, `exa`, `openrouter`, `firecrawl`, `parallel`; anything else falls back to `openrouter` with a warning. The fetch schema carries no domain list (user decision 2026-10-18).

**SERVER_TOOLS** (ze-agents): a `MappingProxyType` over `{"openrouter:web_search": builder, "openrouter:web_fetch": builder}`. The only allowlist; read-only at runtime.

**RawCapture** (ze-core, per model call): `sources: list[Source]`, `server_tools: Counter[str]` (kind = reported key minus `_requests`); each response body contributes its last `server_tool_use` once; `server_tool_targets: list[tuple[str, str]]` (kind, target) from returned server tool calls and fetch result records, deduplicated, target ≤ 500 chars; each `web_fetch` target is also a `Source`.

**TurnTelemetry** (187b recorder) addition: `server_tools: Counter[str]`, `server_tool_targets: list[tuple[str, str]]` (≤ 50), `add_server_tools(counts, targets)`.

**MessageTrace** additions: `server_tools: dict[str, int]` (default `{}`), `server_tool_targets: list[{kind, target}]` (default `[]`), `server_tool_targets_missing: bool` (true when fetches were counted but no fetch target was captured). Same fields on `MessageTraceResponse` and the final `trace_update` frame.

**config.yaml** addition:

```yaml
openrouter:
  server_tools:
    web_fetch:
      engine: openrouter        # openrouter | auto | native | exa | firecrawl | parallel
      max_uses: 5               # fetches per model request
      max_content_tokens: 8000  # longer pages are truncated by OpenRouter
```
