# Phase 0 Research: Session Context Continuity

## R1. Where compaction and the resume recap sit in the graph — CORRECTED after reading the actual node code

**Superseded finding**: the spec's premise ("currently unbounded AgentState.messages
growth") does not match the code. `write_memory`
(`core/ze-core/ze_core/orchestration/nodes/memory.py:111-116`) already replaces
`state["messages"]` every turn with `updated[-SESSION_HISTORY_LIMIT:]`
(`SESSION_HISTORY_LIMIT = 10`, defined in `nodes/context.py:16`) — and `AgentState.messages`
carries no LangGraph reducer annotation (plain `list[dict]`, `state.py:45`), so this is a
real replace, not an accumulate-then-ignore. The actual current failure mode is a silent
5-turn memory cliff (blind hard-trim, no summary), not a hard context-capacity error.
Separately, `fetch_context` (`nodes/context.py:62-68`) already runs a gap check —
`(now - last_active) > inactivity_minutes * 60` read from the same `session_inactivity_minutes`
config key `SessionSummariser` uses — and on a long gap **blanks history to `[]`**, the
literal "blank slate" behavior US2 complains about.

**Decision** (confirmed with the user after surfacing this mismatch): target the real
mechanisms instead of adding parallel new ones.

1. **Compaction** replaces the blind `updated[-SESSION_HISTORY_LIMIT:]` trim in
   `write_memory`. No new graph node — `write_memory` already has access to
   `ze_agents.model_resolution.resolve_model` (imported at `memory.py:9`, used at line
   130 for the synthesis model) and to `config["configurable"]["openrouter_client"]`
   (line 124), everything compaction needs. `SESSION_HISTORY_LIMIT` stays as the
   verbatim-tail size (the "keep recent turns intact" window) but is no longer the sole
   cap — before slicing, `write_memory` now checks the *pre-slice* `updated` list's
   estimated tokens against 70% of `get_context_window(model)`; only when exceeded does
   it summarize everything before the tail into one synthetic message instead of
   dropping it.
2. **Resume recap** replaces the `history = []` branch in `fetch_context`
   (`nodes/context.py:64-66`). No new graph node — the gap check already lives here,
   already reads the shared `session_inactivity_minutes` key (FR-006 is satisfied by
   construction, not by importing `SessionSummariser` itself), and this node already
   constructs `agent_context` (the exact object `AgentContext.resume_recap` needs to be
   set on, mirroring how `screen_context_note` is set later in the same node at line
   121).

**Rationale**: Both new behaviors are direct replacements of existing, narrowly-scoped
logic in the two nodes that already own "what messages does the model see" and "did we
just cross a session boundary." Adding new standalone nodes would either run before
routing decides the model (too early to know which context window applies — routing
happens in `embed_route`, upstream of `fetch_context`/`write_memory`) or duplicate the
gap-check/trim logic that already exists, creating two competing definitions of the
same thing.

