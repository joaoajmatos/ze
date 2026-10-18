# Research: Programmatic Tool Use (197)

## R1 — Channel between the script and Ze

- **Decision**: Ze opens a WebSocket to the sidecar per script (`WS /scripts`, bearer token). Inside the sandbox the script talks to the sidecar over two inherited pipes (requests out, replies in); the sidecar relays.
- **Rationale**: the sandbox has no way to reach Ze today (no socket, no URL, no token; private networks dropped) and that must stay. A run's input is fixed at start (`stdin_b64`) and its events are one-way, so the existing run API cannot carry replies. A WebSocket Ze opens keeps Ze the initiator, gives one connection per script (the script slot), and closing it kills the script. Dedicated pipes keep ordinary `print` output apart from requests.
- **Alternatives**: a callback URL plus a scoped token in the sandbox (breaks isolation, rejected); a new `POST /runs/{id}/input` plus the existing event stream (two channels to keep in step, a script indistinguishable from a run, shares the run slot); a hosted sandbox (third party sees the user's data, rejected by the brief).

## R2 — Script sandbox

- **Decision**: a separate system user `zescript`; all its egress dropped (nft `meta skuid`, iptables `--uid-owner` fallback); scratch directory `/tmp/ze-scripts/<id>` (0700) deleted after the run; `/workspace` set to 0750 so `zescript` cannot read it; `python3 -I` (isolated mode) so the scratch directory is the only import path beyond the stdlib; env limited to `PATH`, `HOME`, `LANG` and the two fd numbers.
- **Rationale**: clarified (no ask, no network). With no network, no files and no credential, the only effects a script can have are the gated tool calls Ze runs for it. Isolated mode stops a planted module in the scratch directory from shadowing the stdlib (the stub is written there by the sidecar, not by the script).
- **Check**: the sidecar reports `scripts_isolated` in `/stat`; the runner refuses to run scripts when the rule could not be applied, so a misconfigured image fails closed.

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

- **Decision**: one action record per finished script (`source_record_type = "tool_script"`, `source_record_id = sha256(normalized source)`); three consecutive successes by one agent submit one candidate through `ProcedureAdmissionService.submit_procedure_candidate`.
- **Rationale**: the action ledger is the evidence store the procedure lifecycle already cites (`candidate_from_action_pattern` requires action records); no new table. `procedure_candidates.source_kind` is unconstrained TEXT (zm022), so `tool_script` needs no migration. Source kind lives only on candidates, so discovery reads it through `procedure_versions.admission_id → procedure_admissions.candidate_id`.

## R7 — Data leaving through tools (lesson from 196 S-1)

- **Finding**: a script has no network, so it cannot send data out itself. It can only call the agent's read tools, and none of the four opted-in agents' read tools sends data to a third party (they read Ze's own stores or Google read APIs with the user's own account). Server tools (`openrouter:*`) are never in the stub. No extra rule needed; the ADR states the property so a future read tool that calls out is reviewed against it.

## R8 — Eval

- **Decision**: `max_llm_calls` per scenario, checked against `llm_calls` from `llm_cost_log` (already computed in `ze_eval/metrics.py`).
- **Rationale**: the round-trip saving is the claim; the runner already measures it and asserts nothing.
