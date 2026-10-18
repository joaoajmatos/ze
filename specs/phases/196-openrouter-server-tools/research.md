# Research: OpenRouter Server Tools (196)

## R1 — `web_fetch` request shape

- **Decision**: `{"type": "openrouter:web_fetch", "parameters": {"engine": "openrouter", "max_uses": 5, "max_content_tokens": 8000}}` (no domain list).
- **Rationale**: OpenRouter docs (2026-10-18, beta): optional `engine` (`auto`, `native`, `exa`, `openrouter`, `firecrawl`, `parallel`), `max_uses`, `max_content_tokens`, `allowed_domains`, `blocked_domains`. The `openrouter` engine is a direct fetch with extraction, free, capped at 50 fetches per request. A successful fetch returns `url`, `title`, `content`, `status`, `retrieved_at`; a failed one `url`, `status: failed`, `error`. Regional endpoints (`eu.`/`us.openrouter.ai`) answer 403. Workspace settings in locked mode reject a request whose engine is outside the workspace list (403).
- **Alternatives**: `auto`/`exa` (paid, URL goes to Exa), rejected by clarification. Strict fetch (`allowed_domains` = the hosts the user pasted): offered and declined by the user (R6). `engine` is validated against the six documented values.
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

## R6 — Exfiltration through fetch URLs (Gauge S-1) — user decision

- **Decision (user, 2026-10-18)**: open fetch. Any URL, `max_uses` from config (default 5), no `allowed_domains`.
- **Risk accepted by the user**: the research prompt carries the user's memory; page text is untrusted; a fetch is a read with no write gate. A page can lead the model to put private text in a fetch URL's path or query, and that text reaches the URL's host. Search queries carry the same risk.
- **Declined alternative**: strict fetch (only on a turn whose user message has links, `allowed_domains` = those hosts, `max_uses` = the number of pasted links, hosts taken only from the user's own turn text through delegates). Gauge's S-12/S-13 belonged to that design and go with it.
- **Mitigations kept**: the per-request cap; instructions (page text is data; nothing from memory in URLs or queries); every fetch target and search query Ze can see is on the trace (R7), so the user can see what left.

## R7 — Fetch targets and sources

- **Decision** (after Gauge D-1/D-2): one owner per kind of evidence. Returned server tool calls come from the agent loop (already parsed, streamed fragments assembled by the client) into `ToolCallTrace.target`; fetch result records (`url` + `status` + `retrieved_at`) come from the raw-body tee. A pure `merge_targets` at stamp time dedups them (a record's status wins), caps at 50 with a dropped count, marks cut targets with their length, and computes per-kind `unreported` = counted requests without a target. Only a record that was read (status not `failed`) becomes a `Source`; a call-only or failed target is on the trace only, so a model-written URL never shows as a citation. When Ze sees fewer targets than OpenRouter counted, the trace says "Ze cannot see which pages were fetched (n of m shown)", never a bare "none".
- **Rationale**: OpenRouter documents fetch results as `url/title/content/status/retrieved_at` but not whether they or the calls reach the client in a chat completion; it does not document `url_citation` annotations for fetched pages. Collecting every documented shape and stating the gap is the honest design; T025 records the real shape. If the chat reply exposes no target at all, the phase is not marked Implemented and the gap goes back to the user (options then: route research through an OpenRouter surface that returns server tool items, or accept counts only).

## R8 — Counting once per response (Gauge S-4)

- **Decision**: the tee keeps the last `server_tool_use` value seen in one response body and adds it to the counter once, when the body finishes.
- **Rationale**: some providers repeat cumulative usage on several stream chunks; summing per chunk would double count.

## R9 — The SDK rejects `openrouter:web_fetch` (build T025, 2026-10-18)

- **Finding**: the installed `openrouter` SDK (0.9.1, also 1.3.65) validates `tools` against its `ChatFunctionTool` union before sending, and that union has no `openrouter:web_fetch`; the first live research turn errored client side ($0 spent).
- **Decision**: the client takes server tools the SDK cannot type out of the SDK call and the citation transport appends them to the request body's `tools`, carried by a ContextVar set for that one request and reset in `finally` (concurrent calls never see each other's tools). The client allowlist guard runs first, unchanged, so only `SERVER_TOOLS` entries can reach the body. Tests first: the body holds the fetch tool with its params, a concurrent call without it does not, the stream and non-stream paths both carry it.
- **Eval**: scenario 2 is worded as a research question about a 404 URL; "Read <url>" alone is an ingest request and routes to ingestion, which is correct (147).
