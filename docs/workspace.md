# Ze — Workspace Sidecar

Ze uses a separate **workspace sidecar** as its durable computer: files under
`/workspace`, a shell, and ordinary scripting runtimes. The main API talks to it
over HTTP. This keeps arbitrary commands out of Ze's process, env, and filesystem.

This is **not** a browsing session. Web pages stay in the [browser sidecar](browser.md).

![Architecture diagram showing Ze's mind (ze-api and secrets) separated from an isolated workspace sidecar that holds files and runs commands. A workspace gate is the only permitted HTTP path into the computer. Public internet egress is allowed. A sibling browser sidecar extracts pages and is not the computer. Forbidden paths from the workspace toward Ze secrets stop at the isolation boundary.](diagrams/docs/workspace-isolation.svg)

<sub>[Interactive version](diagrams/docs/workspace-isolation.html)</sub>

| Piece | Location | Role |
|---|---|---|
| Sidecar service | `sidecar/workspace/` | FastAPI — files, runs (start, status, event stream, cancel), reset |
| Python package | `core/ops/ze-workspace/` | Client, gate, tools, store, REST |
| Web UI | `apps/ze-web` Governance › Files (`/governance#files`) | Read-only tree and occupancy |

If the sidecar is unreachable, workspace tools return an error the agent can skip.
Chat attachments still place files through the API. Governance › Files lists the tree;
it is read-only. It does not start commands, upload, delete or reset.

See [configuration.md](configuration.md#workspace-sidecar) for env vars.

---

## Access

There is no stored execution mode. Conversation always may use the workspace when
it is available: reads proceed, writes and commands confirm in the thread, reset
confirms. Unattended work (goals, workflows) uses the same computer without that
pause. Skill scripts still need executable approval.

## Runs

The sidecar owns each run. `POST /run` returns at once with a run handle that Ze
chooses. Ze records the run in `workspace_runs` before it starts the command.

- **Wait, then detach.** A command that finishes within the short wait (25 seconds
  by default) returns its output in the same turn. A longer command keeps running.
  The turn ends with a "still running" reply.
- **Follow-up turn.** When a detached command ends, Ze starts a new turn on the same
  thread and reports the result. If no client is connected, Ze sends a push
  notification instead. If the follow-up turn needs your approval before it acts,
  Ze shows the confirmation card. With no client connected, Ze saves the request
  and sends a push.
- **One run at a time.** Ze refuses a second command while one runs. The refusal
  names the running command.
- **Restart.** After `ze-api` restarts, Ze reattaches to runs that are still
  running. If the computer lost a run, Ze marks it failed. It never invents a result.
- **Live output.** While a command runs, chat and Doing › Runs show the output
  so far. The `GET /api/v0/workspace/runs/{run_id}/events` route streams it. A page
  opened mid-run replays the lines already printed.
- **Cancel.** `POST /api/v0/workspace/runs/{run_id}/cancel` stops a running command.
- **Doing › Runs.** The web app lists recent runs on Doing (`/doing`). It shows the live output of a running run and a Cancel button. While a run holds the workspace, the list says "busy". The list refreshes every 5 seconds while a run is in progress. A run is coral only when an unattended run failed or timed out. A cancelled run is never coral. If the sidecar is off, Runs says "Workspace is off" and nothing else changes.

The workspace file map is a read-only tree in Governance › Files (`/governance#files`).

## Skill scripts

Skills are reusable instructions. Their bundled scripts are a workspace concern.
Approving a skill's instructions does not approve its scripts.

1. Import and approve the skill in the Skills queue on Doing (`/doing#skills`). The instructions become active.
2. Approve executables (`POST /api/v0/skills/{id}/approve-executables`).
3. When the skill matches a turn, the agent may call `workspace_run_skill_script`.
   The sidecar writes the stored bytes under `/workspace` and runs them after
   the same conversation confirmation as other commands (unattended work does
   not pause).

Matching a skill never auto-executes scripts. Disabled and pending skills never run
them. A source-content change clears `executable_approved` and sends the skill back
to pending review.

Full skill lifecycle, matching, and the two-gate approval: [skills.md](skills.md#workspace-integration).

## Tool scripts

A tool script is a short Python program that the model writes. It calls the agent's data
read tools in one run, then returns only the answer. The sidecar runs the script. It does
not run it in Ze's process. See [architecture.md](architecture.md#tool-scripts) for the flow.

- **Own slot.** Scripts do not share the workspace run slot. A script can run beside a
  workspace run. Only one script runs at a time, and a second script gets `busy`. `GET /stat`
  reports `scripts_busy`.
- **Scratch only.** Each script gets an empty directory under `/tmp/ze-scripts`. The sidecar
  deletes it after the run. The scratch directory holds at most 32 MB.
- **No network.** The script runs as the `zescript` system user. The sidecar rejects all
  output from that user and checks the rule by listing it. `/workspace` is unreadable to
  `zescript`. At the start of each script, a probe tries to list `/workspace` and to reach
  `1.1.1.1:53`. If either works, the script ends `unavailable` and the sidecar reports
  `scripts_isolated: false`.
- **Fails closed.** The sidecar refuses to run a script (`unavailable`) unless it runs as
  root, the `zescript` user exists, and `scripts_isolated` is true. A root sidecar without
  that user always refuses. A non-root sidecar refuses too, unless
  `ZE_SCRIPTS_ALLOW_UNISOLATED=1` is set. That variable runs scripts as the sidecar's own
  user with no network or file isolation. It exists for the test suite only. Never set it in
  a deployment.
- **Resource limits.** Address space 256 MB, 32 processes, 16 MB per file, 64 open files, and
  CPU time of `workspace.scripts.wall_seconds` plus one second. The sidecar kills every
  process of the `zescript` user when the script ends. Stdout goes nowhere.
- **Gates still apply.** Each read the script makes goes through Ze's normal tool path. A
  write is never called from the script. The script proposes it, and the user confirms it.

### Enabling scripts in local Docker

The sidecar needs `NET_ADMIN` for the reject rule. `docker-compose.yml` adds it:

```yaml
  workspace:
    cap_add:
      - NET_ADMIN
```

Without it, `scripts_isolated` is `false`. Ze then reports `sandbox_unavailable` to the model
and runs no script.

Scripts are not verified on Fly. `sidecar/workspace/fly.toml` sets no `NET_ADMIN`, so the
sidecar reports scripts unavailable there unless the isolation rule applies. Ze runs locally;
no Fly check of scripts has been made. Unattended goals and workflows get no script runner,
so they never run scripts.

---

## Isolation

1. Child env is `PATH`, `HOME=/workspace`, `LANG` only. The API token and Ze secrets
   are never inherited.
2. Child processes cannot reach RFC1918, loopback control ports, or Fly 6PN. Public
   internet is allowed.
3. The writable tree is `/workspace` only. Path resolution refuses anything that
   normalizes outside it.
4. Shown command output redacts secrets (`OPENROUTER_API_KEY`, `DATABASE_URL`,
   `ZE_API_KEY`, `WORKSPACE_API_TOKEN`, and keys matching `*_SECRET` / `*_TOKEN`).

`ze-core` and `ze-agents` must not import `ze_workspace`.

---

## Local development

### Docker Compose (full stack)

`docker-compose.yml` includes a `workspace` service and a `workspace_data` volume.
`make docker-up` starts Postgres, both sidecars, and the backend together. The
backend gets `WORKSPACE_SERVICE_URL=http://workspace:8080` from compose overrides.

```bash
make docker-up
curl http://localhost:8081/health
```

### Hybrid workflow (`make dev` on the host)

Most day-to-day dev uses Postgres from compose and uvicorn on the host:

```bash
make db-up
docker compose up -d workspace    # sidecar only
```

Set in `apps/ze-api/.env`:

```
WORKSPACE_SERVICE_URL=http://localhost:8081
WORKSPACE_API_TOKEN=dev-workspace-token
```

Then `make dev` as usual.

### Sidecar only

Build and run from `sidecar/workspace/` — see
[sidecar/workspace/README.md](../sidecar/workspace/README.md) for the control API
and a non-Docker setup.

---

## Production (Fly.io)

The sidecar deploys as a **separate Fly app** (`sidecar/workspace/fly.toml`), not
inside the main `ze-api` image. Keep `min_machines_running = 1` so the volume stays
mounted. Ze reaches it at `http://ze-workspace.internal:8080` on Fly's private
network. Deploy both apps to the **same region**.

```bash
cd sidecar/workspace
fly deploy
```

The main backend deploy does not redeploy the sidecar — release them independently.
Full Fly setup: [sidecar/workspace/README.md](../sidecar/workspace/README.md).

---

## Further reading

- [skills.md](skills.md) — import, review, matching, and how scripts reach this sidecar
- [sidecar/workspace/README.md](../sidecar/workspace/README.md) — API contract, isolation, Fly config
- [core/ops/ze-workspace/README.md](../core/ops/ze-workspace/README.md) — Python package
- [specs/phases/115-workspace-sidecar/spec.md](../specs/phases/115-workspace-sidecar/spec.md) — design
- [deployment.md](deployment.md) — main backend Fly deploy
