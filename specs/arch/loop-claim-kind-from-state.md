# ADR: An Open Loop's Claim Kind Follows Its State

> **Status:** Accepted
> **Date:** 2026-10-22 (architecture review; implemented by phase 199)
> **Scope:** `OpenLoop.claim_kind`, the `open_loops.claim_kind` column, and every posture and ranking
> that reads it.

---

## Context and Problem Statement

A loop gets a claim kind when it is created. A suspected loop gets `SUSPICION`; a declared or
tracked loop gets `PRIORITY`. Nothing changes the kind afterwards:

- A user confirmation (`stamp_declared`) leaves it as it was.
- Corroboration promotion (`promote`) leaves it as it was.

So a loop the user confirmed is still drawn as a dotted hunch on World (`compose/rules.py`,
`claim_tone`), and `PriorityItem.claim_kind` carries the same stale kind.

Every transition would have to remember to rewrite the kind. That is a rule callers forget.

## Considered Options

1. **Derive the kind from state.** It is not stored.
2. **Store the kind, and rewrite it on confirm and promote.** This keeps a column that every new
   transition must remember to update.
3. **Drop claim kind from loops** and draw posture from state alone. Loops would then be the one
   world-state item outside the shared claim vocabulary (`claim-topology.md`).

## Decision Outcome

**Option 1.** A loop's claim kind describes its standing now, not where it came from:

| State | Claim kind |
|---|---|
| `suspected` | suspicion |
| `active`, `drifting`, `closed` | priority |
| `dropped` | none (not shown) |

This fits the doctrine. Open-loop state is Executive's output, and Executive produces priorities and
suspicions (`executive-licence.md`). A loop is a judgment about what deserves attention, not a fact
about the world. Where a loop came from is recorded by its inflow and its origin source row, not by
its claim kind.

The `open_loops.claim_kind` column is dropped as a pre-v1 hard cut. Contributions still declare a
claim kind when a loop is created, and it matches this table, so the contribution seam does not
change.
