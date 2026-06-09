# Ze — Memory Package Extraction

> **Package:** `ze_memory` (new package)
> **Phase:** N/A
> **Status:** Pending

---

## Purpose

Ze's current memory subsystem has outgrown its role as a generic `ze_core` utility.
It now needs explicit ownership over memory-specific invariants: structured long-term
memory, module-specific retrieval, consolidation, provenance, profile synthesis, and
task-state persistence. This spec defines the boundary for extracting memory into a
dedicated package so the architecture can evolve without overloading `ze_core` with
domain semantics. The migration is a hard cutover: no compatibility shim, no dual
API period, and no lingering `ze_core.memory` authority after the move.

---

## Responsibilities

- Own all memory-specific types, storage, retrieval, and consolidation logic.
- Separate long-term memory from live task state and derived prompt context.
- Expose module-specific retrieval policies as explicit code, analogous to how agent
  capabilities are declared in source.
- Preserve provenance for all durable memory mutations.
- Maintain both semantic recall and explicit structured state for the assistant.
- Provide a derived `MemoryContext` projection for orchestration and prompting.
- Own task-state storage as durable operational state inside the memory subsystem.

---

## Out of Scope

- Does not own routing, orchestration, agent execution, or transport concerns.
- Does not define persona, goals, workflow, contacts, or other domain services beyond
  the memory artifacts they consume.
- Does not introduce graph neural networks, hypergraphs, or line-graph machinery in
  the initial cut.
- Does not make embeddings the source of truth for explicit task state.
- Does not change user-facing UI behavior as part of the package move itself.

---

## Module Location

```
packages/ze-memory/
  ze_memory/
    __init__.py
    errors.py
    types.py
    store.py
    retriever.py
    policies.py
    consolidator.py
    synthesizer.py
    projection.py
    defaults.py
    migrations/
```

The existing `ze_core.memory` package becomes a compatibility shim during migration,
then is removed as part of the same migration. `ze_core` retains only generic
infrastructure and no memory-domain authority.

---

## Interface Contract

The package should expose explicit APIs rather than a single generic context fetch.
Retrieval must be policy-driven by module.

### Input

```python
@dataclass
class RetrievalRequest:
    module: str
    agent: str
    query_text: str
    query_embedding: Any
    intent: str | None = None
    task_id: UUID | None = None
    goal_id: UUID | None = None
    max_tokens: int = 2000


class MemoryStore(Protocol):
    async def retrieve(self, request: RetrievalRequest) -> MemoryContext: ...
    async def write_episode(...) -> None: ...
    async def propose_facts(...) -> None: ...
    async def upsert_task_state(...) -> None: ...
    async def get_task_state(...) -> TaskState | None: ...
    async def get_profile(...) -> list[ProfileFacet]: ...


class MemoryRetrievalPolicy(Protocol):
    async def retrieve(self, request: RetrievalRequest) -> MemoryContext: ...


class MemoryPolicyRegistry(Protocol):
    def for_module(self, module: str) -> MemoryRetrievalPolicy: ...
```

### Output

```python
@dataclass
class MemoryContext:
    facts: list[Fact] = field(default_factory=list)
    episodes: list[Episode] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    procedures: list[Procedure] = field(default_factory=list)
    task_state: TaskState | None = None
    profile: list[ProfileFacet] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    token_estimate: int = 0
```

### Errors / Edge Cases

| Condition | Behaviour |
|-----------|-----------|
| Retrieval request omits `module` or `query_embedding` | Fail fast with a typed memory error |
| Task state does not exist | Return `None`, not an empty synthetic state |
| Stored graph state and vector similarity disagree | Prefer explicit state and provenance over similarity |
| Consolidation cannot produce a safe merge | Preserve both records and mark for review |
| Derived profile is empty | Return an empty profile projection, not a fabricated one |
| Unknown module is requested | Raise a typed memory error |

---

## Data Structures

