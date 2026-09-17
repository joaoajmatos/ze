# Ze — Workspace Sidecar

Ze uses a separate **workspace sidecar** as its durable computer: files under
`/workspace`, a shell, and ordinary scripting runtimes. The main API talks to it
over HTTP. This keeps arbitrary commands out of Ze's process, env, and filesystem.

This is **not** a browsing session. Web pages stay in the [browser sidecar](browser.md).

![Architecture diagram showing Ze's mind (ze-api and secrets) separated from an isolated workspace sidecar that holds files and runs commands. A workspace gate is the only permitted HTTP path into the computer. Public internet egress is allowed. A sibling browser sidecar extracts pages and is not the computer. Forbidden paths from the workspace toward Ze secrets stop at the isolation boundary.](diagrams/docs/workspace-isolation.svg)

<sub>[Interactive version](diagrams/docs/workspace-isolation.html)</sub>

| Piece | Location | Role |
|---|---|---|
| Sidecar service | `sidecar/workspace/` | FastAPI — files, run, cancel, reset |
| Python package | `core/ops/ze-workspace/` | Client, gate, tools, store, REST |
| Web UI | `apps/ze-web` System `/workspace` | Tree and occupancy (map only) |

If the sidecar is unreachable, workspace tools return an error the agent can skip.
Chat attachments still place files through the API. The System page lists the tree;
it does not run commands, reset, or switch a mode.

See [configuration.md](configuration.md#workspace-sidecar) for env vars.

---

## Access

There is no stored execution mode. Conversation always may use the workspace when
it is available: reads proceed, writes and commands confirm in the thread, reset
confirms. Unattended work (goals, workflows) uses the same computer without that
pause. Skill scripts still need executable approval.

Detached runs, automatic follow-up turns, and push when a run finishes are spec 116,
not this sidecar.

## Skill scripts

Skills are reusable instructions. Their bundled scripts are a workspace concern.
Approving a skill's instructions does not approve its scripts.

1. Import and approve the skill on `/skills` (instructions become active).
2. Approve executables (`POST /api/v0/skills/{id}/approve-executables`).
3. When the skill matches a turn, the agent may call `workspace_run_skill_script`.
   The sidecar writes the stored bytes under `/workspace` and runs them after
   the same conversation confirmation as other commands (unattended work does
   not pause).

Matching a skill never auto-executes scripts. Disabled and pending skills never run
them. A source-content change clears `executable_approved` and sends the skill back
to pending review.

Full skill lifecycle, matching, and the two-gate approval: [skills.md](skills.md#workspace-integration).

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
