# Contract: Same-turn remember vs extract

- Post-turn extraction MUST NOT persist a second current fact for the same identity as a successful in-turn `remember_fact` (`ok` true) on that turn.
- Extraction MUST remain available for identities not remembered this turn.
- Identity is 140 predicate+value after existing normalize, not embedding merge.
- `speech_act` remains LLM JSON; this phase MUST NOT add a hard non-LLM classifier.
- There MUST NOT be a second extract persist path that ignores this rule.
- Tests MUST distinguish model-lie (143) from extractor-duplicate (cardinality).
