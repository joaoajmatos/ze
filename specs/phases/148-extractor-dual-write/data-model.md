# Data Model: Extractor Dual-Write

No new tables.

## Same-turn identity

`FactIdentity = (normalize(predicate), normalize(value))`

Current row: `memory_facts` where `contradicted = false`.

## Persist rule

After extraction returns proposals, drop any proposal whose identity is in the set of this turn’s `remember_fact` calls with payload `ok is True`.

If no such remember, extraction may still admit (140 gate).

## Failure classes (tests)

| Name | Assert |
|---|---|
| Model-lie | Reply claim without `ok` (143) |
| Extractor-duplicate | Two current rows after remember + extract |
