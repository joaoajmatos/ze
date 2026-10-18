# ze-workspace

Isolated workspace sidecar for [Ze](../../README.md). A small FastAPI service that is Ze's durable computer: files under `/workspace`, a shell, and ordinary scripting runtimes. Ze's agents call it over the private network — not exposed to the public internet.

This is **not** a browsing session. Web pages stay in `sidecar/browser`. This service runs commands and holds files. Skill scripts are ordinary files Ze writes, then runs — the sidecar does not know about skills. See [docs/skills.md](../../docs/skills.md).

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
| `GET /stat` | Bytes used, ceiling, busy, `scripts_busy`, `scripts_isolated` |
| `GET /fs` | List directory |
| `GET /fs/download` | File bytes |
| `PUT /fs` | Write JSON (base64) |
| `POST /fs/upload` | Multipart place |
| `DELETE /fs` | Delete path |
| `POST /run` | Start a command; returns at once (one run at a time, timeout) |
| `GET /runs/{run_id}` | Run status and output preview |
| `GET /runs/{run_id}/events` | Stream stdout, stderr, and exit |
| `POST /runs/{run_id}/cancel` | Kill a running command |
| `POST /reset` | Wipe `/workspace` |
| `WS /scripts` | Run one tool script (see below) |

---

## Tool scripts (`WS /scripts`)

Ze sends a short Python script over a WebSocket. The script calls Ze's read tools through the `ze_tools` module and returns one value. Contract: [contracts/scripts.md](../../specs/phases/197-programmatic-tool-use/contracts/scripts.md).

The sidecar closes the handshake with code 1008 when the bearer token is missing or wrong, or when `WORKSPACE_API_TOKEN` is empty. This route fails closed even though the other routes do not.

| Direction | Frame |
|---|---|
| Ze → sidecar | `start` (`id`, `source`, `stub`, `timeout_seconds`) |
| sidecar → Ze | `call` (`seq`, `tool`, `args`) |
| Ze → sidecar | `reply` (`seq`, `ok`, `value` or `error`), `cancel` |
| sidecar → Ze | `end` (`status`, `value`, `writes`, `stderr_tail`, `exception`) |

`end.status` is one of `ok`, `exception`, `timeout`, `killed`, `bad_request`, `busy`, `unavailable`, `resource_limit`. The sidecar closes the socket after `end`.

**The script slot.** One script runs at a time. A second connection gets `end` with `busy`. The slot is separate from the workspace run journal, so a shell run can go on while a script runs.

**The sandbox.** Each script gets a scratch directory `/tmp/ze-scripts/<id>`, removed at the end. The sidecar spawns `python3 -I -X utf8 _ze_main.py` there as the system user `zescript`. The environment holds only `PATH`, `HOME`, `LANG`, `ZE_REQ_FD` and `ZE_REP_FD`. Requests and replies move over two pipes, one JSON object per line. Standard output goes to `/dev/null`; the last 20 lines of standard error come back as `stderr_tail`.

| Limit | Value |
|---|---|
| Address space (`RLIMIT_AS`) | 256 MiB |
| Processes (`RLIMIT_NPROC`) | 32 |
| File size (`RLIMIT_FSIZE`) | 16 MiB |
| CPU time (`RLIMIT_CPU`) | wall time + 1 s |
| Open files (`RLIMIT_NOFILE`) | 64 |
| Scratch directory | 32 MiB, polled every 0.1 s |
| Request line | 256 KB |
| Reply or `finish` line | 1 MiB |
| Request lines per script | 40 |
| WebSocket frame | 2 MiB |

A line over its cap, malformed JSON, or a bad `writes` entry ends the script `bad_request`. A script killed by a limit signal, or one that dies of `MemoryError`, ends `resource_limit`. Timeout, cancel and end kill every process of the `zescript` user, so a `setsid` child cannot outlive the script.

**Isolation.** At startup the sidecar adds a `reject` rule for all output from the `zescript` uid (`nft` with `meta skuid`, `iptables --uid-owner` as the fallback). It then reads the chain back and looks for the rule; a command that exits 0 is not enough. It also sets `/workspace` to mode 0750. `GET /stat` reports `scripts_isolated: true` only when both hold. Each script starts with a probe: it must fail to list `/workspace` and fail to open a TCP connection to `1.1.1.1:53` within 0.5 s. A breach ends the script `unavailable` and sets `scripts_isolated` to false. Ze refuses to run scripts while `scripts_isolated` is false.

Local dev needs `cap_add: [NET_ADMIN]` on the workspace service (already set in `docker-compose.yml`). Without it the reject rule cannot be added, `scripts_isolated` stays false, and scripts are unavailable.

**Smoke test.** With the sidecar up (`make workspace-up`):

```bash
python sidecar/workspace/tests/smoke_scripts.py
```

It checks the network reject, the closed `/workspace`, each resource limit, the `setsid` kill, discarded standard output, a round trip and the handshake refusal.

---

## Isolation

1. Child env is `PATH`, `HOME=/workspace`, `LANG` only. The API token and Ze secrets are never inherited.
2. Child uid cannot reach RFC1918, loopback control ports, or Fly 6PN. Public internet is allowed.
3. Writable tree is `/workspace` only. Path resolution refuses anything that normalizes outside it.

---

## Local development

Compose service `workspace` + named volume `workspace_data`. Point Ze at it with `WORKSPACE_SERVICE_URL=http://workspace:8080` (compose) or `http://localhost:8081` (hybrid `make dev`).

See [docs/workspace.md](../../docs/workspace.md).

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
