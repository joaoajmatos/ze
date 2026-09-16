# Quickstart: Mixed Gather+Act → Conductor

1. Confirm 151–154 Implemented.
2. Add gather/act intent helpers next to `apply_conductor_rewrite`.
3. Widen rewrite predicate; keep one function.
4. Fail-first tests in `test_nodes.py` (and routing node tests if decompose path needs them).
5. Add eval `conductor_mixed_gather_act_research_messenger`.
6. Do not split parallel gates. Do not implement 156/157.
