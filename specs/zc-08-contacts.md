# Ze Core — Contacts — Spec

## Purpose

Contacts and channel handles are framework-level primitives: who people are and
how to reach them. Ze is a single-user assistant today, but the contacts model is
not Ze-specific — it belongs in ze-core alongside memory and channels.

This spec migrates `PersonStore`, contact types, and `ContactChannelStore` from
`ze/contacts/` into `ze_core/contacts/`. Ze-specific behaviour — contact extraction
from episodes (`ContactsConsolidator`) and tool-call parsing (`extractors.py`) —
stays in `ze/`.

The channel abstraction (`Channel` ABC, `ChannelRegistry`, `ChannelType`,
`ChannelHandle`) is already in `ze_core/channels/` (Phase 18). This spec adds the
contacts side of that relationship.

---

## Out of Scope

- New contact fields or schema changes.
- Moving `ContactsConsolidator` — it depends on `OpenRouterClient`, Ze `Settings`,
  and the Ze-specific `episodes` table; it stays in `ze/contacts/`.
- Moving `extractors.py` — it depends on `ze.agents.types.ToolCall` and Ze-specific
  tool names (`get_email`, `list_events`); it stays in `ze/contacts/`.
- Moving `EmailChannel` — Gmail-specific transport; it stays in `ze/`.

---

## Repository Layout

### Before

```
packages/
├── ze-core/ze_core/
│   └── channels/
│       ├── base.py          # Channel ABC
│       ├── registry.py      # ChannelRegistry
│       └── types.py         # ChannelType, ChannelHandle, Message, Thread, …
└── ze/ze/
    └── contacts/
        ├── types.py         # Person, PersonSource, PersonRelationship, …
        ├── store.py         # PersonStore
        ├── channel_store.py # ContactChannelStore
        ├── consolidator.py  # ContactsConsolidator  ← stays
        └── extractors.py    # extract_email_contacts ← stays
```

### After

```
packages/
├── ze-core/ze_core/
│   ├── channels/            # unchanged
│   └── contacts/
│       ├── __init__.py
│       ├── types.py         # Person, PersonSource, PersonRelationship,
│       │                    # PersonCandidate, PersonContext, StaleFollowUpNudge,
│       │                    # SOURCE_WEIGHTS
│       ├── store.py         # PersonStore
│       └── channel_store.py # ContactChannelStore
└── ze/ze/
    └── contacts/
        ├── __init__.py      # re-exports from ze_core.contacts (compat shim)
        ├── consolidator.py  # unchanged
        └── extractors.py    # unchanged
```

---

## Types (`ze_core/contacts/types.py`)

Moved verbatim from `ze/contacts/types.py`. No changes to field names or defaults.

```python
SOURCE_WEIGHTS: dict[str, float] = {
    "manual":       1.0,
    "conversation": 1.0,
    "email":        0.7,
    "calendar":     0.6,
    "research":     0.2,
}

@dataclass
class Person:
    name: str
    aliases: list[str]
    classification: str             # "personal" | "professional" | "unknown"
    classification_confidence: float
    relationship_to_user: str
    contact_info: dict[str, str]    # unstructured; structured handles go in contact_channels
    notes: str
    confirmed: bool
    dismissed: bool
    confidence: float               # max(source.weight) across all sources
    id: UUID | None
    first_seen: datetime | None
    last_mentioned: datetime | None
    created_at: datetime | None
    updated_at: datetime | None

@dataclass
class PersonSource:
    person_id: UUID
    source_type: str   # "conversation" | "manual" | "email" | "calendar" | "research"
    weight: float
    raw_context: str
    id: UUID | None
    created_at: datetime | None

@dataclass
class PersonRelationship:
    person_a_id: UUID
    person_b_id: UUID
    relationship_description: str
    confidence: float
    source_type: str
    id: UUID | None
    created_at: datetime | None

@dataclass
class PersonCandidate:
    """Intermediate type produced by extraction — not yet persisted as a Person."""
    name: str
    inferred_classification: str
    inferred_relationship: str
    raw_context: str
    source_type: str

@dataclass
class PersonContext:
    people: list[Person]
    token_estimate: int

@dataclass
class StaleFollowUpNudge:
    name: str
    days_ago: int
```

`ContactsConsolidationReport` is not moved — it is a Ze consolidator output type
and stays in `ze/contacts/consolidator.py`.

---

## `PersonStore` (`ze_core/contacts/store.py`)

Moved verbatim from `ze/contacts/store.py`. The only import change is the logger:

```python
# before
from ze.logging import get_logger

# after
from ze_core.logging import get_logger
```

All SQL, row-mapping helpers (`_person_from_row`, `_source_from_row`), and method
signatures are unchanged.

---

## `ContactChannelStore` (`ze_core/contacts/channel_store.py`)

Moved verbatim from `ze/contacts/channel_store.py`. Already imports from
`ze_core.channels.types` — only the logger import changes:

```python
# before
from ze.logging import get_logger

# after
from ze_core.logging import get_logger
```

---

## Compat Shim (`ze/contacts/__init__.py`)

To avoid updating every callsite in `ze/` at once, `ze/contacts/__init__.py` re-exports
all public names from `ze_core.contacts`:

```python
from ze_core.contacts.types import (
    SOURCE_WEIGHTS,
    Person,
    PersonCandidate,
    PersonContext,
    PersonRelationship,
    PersonSource,
    StaleFollowUpNudge,
)
from ze_core.contacts.store import PersonStore
from ze_core.contacts.channel_store import ContactChannelStore

__all__ = [
    "SOURCE_WEIGHTS",
    "Person",
    "PersonCandidate",
    "PersonContext",
    "PersonRelationship",
    "PersonSource",
    "StaleFollowUpNudge",
    "PersonStore",
    "ContactChannelStore",
]
```

Callers in `ze/` that already import from `ze.contacts.*` continue to work without
change. The individual submodule files (`ze/contacts/store.py`,
`ze/contacts/types.py`, `ze/contacts/channel_store.py`) are deleted — they are
replaced by the shim.

New code in `ze/` should import from `ze_core.contacts` directly.

---

## Container

`ze/container.py` wires `PersonStore` and `ContactChannelStore`. The import path
changes from `ze.contacts.store` / `ze.contacts.channel_store` to
`ze_core.contacts.store` / `ze_core.contacts.channel_store`. The wiring logic and
constructor arguments are unchanged.

---

## No Migration Required

This phase is a pure code reorganisation. The database schema (`contacts`,
`contact_sources`, `contact_relationships`, `contact_channels` tables) is
unchanged.

---

## Testing

- Existing tests in `tests/contacts/test_store.py` and
  `tests/contacts/test_channel_store.py` update their import paths to
  `ze_core.contacts.*` and otherwise remain unchanged.
- No new test files are needed — this is a move, not a behaviour change.
- The compat shim is not tested separately; its correctness is validated
  transitively by any test that imports from `ze.contacts`.

---

## What This Enables

After this phase:

- ze-core owns the full contact primitive: who people are (`PersonStore`, types)
  and how to reach them (`ContactChannelStore`, `ChannelHandle`) — symmetric with
  how ze-core owns memory.
- A future ze-core-based app gets contacts and channels for free, supplying only
  its own extractors and consolidator.
- `ze_core/channels/` and `ze_core/contacts/` form a coherent framework layer:
  channel handles belong to contacts, contacts are persisted by `PersonStore`,
  sends go through `ChannelRegistry`.
