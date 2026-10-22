# ADR: Commitments Are Linked Records, Not One Store

> **Status:** Accepted
> **Date:** 2026-10-22 (records executive-function D3, 2026-10)
> **Scope:** Open loops, goals, reminders and waiting-on, and how one commitment spans them.
> **Clarifies:** `aperture-decision.md` ("a goal is the special case: an open loop the user declared").

---

## Context and Problem Statement

One thing the user owes can live in several stores:

- an open loop (ze-worldstate);
- a goal (ze-automation);
- a reminder (ze-calendar);
- task state (ze-memory).

`aperture-decision.md` reads as if a goal were a kind of loop, but the code keeps separate stores,
linked by `open_loops.goal_id` and `open_loops.reminder_id`. Executive-function D3 chose to link
them and to revisit after dogfooding. That choice was never recorded as an ADR, so later reviews keep
proposing to merge the stores.

## Considered Options

1. **Linked records.** Each store owns its lifecycle (reminders fire, goals plan, loops drift), and
   the records link to each other.
2. **One commitment store with kinds.** One lifecycle would have to cover firing times, multi-week
   plans and drift, and every owner package would depend on it.

## Decision Outcome

**Option 1.**

- A **commitment** is a domain concept, not a table.
- One utterance creates at most one record (commitment intake, phase 173), and links it to a
  matching record that already exists.
- **Waiting-on** (phase 174) is an open loop with a direction, *I owe* or *I await*. It is not a new
  store.
- A conditional reminder, such as "remind me Friday if Ana hasn't replied", is a reminder linked to
  an awaiting loop. Closing the loop cancels the reminder.
- Revisit this decision after the dogfood data that phase 175 needs, and only if the links cause real
  friction.
