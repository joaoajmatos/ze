# Contract: `memory_facts` provenance hard-cut

Package: `core/cognition/ze-memory`
Revision: `zm020` (`zm020_facts_doctrine_provenance.py`)
`down_revision`: `zm019` (or next free if `zm020` is taken)

## Upgrade

1. Abort if any row has `provenance` outside
   `{raw, synthesized, graph_recall, live_search, prompt_supplied}` and not NULL.
   (`raw` is input-only; it is rewritten in step 2.)
2. `UPDATE ... SET provenance = 'prompt_supplied' WHERE provenance IS NULL OR provenance = 'raw'`.
3. `ALTER TABLE memory_facts ALTER COLUMN provenance DROP DEFAULT`.
4. `ALTER TABLE memory_facts ALTER COLUMN provenance SET NOT NULL` (already NOT NULL; reaffirm).
5. Add CHECK:

```sql
ALTER TABLE memory_facts ADD CONSTRAINT memory_facts_provenance_doctrine
  CHECK (provenance IN (
    'graph_recall', 'live_search', 'prompt_supplied', 'synthesized'
  ));
```

Existing partial index `idx_memory_facts_provenance` (`WHERE provenance = 'synthesized'`) stays.

## Downgrade

Drop CHECK; restore `DEFAULT 'raw'` (dev-only; pre-v1). Do not attempt to restore which rows
were historically `raw` vs `prompt_supplied`.

## Read SQL

Forbidden: `COALESCE(provenance, 'raw')` on `memory_facts`.
Allowed: `WHERE provenance = 'synthesized'` for decay/corroboration (doctrine value).
