# Data Model: Contribution Seam Extension — Social Cognition + Action

## Retrofitted types — `plugins/ze-personal/ze_personal/contacts/types.py`

### `Person` (dataclass, modified)

```python
@dataclass
class Person:
    name: str
    aliases: list[str] = field(default_factory=list)
    classification: str = "unknown"
    classification_confidence: float = 0.0
    relationship_to_user: str = ""
    contact_info: dict[str, str] = field(default_factory=dict)
    notes: str = ""
    confirmed: bool = False
    dismissed: bool = False
    confidence: float = 0.0                      # unchanged — max(source.weight) aggregate
    claim_kind: ClaimKind = ClaimKind.IDENTITY    # NEW — fixed, never anything else (FR-001)
    provenance: Provenance = Provenance.SYNTHESIZED  # NEW — derived from winning source's
                                                   #   source_type at write time (research.md §1)
    id: UUID | None = None
    first_seen: datetime | None = None
    last_mentioned: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
```

`confidence: float` is unchanged on the dataclass itself (SC-002 requires zero behavioral
regression in the existing `max(source.weight)` aggregation); the `ze_agents.claims.Confidence`
wrapper (`value=confidence, decay_profile=EVIDENCE_WEIGHTED`) is constructed only at the
`Contribution`-conversion boundary (`person_source_to_contribution()`), not stored as a second
field on `Person` — storing both a raw float and a `Confidence` wrapper for the same value would
be the "fourth bespoke convention" the doctrine is retiring, not a fix.

### `PersonSource` (dataclass, modified)

```python
@dataclass
class PersonSource:
    person_id: UUID
    source_type: str                              # unchanged — plugin-owned inflow tag
    weight: float                                  # unchanged
    claim_kind: ClaimKind = ClaimKind.IDENTITY    # NEW (FR-001, per clarify session)
    provenance: Provenance = Provenance.SYNTHESIZED  # NEW — derived from source_type
                                                   #   via _SOURCE_TYPE_TO_PROVENANCE
    raw_context: str = ""
    id: UUID | None = None
    created_at: datetime | None = None
```

