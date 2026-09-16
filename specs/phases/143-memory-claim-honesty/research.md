# Research: Earned Memory Confirmations and Precise Forget

**Feature**: `143-memory-claim-honesty`  
**Date**: 2026-09-16

## 1. Where the turn actually lies

**Decision:** Enforce confirmation in companion on the path that builds `AgentResult.response`, and buffer `token_sink` so streamed tokens cannot outrun the gate. Rewrite `CompanionAgent.stream` so it is not a tool-free completion. Do not add another prompt paragraph. Do not put “I’ll remember” dialect into `ze-agents` (Principle III).

**Rationale:** Phase 140 already told the model to confirm only when `ok` is true. `agentic_loop` still returns the first text completion as soon as the model emits text, including when no tools ran. WebSocket turns set `token_sink` and call `run()`, which uses `agentic_loop`; tokens of that final text are flushed **as they are generated**, before `CompanionAgent.run` can rewrite `response`. A post-loop strip of `AgentResult.response` would leave the live token frames lying. `CompanionAgent.stream` still calls `_client.stream` with no tools; `execute_tool` uses that method only if `token_queue` is set (no in-tree producer today), but it is a second ungated door. Principle VIII: delete the bypass rather than document it.

**Alternatives considered:**
- Prompt-only fix — already shipped in 140/141; this spec exists because it failed.
- Gate inside `BaseAgent.agentic_loop` — would teach core a companion speech dialect and couple every agent to biography confirmations.
- Gate only `AgentResult.response` after the loop — fails FR-005 for `token_sink` and `stream`.
- Extra LLM rewrite of the reply — another chance to lie; slower; not a hard gate.

## 2. What counts as earned `ok`

**Decision:** Parse each `ToolCall` whose `tool_name` is `remember_fact` or `forget_fact`. Earned iff the payload is a mapping with `ok` is `True` (JSON object if `result` is a string). `ToolCall.success` alone is not enough: the Python tools return `{ok: False, error: ...}` without raising.

**Rationale:** `remember_fact` / `forget_fact` already use that payload. `call_tool` marks `success` from exceptions, not from `ok`.

**Alternatives considered:**
- Key off `success` — would treat seam rejection as earned if the function returned.
- Key off “tool was invoked” — invocation with `ok` false is the failure path FR-003 must catch.

## 3. How to detect and correct unearned claims

**Decision:** Deterministic sentence filter in `ze_personal.agents.companion` (new module). Conservative English/Portuguese-adjacent confirmation patterns for remembered and forgotten. If the turn did not earn remember, strip claiming sentences; if nothing usable remains, replace with `I could not store that.` Same for forget → `I could not forget that.` Acknowledgements without a memory-success claim (`got it`, `okay`) stay. If remember is earned and the text also claims an extra unearned memory, strip the extra claiming sentences when they are separable; if mixed in one sentence, drop that sentence (fail closed). Do not call an LLM to judge the reply.

**Rationale:** The product need is “the user is not lied to,” not perfect literary editing. A regex/sentence gate is testable without OpenRouter. Fail-closed mixed sentences match the spec assumption.

**Alternatives considered:**
- Block the entire reply whenever any claim appears without a tool — too coarse; would wipe useful non-claim text.
- LLM judge — cost, latency, and it can agree with the lie.
- Allow “I’ll remember” when post-turn extraction will run — extraction happens after the reply and is synthesized; it is not in-turn `remember_fact`.

## 4. Forget matching (precision over recall)

**Decision:** Replace the current matcher in `_retract_facts_matching` (scan up to 200 live facts; substring `in` on predicate/value; else cosine ≥ 0.75 top 5) with a closed ladder. No second public API; change the private method in place.

