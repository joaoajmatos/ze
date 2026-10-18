# Research: OpenRouter Server Tools (196)

## R1 — `web_fetch` request shape

- **Decision**: `{"type": "openrouter:web_fetch", "parameters": {"engine": "openrouter", "max_uses": 5, "max_content_tokens": 8000, "allowed_domains": [<hosts of the URLs in the user's message>]}}`, sent only when that list is non-empty.
- **Rationale**: OpenRouter docs (2026-10-18, beta): optional `engine` (`auto`, `native`, `exa`, `openrouter`, `firecrawl`, `parallel`), `max_uses`, `max_content_tokens`, `allowed_domains`, `blocked_domains`. The `openrouter` engine is a direct fetch with extraction, free, capped at 50 fetches per request. A successful fetch returns `url`, `title`, `content`, `status`, `retrieved_at`; a failed one `url`, `status: failed`, `error`. Regional endpoints (`eu.`/`us.openrouter.ai`) answer 403. Workspace settings in locked mode reject a request whose engine is outside the workspace list (403).
- **Alternatives**: `auto`/`exa` (paid, URL goes to Exa), rejected by clarification. Open fetch (no `allowed_domains`): rejected pending the user decision (R6). `engine` is validated against the six documented values.
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

## R6 — Exfiltration through fetch URLs (Gauge S-1)

- **Decision (drafted, user decision pending)**: strict fetch. `web_fetch` is sent only when the user's message holds `http(s)` URLs, with `allowed_domains` = their hosts (lowercased, `www.` kept as written, at most 10).
- **Rationale**: the research prompt carries the user's memory; page text is untrusted; a fetch is a read with no write gate. Without a domain rule a page can make the model put private text in a fetch URL's path or query. `allowed_domains` is enforced by OpenRouter, so it does not depend on the model obeying instructions. A test with a fake model is not a guard; the domain rule is.
- **Cost**: "read the full text of a search result" needs the user to paste that link. Stated as a limit in the spec.
- **Search queries** carry the same risk today (a query is text the model writes); recorded in the ADR amendment, not fixed in this phase.
- **Source of the URLs (Gauge S-12)**: only the user's own turn text. `AgentContext.user_turn_text` is set once by `execute_tool` from the turn's raw user message (`state["prompt"]`) and copied unchanged into every delegate and subtask context; `run_delegate`'s `prompt`/`messages` are model-written and never feed `with_fetch_urls`. A retried turn replays the stored user message, so it gets the same hosts.
- **Fetch budget (Gauge S-13)**: `max_uses = min(config.max_uses, distinct pasted URLs)`. Once the pasted pages are read, OpenRouter refuses further fetches, so a hostile pasted page cannot trigger a second, data-carrying fetch on its own host. Residual: the model could fetch a different path on a pasted host instead of the pasted URL; stated in the ADR.
- **Parsing**: `with_fetch_urls` keeps only `http`/`https`, takes `hostname` (userinfo and port dropped, lowercased). T025 confirms how OpenRouter matches `allowed_domains` (exact host or subdomains, `www.`) and the redirect edge is adjusted to it.

## R7 — Sources for fetched pages (Gauge S-5)

- **Decision**: the research agent adds each pasted URL whose host appears in its answer text to `AgentResult.sources`; the instructions require the URL in the answer.
- **Rationale**: OpenRouter documents fetch results as `url/title/content/status/retrieved_at`; it does not document `url_citation` annotations for them, and the agent cannot see the usage counts (they go to the turn recorder).

## R8 — Counting once per response (Gauge S-4)

- **Decision**: the tee keeps the last `server_tool_use` value seen in one response body and adds it to the counter once, when the body finishes.
- **Rationale**: some providers repeat cumulative usage on several stream chunks; summing per chunk would double count.
