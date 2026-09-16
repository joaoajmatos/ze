# Contract: Prompt assembly

Pinned identifiers: `_format_memory`, `_build_system_prompt`, `TurnSurfacing`.

## Order invariant

In the assembled system prompt string, a unique constitution marker (e.g. a heading `Ze constitution`) MUST appear before both the agent job text and the biography/memory block. The biography/memory block MUST appear after the agent job.

## `_format_memory` line shape

Each fact line MUST include predicate, value, provenance (doctrine enum name or stable label), confidence, and recency (relative or ISO date). Do not use the obsolete `"raw"` / `"synthesized"` string dialect as the only signal.

## Always-on

Reviewed, non-contradicted facts MUST be present even when cosine similarity would have dropped them, subject to the existing ~200 token fact budget (reviewed consume the budget first).

## Mentions

No new fact inline-mention component. `TurnSurfacing` continues to cover loops/goals only.

## Out of scope

Constraint veto on mail/calendar tools.
