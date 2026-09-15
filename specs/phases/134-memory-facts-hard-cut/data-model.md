# Data Model: Memory Facts Hard-Cut

## `Fact` (`ze_memory.types.Fact`)

| Field | Before | After |
|---|---|---|
| `provenance` | `str = "raw"` | `Provenance` (required; no default) |
| `claim_kind` | absent (column only) | `ClaimKind` (required on persist; loaded from row) |
| `confidence` | `float` | `float` (unchanged; decay via shared `TIME_LINEAR`) |
| `retrieval_provenance` | `str \| None` | unchanged (not doctrine Provenance) |

Other fields (`predicate`, `value`, `source_refs`, `agent`, flags) unchanged.

Validation on persist:

- `provenance` must be a `Provenance` member; unknown strings raise a typed `ZeError`.
- `claim_kind` must be a `ClaimKind` member.
- Do not coerce `"raw"` at the type boundary.

## `memory_facts` row

Existing table. This phase does not add columns.

| Column | Change |
|---|---|
| `provenance` | Values rewritten; `DEFAULT 'raw'` dropped; NOT NULL retained; CHECK to `graph_recall \| live_search \| prompt_supplied \| synthesized` |
| `claim_kind` | Unchanged (already NOT NULL from `zm016`) |
| `confidence` | Unchanged |

### Backfill

```sql
-- fail if unexpected values exist
-- (implement as a pre-check SELECT; abort upgrade() if count > 0)

UPDATE memory_facts SET provenance = 'prompt_supplied'
 WHERE provenance IS NULL OR provenance = 'raw';
-- synthesized and any already-doctrine values left as-is
```

### Insert contract

Every INSERT lists `provenance` and `claim_kind`. No reliance on column default.

Internal writers:

| Writer | Provenance | Kind |
|---|---|---|
| Seam `write=` / `_persist_facts` | From `Fact` / Contribution envelope | From `Fact` or 111 rule |
| Dream promoter | `synthesized` | `inference` (existing) |
| Consolidation merge | `synthesized` | `fact` (corroborated merge) |

## Contribution (unchanged shape)

Phase 133 already wraps each perception fact. This phase does not add fields. Persist copies
`contribution.provenance` onto `Fact.provenance` if the domain object still lacks a doctrine
value.

## Out of model

- `MemoryStore.propose_facts` — deleted (not an entity; see contracts/memory-store.md)
- Episodes, events, entities, signals — unchanged unless they construct `Fact(..., provenance="raw")`
- `OpenLoop.provenance` (inflow string) — not this table
