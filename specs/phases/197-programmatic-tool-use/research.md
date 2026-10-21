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

- **Finding**: a script has no network, so it cannot send data out itself. It can only call the agent's read tools, and scripts are a capability of every agent (user answer), and at least one READ tool reaches a caller-chosen URL (`browser_extract`, ze-browser). Decision (Gauge R-1, Maestro): such tools carry `egress` and are excluded from the stub, so scripts have no network directly or through a tool; a registry sweep flags any READ tool with a URL-like parameter that lacks `egress` or a stated exemption. Server tools (`openrouter:*`) are never in the stub.

## R8 — Eval

- **Decision**: `max_llm_calls` per scenario, checked against `llm_calls` from `llm_cost_log` (already computed in `ze_eval/metrics.py`).
- **Rationale**: the round-trip saving is the claim; the runner already measures it and asserts nothing.

## Decision record (was the ADR)

Status: accepted 2026-10-18 (phase 197). Scope: ze-agents, ze-workspace, sidecar/workspace, ze-memory.

# ADR: Programmatic tool use runs in a no-network sandbox beside the sidecar

> **Status:** Accepted
> **Date:** 2026-10-18 (Phase 197)
> **Scope:** `ze-agents` (contract, loop), `ze-workspace` (runner, learning), `sidecar/workspace` (sandbox), `ze-memory` (ledger, procedures)
> **Spec:** `specs/phases/197-programmatic-tool-use/`

---

### Context and Problem Statement

A multi-step read ("what did I spend by merchant this month; top five") costs one model round trip per tool call, and every raw result enters the model's context. A short script can call the reads, join, count and return five lines. The question is where that script runs, what it may touch, and how it relates to the gates that govern every tool call today.

### Decision

Every agent whose visible tools include at least one **data read tool** gets one harness tool, `run_tool_script`, handled in the agentic loop like `delegate_to_agent`. It is not a registry tool and needs no opt-in.

- **Ze initiates every connection.** Ze opens one WebSocket (`WS /scripts`) to the workspace sidecar per script. The sandbox writes framed requests to a dedicated pipe; the sidecar relays them to Ze; Ze answers on the same channel. The sandbox never connects to Ze and holds no Ze credential.
- **No network.** The script runs as the `zescript` system user in a throwaway directory. The sidecar adds a `reject` rule for all output from that uid and verifies it by listing the chain (an exit code is not proof). `/workspace` is mode 0750 and unreadable to `zescript`. At the start of each script, `_ze_main.py` probes both (list `/workspace`, connect to `1.1.1.1:53`); a breach ends the script `unavailable` and sets `scripts_isolated` false. `scripts_isolated` false means scripts are unavailable, not unsafe.
- **No network through a tool either.** A READ tool that reaches a caller-chosen URL or host declares `egress=True` (`browser_extract` today) and is never in the stub. A registry sweep fails when a READ tool has a URL-like parameter without `egress` or a stated exemption.
- **Resource limits** in the child's preexec: address space, process count, file size, CPU, open files; scratch size is polled and capped; stdout goes to `DEVNULL`; every process of the `zescript` uid is killed at the end, not only the process group.
- **The stub holds data read tools only**: the visible tools after skill and procedure narrowing, minus server tools, `delegate_to_agent`, `invoke_procedure`, the script tool, `workspace_*`, every WRITE tool, every tool that `produces_ui`, and every `egress` tool. A forged request for anything else is refused inside Ze.
- **Inner calls are ordinary calls.** The dispatcher calls `call_tool` as the agent, so every gate, hook and rule applies. The script's own `max_inner_calls` bounds them, so `ToolCallCapHook` does not also count them (`in_script_call`).
- **Writes are proposed, not called.** The script ends with `finish(result, writes=[propose(tool, **args)])`. Ze runs each proposal after the script as an ordinary tool call in the same loop iteration, so parking, confirmation (phase 181), undo payloads and Retry (phase 180) work unchanged. A write called from inside the script is refused `writes_must_be_proposed`.
- **Spend** is bounded per script: `CostTracker.record` charges an estimate to the active `ScriptBudget`, set only while the dispatcher runs an inner call. One call can overshoot; the check runs before the next.
- **Learning goes through the ledger.** Every finished script is one `action_records` row keyed by its **tool signature** (the agent plus the ordered distinct tools it called). Three consecutive successes for a signature submit one `tool_script` procedure candidate that keeps the latest source. The user reviews every candidate in Mind › Procedures before it can run again, and `run_tool_script(procedure_id=...)` builds the stub from the agent's tools at that moment.

### Alternatives refused

- **A hosted sandbox** (a third-party code-execution service): it needs a credential and a route from the sandbox to Ze or to the data, and puts personal reads on a vendor. The workspace sidecar already exists, is Ze-owned and has no inbound path to Ze.
- **Calling write tools from the script**: it would move the confirmation decision into model-written code.
- **A per-agent opt-in list**: scripts are a harness capability; the data-read set decides.
- **Keying learning on the script text**: two runs of the same job never match; the tool signature is loose on purpose and review is the safeguard.

### Consequences

- Local dev needs `cap_add: [NET_ADMIN]` on the workspace service; without it `scripts_isolated` is false and the tool reports `sandbox_unavailable`.
- Every agent with a data read tool carries the script schema and `SCRIPT_GUIDANCE` in each request. The routing and affected-agent evals must be re-run with the user's approval.
- **AF_UNIX:** the sidecar exposes no unix socket to the `zescript` uid. A future socket the sidecar opens must be checked against this.
- **Finance is pinned to one provider.** A script's source and value go only to that same model and the trace, so nothing leaves the provider.
- Unattended goal and workflow runs get no runner, so no scripts.