1. Normalize query and fields: strip, casefold, collapse whitespace.
2. **Exact identity:** retract every live row whose predicate or value equals the query. Multiple exact duplicates of the same identity may all retract (true dupes, not near-misses).
3. **User named the stored value:** retract rows whose full value (minimum 8 characters or 2+ tokens) appears as a contiguous phrase in the query. This is “forget that I prefer dark mode” when the stored value is `dark mode` or `prefer dark mode`, not a 3-character token sitting inside many values.
4. **No query-as-substring of value** unless the query itself has at least 3 tokens **and** appears as a contiguous phrase in value (avoids `mode` / `I` wiping the table). Predicate substring-contains is removed.
5. **Embedding fallback (optional, only if still unmatched and embedder present):** at most **one** row, cosine ≥ 0.88, and the runner-up below 0.80 (or no runner-up). Otherwise return `[]`. Never top-5.

Empty query still returns `[]` without writes. `forget_fact` still maps empty match to `{ok: False, error: "no matching fact"}`.

**Rationale:** Current step 2 retracts every substring hit in one `UPDATE`. Cosine 0.75 top 5 is the same honesty class. Phrase-in-query preserves conversational forget without ILIKE-everything. Unique high-bar embedding covers paraphrase without batch over-forget.

**Alternatives considered:**
- Exact match only — too deaf for “forget the dark-mode preference” vs value `dark mode`.
- NLI entailment for every candidate — accurate but slower and not required for precision-first; can be a later spec.
- Keep 0.75 / top 5 behind a flag — dual door; forbidden.
- SQL `ILIKE` — the live code is already Python `in`, not SQL ILIKE; do not add ILIKE.

## 5. Streaming and `CompanionAgent.stream`

**Decision:** In `CompanionAgent.run`, wrap `ctx.token_sink` so final-answer tokens are buffered until `enforce_memory_confirmations` runs, then flush the gated text to the real sink (one or more chunks). Rewrite `stream()` to await the same `run()` path and yield the gated `response` (single chunk is acceptable). Do not keep raw `_client.stream` for companion.

**Rationale:** Closes FR-005. Companion honesty beats token-by-token latency on the last model message. Tool-call iterations already do not stream user text.

**Alternatives considered:**
- Leave `stream()` as-is because `token_queue` has no producer — latent dual door.
- Change `ze_core` `execute_tool` — plugin work must not import `ze_core`; engine change is unnecessary if companion `stream` is honest.

## 6. Eval criteria hard-cut

**Decision:** Update `eval/scenarios/memory.yaml` (and any companion test that asserts unearned “I’ll remember”) so implicit preference turns may acknowledge without claiming stored memory unless `remember_fact` returned `ok`. Delete the dual standard in `memory_store_explicit_fact` that currently praises “Got it, I'll remember that.”

**Rationale:** FR-009. Fixtures that reward the lie would make SC-006 fail.

**Alternatives considered:** Keep old criteria as “style” — dual standard.

## 7. Scope risks decided here (not NEEDS CLARIFICATION)

| Risk | Decision |
|---|---|
| Portuguese / other confirmation phrasing | Gate English patterns required in tests; add obvious Portuguese equivalents (`vou lembrar`, `já esqueci`) in the same module if cheap, but do not build a multilingual NLP stack. |
| Specialist agents saying “I’ll remember” | Out of scope; they do not have the tools. 149 on the honesty roadmap. |
| Extraction still writing after a stripped “I’ll remember” | Allowed; 140 already says extraction is not the explicit door. Dual-write race is roadmap 148, not this phase. |
| Raising cosine to 0.88 without a uniqueness gap | Rejected; uniqueness gap is what stops top-N over-forget. |
| Migrating `memory_facts` or adding an index | Not required; 200-row scan stays. |

## 8. Code facts (grounding)

- `remember_fact` / `forget_fact`: `plugins/ze-personal/ze_personal/agents/companion/tools.py` — already return `{ok: True\|False, ...}`.
- Companion `run` uses `agentic_loop`; `stream` does not.
- `agentic_loop` returns on first `text` (`core/contracts/ze-agents/ze_agents/base_agent.py`).
- `_retract_facts_matching`: `core/cognition/ze-memory/ze_memory/retriever.py` — LIMIT 200, substring, then cosine 0.75 top 5.
- WS: `apps/ze-api/ze_api/api/websocket/turns.py` sets `token_sink` only.
- Eval field `memory_proposals_count` remains always 0 — not this phase (roadmap 150).
