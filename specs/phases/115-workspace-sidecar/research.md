# Phase 0 Research: Workspace Environment

All items below were resolved either by the spec's Clarifications session
(2026-08-14) or by surveying existing Ze architecture for the closest precedent. No
open `NEEDS CLARIFICATION` markers remain.

## 1. Package placement: client + domain core package, plus a sidecar

**Decision**: New `core/ze-workspace/` package (client, types, store, gate, tools,
bootstrap) wired directly into `apps/ze-api`, plus a new `sidecar/workspace/` process
that is the actual computer. Not a `ZePlugin`.

**Rationale**: The workspace is cross-cutting infrastructure — every agent may use it,
skills may run scripts in it, unattended work may use it when mode is Auto, and the
mind must stay where it is (FR-023). That is the same split as the browser helper
(`core/ze-browser` + `sidecar/browser`) combined with the store/bootstrap shape of
`ze-skills` / `ze-worldstate` (durable records, REST facade, migrations). A plugin
would imply a single owning domain; the workspace is the computer beside the mind.

**Alternatives considered**:
- *Fold into `ze-core`* — rejected. `ze-core` stays pure engine; `ze-browser` and
  `ze-worldstate` exist specifically so this kind of substrate does not land there.
  Graph/confirmation integration is dependency-injected (`config["configurable"]`),
  same as `skill_matcher` / `loop_surfacer`.
- *A `ZePlugin`* — rejected. No single domain owns "the computer". Plugins must not
  import `ze_core`; the confirmation interrupt and `MessageTrace` fields live in the
  engine composition root.
- *Only a sidecar client, no store* — rejected. FR-008 / FR-025 require durable run
  records with a stable identity a sibling follow-through spec can attach to. That
  belongs in Postgres, owned by this package.

## 2. Isolation: separate process, stripped child env, private-range deny

**Decision**: The workspace is a dedicated long-lived container/app with a durable
volume at `/workspace`. Ze talks to a control API on that process (mirroring
`BrowserClient` → `http://ze-browser.internal:8080`). Workspace *programs* are
subprocesses of that sidecar, not of `ze-api`.

Hard isolation rules (enforced in the sidecar, tested without a real container in
unit tests via fakes):

1. Child processes receive a clean env (`PATH`, `HOME=/workspace`, `LANG` only). Ze
   credentials, `DATABASE_URL`, `OPENROUTER_API_KEY`, `ZE_API_KEY`,
   `WORKSPACE_API_TOKEN`, and internal hostnames are not present.
2. Child processes run as an unprivileged `workspace` user. The control API runs as
   a supervisor user. The API token is never inherited.
3. Owner-uid firewall (nftables/iptables): the `workspace` uid cannot reach RFC1918,
   loopback control ports, or Fly 6PN (`fdaa::/16` / `fd00::/8`). Public internet
   egress is allowed (FR-026). Failed public fetches surface as failed runs, not as
   internal outages.
4. Filesystem: the writable tree is `/workspace` only. Path resolution refuses
   anything that normalizes outside it (FR-015). Ze config, `.env`, docker.sock, and
   Postgres data are not mounted.
5. Control API is reachable from `ze-api` over the private compose/Fly network, like
   the browser sidecar. It is not a browsing session and does not replace
   `ze-browser` (FR-022).
6. Before persist and before inlining into chat, `output_preview` and `error_summary`
   pass a denylist sanitizer (`ze_workspace/sanitize.py`) that redacts env-key names
   (`OPENROUTER_API_KEY`, `DATABASE_URL`, `ZE_API_KEY`, `WORKSPACE_API_TOKEN`, and
   `*_SECRET` / `*_TOKEN` / `*_PASSWORD`). Child env stripping is not enough for
   SC-004 if a process prints a secret it obtained another way — still redact the
   shown preview.

Local: Compose service `workspace` + named volume `workspace_data`,
`WORKSPACE_SERVICE_URL=http://workspace:8080`. Prod: Fly app `ze-workspace` with a
volume, `WORKSPACE_SERVICE_URL=http://ze-workspace.internal:8080`,
`min_machines_running = 1` (always-on, FR-001).

