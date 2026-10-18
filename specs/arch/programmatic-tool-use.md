# ADR: Programmatic tool use runs in a no-network sandbox beside the sidecar

> **Status:** Accepted
> **Date:** 2026-10-18 (Phase 197)
> **Scope:** `ze-agents` (contract, loop), `ze-workspace` (runner, learning), `sidecar/workspace` (sandbox), `ze-memory` (ledger, procedures)
> **Spec:** `specs/phases/197-programmatic-tool-use/`

---

## Context and Problem Statement

A multi-step read ("what did I spend by merchant this month; top five") costs one model round trip per tool call, and every raw result enters the model's context. A short script can call the reads, join, count and return five lines. The question is where that script runs, what it may touch, and how it relates to the gates that govern every tool call today.

## Decision

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

## Alternatives refused

- **A hosted sandbox** (a third-party code-execution service): it needs a credential and a route from the sandbox to Ze or to the data, and puts personal reads on a vendor. The workspace sidecar already exists, is Ze-owned and has no inbound path to Ze.
- **Calling write tools from the script**: it would move the confirmation decision into model-written code.
- **A per-agent opt-in list**: scripts are a harness capability; the data-read set decides.
- **Keying learning on the script text**: two runs of the same job never match; the tool signature is loose on purpose and review is the safeguard.

## Consequences

- Local dev needs `cap_add: [NET_ADMIN]` on the workspace service; without it `scripts_isolated` is false and the tool reports `sandbox_unavailable`.
- Every agent with a data read tool carries the script schema and `SCRIPT_GUIDANCE` in each request. The routing and affected-agent evals must be re-run with the user's approval.
- **AF_UNIX:** the sidecar exposes no unix socket to the `zescript` uid. A future socket the sidecar opens must be checked against this.
- **Finance is pinned to one provider.** A script's source and value go only to that same model and the trace, so nothing leaves the provider.
- Unattended goal and workflow runs get no runner, so no scripts.
