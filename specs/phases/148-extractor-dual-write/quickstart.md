# Quickstart: Extractor Dual-Write

1. `remember_fact` `ok` true for `(preference, aisle seats)`.
2. Run extraction on the same prompt/response that restates that fact.
3. Assert one current fact for that identity.
4. Separate test: no `ok`, model says “I’ll remember” → honesty test fails on reply, not row count.
5. Confirm `_remembered_predicates` no longer keys skip on `ToolCall.success` + predicate-only.