**Rationale**: The spec asks for the same kind of split as the web-browsing helper,
not a nested hypervisor. Browser isolation today is "separate service + internal
URL" with no credential scrubbing. Workspace must go further because it runs
*arbitrary* commands. The uid-firewall + stripped env is proportionate for a
single-user assistant and implementable on both Compose and Fly without Firecracker.

**Alternatives considered**:
- *gVisor / Firecracker / Kata* — rejected for this phase. Stronger isolation, but
  new runtime, new ops, and no existing precedent in the repo. Can harden later
  without changing the control-API contract.
- *In-process subprocess of ze-api* — rejected. Same filesystem and env as the mind;
  FR-003 would be a convention, not a boundary.
- *Keep workspace off Fly 6PN entirely and expose the API publicly* — rejected.
  Would require putting a capability token on the public internet; the browser
  sidecar already uses `*.internal`. Binding the API internally and denying the
  workspace uid access to that network is the tighter design.
- *Sibling "box" container + docker.sock* — rejected. docker.sock in the supervisor
  is a privilege escalation path; uid-firewall in one container is enough for v1.

## 3. Runtime inventory

**Decision**: The workspace image ships bash, coreutils, curl, python3, and node
(for `.js`). Missing interpreters (Ruby, Perl, TypeScript-without-a-loader, etc.)
fail with a clear "not available" outcome. The sidecar does not `apt-get install` /
`npm install -g` to satisfy a skill (FR-016). `npm install` / `pip install --user`
*inside `/workspace`* is allowed (user-space, ephemeral to this workspace).

**Rationale**: The open Agent Skills script extensions Ze already detects are
`.py`, `.sh`, `.js`, `.ts`, `.rb`, `.pl` (`ze_skills.parser._SCRIPT_REF_RE`,
`importer._SCRIPT_EXTENSIONS`). Shipping bash/python/node covers the common case.
`.ts` / `.rb` / `.pl` fail clearly rather than pulling extra runtimes into the
always-on image. curl is required for FR-026 (public fetch).

**Alternatives considered**:
- *Full desktop/dev image (build-essential, ruby, go, …)* — rejected. Larger attack
  surface and image; spec says missing tools fail clearly.
- *No curl; only Python `urllib`* — rejected. Skill scripts and ordinary shell
  work expect `curl`.

## 4. Time budget, output cap, storage ceiling

**Decision** (config under `workspace:` in `config/config.yaml`, overridable by env
where noted):

| Knob | Default | Why |
|---|---|---|
| `run_timeout_seconds` | `120` | In-turn wait (FR-024). Minutes, not hours, per spec Assumptions. |
| `output_preview_chars` | `8000` | Same order as `browser_max_text_chars`. Remainder lands as a workspace file. |
| `storage_ceiling_bytes` | `1073741824` (1 GiB) | Bounded disk for a personal assistant. |
| `run_lock_wait_seconds` | `30` | Second run waits this long for the mutex, then is refused (FR-019). |

A run that hits the time budget is stopped (SIGTERM then SIGKILL), status
`timed_out`, partial files remain inspectable.

**Rationale**: Spec left exact numbers to plan time. 120s is long enough for a
script + public fetch to finish inside the turn, short enough that a stuck process
does not hold the conversation graph indefinitely. 1 GiB is visible in the
workspace view (how full) without pretending at unlimited disk.

**Alternatives considered**: Matching the agent `timeout` (often 30s) — rejected;
workspace work is slower than an LLM tool call. Multi-hour budgets — rejected;
those belong to the sibling follow-through spec (FR-024).

## 5. WorkspaceMode vs CapabilityGate

**Decision**: `WorkspaceMode` is a **new persisted singleton** (`workspace_state`
row, like `persona_state`), not a new `Mode` on `CapabilityGate` and not a
`(agent, intent)` row in `capability_overrides`. Workspace tools consult
`WorkspaceGate` at call time. CapabilityGate continues to govern agent intents
unchanged.

Mapping (spec names are the user-visible labels; stored values are snake_case):

