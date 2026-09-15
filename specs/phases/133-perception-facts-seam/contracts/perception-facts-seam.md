# Contract: Perception-fact contribution submit

Internal Python interface. No new REST routes. Identifiers pinned in the spec.

## `fact_to_contribution`

```python
def fact_to_contribution(
    fact: Fact,
    *,
    provenance: Provenance,
    target_face: TargetFace,
    evidence: list[EvidenceRef] | None = None,
) -> Contribution:
    ...
```

Always `claim_kind=ClaimKind.FACT`, `source_function=SourceFunction.PERCEPTION`.

## `submit_perception_facts`

Name may be singular-in-a-loop; the public helper MUST accept a sequence of facts each paired with envelope fields (or stamp provenance inside from an explicit-predicate set).

```python
async def submit_perception_facts(
    store: MemoryStore,
    items: Sequence[PerceptionFactSubmit],
) -> None:
    ...

@dataclass
class PerceptionFactSubmit:
    fact: Fact
    provenance: Provenance  # SYNTHESIZED | PROMPT_SUPPLIED
    target_face: TargetFace
    evidence: list[EvidenceRef]
```

For each item:

1. `contribution = fact_to_contribution(...)`
2. `await submit_and_detect_collisions(contribution, write, result_id=lambda fact_id: fact_id, producer_kind="fact", ...)`
3. `write` = persist that one `Fact` (existing contradiction check + INSERT), return UUID

License violations raise the existing typed seam errors **before** persist. Callers that today swallow store errors MAY catch and log the same way.

## Call-site stamps (verbatim)

| Caller | `provenance` | `target_face` | evidence / `source_refs` |
|---|---|---|---|
| `write_memory` extracted | `Provenance.SYNTHESIZED` | `USER` | none required |
| `write_memory` explicit `memory_proposals` | `Provenance.PROMPT_SUPPLIED` | `USER` | none required |
| `MemorySink.push` | `Provenance.SYNTHESIZED` | `WORLD` | `EvidenceRef(kind="ingestion", id=UUID(ingestion_id))` when parseable; always `source_refs` |
| messenger `_extract_facts` | `Provenance.SYNTHESIZED` | `USER` | none required |
| onboarding `memory_fact` | `Provenance.PROMPT_SUPPLIED` | `USER` | none required; `reviewed=True` |
| `_promote_learnings` | `Provenance.SYNTHESIZED` | `USER` | `EvidenceRef(kind="goal", id=goal.id)` + `source_refs` |

## `MemoryStore.propose_facts`

Remains on the Protocol. Signature unchanged. Listed call sites MUST NOT invoke it as the ungated front door. Tests MAY still mock it as the persist callback.

## `EvidenceRef.kind`

```python
Literal["fact", "episode", "signal", "ingestion", "goal"]
```

Dangling: skip `"ingestion"` and `"goal"` when no checker is supplied.

## Forbidden this phase

- New routes
- Changes to `surface_loops`, resume recap, `rank_subset`, push budget
- Deleting `propose_facts` from `MemoryStore`
- Rewiring `signal_sources()`