```python
@dataclass
class Entity:
    id: UUID | None
    entity_type: str
    canonical_name: str
    aliases: list[str] = field(default_factory=list)
    attrs: dict[str, str] = field(default_factory=dict)
    embedding: Any = field(default=None, repr=False, compare=False)


@dataclass
class Fact:
    id: UUID | None
    subject_id: UUID | None
    predicate: str
    object_text: str | None
    object_id: UUID | None
    value: str
    confidence: float = 1.0
    reviewed: bool = False
    contradicted: bool = False
    source_episode_id: UUID | None = None
    source_refs: list[UUID] = field(default_factory=list)
    embedding: Any = field(default=None, repr=False, compare=False)


@dataclass
class Episode:
    id: UUID | None
    session_id: str
    agent: str
    prompt: str
    response: str
    summary: str | None = None
    relevance: float = 0.0
    created_at: datetime | None = None
    linked_entity_ids: list[UUID] = field(default_factory=list)
    linked_fact_ids: list[UUID] = field(default_factory=list)
    embedding: Any = field(default=None, repr=False, compare=False)


@dataclass
class Event:
    id: UUID | None
    event_type: str
    title: str
    start_at: datetime | None = None
    end_at: datetime | None = None
    participants: list[UUID] = field(default_factory=list)
    roles: dict[str, UUID] = field(default_factory=dict)
    summary: str | None = None
    outcome: str | None = None
    source_episode_id: UUID | None = None
    embedding: Any = field(default=None, repr=False, compare=False)


@dataclass
class Procedure:
    id: UUID | None
    name: str
    trigger: str
    preconditions: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    success_criteria: list[str] = field(default_factory=list)
    version: int = 1
    source_refs: list[UUID] = field(default_factory=list)
    embedding: Any = field(default=None, repr=False, compare=False)


@dataclass
class TaskState:
    id: UUID | None
    task_id: UUID | None
    goal_id: UUID | None
    status: str
    open_steps: list[str] = field(default_factory=list)
    blocked_by: list[str] = field(default_factory=list)
    last_action: str | None = None
    next_action: str | None = None
    tool_cursors: dict[str, str] = field(default_factory=dict)
    updated_at: datetime | None = None


@dataclass
class ProfileFacet:
    key: str
    value: str
    stability: str
    confidence: float = 1.0
    source_refs: list[UUID] = field(default_factory=list)
    updated_at: datetime | None = None


@dataclass
class MemoryContext:
    facts: list[Fact] = field(default_factory=list)
    episodes: list[Episode] = field(default_factory=list)
    events: list[Event] = field(default_factory=list)
    procedures: list[Procedure] = field(default_factory=list)
    task_state: TaskState | None = None
    profile: list[ProfileFacet] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    token_estimate: int = 0
```

---

## Database Schema

