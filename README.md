# Ze — Personal AI Assistant

A single-user AI assistant accessed via Telegram. Routes conversations to specialised
agents (research, companion, calendar, email) via a LangGraph orchestration layer.
All LLM inference goes through OpenRouter.

## Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12 · FastAPI · LangGraph |
| Bot interface | Telegram (aiogram 3.x) |
| LLM gateway | OpenRouter (all models) |
| Embeddings | `all-MiniLM-L6-v2` (local, no API cost) |
| Graph persistence | LangGraph `AsyncPostgresSaver` → Postgres |
| Database | PostgreSQL 16 + pgvector |
| Migrations | Alembic (raw SQL) |
| Deployment | Fly.io |

## Prerequisites

- Python 3.12+
- [uv](https://github.com/astral-sh/uv) — `pip install uv`
- Docker (for Postgres)
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Quick start

```bash
# 1. Clone
git clone <repo-url> ze && cd ze

# 2. Install dependencies
make install

# 3. Configure secrets
cp .env.example .env
# Edit .env — fill in all required variables (see below).

# 4. Start Postgres and apply migrations
make db-up
make migrate

# 5. Start the backend
make dev
```

The backend registers the Telegram webhook automatically on startup. Messages sent
to your bot will be routed to the running server.

For local development, expose the backend with a tunnelling tool (e.g. `ngrok http 8000`)
and set `PUBLIC_URL` in `.env` to the tunnel URL before starting.

## Environment variables

Copy `.env.example` to `.env` and fill in:

| Variable | Required | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | Yes | OpenRouter API key |
| `TAVILY_API_KEY` | Yes | Tavily search API key (research agent) |
| `ZE_API_KEY` | Yes | Static bearer token for REST endpoints |
| `DATABASE_URL` | No | asyncpg-format Postgres URL (default: `postgresql://ze:ze@localhost:5432/ze`) |
| `DATABASE_URL_SYNC` | No | psycopg2-format URL for Alembic CLI |
| `TELEGRAM_BOT_TOKEN` | Yes | Token from @BotFather |
| `TELEGRAM_WEBHOOK_SECRET` | Yes | Arbitrary secret used to verify Telegram POSTs |
| `TELEGRAM_ALLOWED_CHAT_ID` | Yes | Your personal Telegram chat ID |
| `PUBLIC_URL` | Yes | Public HTTPS base URL (e.g. `https://ze.fly.dev` or ngrok tunnel) |
| `CONFIRM_TIMEOUT_SECONDS` | No | Confirmation timeout in seconds (default: `900`) |
| `LOG_LEVEL` | No | `DEBUG` / `INFO` / `WARNING` (default: `INFO`) |

## Development commands

```bash
make help           # list all targets

make test           # backend unit tests (fast)
make test-all       # include slow embedding-model tests

make lint           # ruff
make migrate        # apply pending DB migrations
make migrate-down   # roll back one step
make db-reset       # drop + recreate the database
```

## Project structure

```
ze/
├── backend/
│   ├── ze/
│   │   ├── api/          # FastAPI app, Telegram webhook handler, REST routes
│   │   ├── agents/       # Agent implementations (research, companion, …)
│   │   ├── capability/   # Permission gate (autonomous / confirm / draft_only)
│   │   ├── memory/       # User facts + episodic memory (Phase 2)
│   │   ├── openrouter/   # LLM client (complete + stream)
│   │   ├── orchestration/# LangGraph graph, nodes, edges, state
│   │   ├── routing/      # Embedding router + Haiku fallback
│   │   └── telegram/     # ZeBot, handlers, keyboards, session store
│   ├── config/
│   │   ├── agents/       # Per-agent YAML (model, tools, timeout, description)
│   │   ├── capabilities.yaml
│   │   └── models.yaml
│   └── migrations/       # Alembic versions
└── specs/                # Design specs for every module
```

## Agent routing

Incoming messages are scored against agent embeddings (cosine similarity). If the
top score is above threshold and the gap to the second agent is wide enough, the
message routes directly. Otherwise Haiku decomposes it into subtasks — one per agent.

```
Telegram message
  → EmbeddingRouter (all-MiniLM-L6-v2, local)
      confident → agent directly
      ambiguous → Haiku decompose → one or more agents
  → CapabilityGate (autonomous / confirm / draft_only / blocked)
  → Agent.run() with asyncio.wait_for timeout
  → memory written (fire and forget)
  → response sent via Telegram Bot API
```

## Agents

| Agent | Phase | Description |
|---|---|---|
| `research` | 1 ✅ | Web search via Tavily + OpenRouter synthesis |
| `companion` | 1 ✅ | Conversational reasoning, memory injection |
| `calendar` | 3 | Google Calendar read/write |
| `email` | 3 | Gmail read/draft/send |
| `workflow` | 4 | Multi-step task planning and execution |

## Capability gate

Each `agent.intent` pair has a permission mode in `config/capabilities.yaml`:

- `autonomous` — executes immediately
- `confirm` — sends a Telegram message with Yes / No / Edit inline buttons (15-min timeout)
- `draft_only` — generates draft, never executes without a YAML change
- `disabled` — always blocked

Config hot-reloads on `SIGHUP`.

## Docker

```bash
make docker-up      # start all services (Postgres + backend)
make docker-down    # stop all services
make docker-build   # rebuild images
```

## CI/CD (GitHub Actions)

On every push and pull request to `main`, CI runs:

- `ruff check`
- fast `pytest` (embedding-model tests excluded)

Merges to `main` that touch `backend/` trigger deployment to Fly.io.

### One-time setup

1. **Fly deploy token** — create a repo secret `FLY_API_TOKEN`:
   ```bash
   fly tokens create deploy -x 999999h
   ```
2. **Fly secrets** — set runtime env on the app:
   ```bash
   fly secrets set OPENROUTER_API_KEY=... TELEGRAM_BOT_TOKEN=... TELEGRAM_WEBHOOK_SECRET=...
   ```

## Deployment (Fly.io)

```bash
fly deploy   # or rely on GitHub Actions on push to main
```

Set all env vars as Fly secrets: `fly secrets set OPENROUTER_API_KEY=...`
