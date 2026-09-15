# Contract: `MemoryStore` fact write

## Public Protocol (`ze_memory.store.MemoryStore`)

**Remove**:

```python
async def propose_facts(self, proposals: list[Fact]) -> None: ...
```

No replacement method on the Protocol. `ze_sdk.memory.MemoryStore` re-export follows.

## Private persist (`PostgresMemoryStore`)

```python
async def _persist_facts(self, proposals: list[Fact]) -> None:
    """Contradiction check + INSERT. Not part of MemoryStore. Bound as Contribution write=."""
```

Behavior inherited from today's `propose_facts` loop: per-fact
`_write_fact_with_contradiction_check`; log and continue on per-fact failure.

`_write_fact_with_contradiction_check` MUST INSERT `provenance` (`fact.provenance.value`) and
`claim_kind` (`fact.claim_kind.value`). MUST NOT omit provenance.

## Seam binding (Phase 133 owns the submit; 134 retargets the callback)

After this phase, every perception `submit_and_detect_collisions(..., write=...)` uses
`_persist_facts` / a lambda that calls it — never `store.propose_facts`.

If a production module still calls `propose_facts` as a front door, implementation of this
contract **stops** (spec FR-007). Tests may call `_persist_facts` directly.

## Typed errors

Unknown `provenance` / missing required `claim_kind` on persist: subclass of `ZeError` from
`ze_sdk.errors` / `ze_agents.errors`, not bare `ValueError`.
