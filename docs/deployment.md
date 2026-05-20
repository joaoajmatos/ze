# Ze — Deployment Guide

Ze runs on [Fly.io](https://fly.io) as a single-machine app with an attached
Postgres database. GitHub Actions handles CI and automated deploys on push to `main`.

---

## Prerequisites

- [flyctl](https://fly.io/docs/hands-on/install-flyctl/) installed and authenticated
- A Fly.io account
- All environment variables from `.env.example` ready

---

## First-time setup

### 1. Create the Fly app

```bash
fly launch --no-deploy
```

Accept the generated `fly.toml` defaults or adjust the app name and region. The
current config targets `lhr` (London). Edit `fly.toml` to change the region.

### 2. Provision Postgres

```bash
fly postgres create --name ze-db --region lhr
fly postgres attach ze-db
```

`attach` sets `DATABASE_URL` automatically as a Fly secret. You still need to
set `DATABASE_URL_SYNC` manually (see step 3).

### 3. Set secrets

Set every required env var as a Fly secret. Secrets are encrypted at rest and
injected as environment variables at runtime.

```bash
fly secrets set \
  OPENROUTER_API_KEY=sk-or-... \
  TAVILY_API_KEY=tvly-... \
  ZE_API_KEY=your-secret-key \
  DATABASE_URL_SYNC="postgresql+psycopg2://..." \
  TELEGRAM_BOT_TOKEN=... \
  TELEGRAM_WEBHOOK_SECRET=your-webhook-secret \
  TELEGRAM_ALLOWED_CHAT_ID=123456789 \
  PUBLIC_URL=https://ze-backend.fly.dev \
  TIMEZONE=Europe/Lisbon
```

For calendar and email (if enabled):

```bash
fly secrets set \
  GOOGLE_CLIENT_ID=... \
  GOOGLE_CLIENT_SECRET=... \
  GOOGLE_REFRESH_TOKEN=...
```

List current secrets (names only, values hidden):
```bash
fly secrets list
```

### 4. Apply database migrations

```bash
fly ssh console -C "python -m alembic upgrade head"
```

Or use the `DATABASE_URL_SYNC` value locally and run `make migrate` pointed at the
production database. The SSH console approach is simpler for initial setup.

### 5. Deploy

```bash
fly deploy
```

The Dockerfile builds the image, Fly pushes it, and the app starts. Check the
logs immediately after:

```bash
fly logs
```

Look for `webhook registered` to confirm Telegram received the webhook URL.

---

## Ongoing operations

### Deploy

```bash
fly deploy
```

Or push to `main` — GitHub Actions will deploy automatically.

### View logs

```bash
fly logs              # tail live logs
fly logs --tail       # keep tailing
```

### SSH into the running machine

```bash
fly ssh console
```

### Scale

The default config uses one shared-cpu-1x machine with 1 GB RAM. The embedding
model (`all-MiniLM-L6-v2`) loads into ~200 MB RAM at startup.

```bash
fly scale memory 2048   # upgrade to 2 GB if needed
fly scale count 1       # always 1 — Ze is single-user, no horizontal scaling
```

### Run migrations on production

```bash
fly ssh console -C "python -m alembic upgrade head"
```

### Hot-reload config (no restart)

```bash
fly ssh console -C "kill -HUP 1"
```

This reloads capability modes and persona settings without interrupting the process.
Changes to agent `enabled` flags or model assignments require a full `fly deploy`.

### Update a secret

```bash
fly secrets set OPENROUTER_API_KEY=sk-or-new-key
```

Fly restarts the machine automatically after a secret update.

---

## CI/CD (GitHub Actions)

Two workflows live in `.github/workflows/`:

**`ci.yml`** — runs on every push and pull request to `main`:
- `ruff check` (linting)
- `pytest` with fast tests only (embedding model tests excluded)

**`deploy.yml`** — runs on merge to `main` when application code changes:
- Runs CI first
- Calls `fly deploy --remote-only` using a scoped deploy token

### One-time GitHub setup

1. Create a Fly deploy token (scoped to Ze's app, long-lived):
   ```bash
   fly tokens create deploy -x 999999h
   ```
2. Add it as a GitHub Actions secret named `FLY_API_TOKEN`:
   - Repo → Settings → Secrets and variables → Actions → New repository secret

No other secrets are needed in GitHub — all runtime secrets live in Fly.

---

## Telegram webhook

In production, Ze uses a webhook. Telegram POSTs every update to:

```
POST https://ze-backend.fly.dev/telegram/webhook
```

The webhook is registered at startup (in the FastAPI lifespan) when `PUBLIC_URL` is
set. If it falls out of sync:

```bash
# Re-register manually
fly ssh console -C "python -c \"
import asyncio
from ze.container import build_container
from ze.settings import get_settings

async def main():
    s = get_settings()
    c = await build_container(s)
    await c.bot.set_webhook()

asyncio.run(main())
\""
```

Or redeploy — the lifespan handler re-registers on every start.

To verify the registered webhook:
```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

---

## Machine spec (`fly.toml`)

```toml
[build]
  dockerfile = "Dockerfile"

[env]
  PORT = "8000"

[http_service]
  internal_port = 8000
  force_https = true
  auto_stop_machines = true    # machine sleeps when idle
  auto_start_machines = true   # wakes on incoming request
  min_machines_running = 0

[[vm]]
  memory = "1gb"
  cpu_kind = "shared"
  cpus = 1
```

`auto_stop_machines = true` means the machine sleeps when there is no traffic.
The cold start (machine wake + model load) takes ~5–10 seconds. If this latency
is unacceptable, set `min_machines_running = 1` to keep the machine always warm
(increases monthly cost).

---

## Troubleshooting

**Telegram stops delivering messages**

Check if polling is running locally — it steals delivery from the webhook while active.
Stop the local process (Ctrl-C) and Telegram resumes webhook delivery within seconds.

Verify the webhook is registered:
```bash
curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
```

**`webhook registered` not in logs after deploy**

`PUBLIC_URL` may be missing or wrong. Confirm the secret:
```bash
fly secrets list
```

**Database migrations not applied**

```bash
fly ssh console -C "python -m alembic upgrade head"
fly ssh console -C "python -m alembic current"
```

**Machine OOM (out of memory)**

The embedding model uses ~200 MB. If other memory pressure exists, upgrade:
```bash
fly scale memory 2048
```

**Google Calendar / Gmail 401 errors**

The refresh token has been revoked. Re-run `scripts/google_auth.py` locally,
get a new refresh token, and update the secret:
```bash
fly secrets set GOOGLE_REFRESH_TOKEN=new-token
```