| WorkspaceMode | Stored value | File writes / edits Ze makes | Commands and skill scripts | Reset | User place/read/list/retrieve |
|---|---|---|---|---|---|
| Off | `off` | refuse | refuse | confirm | allowed |
| Plan | `plan` | dry-run only | dry-run only | confirm | allowed |
| Ask (default) | `ask` | confirm | confirm | confirm | allowed |
| Auto-edit | `auto_edit` | execute | confirm | confirm | allowed |
| Auto | `auto` | execute | execute | confirm | allowed |

Unattended (goals/workflows/jobs): commands and skill scripts run only when mode is
`auto`. Unattended file mutations require `auto_edit` or `auto`. Auto-edit is not
permission for unattended commands (FR-018). GoalExecutor's current
`GateDecision.EXECUTE` bypass stays for non-workspace tools; workspace tools still
ask `WorkspaceGate`. The gate is consulted only from `ze-automation` executors
(and conversation tools), with `WorkspaceGate` injected via
`config["configurable"]` / constructor — never imported from a `ZePlugin`
(`ze_personal` included).

**Rationale**: CapabilityGate is per `agent.intent` and has no Auto-edit. Mixing
"calendar confirm" with "workspace confirm" would make a global workspace mode
impossible (FR-029: one mode, persists across conversations). A singleton matches
"one workspace for this Ze". User-initiated place/read/list/retrieve skip the gate
because they are the user's own file ops, not Ze acting.

**Alternatives considered**:
- *Add `AUTO_EDIT` to `Mode` and reuse CapabilityGate* — rejected. Would collide
  with per-intent overrides, cannot express "files yes, commands no" without
  splitting every agent into two intents, and would confirm *entire turns* rather
  than workspace actions.
- *Session-only mode* — rejected by clarification: survives closing the chat app.

## 6. Confirmation: in-node `interrupt()` for workspace actions

**Decision**: Ask / Auto-edit-for-commands / reset use the existing
`pending_confirmations` table and `confirm_request` WS frame, triggered by
LangGraph `interrupt()` from inside the workspace tool (LangGraph 1.2.2 already
on `ze-api`). The graph's current `interrupt_before=["await_confirmation"]` path
stays for CapabilityGate. Workspace confirmation is a second, finer interrupt
inside `execute_tool` so the agentic loop can run a command, see output, then
write a file, confirming each mutating step.

The exception type is `ToolConfirmationRequired` in `ze_agents.errors` (alongside
`ToolBlockedError`). Workspace tools raise it; `BaseAgent.call_tool` /
`execute_tool` catch it. `ze_core` and `ze_agents` MUST NOT import `ze_workspace`.
`ze_workspace` already depends on `ze-agents`, so tools can raise the agents type
without a cycle.

On approve, `resume_turn` passes the choice through `Command(resume=...)` so
`interrupt()` returns it and the tool proceeds. On deny, the tool does not execute
and the agent is told so. On edit, the resumed value includes the edited command
or file contents; Ze runs the edited version (spec Edge Cases).

`WsConfirmFrame` gains an optional `edited_content` field; `ConfirmBar` shows an
edit control when the request is `editable: true`. Reset always uses this path.

**Rationale**: CapabilityGate pauses *before* the agent runs, so the agent cannot
use command output in the same turn. Claude Code-like Ask mode (clarification) is
per action. `interrupt()` is the LangGraph 1.2 primitive that checkpoints inside a
node; inventing a parallel WS auth channel is forbidden by the spec Assumptions.
A generic agents-layer error keeps constitution III: the engine never depends on
the workspace package.

**Alternatives considered**:
- *`WorkspaceConfirmInterrupt` in `ze_workspace.errors` caught by `ze_core`* —
  rejected at analyze time; would make `ze-core` depend on `ze-workspace`, or a
  cycle if `ze-agents` caught it (`ze-workspace` already depends on `ze-agents`).
- *One confirmation for the whole agent run* — rejected; Auto-edit vs Ask cannot
  be expressed, and the agent cannot iterate on output.
- *Synchronous HTTP wait from the tool* — rejected; the WS confirm machinery and
  reconnect replay already exist.
- *Cosmetic `render_confirm`* — rejected; that path does not resume the graph.

## 7. Platform tools, not per-agent lists

**Decision**: `BaseAgent.agentic_loop` merges a fixed `WORKSPACE_TOOLS` set into
the agent's available tools (opt-out flag for agents that must not have a
computer). Skills still **intersect** (never union) that merged list (FR-017 /
phase 114). Tools live in `ze_workspace.tools` and register via `@tool` like
`browser_extract`.

