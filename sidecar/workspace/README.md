# ze-workspace

Isolated workspace sidecar for [Ze](../../README.md). A small FastAPI service that is Ze's durable computer: files under `/workspace`, a shell, and ordinary scripting runtimes. Ze's agents call it over the private network — not exposed to the public internet.

This is **not** a browsing session. Web pages stay in `sidecar/browser`. This service runs commands and holds files.

## Why a separate service

Arbitrary commands must not share Ze's process, env, or filesystem. The sidecar is the always-on computer; Ze is the mind. Child processes run as an unprivileged `workspace` user with a stripped env and cannot reach Ze's private services or credentials.

| Concern | Main Ze app | ze-workspace |
|---|---|---|
| Role | Orchestration, agents, memory | Files + shell + runtimes |
| Stack | LangGraph, Postgres, embeddings | FastAPI + bash/python/node |
| Network | Public API + internal calls | Internal control API; public egress from child uid |
| Deploy | `fly deploy` (repo root) | `fly deploy` (this directory) + volume |

Deploy both apps to the **same Fly region**. Keep `min_machines_running = 1` so the volume stays mounted (FR-001).

---

## API

Internal control API. Auth: `Authorization: Bearer $WORKSPACE_API_TOKEN` on every route except `GET /health`. See [contracts/workspace-sidecar.md](../../specs/phases/115-workspace-sidecar/contracts/workspace-sidecar.md).

| Route | Role |
|---|---|
| `GET /health` | Process + volume ready |
| `GET /stat` | Bytes used, ceiling, busy |
| `GET /fs` | List directory |
| `GET /fs/download` | File bytes |
| `PUT /fs` | Write JSON (base64) |
| `POST /fs/upload` | Multipart place |
| `DELETE /fs` | Delete path |
| `POST /run` | Exec command (mutex, timeout) |
| `POST /cancel` | Kill in-flight run |
| `POST /reset` | Wipe `/workspace` |

---

## Isolation

1. Child env is `PATH`, `HOME=/workspace`, `LANG` only. The API token and Ze secrets are never inherited.
2. Child uid cannot reach RFC1918, loopback control ports, or Fly 6PN. Public internet is allowed.
3. Writable tree is `/workspace` only. Path resolution refuses anything that normalizes outside it.

---

## Local development

Compose service `workspace` + named volume `workspace_data`. Point Ze at it with `WORKSPACE_SERVICE_URL=http://workspace:8080` (compose) or `http://localhost:8081` (hybrid `make dev`).

See [docs/workspace.md](../../docs/workspace.md) once that doc lands.

### Docker

```bash
docker build -t ze-workspace .
docker run --rm -p 8081:8080 \
  -e WORKSPACE_API_TOKEN=dev-token \
  -v workspace_data:/workspace \
  ze-workspace
```

```bash
curl http://localhost:8081/health
```

---

## Deployment (Fly.io)

```bash
cd sidecar/workspace
fly launch --no-deploy
fly volumes create workspace_data --region iad --size 2
fly deploy
```

`fly.toml` keeps `min_machines_running = 1`. Ze talks to `http://ze-workspace.internal:8080`.
