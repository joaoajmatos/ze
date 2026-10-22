# ADR: Executive Is Licensed for Priority and Suspicion Only

> **Status:** Accepted
> **Date:** 2026-10-22 (architecture review; implemented by phase 199)
> **Scope:** The `_LICENSE` table in `ze_plugin/contribution.py`, and which source function submits
> open loops.
> **Amends:** `contribution-seam.md` (candidate loops are attributed to Executive, not Perception).

---

## Context and Problem Statement

The doctrine's licensing table says Executive produces "priorities, open-loop state" and may not
produce "facts about the world" (`ze-doctrine.md`). The code still has the Phase 124 placeholder,
which licenses Executive for all five claim kinds (identity, fact, inference, suspicion, priority).
So the type-enforced doctrine, which is the seam's main promise, is not enforced for its busiest
producer.

`contribution-seam.md` attributes "candidate loops" to Perception, but the code submits every loop
as Executive. One of the two is wrong.

## Considered Options

1. **Narrow Executive to {priority, suspicion} and keep loops under Executive.** Perception observes
   ("Ana asked for the budget by Friday", a fact). Executive interprets ("you owe Ana the budget", a
   loop).
2. **Move extracted loops to Perception.** Perception would then need a suspicion licence, which
   gives the function that observes the right to hold hunches.

## Decision Outcome

**Option 1.**

- Executive's licence is `{PRIORITY, SUSPICION}`. Today's producers (`ze_priority/contribution.py`
  and `ze_worldstate/contribution.py`) already submit only these kinds, so nothing has to change
  upstream.
- Perception's licence stays `{FACT, FEEDBACK_RECORD}`.
- A loop's claim kind follows its state (`loop-claim-kind-from-state.md`).
- `contribution-seam.md` is corrected to attribute candidate loops to Executive.
