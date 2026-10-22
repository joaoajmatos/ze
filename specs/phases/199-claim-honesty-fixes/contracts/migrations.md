# Contract: migrations

| Revision | Package / chain | Down revision | Effect | Test constant |
|---|---|---|---|---|
| `zm026` | ze-memory / `zm` | `zm025` | Re-stamp perception facts (`synthesized`, no `dream_run_id`) to `prompt_supplied` with claim kind `fact`; log `restamped` and `decay_damaged` counts | `COUNT_SQL`, `REPAIR_SQL` |
| `zw006` | ze-worldstate / `zw` | `zw005` | `ALTER TABLE open_loops DROP COLUMN claim_kind`; downgrade re-adds it, filled from `state` | — |
| `zc041` | ze-personal / `zc` | `zc040` | Re-stamp `contact_sources.provenance` from `source_type`; `contacts.provenance` from the earliest source | `REPAIR_SQL` |

All three are idempotent. The two re-stamps have no-op downgrades (pre-v1 hard cut; the old labels were wrong). Each re-stamp has a test-pg test that runs its SQL constant on seeded rows twice.
