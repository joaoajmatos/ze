# Contract: Forget match (`_retract_facts_matching`)

Identifier from the spec: `_retract_facts_matching`.

## Signature (unchanged)

`async def _retract_facts_matching(self, query: str) -> list[UUID]`

Private on the memory store. No public alias of the old substring/top-5 behavior.

## Behavior

1. Blank query → `[]`, no `UPDATE`.
2. Load up to 200 rows with `contradicted = false` (same cap as today).
3. Select ids by the ladder in `data-model.md` (exact → named value in query → long query phrase in value → unique embedding). **Stop at the first non-empty class.**
4. Forbidden (deleted, not flagged):
   - Retract because the query is a short substring of `predicate` or `value`.
   - Retract cosine ≥ 0.75 top 5 as a batch.
5. Embedding fallback: at most one id; cosine ≥ 0.88; runner-up cosine < 0.80 or absent; skip rows with null embedding.
6. If ids non-empty, `UPDATE memory_facts SET contradicted = true WHERE id = ANY(...)`.
7. Return the retracted ids (empty list on miss).

## `forget_fact` mapping (unchanged shape)

- Empty ids → `{"ok": false, "error": "no matching fact"}`
- Else → `{"ok": true, "ids": [...]}`

Precision over recall: better `ok` false than the wrong rows.
