# CF-04: contacts consolidator on `memory_episodes`

Status: Implemented on the CF-04 cleanup floor (2026-10-16). Findings R-06 and S-09 in
`specs/arch/cleanup-report-2026-10.md`.

## Problem

`ContactsConsolidator` (nightly `contacts_consolidation` job, phase 12) read
`FROM episodes WHERE contacts_extracted = false AND is_archive = false` and marked rows
with `UPDATE episodes SET contacts_extracted = true`. Since the memory rewrite, turns are
written to `memory_episodes` and nothing inserts into `episodes`. The job found no
episodes, so contact, project and relationship extraction from conversation stopped.
`episodes`, `user_facts` and `user_profile` (`zc001`) and the `zc013` column are dead
schema.

## Decision

1. The consolidator reads `memory_episodes`. Turn episodes only: rows with
   `agent = 'consolidator'` (session summaries and archive rows written by the memory
   consolidation job) are skipped, which replaces the old `is_archive = false` filter.
   Those rows restate turns that were already extracted.
2. Progress is a keyset watermark owned by ze-personal, not a flag column on a
   ze-memory table. One row in `contacts_episode_watermark`:
   `(last_created_at, last_episode_id)`. The job selects
   `(created_at, id) > (last_created_at, last_episode_id)` ordered by `created_at, id`,
   at most `contacts.consolidation.max_episodes_per_run` rows, and moves the watermark
   to the last row of each batch after the batch is stored.
3. No watermark row means "start at the oldest episode". The backlog drains at
   `max_episodes_per_run` (default 50) per run, as the old flag column did.
4. ze-memory consolidation archives raw episodes older than
   `memory.consolidation.episode_archive_days` (default 7) into session summaries and
   deletes them. An episode archived before extraction is not extracted. At the default
   50 episodes per run, the nightly job keeps up while the user averages fewer than 50
   turns a day; above that, raise `contacts.consolidation.max_episodes_per_run`. This is
   accepted for a single-user assistant.
5. Migrations (one `zc` chain; numbers set by the Maestro, rechained on land):
   - `zc035` (ze-personal): create `contacts_episode_watermark`; drop `zc013`'s
     `episodes.contacts_extracted` column and index.
   - `zc036` (ze-core): drop `user_facts`, `episodes`, `user_profile`.

## Not changed

The extraction prompt, batch size, contribution seam path and report shape stay the
same. No new config keys.
