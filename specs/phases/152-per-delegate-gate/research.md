# Research: Per-Delegate Capability and Confirmation

**Feature**: `152-per-delegate-gate`  
**Date**: 2026-09-16

## 1. Delete wholesale inherit

**Decision:** Worker `gate_decision` is the result of `CapabilityGate.evaluate(specialist, intent, session_overrides)` composed with spend budget. Parent companion EXECUTE is not copied.

**Rejected:** Copy parent then AND with specialist (still holds lookups if parent were ever CONFIRM). Keep inherit “until 153”.

## 2. Injected protocol, not ze_core import

**Decision:** `AgentContext` (or `extensions`) carries an engine-supplied callable `evaluate_delegate(agent, intent) -> GateDecision` (sync is enough; budget check may be async and done in the wrapper). `execute_tool` / `_execute_single` sets it from `config["configurable"]["capability_gate"]` and `budget_checker`.

**Rejected:** `from ze_core.capability.gate import CapabilityGate` inside `ze_agents.delegate`.

## 3. Optional `intent` on the tool

**Decision:** Add optional `intent` to `DELEGATE_TOOL_SCHEMA` without removing 151 fields. If omitted, call `CapabilityGate.evaluate` with the same fallback it uses for unknown intent (`default_mode`).

**Rejected:** A second Haiku classifier inside `run_delegate`. Required `intent` (would break speech-act one-shots).

## 4. Pause via existing confirmation + interrupt

**Decision:** AWAIT_CONFIRMATION uses the same user-facing confirmation path as graph (`pending_confirmations.request_id`, NativeAppInterface). Reuse `tool_interrupt_fn` or graph interrupt with kind `delegate` so `agentic_loop` pauses inside `execute_tool` and LangGraph checkpoints. On approve, that invocation re-enters `run_delegate` with EXECUTE for the specialist (budget already acknowledged).

**Rejected:** A new confirmation table. Keying by `thread_id` only. Running the worker in EXECUTE then asking after the send.

## 5. Graph parallel out of scope

**Decision:** `capability_check` strictest-wins across fan-out subtasks stays. Tests that document it must still pass.

**Rejected:** Per-subtask parallel gates in this phase (roadmap: after 154).

## 6. Do not retune Mode tables

**Decision:** Messenger `create` remaining DRAFT_ONLY is not a 152 bug. The product rule is per-invocation evaluation. If send later becomes CONFIRM, this path already pauses.

**Rejected:** Changing `send_email` to CONFIRM as a hidden extra.
