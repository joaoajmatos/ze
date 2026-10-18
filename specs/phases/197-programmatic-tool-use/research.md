# Research: Programmatic Tool Use (197)

## R1 — Channel between the script and Ze

- **Decision**: Ze opens a WebSocket to the sidecar per script (`WS /scripts`, bearer token). Inside the sandbox the script talks to the sidecar over two inherited pipes (requests out, replies in); the sidecar relays.
- **Rationale**: the sandbox has no way to reach Ze today (no socket, no URL, no token; private networks dropped) and that must stay. A run's input is fixed at start (`stdin_b64`) and its events are one-way, so the existing run API cannot carry replies. A WebSocket Ze opens keeps Ze the initiator, gives one connection per script (the script slot), and closing it kills the script. Dedicated pipes keep ordinary `print` output apart from requests.
- **Alternatives**: a callback URL plus a scoped token in the sandbox (breaks isolation, rejected); a new `POST /runs/{id}/input` plus the existing event stream (two channels to keep in step, a script indistinguishable from a run, shares the run slot); a hosted sandbox (third party sees the user's data, rejected by the brief).

## R2 — Script sandbox

- **Decision** (revised after Gauge M-6/M-7): a separate system user `zescript`; all its egress rejected (nft `meta skuid`, iptables `--uid-owner` fallback), the rule verified by listing the chain; `/workspace` set to 0750 at runtime in the lifespan (the volume mount masks the image's mode); a per-script probe run as `zescript` (cannot list `/workspace`, cannot connect out) before the script; rlimits (256 MiB address space, 32 processes, 16 MiB per file, CPU = wall + 1 s, 64 files) and a 32 MiB scratch cap; stdout to DEVNULL, stderr into a 64 KB ring; every process of the uid killed at the end; scratch `/tmp/ze-scripts/<id>` (0700) deleted; `python3 -I` for environment hygiene, with `_ze_main.py` putting the scratch dir on `sys.path`; env limited to `PATH`, `HOME`, `LANG` and the two fd numbers; `/scripts` refuses when no token is configured.
- **Rationale**: clarified (no ask, no network). The uid is the boundary: with no network, no `/workspace`, no credential and bounded resources, the only effects a script can have are the gated tool calls Ze runs for it. The sidecar VM is small (1 GB, shared with the user's workspace), so a runaway allocation or fork must hit a limit before the OOM killer picks uvicorn.
- **Check**: `/stat` reports `scripts_isolated` (rule verified and mode set; the per-script probe can only lower it); the runner refuses to run scripts when it is false, so a misconfigured image or a dev container without `NET_ADMIN` fails closed. AF_UNIX sockets are outside the inet rule; the sidecar exposes none to that uid.

## R3 — Where the dispatch lives

- **Decision**: in ze-agents (`script_step.py`), as a harness branch of `agentic_loop`, with the runner behind a Protocol.
- **Rationale**: inner calls must go through `BaseAgent.call_tool` as the calling agent; a registry `@tool` only receives `ctx`, not the agent, and ze-agents may not import ze-workspace. `delegate_to_agent` already sets the pattern for a harness tool handled in the loop.

## R4 — Writes

- **Decision**: proposed writes in the script's `finish(...)`, run after the script as synthetic tool calls in the same loop iteration (clarified).
- **Rationale**: the 181 park/resume path works per loop iteration and checkpoints `ParkedLoop`; a live script process cannot survive a graph interrupt or a restart. Running proposed writes through the iteration's pending list reuses the gate, the round cap, the constraint veto, approvals and undo payloads with no new path.

## R5 — Spend attribution

- **Decision**: a ContextVar budget in ze-agents, set only while the dispatcher runs an inner call; `CostTracker.record` charges each model call's estimate (existing static price table) to it.
- **Rationale**: most read tools make no model call; those that do (composers, judges) are the spend risk. The estimate is the same one 187b's usage readout and the budget pause use.

## R6 — Learning

- **Decision** (revised after Gauge M-1, Me-4): one action record per run (`source_record_id` = the script id, so the recorder's idempotency key `producer:type:id:action:lifecycle` is unique per run; the ledger's `ON CONFLICT DO NOTHING` would otherwise keep only the first run of a key); the learning key goes in `ActionContext.script_key` (JSONB, no migration) and is the tool signature (agent + ordered distinct tools called; recommended answer, user decision pending); three consecutive successes for a key submit one candidate through `ProcedureAdmissionService.submit_procedure_candidate`, storing the latest source. Identical source rarely repeats because the model writes each script fresh.
- **Rationale**: the action ledger is the evidence store the procedure lifecycle already cites (`candidate_from_action_pattern` requires action records); no new table. `procedure_candidates.source_kind` is unconstrained TEXT (zm022), so `tool_script` needs no migration. Source kind lives only on candidates, so discovery reads it through `procedure_versions.admission_id → procedure_admissions.candidate_id`.

## R7 — Data leaving through tools (lesson from 196 S-1)

- **Finding**: a script has no network, so it cannot send data out itself. It can only call the agent's read tools, and scripts are a capability of every agent (user answer), so a data read tool that reaches the network (for example a browser extract tool) is reachable from a script exactly as from a direct call: same gates, every inner call on the trace. Scripts grant no tool the agent lacks and add no network of their own. Server tools (`openrouter:*`) are never in the stub. The ADR states this so a new outbound read tool is reviewed knowing scripts can loop over it within the script caps.

## R8 — Eval

- **Decision**: `max_llm_calls` per scenario, checked against `llm_calls` from `llm_cost_log` (already computed in `ze_eval/metrics.py`).
- **Rationale**: the round-trip saving is the claim; the runner already measures it and asserts nothing.
