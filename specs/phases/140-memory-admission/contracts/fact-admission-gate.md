# Contract: Fact admission gate

Post-turn `extract_facts` (policy name in spec: `extract_facts`) MUST:

1. Return `[]` for empty, greeting, ephemeral, mood, weather, and **commitment** / timed to-do content.
2. Emit facts only in closed families: `identity`, `preference`, `relationship`, `constraint`, `contact_detail`.
3. Stamp surviving facts `Provenance.SYNTHESIZED` at `write_memory` (existing 133 behavior).
4. Dedup predicates already written this turn by `remember_fact`.
5. Still persist via `submit_perception_facts` — not `propose_facts`.
