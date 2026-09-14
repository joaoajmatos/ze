# Contract: Memory graph vocabulary additions

This phase extends two controlled vocabularies in `core/ze-memory`. Both are
Python-level conventions today (see research.md §1), not DB-enforced — this
contract documents the addition so other packages/agents that read these
vocabularies (the extractor, any future consumer of `ALL_PREDICATES`) have
one place to check them.

## `entity_type`

`core/ze-memory/ze_memory/types.py` — `EntityRef.entity_type` /
`Entity.entity_type` comment:

```
Before: "person" | "org" | "topic" | "ticker" | "place" | "product"
After:  "person" | "org" | "topic" | "ticker" | "place" | "product" | "project"
```

`core/ze-memory/ze_memory/extractor.py`'s LLM extraction prompt (currently
listing `"person|organisation|pl..."` and defaulting unrecognized types to
`"concept"`) must list `"project"` as a recognized type so generic
extraction classifies project mentions correctly rather than falling back
to `"concept"`.

## Relationship predicates

`core/ze-memory/ze_memory/graph/predicates.py` — new module-level
constants, folded into `ALL_PREDICATES`:

```python
WORKS_ON = "WORKS_ON"              # person → project
COLLABORATES_WITH = "COLLABORATES_WITH"  # person ↔ person
```

**Invariant**: existing predicates, including `PARTICIPATES_IN`, are never
repurposed to carry this phase's semantics (FR-002). `WORKS_ON` and
`COLLABORATES_WITH` are the only two new predicates this phase adds — no
closed taxonomy of person↔person relationship *types* is introduced beyond
these two edges (FR-012); `Person.classification` remains the mechanism for
`personal | professional | unknown` distinctions.

## `Relationship.confidence` — type contract

Any code constructing or reading a `Relationship` must treat `confidence`
as `ze_agents.claims.Confidence`, not `float`, after this phase ships:

```python
# Before
relationship.confidence: float

# After
relationship.confidence: Confidence  # .value, .decay_profile
```

Callers that previously read `relationship.confidence` as a bare float
(if any exist outside `core/ze-memory` — none found in the current
codebase, but this is the compatibility boundary to check during
implementation) must switch to `relationship.confidence.value`.
`decay_profile` is always `DecayProfile.TIME_LINEAR` for `Relationship`
(FR-004 — no relationship-specific decay profile).
