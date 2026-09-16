# ze-memory — Memory Stack

> **Package:** `core/cognition/ze-memory` — `ze_memory/`
> **Status:** Done (78b dream pass in progress)
> **Architecture:** [arch/memory-package-split.md](../arch/memory-package-split.md), [arch/memory-graph-augmentation.md](../arch/memory-graph-augmentation.md), [arch/dream-memory.md](../arch/dream-memory.md)
> **Supersedes:** [06-memory.md (stale)](06-memory.md)

---

## Purpose

The full memory stack: write, retrieve, consolidate, and evolve what Ze knows about
the user. Memory is divided into facts (structured beliefs), episodes (raw experience
records), a relationship graph, and procedures (reusable skill patterns). The dream
subsystem runs an offline consolidation loop.

---

## Responsibilities

- **Write path** — Perception facts (conversation extraction, ingest sink, onboarding seeds,
  goal-learning promotion, companion `remember_fact`) go through `submit_perception_facts`
  (contribution seam + NLI). There is no public `MemoryStore.propose_facts` and no
  `AgentResult.memory_proposals` persist door. Post-turn `extractor.py` is a keep/drop
  admission gate: closed families (`identity`, `preference`, `relationship`, `constraint`,
  `contact_detail`), `speech_act` must be `fact` or `facts` is `[]`. Explicit remember stamps
  `PROMPT_SUPPLIED` + `reviewed=true`. `forget_fact` retracts matching rows (`contradicted=true`).
  Episode writes remain `write_episode`.
- **Retrieval** — `MemoryRetriever`: semantic search over facts and episodes using the
  shared embedding singleton; `retrieval_rerank.py` re-ranks with NLI cross-encoder
- **Graph** — `MemoryGraph`: entity and relationship store; neighbourhood traversal for
  correlation context injection
- **Consolidation** — `MemoryConsolidator`: periodic dedup, expiry, episode archival,
  session-grouped summarisation
- **Dream** — `dream/`: sleep pass (NREM: compress, dedup), dream pass (REM: synthesise
  variants), morning integration (gate scoring + critic-gated promotion to live memory)
- **Surfacing** — `surfacing.py`: relevance-scored fact surfacing for context injection
  before agent calls
- **Session summaries** — `session_summary.py`: session-grouped episode summarisation
- **Retrieval cache** — `retrieval_cache.py`: caches embedding lookups for hot facts
- **NLI config** — `nli_config.py`: thresholds for contradiction detection and re-ranking
- Migrations — `zm` chain

---

## Out of Scope

- The NLI model itself — `ze-core/nli.py` (shared singleton)
- Memory write orchestration from the graph — `ze-core` `write_memory` node
- User-facing memory API routes — `ze-api`
- Domain-specific memory content (contacts, goals) — plugin packages

---

## Module Location

```
core/cognition/ze-memory/ze_memory/
  store.py              ← MemoryStore (facts, episodes)
  retriever.py          ← MemoryRetriever (semantic search)
  graph/                ← MemoryGraph, entity/relationship store
  consolidator.py       ← MemoryConsolidator
  consolidation_store.py← ConsolidationStore (dedup state)
  admission.py          ← write-time admission gates (NLI, novelty)
  synthesizer.py        ← fact synthesis (generalisation from episodes)
  surfacing.py          ← relevance-scored surfacing for context injection
  session_summary.py    ← session-grouped summarisation
  retrieval_rerank.py   ← NLI-based re-ranking
  retrieval_cache.py    ← embedding lookup cache
  extractor.py          ← keep/drop fact admission + speech_act gate from conversation turns
  relevance.py          ← salience / relevance model
  projection.py         ← structured user profile projection
  policies.py           ← MemoryPolicy definitions
  dream/                ← sleep pass, dream pass, morning integration, staging buffer
  nli_config.py         ← NLI thresholds
  defaults.py           ← default policies and settings
  types.py              ← FactRecord, EpisodeRecord, MemoryEntity, MemoryRelationship
  migrations/           ← zm chain
```

---

## Key invariants

- A compressed episode (`provenance="compressed"`) is never re-compressed. This prevents
  model collapse (TiMem's documented failure mode).
- `support_count >= 3` for fact promotion requires supporters spanning ≥ 2 distinct
  `session_id`s AND ≥ 7 calendar days. Breaks self-confirming belief clusters.
- `user_asserted` episodes cap at 1 toward `support_count` regardless of quantity
  (provenance laundering guard).
- The dream staging buffer (`dream/`) is the only path to synthetic fact promotion.
  No phase writes synthetic output directly to live memory.

---

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `ze-agents` | `LLMClient`, `DBPool`, `Settings`, error types |
| `ze-logging` | `get_logger` |

---

## Links

- [Phase 140 — Memory Admission](../phases/140-memory-admission/spec.md)
- [Phase 141 — Read Contract + Prompt Constitution](../phases/141-memory-prompt-constitution/spec.md)
- [Phase 142 — Speech-Act Routing](../phases/142-speech-act-routing/spec.md)
- [Phase 140 — Memory Admission](../phases/140-memory-admission/spec.md)
- [Phase 141 — Read Contract + Prompt Constitution](../phases/141-memory-prompt-constitution/spec.md)
- [Phase 142 — Speech-Act Routing](../phases/142-speech-act-routing/spec.md)