Tools:

| Tool | Access | Confirm under Ask? |
|---|---|---|
| `workspace_list` | READ | never |
| `workspace_read` | READ | never |
| `workspace_write` | WRITE | yes (no if Auto-edit/Auto) |
| `workspace_delete` | WRITE | yes (no if Auto-edit/Auto) |
| `workspace_run` | WRITE | yes (no if Auto) |
| `workspace_run_skill_script` | WRITE | yes (no if Auto); also requires executable approval |
| `ingest_workspace_file` | WRITE | yes — this is opt-in memory ingestion, not a place |

Off: conversation/agent tools remain listed but `WorkspaceGate` refuses with a
clear error (workspace unchanged by Ze). User-initiated REST list/read/place/
retrieve still work. Sidecar-down is `WorkspaceUnavailableError` (FR-010), not
Off. Plan: mutating tools return a dry-run preview and do not call the sidecar's
execute endpoints.

`ingest_workspace_file` MUST receive `IngestionPipeline` via tool `deps` /
container `dep_map` (same pattern as `BrowserClient`). `ze-workspace` does **not**
depend on `ze-ingestion`.

**Rationale**: Editing every `@agent.tools` list is invasive and will drift.
Platform merge at the single `agentic_loop` site matches how `skill_tool_names`
already narrows. The ingest bytes path already exists on `IngestionPipeline`;
injection avoids a new `ze-workspace → ze-ingestion` package edge.

**Alternatives considered**: Graph node that executes workspace outside the agent
— rejected; the agent needs to see output to plan the next step. Per-agent `tools`
edits — rejected as busywork. `ze-workspace` depending on `ze-ingestion` — rejected
at analyze time; injection matches `BrowserClient` and keeps the package graph
unchanged.

## 8. Skill scripts: store them, separately approve them, never auto-run

**Decision**: Phase 114 detected scripts then discarded bytes (`importer.py`
skips `_SCRIPT_EXTENSIONS`; only `has_unsupported_scripts` remains). This phase:

- Renames the stored flag to `has_scripts` (migration `zsk002`) and **persists**
  script files in a new `skill_scripts` table (filename + bytes/text).
- Adds `executable_approved: bool` (default `false`) and
  `executable_approved_at`. Instructions-only `POST .../approve` does not set it
  (FR-012). New `POST /api/v0/skills/{id}/approve-executables` is the separate
  gate (FR-011). Recheck/content change that touches scripts reverts executable
  approval (same pending-review spirit as instructions).
- Review UI finally surfaces script presence (the API field exists; 
  `SkillManagementList` currently ignores it) and the executable-approval action,
  distinct from instructions approval (FR-013).
- Matched skills do not auto-exec scripts. The agent (or unattended Auto work)
  calls `workspace_run_skill_script`. Each run materializes the stored script
  from Postgres into a temp path under `/workspace` and executes it; the DB copy
  is the source of truth.
- `SkillUsageTrace` gains `script_ran: bool` (and optional `script_path`) so the
  turn annotation can say a script ran (FR-007). Disabled / pending skills never
  run scripts (FR-011/US2.5). Off and Plan do not run scripts even if
  executable-approved (FR-030).

**Rationale**: Without stored bytes, Ze would re-fetch origin URLs at run time
(fragile, and bundled skills have no origin). Silent promotion of 114 approvals
is explicitly forbidden. Auto-running every script on match would surprise the
user and ignore the agent's tool loop.

**Alternatives considered**: Re-fetch from `origin_url` at run time — rejected;
bundled skills have no URL, and a changed source must not execute until
re-approved. Reuse `skill_reference_files` with a kind column — weaker than a
dedicated table because reference files are injected into prompts (text) while
scripts are bytes to execute and must never land in the system prompt by
accident.

## 9. Placing files is not ingestion; chat attachments via REST then reference

**Decision**: Chat attachments do not exist today (`WsSendMessageFrame` is text
only; spec 042 deferred them). Place paths:

1. Workspace view: `POST /api/v0/workspace/files` multipart → sidecar. Never
   calls `IngestionPipeline` (FR-027).
