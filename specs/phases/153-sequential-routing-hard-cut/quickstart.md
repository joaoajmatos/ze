# Quickstart: Sequential Routing Hard-Cut

1. Implement 151 and 152 first.
2. Fail-first: sequential multi → companion; parallel unchanged; `plan_sequential` missing.
3. Delete planner node, state fields, sequential compound loop.
4. Rewrite envelope in decompose/after_decompose; stash hint.
5. Update companion `description` + conductor instructions; add ledger → MessageTrace.
6. Do not add eval YAML or trace panel (154). Do not promote to workflow.
