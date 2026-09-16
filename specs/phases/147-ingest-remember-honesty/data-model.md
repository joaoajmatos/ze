# Data Model: Ingest vs Remember Honesty

No new tables.

| Write | Provenance | User-visible remember-tool success |
|---|---|---|
| `MemorySink` / ingest extraction | `SYNTHESIZED` perception | Never |
| `remember_fact` `ok` true (companion) | `PROMPT_SUPPLIED` biography | Allowed (143) |
| `remember_fact` missing or `ok` false | — | Forbidden |

Mixed turn: two actions; two honesty rules. File-as-whole is ingest, not remember.
