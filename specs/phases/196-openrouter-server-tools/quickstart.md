# Quickstart: OpenRouter Server Tools (196)

## Offline gates

```bash
make test-agents        # allowlist, schema builder, registry rejection, loop reply handling
make test-core          # tee capture of server_tool_use, tracker → recorder, trace stamp, token_queue path gone
make test-personal      # research agent declares web_fetch, passes config, no stream()
make test-py            # every suite still green after the stream() deletions
make test-web           # ToolsTimeline server tool line + label helper
make typecheck-web
rtk proxy grep -rn ":online" --include=*.py --include=*.yaml core plugins apps packages   # expect nothing
```

## Manual (local dev, optional)

1. `make dev-full`, open Ask, send "What does https://example.com say?".
2. Expect a research reply that quotes the page and cites the URL.
3. Open the trace: the Tools instrument shows "Read page ×1" when OpenRouter reports the count.

## Live eval (only with the user's OK; costs credits)

```bash
python eval/run.py --tag research_fetch
```

Two scenarios in `eval/scenarios/research.yaml`: a named public URL is read and cited; a 404 URL is reported as unreadable without invented content.
