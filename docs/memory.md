# Ze — Memory System

Ze maintains two kinds of long-term memory: **facts** (declarative statements) and
**episodes** (conversation summaries). Over time these accumulate into a **user profile**
and weekly **insights** that Ze injects into every agent's system prompt.

---

## Data types

```python
@dataclass
class UserFact:
    key: str             # e.g. "communication_preference"
    value: str           # e.g. "prefers async over meetings"
    agent: str           # which agent proposed this fact
    confidence: float    # 0.0–1.0, set by the proposing agent
    reviewed: bool       # True = user has confirmed or edited this fact
    contradicted: bool   # True = superseded by a newer/merged fact
    expires_at: datetime | None

@dataclass
class Episode:
    agent: str           # which agent handled the turn
    prompt: str          # the user's original message
    response: str        # Ze's response
    summary: str | None  # brief summary (set during archival)
    is_archive: bool     # True = this row is an archival summary
    embedding: ...       # pgvector embedding (write-time only; None in context)

@dataclass
class UserProfile:
    preferences: str     # communication style, format preferences
    habits: str          # routines, work patterns
    topics: str          # recurring subjects, domains of interest
    relationships: str   # people mentioned, their roles
    goals: str           # stated objectives, in-progress projects
    version: int         # incremented on every synthesis
    updated_at: datetime
```

---

## How memory is written

### Facts (user approval required)

After each agent run, `write_memory` (a fire-and-forget graph node) asks the agent
for fact proposals. The agent returns a list of `UserFact` objects via `AgentResult.memory_proposals`.

`write_memory` calls `store.propose_facts(proposals)` — this writes facts with
`reviewed = False`. Ze then sends a Telegram message asking the user to confirm,
reject, or edit each proposal. Only after a `POST /memory/facts/review` call does
`reviewed` flip to `True`.

**Reviewed facts are never auto-merged or auto-expired.**
They represent an explicit user decision and are treated as ground truth.

### Episodes (automatic, no approval)

After every agent run, `write_memory` calls `store.write_episode()`. This writes a
row to the `episodes` table with a pgvector embedding of the prompt+response text.
No user action is required.

---

## How memory is retrieved

Before every agent execution, `fetch_context` runs:

1. **Semantic search** — embeds the current prompt with `all-MiniLM-L6-v2` and runs a
   pgvector cosine similarity search over both `user_facts` and `episodes`. Returns
   the top-k most relevant results as `MemoryContext`.
2. **Profile injection** — calls `store.get_profile()` and attaches the current
   `UserProfile` to `MemoryContext`.
3. **Identity block assembly** — `identity_builder` (`build_identity_block()` from
   `ze_personal.persona`) assembles the full system prompt identity block from:
   - Persona profile (name, traits, verbosity, custom instructions, dials)
   - User profile (synthesised portrait)
   - Top-k facts and episode summaries

Agents never query memory themselves — they receive the assembled context via
`AgentContext` and `_build_system_prompt()`.

---

## Nightly consolidation

`MemoryConsolidator.run()` runs every night at 2 AM UTC
(`ze_core/memory/consolidator.py`). Four passes run in sequence:

### 1. Fact deduplication

Scans all unreviewed facts, computes pairwise cosine similarity, merges candidates:

| Similarity | Action |
|---|---|
| > 0.95 | Silent merge — keep newer, mark older `contradicted = true`. No LLM call. |
| 0.85–0.95 | LLM merge — Haiku synthesises one value, inserts it, marks both originals `contradicted = true`. |
| < 0.85 | No action. |

### 2. Fact expiry

Three rules per run:

| Rule | Condition | Action |
|---|---|---|
| Grace delete | `expires_at` elapsed | Hard-delete |
| Contradicted cleanup | `contradicted = true` + older than `contradicted_ttl_days` (30d default) | Hard-delete |
| Stale unreviewed | `reviewed = false` + no activity for `unreviewed_ttl_days` (90d default) | Soft-expire: set `expires_at = NOW() + expiry_grace_days` |

Soft-expired facts appear in the morning briefing as a nudge to review before they
are permanently deleted.

### 3. Episode archival

Episodes older than `episode_recency_days` (14d default) are archived in batches.
When at least `episode_min_archive_batch` (10 default) candidates exist, Haiku
summarises the batch into one archive row (`is_archive = true`) and the originals
are deleted.

This keeps the `episodes` table lean while preserving history in compressed form.

### 4. Profile synthesis

After the three cleanup passes, `synthesise_profile()` reads all reviewed facts and
recent episodes (up to `profile.episode_limit`, default: 50) and asks Haiku to
produce a structured `UserProfile`. The result is upserted into the `user_profile`
table and is available immediately on the next graph invocation.

Synthesis is skipped if fewer than `profile.min_facts` (3 default) reviewed facts exist.

---

## Inspecting memory

### REST API

| Endpoint | Description |
|----------|-------------|
| `GET /memory/facts` | All facts — query params: `reviewed`, `contradicted`, `expires_before` |
| `GET /memory/digest` | Unreviewed facts + facts near expiry |
| `GET /memory/profile` | Current user profile (latest synthesis) |
| `POST /memory/facts/review` | Confirm, reject, or edit a proposed fact |
| `POST /memory/consolidate` | Trigger a consolidation run manually |

### Telegram commands

- `/memory` — sends a digest of unreviewed facts and the current profile summary.

### Manual consolidation

```bash
curl -X POST https://ze-backend.fly.dev/memory/consolidate \
  -H "Authorization: Bearer $ZE_API_KEY"
```

---

## Configuration

All thresholds live in `config/config.yaml` under `memory.*`:

```yaml
memory:
  consolidation:
    merge_silent_threshold: 0.95
    merge_llm_threshold: 0.85
    contradicted_ttl_days: 30
    unreviewed_ttl_days: 90
    expiry_grace_days: 7
    episode_recency_days: 14
    episode_min_archive_batch: 10
  profile:
    episode_limit: 50
    min_facts: 3
```

---

## Database tables

| Table | Purpose |
|-------|---------|
| `user_facts` | Facts with pgvector embeddings, review status, expiry |
| `episodes` | Conversation turn summaries with pgvector embeddings |
| `user_profile` | Single-row (versioned) synthesised portrait |

Migrations: `migrations/versions/` (raw SQL, Alembic).

---

## Key invariants

- **Reviewed facts are never auto-merged or auto-expired.** Only the user can modify them.
- **Embeddings are stored at write time only.** At query time they are dropped from context
  objects so `AgentState` stays JSON-serialisable for the LangGraph checkpointer.
- **Memory is editorial, not automatic.** Facts require user approval; agents propose,
  users decide. Episodes are automatic because they are low-stakes and non-persistent
  (they archive away within ~2 weeks).
