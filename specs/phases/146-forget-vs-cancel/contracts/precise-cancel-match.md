# Contract: Precise cancel match

Identifier spirit from the spec (Phase 143 precision): miss rather than wrong retract; do not cancel the set on a short token.

Function (generic, `ze_agents`):

`precise_label_match(query: str, items: Sequence[tuple[id, label]]) -> Unique | Miss | Ambiguous`

No domain type names in this module.

## Behavior

1. Normalize: strip, casefold, collapse whitespace. Strip a leading cancel-verb prefix (`forget`, `cancel`, `drop`, `abandon`, `close`) and articles (`the`, `my`, `a`, `an`) from the query.
2. Empty remainder → `Miss`.
3. **Exact:** items whose normalized label equals the remainder. One hit → `Unique`. More than one → `Ambiguous`.
4. **Named label in query:** remainder contains the full stored label as a contiguous phrase; label has at least 8 characters or 2+ tokens. One → `Unique`. More than one → `Ambiguous`.
5. **Short token:** if remainder has fewer than 2 tokens, do not substring-match labels (blocks `dentist` cancelling every dentist-labelled reminder).
6. **Optional embedding:** only if caller passes scores; at most one item, cosine ≥ 0.88, runner-up &lt; 0.80; else skip. Never top-N batch.
7. Else `Miss`.

Owning agents MUST list pending/open items, run this match, and call `cancel_reminder` / `close_loop` / `drop_loop` / `abandon_goal` **at most once** and only on `Unique`. `Miss` or `Ambiguous` → no write.

## Forbidden

- `cancel_reminder` deleting all ILIKE / substring hits for a query.
- Cancelling every reminder whose label contains a one-token remainder.

## Tests code against

- Labels `Call the dentist` and `Dentist bill`: query `forget the dentist` → `Ambiguous` or `Miss`, never both cancelled.
- Single pending `Call the dentist`: query `forget the dentist` → `Unique` that id.
- Query `forget that` → `Miss`.
