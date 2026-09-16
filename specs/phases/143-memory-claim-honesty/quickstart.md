# Quickstart: 143 memory claim honesty

Phase 140 tools exist. This phase does not add tools.

## Implementer order

1. Matcher tests in `core/cognition/ze-memory/tests/test_forget_retract.py` (substring must **not** retract; exact and named-value must; cosine batch must **not**).
2. Change `_retract_facts_matching` until those tests pass.
3. Gate unit tests in `plugins/ze-personal/tests/agents/companion/test_memory_claim_honesty.py`.
4. Wire `CompanionAgent.run` (buffer `token_sink`, gate response) and hard-cut `stream`.
5. Hard-cut eval criteria that reward unearned “I’ll remember.”
6. `make test-memory` and `make test-personal` (and lint).

## Manual check

- “Remember that I prefer dark mode” with a mocked model that replies “I’ll remember that” and **no** tool → user-visible text does not claim memory; sink must not have streamed the lie first.
- Same with `remember_fact` `{ok: true}` → confirmation allowed.
- Seed two facts, forget query `mode` → `ok` false, neither retracted.
- Seed `preference` / `dark mode`, forget `dark mode` → that row retracted.

## Out of scope while implementing

P5 mail/calendar veto, speech-act classifier rewrite, specialist catalogs, `/memories` filesystem, 140–142 contract rewrites.