This is the actual per-contribution record `Person.confidence` is aggregated from
(`max(source.weight)` across a person's `PersonSource` rows) — retrofitted per the
`/speckit-clarify` session so provenance is attached at the point of origin, not lost when a
`Person` has sources of differing provenance.

### `PersonRelationship` (dataclass, modified)

```python
@dataclass
class PersonRelationship:
    person_a_id: UUID
    person_b_id: UUID
    relationship_description: str
    confidence: float = 0.5
    source_type: str = "manual"
    claim_kind: ClaimKind = ClaimKind.IDENTITY    # NEW
    provenance: Provenance = Provenance.PROMPT_SUPPLIED  # NEW — derived from source_type
    id: UUID | None = None
    created_at: datetime | None = None
```

### `ContactProposal` (dataclass, modified)

```python
@dataclass
class ContactProposal:
    """Typed output of any contact extraction step (extractors, consolidator, agents)."""

    name: str
    classification: str = "unknown"
    relationship: str = ""
    contact_info: dict[str, str] = field(default_factory=dict)
    confidence: float = 0.5
    confirmed: bool = False
    source_type: str = "conversation"
    claim_kind: ClaimKind = ClaimKind.IDENTITY    # NEW
    provenance: Provenance = Provenance.SYNTHESIZED  # NEW — derived from source_type
    raw_context: str = ""
```

This is also the type `AgentResult.contact_proposals` holds (research.md §3) — no separate
"agent proposal" type is introduced.

### `_SOURCE_TYPE_TO_PROVENANCE` (new module constant, `types.py` or `contribution.py`)

```python
_SOURCE_TYPE_TO_PROVENANCE: dict[str, Provenance] = {
    "manual": Provenance.PROMPT_SUPPLIED,
    "conversation": Provenance.SYNTHESIZED,
    "email": Provenance.LIVE_SEARCH,
    "calendar": Provenance.LIVE_SEARCH,
    "research": Provenance.SYNTHESIZED,
}
```

Unmapped/unknown `source_type` values fall back to `Provenance.SYNTHESIZED` (the least
epistemically-committal value), never raise — matching `loop_to_contribution()`'s
`.get(loop.provenance, Provenance.SYNTHESIZED)` fallback precedent.

## New module — `packages/ze-sdk/ze_sdk/contribution.py`

Re-exports from `ze_plugin.contribution` (mirrors `ze_sdk/channels.py`'s existing pattern —
see research.md §7a):

```python
from ze_plugin.contribution import (
    Contribution,
    EvidenceRef,
    SourceFunction,
    TargetFace,
    validate_and_submit,
)

__all__ = [
    "Contribution",
    "EvidenceRef",
    "SourceFunction",
    "TargetFace",
    "validate_and_submit",
]
```

## New module — `plugins/ze-personal/ze_personal/contacts/contribution.py`

Mirrors `ze_memory/contribution.py`/`ze_worldstate/contribution.py` — a producer-owned
conversion module, importing the shared type only through `ze_sdk.contribution` (never
`ze_plugin.contribution` directly — `ze-personal` is a plugin), never imported by `ze-plugin`
itself (conversion direction stays one-way).

```python
from ze_sdk.contribution import Contribution, SourceFunction, TargetFace
from ze_agents.claims import ClaimKind, Confidence, DecayProfile


def person_source_to_contribution(source: PersonSource) -> Contribution:
    return Contribution(
        claim_kind=ClaimKind.IDENTITY,
        provenance=source.provenance,
        confidence=Confidence(value=source.weight, decay_profile=DecayProfile.EVIDENCE_WEIGHTED),
        target_face=TargetFace.USER,
        source_function=SourceFunction.SOCIAL_COGNITION,
        evidence=[],
    )
```

## Modified type — `core/contracts/ze-agents/ze_agents/types.py`

### `ClaimBearingProposal` (new Protocol)

```python
from typing import Protocol, runtime_checkable
from ze_agents.claims import ClaimKind, Provenance


@runtime_checkable
class ClaimBearingProposal(Protocol):
    claim_kind: ClaimKind
    provenance: Provenance
    confidence: float
```

Mirrors the existing `LLMClient` (`ze_agents/client.py`) / `DBPool` (`ze_agents/db.py`) Protocol
pattern already used in this package to reference a shape without depending on its concrete
implementation. `ClaimKind`/`Provenance` are safe to import — they already live in
`ze_agents.claims`, inside this same package.

### `AgentResult` (dataclass, modified)

```python
@dataclass
class AgentResult:
    ...
    memory_proposals: list[ClaimBearingProposal] = field(default_factory=list)   # was: list
    contact_proposals: list[ClaimBearingProposal] = field(default_factory=list)  # was: list
```

**Why a Protocol, not the concrete types**: `core/contracts/ze-agents` sits at the bottom of the package
graph (`ze-memory → ze-agents`, `ze-personal → ze-sdk → ze-agents` — both depend on
`ze-agents`, never the reverse); importing `ze_memory.types.Fact` or
`ze_personal.contacts.types.ContactProposal` directly from `ze_agents/types.py` would invert the
graph and give core domain knowledge of a plugin's types, violating Principle III.
`ze_plugin.contribution.Contribution` is equally unreachable (`ze-plugin → ze-agents`). The
`ClaimBearingProposal` Protocol is defined *in* `ze-agents`, so no new import edge is created;
any producer's concrete type satisfies it structurally.

**`contact_proposals`** is populated with `ContactProposal` instances (`ze-personal`), which
satisfy `ClaimBearingProposal` once FR-001/FR-002 add `claim_kind: ClaimKind`,
`provenance: Provenance`, `confidence: float` to that dataclass — types match the Protocol
exactly, no adapter needed.

**`memory_proposals`** stays unpopulated — confirmed zero current producers (only the
`field(default_factory=list)` declaration; `eval.py`/`schemas.py` only read its length).
`ze_memory.types.Fact` does **not** currently satisfy `ClaimBearingProposal` (`confidence: float`
present, but `provenance: str` untyped and no `claim_kind` field — Phase 111 added `claim_kind`
only as a `memory_facts` DB column, computed inline in `retriever.py`, never stored on the `Fact`
dataclass). Retrofitting `Fact` itself is out of this feature's scope (FR-001/FR-002 name only
the `Person` family) — the field is typed against the Protocol for whichever future producer
populates it (research.md §3).

## Modified table — `core/contracts/ze-plugin/ze_plugin/contribution.py`

```python
_LICENSE: dict[SourceFunction, frozenset[ClaimKind]] = {
    ...
    SourceFunction.SOCIAL_COGNITION: frozenset({ClaimKind.IDENTITY}),  # was: frozenset()
    ...
}
```

## Schema changes — `zc028_contacts_claim_kind.py` (`ze-personal`, chain tip `zc027`)

| Table | New columns | Backfill |
|---|---|---|
| `contacts` | `claim_kind TEXT NOT NULL`, `provenance TEXT NOT NULL` | `claim_kind = 'identity'` unconditionally; `provenance` derived from the `contacts` row's most recent `contact_sources.source_type` via the Decision 1 mapping (`SYNTHESIZED` if no source row exists) |
| `contact_sources` | `claim_kind TEXT NOT NULL`, `provenance TEXT NOT NULL` | `claim_kind = 'identity'` unconditionally; `provenance` derived from that row's own `source_type` via the Decision 1 mapping |
| `contact_relationships` | `claim_kind TEXT NOT NULL`, `provenance TEXT NOT NULL` | same pattern, keyed off `contact_relationships.source_type` |

No migration for `ContactProposal` — never persisted to its own table (transient
extraction-result type only).
