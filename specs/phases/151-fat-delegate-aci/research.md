# Research: Fat Delegate ACI

**Feature**: `151-fat-delegate-aci`  
**Date**: 2026-09-16

## 1. Hard-cut `task` / `context` → `objective` + optional fat fields

**Decision:** Required `agent_name` + `objective`. Optional `prior_outputs`, `inputs`, `output_shape`, `stop_condition`. Delete `task` and `context`. Update all in-tree callers and tests in this phase.

**Rationale:** Principle VIII forbids a dual ACI. Speech-act one-shots only need `objective`. Fat fields exist so 153 can pass prior specialist output without a shared blackboard.

**Rejected:** Keep `task` as an alias of `objective`. Keep `context` beside `inputs`.

## 2. Caller identity is `BaseAgent.name`, not `ctx.intent`

**Decision:** `agentic_loop` passes `self.name` into `run_delegate`. Allow only `companion`. Refuse target `companion`.

**Rationale:** Companion’s intent is `reason`. Tests today set `intent="research"` on the parent context; that would falsely allow research if we keyed on intent.

**Rejected:** Infer caller from `ctx.intent`. Add a new public `AgentContext` field unless tests prove the extra arg is insufficient.

## 3. Depth cap 1

**Decision:** `_DELEGATE_MAX_DEPTH = 1` meaning a parent at depth 0 may call once; the worker is depth 1 and cannot re-delegate.

**Rationale:** Roadmap pin 2. Today’s cap is 2 so research could nest.

**Rejected:** Cap 0 (would break speech-act). Cap 2 with a companion-only allow-list (still a swarm).

## 4. Prompt assembly (isolated worker)

**Decision:** Build a single user message from labeled sections that are present. Omit empty optional fields. Fresh `messages=[{role: user, content: assembled}]`. Do not copy parent `messages`.

**Rationale:** Roadmap pin 6. 146 already uses a fresh prompt from `task`/`context`.

**Rejected:** Append specialist turns onto session history. Shared chat blackboard.

## 5. Research loses the tool

**Decision:** `tools = ["openrouter:web_search"]` only. Replace the calendar-delegate instruction with “say you need the calendar agent / state the limitation; do not guess the calendar.”

**Rationale:** Until 153, mixed turns are not companion-primary. Guessing calendar is worse than a visible limitation.

**Rejected:** Leave research’s tool listed but refuse in `run_delegate` only (still a dual door in the schema the model sees).

## 6. What this phase does not touch

**Decision:** No graph edits. Companion `description` byte-for-byte unchanged. `plan_sequential` / `dynamic_plan_steps` stay. Worker `gate_decision=ctx.gate_decision`.

**Rejected:** Bundling 152 or 153. Changing companion embeddings so mixed turns route early.

## 7. 146 honesty

**Decision:** Keep `result = {response, tool_calls}`. Companion honesty still walks nested `tool_calls`. Update 146 contract docs only if they still say `task` (same-phase string update, not a behavior change).

**Rejected:** String-only result. Flattening nested tools into session `messages`.