**Alternatives considered**: New standalone nodes before `embed_route` (this doc's
original R1 answer, now superseded — rejected because the routed model, needed for the
context-window lookup, isn't known that early) and running trim logic inside
`BaseAgent.agentic_loop` per-agent (rejected — `write_memory`/`fetch_context` are
already the single choke points for `state["messages"]`; duplicating logic per-agent
would fragment it).

## R2. How compaction mutates state

**Decision**: Inside `write_memory`, after building `updated` (existing history + this
turn's user/assistant messages, `memory.py:112-115`), estimate its token count (R4) and
compare it against 70% of `get_context_window(model)` (R3), where `model` is resolved
the same way the node already resolves the synthesis model (`resolve_model(...)`,
`memory.py:130` — R3 discusses the exact key). If under budget, behavior is unchanged:
return `{"messages": updated[-SESSION_HISTORY_LIMIT:]}`. If over budget, split `updated`
at `-SESSION_HISTORY_LIMIT` (the verbatim tail, unchanged in size) and summarize
everything before that split into **one** synthetic message (`role: "system"`, tagged
`compaction_summary: true`) via an LLM call using a new prompt distinct from
`SessionSummariser._SUMMARY_SYSTEM`, then return
`{"messages": [summary_message] + updated[-SESSION_HISTORY_LIMIT:]}`. Because this is
the same `update_state`-on-return mechanism the node already uses for the `[-10:]` trim,
the compacted list becomes the new checkpointed lineage the same way today's trim
already does — no new persistence primitive, no checkpoint branching.

**Rationale**: Spec explicitly says compaction is "an in-place `update_state` on the
same thread lineage," not checkpoint branching (out of scope, per spec Input). The
stored, permanent record obligation (FR-003a) is satisfied separately — `messages`
in `AgentState`/checkpoints was never the durable record; the durable record is the
`messages` table + `trace` column (`core/ze-core/ze_core/conversation/messages/`),
written by the existing message-persistence path independent of graph state. Compacting
the graph-state copy therefore cannot violate FR-003a as long as message persistence
(save to `messages` table) happens with the original, uncompacted text — which it
already does, upstream of/independent from graph invocation (the API layer persists
the inbound user message and the final assistant reply verbatim; graph state is a
working copy for the model call only).

**Alternatives considered**: Storing a separate `compacted_messages` field and leaving
`messages` untouched (rejected — doubles the state size in every checkpoint and
requires every downstream consumer to know which field to read; the "keep it simple"
posture from CLAUDE.md and the spec's own framing ("in-place update_state") favor
mutating `messages` directly).

## R3. Per-model context-window table

**Decision**: New static module `core/ze-core/ze_core/openrouter/context_windows.py`:
a read-only `dict[str, int]` (`MODEL_CONTEXT_WINDOWS`) keyed by OpenRouter model slug,
covering the models `config/config.yaml` currently assigns to agents, plus a
`DEFAULT_CONTEXT_WINDOW_TOKENS` fallback constant (conservative, e.g. 32_000) and a
`get_context_window(model: str) -> int` accessor. This mirrors the existing
`lru_cache` singleton pattern used by `embeddings.py` (module-level constant, no
mutable global) — allowed under the constitution's "no module-level mutable globals"
constraint because the dict is never mutated at runtime.

The model to look up is resolved the same way `write_memory` already resolves the
synthesis model — `resolve_model(key, declared, app_config)` from
`ze_agents.model_resolution` (`memory.py:9,130`) — using a new `"compaction"`-analogous
call: `ctx.model or resolve_model("synthesis", MODEL_SYNTHESIS, app_config)` as the
best-effort proxy for "the model handling this thread's turns" (FR-001), since
`AgentContext.model` isn't always populated this late and the synthesis model is the
existing fallback pattern already used at this exact call site for a similar purpose.

**Rationale**: `OpenRouterClient` (`core/ze-core/ze_core/openrouter/client.py`) has no
context-length metadata today (confirmed by exploration — only `fetch_generation_cost`
exists, a post-hoc cost lookup). OpenRouter's `/models` endpoint does return
`context_length`, but adding a live network call into the pre-turn budget check on
every single message would add latency and a new failure mode to every turn, which
conflicts with SC-004 ("no perceptible delay") and FR-005's fallback requirement (a
network-sourced table can itself be unavailable, becoming the same problem twice).
A static table refreshed manually (or by a small offline script, out of scope here)
matches how `config/config.yaml` model assignments are already curated by hand.

**Alternatives considered**: Live OpenRouter `/models` fetch with an in-process TTL
cache (rejected for latency/failure-mode reasons above, though the table's shape keeps
this open as a future upgrade — the accessor signature doesn't change either way).

## R4. Token estimation

**Decision**: Reuse the existing token estimation already used by
`core/ze-core/ze_core/telemetry/` (cost tracking necessarily estimates or reads token
counts today) rather than introducing a second tokenizer dependency. If telemetry's
estimation is post-hoc only (actual usage from OpenRouter's response), compaction needs
a *pre-call* estimate — a simple chars/4 heuristic (used defensively, since the 70%
threshold already carries conservative headroom per FR-001's stated rationale) is
adopted as the estimator, avoiding a new heavy tokenizer dependency (e.g. `tiktoken`)
that would need per-model-family selection logic OpenRouter doesn't expose uniformly
across providers.

**Rationale**: FR-001 itself justifies a conservative, approximate check ("leaves
headroom for token growth that happens later in the same turn") — exactness is not the
requirement, staying under budget is.

**Alternatives considered**: `tiktoken` (rejected — accurate only for OpenAI-family
models; OpenRouter routes to Anthropic, Google, etc. with different tokenizers, so a
single library can't be authoritative anyway).

## R5. Resume recap assembly and injection point

**Decision**: Extend the gap check `fetch_context` already runs (`nodes/context.py:62-68`
— `(now - last_active) > inactivity_minutes * 60`, reading `session_inactivity_minutes`
from `cfg`, the same config key `SessionSummariser._inactivity_minutes()` reads at
`core/ze-memory/ze_memory/session_summary.py:17,239` — this identity is what satisfies
FR-006's "same shared value" requirement; no new threshold constant, no dependency on
importing `SessionSummariser` itself). Today that branch sets `history: list[dict] = []`
(blanking); it becomes: when the gap is exceeded, keep `history = []` (compaction/trim
behavior for messages is unaffected — the model still starts this turn's window fresh)
but additionally assemble a `ResumeRecap` from:
`get_session_summary(session_id)` (`ze_memory/retriever.py:634`), `LoopSurfacer`
entity-overlap candidates (`ze_worldstate/surfacing.py:35`, seeded the same way
`surface_loops` already seeds them — `_extract_seeds` pattern in
`nodes/loop_surfacing.py`/`nodes/correlation.py`), and in-flight goals/workflows.
Because Ze is single-user (constitution Principle II — no per-user or per-thread
scoping exists on `GoalStore`/`WorkflowStore`, confirmed by exploration), "in-flight
goals/workflows relevant to the thread" resolves to simply *all* currently in-flight
goals/workflows — there is exactly one user, so every open loop/goal/workflow is
already "relevant" to whichever thread that user is in. No new thread-scoping query is
added to `ze-automation`.

The assembled recap is set directly on `agent_context.resume_recap` inside
`fetch_context`, the same way `screen_context_note` is set on the same `agent_context`
object later in the same node (`nodes/context.py:121`) — no state plumbing needed, since
`fetch_context` both owns the gap check and constructs `agent_context`. New
`AgentContext.resume_recap: str | None` field (`ze_agents/types.py`), formatted into the
system prompt by `_build_system_prompt` (`base_agent.py:162-163`, extended the same way
`screen_context_note` is rendered there), never appended to `state["messages"]` as a
chat turn (this is what keeps it out of the visible transcript, satisfying FR-007a's
"silent priming" requirement — the existing `screen_context_note` mechanism already
proves this pattern does not surface as a chat bubble).

**Rationale**: Reuses three already-built subsystems verbatim per the spec's explicit
instruction ("existing structured state ... rather than re-summarizing raw chat
text"); avoids inventing a fourth notion of "thread relevance" the codebase doesn't
have and doesn't need under the single-user model.

**Alternatives considered**: Injecting the recap as a synthetic message in
`state["messages"]` (rejected — would appear indistinguishable from a real turn to
anything reading message history, and risks leaking into the visible transcript if a
future feature ever surfaces raw `messages`, violating FR-007a's intent even if not
its letter today).

## R6. Trace fields (FR-011, User Story 3)

**Decision**: Extend `MessageTrace` (`core/ze-core/ze_core/conversation/messages/types.py:38-48`)
with two optional fields: `compaction: CompactionTrace | None` (whether a rolling
summary was present this turn, and the turn-index span it covers) and
`resume_recap_applied: bool`. New `AgentState` fields `compaction_span: tuple[int, int]
| None` (set by `write_memory`) and `resume_recap_applied: bool` (set by
`fetch_context`) carry this from the two edited nodes through to `record_trace`
(`nodes/trace.py:18`), which reads them the same way it already reads `memory_context`
for `memory_chunks`. Persisted through the existing
`MessageStore.save_trace` path — no new migration needed beyond the already-existing
`trace JSONB` column (`zc020_message_trace.py`).

**Rationale**: FR-011 asks for inspectability "via Ze's existing per-message
explainability trace" — this is that trace, extended, not a new surface.

## R7. Compaction failure fallback (FR-010, edge case)

**Decision**: If the LLM summarization call inside `write_memory`'s new compaction
branch raises or times out, catch it and fall back to today's existing behavior exactly:
`updated[-SESSION_HISTORY_LIMIT:]` (drop the older span entirely for this turn, no
synthetic summary message), log a warning, and proceed. The dropped span is never lost
from the durable record (R2) — only this turn's model-facing context loses it, and the
next turn's compaction check re-covers the same span from the (still fully intact)
checkpointed `messages` history... except `messages` itself was just hard-trimmed by
this same fallback, so in practice the span is only recoverable from the durable
`messages` DB table (FR-003a), not from the graph-state checkpoint, once a fallback
trim has occurred. This is an accepted, spec-compliant tradeoff — FR-010 requires the
turn not be lost, not that the graph-state checkpoint retain everything.

**Rationale**: Matches the edge case's required behavior exactly ("fall back to a safe
behavior ... hard-trim to the verbatim window and proceed") without inventing retry
logic that could itself stall the turn.

## R8. Test placement

**Decision**: New test cases added to the existing `core/ze-core/tests/orchestration/nodes/
test_memory.py` (compaction branch) and a new `core/ze-core/tests/orchestration/nodes/
test_context.py` (no test file for `fetch_context` exists today — confirmed by search —
so this is a new file covering both the pre-existing gap-check behavior and the new
resume-recap branch; no dedicated file per new node since there are no new nodes — R1),
mirroring the existing `nodes/test_loop_surfacing.py` pattern for fakes/`AsyncMock`
style. A model-context-window table test
(`test_context_windows.py`) covers the fallback-default path (FR-005's "unknown model"
edge case). Eval-suite additions for SC-002 (recall accuracy) live under `eval/scenarios/`
per existing convention, not under `tests/`.
