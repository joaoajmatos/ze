# ADR: A Resolved Suspected Loop Is Closed, Not Dropped

> **Status:** Accepted
> **Date:** 2026-10-22 (architecture review; implemented by phases 199 and 203)
> **Scope:** The open-loop transition table and the resolve path for conversation, email, calendar
> and ingestion.

---

## Context and Problem Statement

When a turn or an email says something is done, the inflow looks for a matching loop that is
`suspected`, `active` or `drifting`, and moves it to `closed`. The transition table does not allow
`suspected → closed`, so the store raises an error. The inflow catches it and logs
`loop_extraction_failed`. As a result, "that's done" never resolves a loop that nobody confirmed, and
the loop stays in Needs you.

## Considered Options

1. **Close it.** Add a `suspected → closed` edge for the resolve event only.
2. **Drop it.** `dropped` means "not real, or not wanted". It stores a dismissed-evidence fingerprint
   that stops the same evidence from bringing the loop back.
3. **Confirm, then close.** That is two transitions, and it records a confirmation the user never
   gave.

## Decision Outcome

**Option 1.** Saying it is done is evidence that the concern was real and is now finished. So the
loop moves to `closed`, and the resolving evidence is recorded on it.

The new edge belongs to the resolve event alone. The REST confirm route, the user drop route, decay
and the drift sweep keep the transitions they have. `dropped` keeps its meaning, and its fingerprint
is never written by a resolve.
