# ADR: A Fact Perception Reads From the User Is `prompt_supplied`

> **Status:** Accepted
> **Date:** 2026-10-22 (architecture review; implemented by phase 199)
> **Scope:** The `Provenance` stamped on facts that perception writes from conversation, ingestion,
> inbound messages and calendar. The dream pass's decay and expiry rules.

---

## Context and Problem Statement

The doctrine reserves `synthesized` for reflection: a dream or correlation output that passed the
promotion gate (`ze-doctrine.md`, "reflection may never emit a fact"). The code drifted from that:

- The conversation extractor and the ingestion sink stamp every extracted fact `SYNTHESIZED`
  (`ze_core/orchestration/nodes/memory.py`, `ze_ingestion/sink.py`).
- Contact facts from email and calendar are stamped `LIVE_SEARCH`, though nothing searched the web
  (`ze_personal/contacts/types.py`).

The dream pass decays every uncorroborated `synthesized` fact older than 30 days by 0.03 a night. It
clears `reviewed` below 0.50 and sets `contradicted` below 0.25 (`dream/promoter.py`). The only thing
that sets `corroborated` is a later episode with cosine ≥ 0.88 to the fact. So a fact the user said
once, such as "I'm vegetarian", starts to decay after a month, and about 19 nights later it is marked
contradicted. That breaks the doctrine rule that stated beliefs outrank inferred ones.

Does an extractor's paraphrase of the user's own words count as "supplied by the user", or as "Ze's
synthesis"?

## Considered Options

1. **`prompt_supplied`, the existing value.** It applies to anything perception reads from the user,
   or from sources the user owns: their words, their documents, their mailbox and their calendar.
2. **A new `extracted` provenance.** This is more precise, but it amends the doctrine's four-value
   vocabulary, and every switch on `Provenance` would have to learn the new value.
3. **Keep `synthesized`, and have decay select by source function instead.** This fixes the decay
   bug, but `synthesized` would keep two meanings, and every other reader of provenance would still
   be wrong (retrieval contamination rules, posture).

## Decision Outcome

**Option 1.**

- Perception stamps facts it reads from the user or the user's own sources `prompt_supplied`.
- `live_search` means a search of the web, and nothing else.
- `synthesized` means a reflection output, and nothing else.
- The dream pass's decay and expiry also check `creation_method`. They touch only facts the dream
  wrote, so a wrong provenance cannot bring the bug back.
- A one-time migration re-stamps existing facts and restores the ones decay damaged. It re-stamps
  facts whose `creation_method` is `extracted` or `explicit`, and resets `reviewed` and
  `contradicted` where decay alone set them. This is a pre-v1 hard cut (`pre-v1-hard-cuts.md`); no
  dual reading.

## Consequences

- Retrieval rules that treat `synthesized` facts as possible session contamination now apply only
  to reflection output, which was their intent.
- Inflow (conversation, email, calendar, ingestion) is not provenance. It stays a separate field
  (`plugin-domain-vocabulary.md`).