2. Chat composer: same REST upload, then the send frame's `context` includes
   `workspace_placed: [{path, size}]`. Bytes never go over WebSocket.
3. Duplicate names: do not overwrite; suffix `name-1.ext` and tell the user both
   names (spec Edge Cases).
4. Over ceiling: refuse, workspace unchanged (FR-020).

Opt-in ingest (FR-028): `ingest_workspace_file` tool and optional
`POST /api/v0/workspace/files/{path}/ingest` both read bytes from the sidecar and
call `IngestionPipeline.ingest(IngestionRequest(file_bytes=..., mime_type=...,
label=path))`. Original bytes stay in the workspace; ingestion still stores only
processed text in `ingested_content` (existing behavior).

**Rationale**: Reuse the proven ingest bytes path (`test_ingest_file_bytes_skips_fetch`)
rather than a second pipeline. Keep WS text-only; multipart already exists on
`POST /api/v0/ingest` and data-import.

**Alternatives considered**: Base64 attachments on the WS message frame — rejected;
large/binary files and the existing ingest REST pattern make multipart the fit.
Auto-ingest on place — rejected by FR-021 / FR-027.

## 10. Run records vs turn annotation

**Decision**: Two layers, not one.

- **Durable `workspace_runs` table** (FR-008, FR-025): stable id, timestamps,
  command/script, origin (`conversation` | `unattended`), `thread_id` /
  `message_id` nullable, `skill_id` nullable, status, output preview, files
  touched. This is what a later follow-through spec attaches to. This spec does
  not detach, auto-follow-up, or push (FR-024).
- **`MessageTrace.workspace`**: a `WorkspaceUsageTrace` (runs + files +
  `script_ran`) on the existing `messages.trace` JSONB and `trace_update` frame,
  plus a **visible chip on the message bubble** (SC-002: users can tell the
  workspace was used without opening Why?).

Listing recent activity for User Story 4 uses `GET /api/v0/workspace/runs`.

**Rationale**: Same split as skills: trace for per-message explainability, a real
table when the entity must outlive the message and be addressable by id. Runs
must outlive the turn for follow-through.

**Alternatives considered**: Trace-only, no table — rejected; FR-025 requires a
stable identity a later spec can attach to, independent of message JSONB shape.

## 11. Concurrency, reset, availability

**Decision**: One run at a time, mutex in the sidecar. A second `POST /run` waits
up to `run_lock_wait_seconds` then returns busy; Ze tells the user the workspace
is occupied (FR-019). Reset: if a run is active, cancel it (SIGTERM/KILL), then
wipe `/workspace`; never reset under a live writer without saying so. Sidecar
down / timeout on the control API: tools raise `WorkspaceUnavailableError`; the
turn warns and does not fabricate success (FR-010); other Ze capabilities
continue. Health: `GET /health` like the browser sidecar; compose `depends_on`
healthy.

**Rationale**: Spec forbids silent interleaving. A global mutex is the honest
single-user answer; a later spec can add queues.

## 12. UI placement

**Decision**: Dedicated System nav page `/workspace` (mirror `/skills`), not
Brain and not Settings. Entities `entities/workspace` + widget
`widgets/workspace-management` + thin `pages/workspace`. Mode switcher lives on
that page and is also shown in chat chrome when a workspace confirmation is
pending (FR-029: mode visible when Ze is about to do workspace work). Skill
executable approval stays on `/skills`. File chips on `MessageBubble`;
`SkillsSection`-style `WorkspaceSection` in `widgets/trace-panel`.

**Rationale**: Skills established core System pages for operational surfaces.
Brain is memory; Settings is prefs.

## 13. Migration ownership

**Decision**: New chain prefix `zws` owned by `core/ze-workspace/` (`zws001`
workspace_state + workspace_runs). Skill-script persistence and executable
approval are `zsk002` on the existing `ze-skills` chain (`depends_on` zsk001).
Register `_ZE_WORKSPACE_VERSIONS` in `ze_api/migrate.py` next to
`_ZE_SKILLS_VERSIONS`.

**Rationale**: The package that owns the store owns the chain. Script bytes are
skill domain, not workspace domain.
