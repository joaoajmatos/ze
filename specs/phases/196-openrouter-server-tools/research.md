# Research: OpenRouter Server Tools (196)

## R1 — `web_fetch` request shape

- **Decision**: `{"type": "openrouter:web_fetch", "parameters": {"engine": "openrouter", "max_uses": 5, "max_content_tokens": 8000}}`.
- **Rationale**: OpenRouter docs (2026-10-18, beta): optional `engine` (`auto`, `native`, `exa`, `openrouter`, `firecrawl`, `parallel`), `max_uses`, `max_content_tokens`, `allowed_domains`, `blocked_domains`. The `openrouter` engine is a direct fetch with extraction, free, capped at 50 fetches per request. A successful fetch returns `url`, `title`, `content`, `status`, `retrieved_at`; a failed one `url`, `status: failed`, `error`. Regional endpoints (`eu.`/`us.openrouter.ai`) answer 403. Workspace settings in locked mode reject a request whose engine is outside the workspace list (403).
- **Alternatives**: `auto`/`exa` (paid, URL goes to Exa), rejected by clarification. Domain lists: no Ze use; the fetch runs on OpenRouter, so it cannot reach the user's network.
- **Build-time check**: the lead re-reads the OpenRouter web-fetch page before T001 and adjusts names if the beta changed.

## R2 — Where server tool counts come from

- **Decision**: read `usage.server_tool_use` from the raw response body in the existing tee transport.
- **Rationale**: the installed SDK's `ChatUsage` model has no `server_tool_use` field (verified in `.venv/.../openrouter/components/chatusage.py`), the same reason citations are teed (`citations.py` docstring). OpenRouter's docs show `"usage": {..., "server_tool_use": {"web_search_requests": 2}}`; other keys are not documented, so Ze keeps any `<kind>_requests` key generically.
- **Alternatives**: upgrade the SDK (no version with the field known); fetch generation details per call (extra request per model call).

## R3 — Where counts accumulate for one turn

- **Decision**: the 187b `TurnTelemetry` recorder, through `CostTracker.record_server_tools`.
- **Rationale**: the recorder already accumulates per-model usage across delegates and survives confirmation pauses (registry per thread on the container). A separate ContextVar would lose counts across a resume, which runs in a new request task.
- **Consequence**: 196 builds after 187b.

## R4 — Are server tool calls returned to Ze?

- **Decision**: keep handling them if they arrive, but treat the usage counts as the record.
- **Rationale**: OpenRouter's docs say server tools run transparently; they do not say the calls are returned. The current loop already handles returned server tool calls defensively (`base_agent.py:896`).

## R5 — Dead streaming path

- **Decision**: delete it (clarified).
- **Rationale**: `token_queue` is read from `config["configurable"]` in `execute_tool` but no code sets it (grep 2026-10-18); tokens reach the client through `token_sink` and `stream_complete_with_tools`. The only behavior the dead path carried was the research agent's `:online` suffix, a web search outside the declared tool list.