```sql
CREATE TABLE memory_entities (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    entity_type    TEXT NOT NULL,
    canonical_name TEXT NOT NULL,
    aliases        JSONB NOT NULL DEFAULT '[]'::jsonb,
    attrs          JSONB NOT NULL DEFAULT '{}'::jsonb,
    embedding      VECTOR(384),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE memory_facts (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subject_id         UUID NULL REFERENCES memory_entities(id),
    predicate          TEXT NOT NULL,
    object_text        TEXT NULL,
    object_id          UUID NULL REFERENCES memory_entities(id),
    value              TEXT NOT NULL,
    agent_scope        TEXT NOT NULL DEFAULT 'global',
    confidence         FLOAT NOT NULL DEFAULT 1.0,
    reviewed           BOOLEAN NOT NULL DEFAULT false,
    contradicted       BOOLEAN NOT NULL DEFAULT false,
    source_episode_id  UUID NULL,
    source_refs        JSONB NOT NULL DEFAULT '[]'::jsonb,
    embedding          VECTOR(384),
    expires_at         TIMESTAMPTZ NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE memory_episodes (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id     TEXT NOT NULL,
    agent          TEXT NOT NULL,
    prompt         TEXT NOT NULL,
    response       TEXT NOT NULL,
    summary        TEXT NULL,
    linked_entity_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    linked_fact_ids   JSONB NOT NULL DEFAULT '[]'::jsonb,
    relevance      FLOAT NOT NULL DEFAULT 0.0,
    embedding      VECTOR(384),
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE memory_events (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_type       TEXT NOT NULL,
    title            TEXT NOT NULL,
    start_at         TIMESTAMPTZ NULL,
    end_at           TIMESTAMPTZ NULL,
    participants     JSONB NOT NULL DEFAULT '[]'::jsonb,
    roles            JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary          TEXT NULL,
    outcome          TEXT NULL,
    source_episode_id UUID NULL,
    embedding        VECTOR(384),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE memory_procedures (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name             TEXT NOT NULL,
    trigger          TEXT NOT NULL,
    preconditions    JSONB NOT NULL DEFAULT '[]'::jsonb,
    steps            JSONB NOT NULL DEFAULT '[]'::jsonb,
    success_criteria JSONB NOT NULL DEFAULT '[]'::jsonb,
    version          INT NOT NULL DEFAULT 1,
    source_refs      JSONB NOT NULL DEFAULT '[]'::jsonb,
    embedding        VECTOR(384),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE memory_task_state (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id       UUID NULL,
    goal_id       UUID NULL,
    status        TEXT NOT NULL,
    open_steps    JSONB NOT NULL DEFAULT '[]'::jsonb,
    blocked_by    JSONB NOT NULL DEFAULT '[]'::jsonb,
    last_action   TEXT NULL,
    next_action   TEXT NULL,
    tool_cursors  JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE memory_profile_facets (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key          TEXT NOT NULL,
    value        TEXT NOT NULL,
    stability    TEXT NOT NULL,
    confidence   FLOAT NOT NULL DEFAULT 1.0,
    source_refs  JSONB NOT NULL DEFAULT '[]'::jsonb,
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

The exact table set may be normalized further, but the spec requires the above
conceptual entities and provenance fields to exist.

Task state is owned by memory, but it is operational state rather than fuzzy recall:
it should be read and written deterministically, not inferred from embeddings.

---

## Configuration

```yaml
# config/config.yaml
memory:
  default_fact_budget_tokens: 200
  default_episode_budget_tokens: 500
  retrieval:
    companion:
      policy: companion
    planner:
      policy: planner
    tool_executor:
      policy: tool_executor
    profile:
      policy: profile
    memory_ui:
      policy: memory_ui
```

The implementation may keep some thresholds in code defaults, but module-specific
retrieval policy must be selected explicitly per module. YAML may tune weights later,
but the policy shape itself is code-owned.

---

## Dependencies

| Dependency | Purpose |
|------------|---------|
| `ze_core.errors` | Typed error hierarchy shared across packages |
| `ze_core.logging` | Structured logging |
| `ze_core.embeddings` | Shared local embedding model |
| `ze_core.openrouter` | LLM-based consolidation and synthesis where needed |
| `asyncpg` / `psycopg2` | PostgreSQL runtime and Alembic CLI support |
| `pgvector` | Semantic retrieval over embedded memory artifacts |

---

## Implementation Notes

- `MemoryContext` is a projection consumed by orchestration; it is not the canonical
  storage model.
- Module-specific retrieval policies are explicit code objects, not ad hoc branching
  inside the store implementation.
- Explicit task state and structured relations take precedence over fuzzy semantic
  similarity when the two disagree.
- Retrieval must be policy-driven by module, not globally optimized with one score.
- Graph relationships are useful only where they expose concrete joins or provenance;
  they are not a justification for universal edge embeddings. Graph expansion is
  deferred until a later follow-up spec proves it necessary.
- Consolidation must preserve source references and auditability for all durable
  changes.
- `ze_core` should not import memory-domain types after cutover.
