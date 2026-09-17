# ADR: Local embedding model for routing and memory

> **Status:** Accepted
> **Date:** 2023-11-01 (Phase 1)
> **Scope:** `EmbeddingRouter` (routing), `ze-memory` (semantic retrieval, dedup)

---

## Context and Problem Statement

Ze embeds every inbound message to route it to the right agent, and embeds memory
entries for semantic retrieval and deduplication. Embeddings are on the hot path —
called for every message. The question is whether to use a hosted embedding API or a
local model.

---

## Decision Drivers

- Embeddings are called on every single user message — API cost at low volume is
  acceptable but the per-call latency and per-token cost compound over time
- Ze is multilingual — the model must handle non-English input without degradation
- 384 dimensions is sufficient for Ze's routing task (a handful of agents, dense
  intent clusters) and for memory dedup (cosine similarity threshold)
- The model can be loaded once at startup and kept in memory — no cold-start per call

---

## Considered Options

1. **OpenAI `text-embedding-3-small`** — 1536-dim, hosted, $0.02/1M tokens
2. **Hosted via OpenRouter** — embedding APIs are not currently supported by OpenRouter
3. **Local `paraphrase-multilingual-MiniLM-L12-v2`** — 384-dim, ~90MB, sentence-transformers (superseded)
4. **Local `intfloat/multilingual-e5-base`** — 768-dim, sentence-transformers, required `query:` / `passage:` prefixes

---

## Decision Outcome

**Chosen option: Local `intfloat/multilingual-e5-base` (Option 4).** MiniLM (Option 3) was the Phase 1 choice and is superseded as of the Phase 97 model swap plus Phase 160 confidence calibration.

Zero per-call cost, no external dependency for the hot path, and native multilingual
support. The model is loaded as a singleton at startup via `sentence-transformers`
and kept in memory for the process lifetime. Callers must use `encode_query` for
user text and `encode_passage` for agent descriptions and stored content.

Routing confidence defaults (`ROUTING_THRESHOLD` 0.73, `ROUTING_GAP_THRESHOLD` 0.02)
are calibrated to E5's compressed high band, not MiniLM's 0.55 / 0.10.

### Positive Consequences

- Zero marginal cost per message regardless of usage
- Embedding is synchronous in-process — no network call, no latency variance
- Multilingual by default — handles Portuguese, Spanish, French, etc. without
  a separate model or prompting trick
- No dependency on OpenAI for a core infrastructure primitive

### Negative Consequences / Trade-offs

- ~420MB+ model resident in the Python process — increases container memory footprint
- 768 dimensions: richer than MiniLM's 384-dim vectors; still lower fidelity than
  hosted 1536-dim models for nuanced semantic retrieval
- Marked `@pytest.mark.slow` in tests — slow to load in CI, excluded from default
  test runs (pass `SLOW=1` to include)
- Prefixes are mandatory. Encoding without `query:` / `passage:` collapses scores
  into a useless band. Routing confidence (threshold 0.73, gap 0.02) is calibrated
  to prefixed E5 scores, not MiniLM.
- If a significantly better multilingual model emerges, swapping it requires changing
  the singleton in `core/engine/ze-core/ze_core/embeddings.py` and re-indexing stored vectors

---

## Pros and Cons of the Options

### Option 1 — OpenAI text-embedding-3-small

**Pros:** Higher dimensionality, OpenAI quality, no memory footprint.

**Cons:** Per-call cost on the hot path; US English-biased; adds OpenAI as a runtime
dependency (Ze currently uses OpenRouter only for LLM calls); latency per embed call.

### Option 2 — Hosted via OpenRouter

**Cons:** OpenRouter does not currently offer embedding APIs.

### Option 3 — Local sentence-transformers

**Pros:** Zero cost, in-process, multilingual, reliable.

**Cons:** Memory overhead; lower dimensionality.

---

## Links

- `core/engine/ze-core/ze_core/embeddings.py` — singleton loader
- `core/engine/ze-core/ze_core/routing/` — `EmbeddingRouter` usage
- `core/cognition/ze-memory/` — semantic retrieval and dedup usage
