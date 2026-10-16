# ze-core — Orchestration Engine

> **Package:** `core/engine/ze-core` — `ze_core/`
> **Status:** Done
> **Supersedes:** [01-agent.md](01-agent.md), [02-app-interface.md](02-app-interface.md), [03-capability-gate.md](03-capability-gate.md), [04-routing.md](04-routing.md), [05-orchestration.md](05-orchestration.md), [07-container.md](07-container.md), [09-conversation.md](09-conversation.md) (all stale)

The engine. Routes messages, builds and runs the LangGraph graph, manages
DI, wires plugins together. Plugin code never imports from `ze_core`.

---

## Purpose

Owns the full request lifecycle: receive a message → embed → route → preflight →
execute agent → write memory → send response. Manages the LangGraph graph with
`AsyncPostgresSaver` checkpoints, the DI container, plugin discovery, and telemetry.

---

## Responsibilities

- **Routing** — `EmbeddingRouter` embeds the message, cosine-similarity matches to
  agent intents; `ComplexityEstimator` decided compound vs. single-agent (superseded by 182: removed); fallback
  to haiku-class on low-confidence. With `system_one.surfaces.routing` on and
  calibrated (Phase 164), E5 stays the shortlist and one batched System One request
  (`ze_core/routing/judge.py`) asks a Choice over the shortlist plus `none`, a Noul
  ("more than one specialist?") and, until 182, a Score (complexity; superseded by 182,
  removed). Pure `decide()` turns the answers into trust / decompose / abstain / skip;
  abstain and skip fall back to the E5 bars and the regex `ComplexityEstimator`
  (superseded by 182, removed: routing always assigns the full model). `embed_route` records the judgments on
  the trace. Both call sites (`Container` and `bootstrap.build_router`) build the
  router through `build_embedding_router` in `ze_core/routing/factory.py`.
- **Skill matching glue** — `match_skills` (`orchestration/nodes/skills.py`) calls the
  injected `skill_matcher` (`ze-core` never imports `ze_skills`) with the shared
  `build_judgment_state(state)` from `orchestration/judgment_state.py` (the 164
  user-text / history-hint / routing-hint shape, now used by routing and skills). With
  `system_one.surfaces.skills` calibrated (Phase 166) the matcher returns a
  `SkillMatchOutcome`: the matches, plus a judgment whose rows `match_skills` converts
  with `judgments_from_result` and **appends** to `state["judgments"]`. It never
  replaces the rows `embed_route` wrote. `SkillUsageTrace.below_floor` marks an
  automatic skill applied under `match_threshold`.
- **Preflight** — the node after `choose_tier` (`orchestration/nodes/execution.py`) refuses
  a disabled agent and pauses for the spend budget. Phase 181 removed the capability gate,
  its confirmation modes and the per-agent override store; writes ask first.
- **Orchestration graph** — `graph_builder` compiles the LangGraph graph; nodes are
  `transcribe`, `embed_route`, `decompose`, `fetch_context`, `choose_tier`, `preflight`,
  `execute_tool`, `synthesize`, `write_memory`, `draft_response`, `await_confirmation`,
  `record_trace`
- **Container** — `BaseContainer` wires all dependencies; `invoke_raw_turn` and `resume`
  are the entry points; plugins register via `startup(container)`
- **Telemetry** — `CostTracker` accumulates per-flow token usage; `CostReconciler`
  reconciles against OpenRouter invoices; `PostgresCostStore` persists
- **Conversation** — `MessageStore` persists messages; `PendingConfirmationStore`
  persists paused confirmation requests for replay after restart
- **NLI** — `NLIClient` singleton (`cross-encoder/nli-deberta-v3-small`) shared across
  memory and correlation
- **System One** — `OpenRouterSystemOneClient` posts typed noul/choice/score questions
  to `{openrouter_base_url}/systemone` (model `typesafe/jev-1.13`, same
  `OPENROUTER_API_KEY` as chat). Default-off via `system_one.enabled`; missing key,
  timeout, and 429/529 skip rather than raising. Plugins type against
  `SystemOneClient` and never import this module.
- **Embeddings** — `intfloat/multilingual-e5-base` singleton (`query:` / `passage:`
  prefixes) used by router and memory; loaded once at startup

---

## Out of Scope

- Agent logic and tool execution — `ze-agents`
- Plugin definitions and ZePlugin ABC — `ze-plugin`
- Domain features (contacts, goals, calendar) — plugin packages
- Public plugin API — `ze-sdk`

---

## Module Location

```
core/engine/ze-core/ze_core/
  orchestration/      ← graph_builder, nodes, AgentState, edges, agent registry
  routing/            ← EmbeddingRouter, tier.py, fallback, RouterStore (ComplexityEstimator superseded by 182)
  (capability/ removed by 181)
  telemetry/          ← CostTracker, CostReconciler, PostgresCostStore, ContextVar
  openrouter/         ← OpenRouterClient + OpenRouterSystemOneClient (engine-internal)
  interface/          ← AppInterface wiring, InputPreprocessor
  conversation/       ← MessageStore, PendingConfirmationStore, SessionStore
  messages/           ← message types used in graph state
  container.py        ← BaseContainer — DI wiring, invoke_raw_turn, resume
  embeddings.py       ← embedding singleton (lru_cache)
  nli.py              ← NLIClient singleton
  checkpoint_serde.py ← LangGraph checkpoint type serialisers
  migrate.py          ← meta-runner entry (owned migrations only)
  migrations/         ← zc* chain (graph checkpoints, messages, sessions, confirmations)
```

---

## Key invariants

- `OpenRouterClient` and `OpenRouterSystemOneClient` are engine-internal. Plugins
  receive `LLMClient` / `SystemOneClient` (Protocols) via DI and never import
  `ze_core.openrouter` directly.
- The graph is compiled once at startup (`graph_builder(plugins)`). Adding a node
  requires a restart.
- `invoke_raw_turn` uses `graph.astream_events` (Phase 95+); prior to Phase 95 it used
  `graph.ainvoke`.
- Confirmation resume: `resume(thread_id, choice)` calls `graph.ainvoke(None, config)`
  with the same `thread_id` — the graph continues from the `await_confirmation` node.

---

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `ze-agents` | `BaseAgent`, `AgentRegistry`, `AppInterface`, `LLMClient`, `SystemOneClient` |
| `ze-communication` | `ChannelRegistry` |
| `ze-plugin` | `ZePlugin`, plugin discovery |
| `ze-logging` | `get_logger` |

---

## Links

- [ADR — LangGraph Orchestration](../arch/langgraph-orchestration.md)
- [ADR — OpenRouter Gateway](../arch/openrouter-gateway.md)
- [ADR — Local Embeddings](../arch/local-embeddings.md)
