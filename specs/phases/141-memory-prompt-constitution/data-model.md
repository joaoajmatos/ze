# Data Model: Memory Prompt Constitution (Phase 141)

## Fact (projection)

Add `created_at: datetime | None` if absent so `_format_memory` can show recency. No migration.

## MemoryContext

Unchanged type. `CompanionPolicy.retrieve` fills `facts` as: reviewed-always-on ∪ similarity survivors, reviewed first, then `budget_facts`.

## Prompt sections (logical, not stored)

1. Datetime
2. Shared constitution (static string on `BaseAgent`)
3. Agent job (`agent_instructions`)
4. Biography: persona traits + profile facets + `_format_memory` + contacts
5. Existing runtime notes: screen, resume recap, `open_priorities_note` (`TurnSurfacing`), skills, procedures

Open items remain entity `TurnSurfacing`; not facts.
