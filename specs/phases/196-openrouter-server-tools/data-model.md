# Data Model: OpenRouter Server Tools (196)

No migration. All changes are in-process types or fields of `messages.trace` JSON.

**WebFetchConfig** (ze-agents, frozen dataclass): `engine: str = "openrouter"`, `max_uses: int = 5`, `max_content_tokens: int = 8000`. Invalid values (wrong type, `max_uses < 1`, `max_content_tokens < 500`) fall back to the default with a warning.

**ServerToolConfig** (ze-agents, frozen dataclass): `web_fetch: WebFetchConfig`. `from_config(config: dict)` reads `openrouter.server_tools.web_fetch`. `WebFetchConfig.engine` must be one of `auto`, `native`, `exa`, `openrouter`, `firecrawl`, `parallel`; anything else falls back to `openrouter` with a warning. The fetch schema carries no domain list (user decision 2026-10-18).

**SERVER_TOOLS** (ze-agents): a `MappingProxyType` over `{"openrouter:web_search": builder, "openrouter:web_fetch": builder}`. The only allowlist; read-only at runtime.

**RawCapture** (ze-core, per model call): `sources: list[Source]`, `server_tools: Counter[str]` (kind = reported key minus `_requests`); each response body contributes its last `server_tool_use` once; `server_tool_records: list[tuple[str, str, str]]` (kind, url, status) from fetch result records in the body; a record whose status is not `failed` is also a `Source`. Returned server tool calls are not parsed here: the agent loop owns them (`ToolCallTrace.target`).

**TurnTelemetry** (187b recorder) addition: `server_tools: Counter[str]`, `server_tool_records: list[tuple[str, str, str]]` (pre-dedup), `add_server_tools(counts, records)`. `stamp` merges records with the call targets of the trace's server tool rows through `merge_targets` (`ze_core/telemetry/server_tool_targets.py`).

**ServerToolTarget**: `kind: str`, `target: str` (≤ 500 chars), `status: "requested" | "completed" | "failed"`, `length: int` (full length), `cut: bool`.

**MessageTrace** additions: `server_tools: dict[str, int]` (default `{}`), `server_tool_targets: list[ServerToolTarget]` (≤ 50, default `[]`), `server_tool_targets_dropped: int` (default 0), `server_tool_unreported: dict[str, int]` (kind → counted requests without a target; default `{}`). **ToolCallTrace** addition: `target: str | None` (url or query of a server tool row). Same fields on the REST responses and the final `trace_update` frame. Targets may hold signed URLs or tokens the user pasted; they are the user's own data behind the API key and are never written to logs.

**config.yaml** addition:

```yaml
openrouter:
  server_tools:
    web_fetch:
      engine: openrouter        # openrouter | auto | native | exa | firecrawl | parallel
      max_uses: 5               # fetches per model request
      max_content_tokens: 8000  # longer pages are truncated by OpenRouter
```
