# Research: Conductor Stall / Replan

**Feature**: `156-conductor-stall-replan`  
**Date**: 2026-09-16

## 1. Engine-enforced, not prompt-only

**Decision:** Enforce in `run_delegate` (companion-only tool). Companion instructions describe the same loop but cannot exceed caps.

**Rejected:** Prompt-only “please stop flailing.” A new LangGraph outer node (would pause the whole graph between delegates; 152 already pauses on confirmation).

## 2. Silent retry vs ask (pinned policy)

**Decision:**

1. **Not stall:** `awaiting_confirmation`, `denied`, successful non-empty `response`, 152 resume.
2. **Stall detector (deterministic):** `run_delegate` error payload; empty or whitespace-only `response`; specialist never started (unknown agent). Do **not** LLM-judge a fluent but useless paragraph this phase.
3. **Silent retry:** at most **one** extra `delegate_to_agent` per specialist **name** per turn after a stall, with `prior_outputs` including the stalled output/error and instruction to try a different approach or smaller scope. Ledger: `stalled` then `replanned`.
4. **Ask (user-visible):** if that specialist stalls again, or **per-specialist cap 2** would be exceeded, or **turn cap 6** total delegates would be exceeded. Block the tool call; return a structured error the companion must surface as a question. Ledger `ask_user`.
5. Never silent-retry a different user-visible story (do not auto-email after research stall without ask if the act was not yet reached — next specialist after a **successful** gather is allowed as today).

**Rejected:** Unlimited retries until agentic_loop max iterations. Asking on the first stall (too noisy for transient tool errors).

## 3. Counters

**Decision:** Store `conductor_delegate_counts: dict[str, int]` and `conductor_delegate_total: int` on `AgentContext` / `AgentState`, copied like `conductor_ledger` through confirmation resume. Reset only on a new user turn.

**Rejected:** Module-level globals. A Postgres Magentic table.

## 4. Rebrief target

**Decision:** Silent retry is the **same** specialist name. Choosing a *different* next specialist after success remains companion’s inner loop (153). After stall, engine does not auto-switch agents (that would be a second classifier).

**Rejected:** Engine picks news after research stalls.

## 5. 154 / 157

**Decision:** Additive statuses `stalled` | `replanned`. Trace panel prints status strings (154). Promote remains 157 — stall ask is not an auto workflow.

**Rejected:** Reusing `skipped` for stall (154 already uses skipped for unused hint steps).
