# ADR: The Memory-Graph Person Entity Is the Canonical Person Id

> **Status:** Accepted
> **Date:** 2026-10-22 (architecture review; implemented by phase 211)
> **Scope:** The id that contacts, graph entities, relationship nudges, priority items and
> contributions use for one person.

---

## Context and Problem Statement

One person ("Ana Silva") has three ids:

- the contacts row id (`contacts.id`, owned by ze-personal);
- a `person` entity in the memory graph (`memory_entities`, owned by ze-memory);
- `uuid5(name)` in relationship ranking (`ze_priority/scoring.py`).

The contact contribution sends the contacts id as `entity_ids`, so the collision check compares ids
from two different spaces. A rename can split the person across the three records.

## Considered Options

1. **The graph entity is canonical.** The contact row references it one-to-one.
2. **The contacts row is canonical.** Contacts live in a plugin, so core packages (worldstate,
   priority, collision) would have to key on an id a plugin owns.
3. **Keep three ids and add a mapping table.** That is a fourth record to keep in step.

## Decision Outcome

**Option 1.**

- Every core package can see the memory graph, and the graph already models people as entities with
  relationships.
- A contact is the person's address book projection. It holds aliases, channels and relationship,
  and points to exactly one `person` entity.
- Relationship nudges, priority items and contributions use the entity id.
- A rename changes names on the entity and the contact, never an id.
- `uuid5(name)` is removed.
