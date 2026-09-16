# Research: Promote Conductor Instance to Workflow/Goal

**Feature**: `157-promote-conductor-instance`  
**Date**: 2026-09-16

## 1. Offer vs create

**Decision:** Default is **offer**. Silent `create_goal` / `create_workflow` is forbidden on timeout, abort, and turn-end unfinished. Explicit user “keep going on this” (or accept of the offer) starts create via delegate, still under 152.

**Rejected:** Auto-insert a workflow on every unfinished conductor (surprise durable jobs). Making timeout auto-create so work is never lost (violates confirm-the-write).

## 2. Goal vs workflow (pinned)

**Decision:**

- **Goal** if the remaining job is a multi-week outcome with milestones (142 R6).
- **Workflow** if the remaining job is a named, repeatable, or schedulable sequence the user wants unattended.
- **Ambiguous:** one ask (goal or workflow), never both.
- In-chat sequence that can finish **this turn** stays conductor (153/155); promote is only the durable escape.

**Rejected:** Always workflow (goals exist for multi-week). Always goal (recurring mail reports are workflows). Procedure as the third type.

## 3. Procedures stay out

**Decision:** Promote path MUST NOT import or call `memory_procedures` / procedure activation APIs. Spec 135–139 remain a different series.

**Rejected:** “Procedure is just a workflow-lite.”

## 4. Timeout hook

**Decision:** Extend `confirmation_timeout` message (and ntfy) when `conductor_ledger` has unfinished work: offer to continue as a goal or workflow, not only “try again.” Need ledger available on the pending confirmation / checkpoint; if missing, keep today’s generic timeout copy.

**Rejected:** A new timeout table. Spawning companion graph on timeout without user accept.

## 5. Unfinished detector

**Decision:** Ledger is unfinished if any item is not terminal (`done`, `skipped`, `denied`).

- **Offer in the same assistant reply:** unfinished **and** the close is not already a 156 `ask_user` question (do not stack promote on top of stall-ask).
- **Timeout / abort / user left:** offer even if last status was `ask_user` or `awaiting_confirmation`.
- All `done` → no auto-offer.

**Rejected:** LLM judge “did we finish?”
