# Data Model: Response-Level Unsolicited Recitation

No new tables.

## Reply classes (same turn)

| Class | Trigger | Gate action |
|---|---|---|
| Unearned remember/forget confirmation | 143 regex + no `ok` true | Strip / 143 fallback |
| Earned confirmation | `remember_fact` / `forget_fact` `ok` true | Keep |
| Unsolicited recitation | Memory-reveal framing of biography without asked recall | Strip; non-store fallback if empty |
| Asked recall | User asked what Ze knows / named fact | May state facts |
| Open items | `TurnSurfacing` wording | Leave alone |
| Task paraphrase | “you asked me to send…” | Not recitation |

## Detection

Conservative regex family: “I remember that you…”, “I remember you…”, “as I recall you…”, close multilingual equivalents. Sentence split reuses 143.
