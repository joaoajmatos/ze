# Data Model: Memory Admission (Phase 140)

## AdmittedFact (existing `Fact`)

Unchanged schema. This phase **sets** fields:

| Field | remember_fact | gated extraction |
|---|---|---|
| `predicate` | tool arg, snake_case from closed family or user-aligned label | closed family label |
| `value` | tool arg | extractor value |
| `provenance` | `PROMPT_SUPPLIED` | `SYNTHESIZED` |
| `reviewed` | `true` | `false` unless already reviewed |
| `claim_kind` | `FACT` | `FACT` |
| `contradicted` | false on insert | false on insert |
| `confidence` | high default (e.g. 0.95) | extractor 0–1, capped |

No new tables.

## PredicateFamily (extractor-only enum, not a DB column)

`identity` | `preference` | `relationship` | `constraint` | `contact_detail`

Unknown / `commitment` / `ephemeral` → no row.

## Forget

State transition: matching `Fact.contradicted` false → true. Retrieval (`contradicted = false`) hides it. No physical delete this phase.

## AgentResult (hard-cut)

Remove `memory_proposals: list[ClaimBearingProposal]`. Contact proposals unchanged.

## ExtractionGateResult (in-memory)

`keep: bool`, `family: PredicateFamily | None`, `facts: list[Fact]`. Empty list when `keep` is false.
