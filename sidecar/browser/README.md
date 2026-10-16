# ze-browser

Headless browser sidecar for [Ze](../../README.md). A small FastAPI service that loads web pages with Playwright and returns extracted text. Ze's prospecting agent calls it over the private network — not exposed to the public internet.

## Why a separate service

Chromium needs ~512 MB RAM and a full browser stack. Running it inside the main Ze process would bloat the API container and slow cold starts. `ze-browser` deploys as its own Fly.io app; Ze talks to it at `http://ze-browser.internal:8080` via Fly's internal DNS.

| Concern | Main Ze app | ze-browser |
|---|---|---|
| Role | Orchestration, agents, web client API | Page fetch + text extraction |
| Stack | LangGraph, Postgres, embeddings | Playwright + Chromium |
| Network | Public webhook + internal calls | Internal only |
| Deploy | `fly deploy` (repo root) | `fly deploy` (this directory) |

Deploy both apps to the **same Fly region** so private-network latency stays low.

---

## API

### `GET /health`

```json
{"status": "ok"}
```

Used by Ze at startup (`BrowserClient.health()`) to detect whether browser extraction is available.

### `POST /extract`

**Request**

```json
{
  "url": "https://example.com/about",
  "timeout_ms": 15000
}
```

**Response**

```json
{
  "url": "https://example.com/about",
  "title": "About us",
  "text": "…visible page text…",
  "status_code": 200
}
```

| HTTP status | Meaning |
|---|---|
| `400` | Invalid URL |
| `502` | Navigation failed |
| `504` | Page load timed out |
| `200` with `status_code: 403` and empty `text` | Blocked, CAPTCHA, or body too short (< 200 chars) |

No LLM runs in this service — Ze's agents decide what to do with the returned text.

---

## Behaviour

On each request the extractor:

1. Waits **1–3 s** (random jitter) before navigation
2. Launches Chromium with `--no-sandbox` (required in containers)
3. Applies **playwright-stealth** when available
4. Rotates among a pool of recent Chrome **user-agents**
5. Navigates with `networkidle`, falling back to `domcontentloaded` on timeout
6. Reads `body` via `inner_text`, then strips HTML tags if the result is too short

Sites that return 403/429 or unusable content get `status_code: 403` and empty `text` so the prospecting agent can skip to the next source.

---

## Local development

For compose, health checks, and hybrid `make dev` setup, see
[docs/browser.md](../../docs/browser.md).

### Docker (recommended)

From this directory:

```bash
docker build -t ze-browser .
docker run --rm -p 8080:8080 ze-browser
```

```bash
curl http://localhost:8080/health
curl -X POST http://localhost:8080/extract \
  -H 'Content-Type: application/json' \
  -d '{"url": "https://example.com"}'
```

### Without Docker

Requires Python 3.12+ and a Chromium install via Playwright:

```bash
pip install -r requirements.txt
playwright install chromium --with-deps

uvicorn main:app --host 0.0.0.0 --port 8080
```

Point Ze at the local sidecar by setting in `.env` or `config/config.yaml`:

```yaml
browser:
  service_url: "http://localhost:8080"
```

---

## Deployment (Fly.io)

First-time setup:

```bash
cd ze-browser
fly launch --no-deploy   # accept generated fly.toml or adjust region
fly deploy
fly logs
```

Subsequent releases:

```bash
fly deploy
```

`fly.toml` keeps `min_machines_running = 1` to avoid a 30–60 s cold start on the first browser call after idle. The VM is `shared-cpu-1x` with **1 GB** memory for Chromium headroom.

Ze does **not** redeploy this app when the main backend deploys — version and release them independently. Breaking changes to `/extract` must be coordinated with `integrations/ze-browser/ze_browser/client.py`.

---

## Integration with Ze

| Ze module | Role |
|---|---|
| `integrations/ze-browser/ze_browser/client.py` | `BrowserClient` — HTTP client for `/extract` and `/health` |
| `integrations/ze-browser/ze_browser/tool.py` | `browser_extract` tool (rate limit + text truncation) |
| `plugins/ze-prospecting/ze_prospecting/agents/` | Primary consumer — team pages, registries, search result URLs |

`ze-api` reads these settings from the environment (see `apps/ze-api/.env.example`):

```bash
BROWSER_SERVICE_URL=http://ze-browser.internal:8080
BROWSER_TIMEOUT_SECONDS=20
BROWSER_MAX_TEXT_CHARS=8000
BROWSER_DELAY_MS=2000
```

If the sidecar is unreachable, Ze logs a warning and prospecting falls back to web-search-only research; individual `browser_extract` calls return an error string the agent can skip.

---

## Further reading

- [specs/phases/026-prospecting-agent/spec.md](../../specs/phases/026-prospecting-agent/spec.md) — full design for the prospecting agent and browser contract
- [README.md](../../README.md) — main Ze project setup and deployment
