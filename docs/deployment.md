# Ze — Deployment Guide

Ze runs on [Fly.io](https://fly.io) as a single-machine app with an attached
Postgres database. GitHub Actions runs CI on every push and pull request to `main`.
You start a deploy by hand.

The deployment unit is `apps/ze-api/`. The `fly.toml` and `Dockerfile` both live
there.

---

## Prerequisites

- [flyctl](https://fly.io/docs/hands-on/install-flyctl/) installed and authenticated
- A Fly.io account
- All environment variables from `apps/ze-api/.env.example` ready

---

## First-time setup

### 1. Create the Fly app

```bash
cd apps/ze-api
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

Set every required env var as a Fly secret. Fly encrypts secrets at rest and
injects them as environment variables at runtime.

```bash
fly secrets set \
  OPENROUTER_API_KEY=sk-or-... \
  ZE_API_KEY=your-secret-key \
  DATABASE_URL_SYNC="postgresql+psycopg2://..." \
  NTFY_BASE_URL=https://ntfy.sh \
  NTFY_TOPIC=ze-your-topic \
  NTFY_TOKEN=your-ntfy-token \
  TIMEZONE=Europe/Lisbon
```

For calendar and email (if you have Google credentials):

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
fly ssh console -C "python -m ze_api.migrate upgrade"
```

Or use the `DATABASE_URL_SYNC` value locally and run `make migrate` pointed at the
production database. The SSH console approach is simpler for initial setup.

#### Upgrading after the conversation-module reorg (zc015–zc018)

If your database was stamped with the old `ze` branch heads (`ze001`, `ze002`, `006`,
`008`), run:

```bash
make migrate        # applies zc015–zc018 (no-op if tables already exist)
make migrate-stamp  # purges orphan revision rows and sets correct heads
```

### 5. Deploy

```bash
fly deploy
```

The Dockerfile builds the image, Fly pushes it, and the app starts. Check the
logs immediately after:

```bash
fly logs
```

Look for `ze_startup_complete` to confirm the app is healthy.

---

## Ongoing operations

### Deploy

```bash
fly deploy
```

Or run the **Deploy backend** workflow by hand: Actions → Deploy backend → Run workflow.
A push to `main` does not deploy.

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

The default config uses one shared-cpu-1x machine with 1 GB RAM. Two local models
load at startup: the embedding model (`intfloat/multilingual-e5-base`)
and the NLI cross-encoder (`cross-encoder/nli-deberta-v3-small`, ~90 MB). The Docker
build (`apps/ze-api/Dockerfile`) pre-downloads both.

```bash
fly scale memory 2048   # upgrade to 2 GB if needed
fly scale count 1       # always 1 — Ze is single-user, no horizontal scaling
```

### Run migrations on production

```bash
fly ssh console -C "cd /app && python -m alembic upgrade head"
```

Or from the repo root:
```bash
make migrate  # runs against DATABASE_URL_SYNC
```

### Hot-reload config (no restart)

```bash
fly ssh console -C "kill -HUP 1"
```

This reloads YAML settings without interrupting the process.
Changes to model assignments or plugin configuration require a full `fly deploy`.

### Update a secret

```bash
fly secrets set OPENROUTER_API_KEY=sk-or-new-key
```

Fly restarts the machine automatically after a secret update.

---

## CI/CD (GitHub Actions)

Three workflows live in `.github/workflows/`:

**`ci.yml`** — runs on every push and pull request to `main`. Each job runs all its
gates, even when an earlier gate fails, so one red run shows every broken gate:
- **Web:** `make typecheck-web`, `make lint-web`, `make web-build`, `make test-web`
- **Backend:** `make lint` (ruff), then `make test-py` (every Python package suite,
  fast tests only)

**`deploy-backend.yml`** — runs only when you start it (`workflow_dispatch`). It calls
`flyctl deploy . --remote-only` with `apps/ze-api/fly.toml` and
`apps/ze-api/Dockerfile`, using the `FLY_API_TOKEN` secret. It does not run CI first.

**`publish-packages.yml`** — runs when you push a tag that matches `pkg-v*`. It
publishes the shared npm packages.

### One-time GitHub setup

1. Create a Fly deploy token (scoped to Ze's app, long-lived):
   ```bash
   fly tokens create deploy -x 999999h
   ```
2. Add it as a GitHub Actions secret named `FLY_API_TOKEN`:
   - Repo → Settings → Secrets and variables → Actions → New repository secret

GitHub needs no other secrets — all runtime secrets live in Fly.

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

  [http_service.concurrency]
    type = "connections"
    hard_limit = 25
    soft_limit = 20

[[vm]]
  memory = "1gb"
  cpu_kind = "shared"
  cpus = 1
```

`auto_stop_machines = true` means the machine sleeps when there is no traffic.
The cold start (machine wake + model load) takes ~5–10 seconds. If this latency
is unacceptable, set `min_machines_running = 1` to keep the machine always warm
(increases monthly cost).

**Note:** WebSocket connections require the machine to stay awake. If you rely on
a persistent WebSocket from the web app, set `min_machines_running = 1` or use
ntfy push notifications as the fallback when the machine is cold.

---

## Laptop hosts

Ze also runs locally on a laptop, where a scheduled time can pass while the machine
sleeps or is shut. Ze runs each missed cron job once on startup, within the job's
`catch_up_max_age_hours` (the morning briefing defaults to 6 hours). A process that
was suspended over a fire time runs the job once on resume, because APScheduler uses
`misfire_grace_time=None` with `coalesce=True`. Overdue calendar reminders fire on
startup, marked late. A job with no recorded run does not catch up. When quiet hours
end while the host was down, the release sweep runs within five minutes of startup.
See [scheduled-jobs.md](scheduled-jobs.md#catch-up-for-missed-runs).

---

## Troubleshooting

**`ze_startup_complete` not in logs after deploy**

The app failed during startup. Common causes:

- Missing required env var (check `fly secrets list`)
- Database not reachable (check `DATABASE_URL` and Postgres status)
- Migration not applied (run `fly ssh console -C "python -m alembic upgrade head"`)

**WebSocket disconnects / cannot connect**

- Verify `ZE_API_KEY` secret is set and matches what the app sends as the bearer token.
- Check `fly logs` for `ws_handler_error` events.
- If using `auto_stop_machines = true`, the machine may be cold — the first WebSocket
  connect triggers a wake; subsequent reconnects will be faster.

**Database migrations not applied**

```bash
fly ssh console -C "cd /app && python -m alembic current"
fly ssh console -C "cd /app && python -m alembic upgrade head"
```

**Machine OOM (out of memory)**

The embedding model uses ~450 MB. If other memory pressure exists, upgrade:
```bash
fly scale memory 2048
```

**Google Calendar / Gmail 401 errors**

Google revoked the refresh token. Re-run `scripts/google_auth.py` locally,
get a new refresh token, and update the secret:
```bash
fly secrets set GOOGLE_REFRESH_TOKEN=new-token
```

**ntfy push not delivering**

- Confirm `NTFY_TOPIC` and `NTFY_TOKEN` are set correctly.
- Check `fly logs` for `native_interface_ntfy_failed` events.
- Verify the ntfy server is reachable from the Fly machine (use a public server if
  self-hosting over a private network).
