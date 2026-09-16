# Companion conductor roadmap

> **Status:** Living note. Phases 151–157 Implemented. Procedures are **not** 157.
> **Date:** 2026-09-16
> **Related:** [Pre-v1 Hard Cuts](pre-v1-hard-cuts.md), [Ze Doctrine](ze-doctrine.md),
> harness [`030-agent-harness`](../phases/030-agent-harness/spec.md),
> speech-act [`142-speech-act-routing`](../phases/142-speech-act-routing/spec.md),
> nested delegate [`146-forget-vs-cancel`](../phases/146-forget-vs-cancel/spec.md)

---

## Context

Ze has specialists and two coordination paths: graph **compound** (independent
parallel fan-out + synthesize) and nested **`delegate_to_agent`** (fat brief,
per-invocation gate, isolated worker, depth 1, companion-only). Sequential /
mixed / dependent multi-specialist turns route to companion as the in-chat
conductor. `plan_sequential` is gone. Durable promote to workflow/goal is
phase **157** (not a procedure).

The product decision: **one user-facing voice (companion / Ze), specialists as
tools, sequence owned in-chat by that conductor.** Independent parallel work
stays a graph fan-out. Work that must outlive the turn stays goals/workflows.
No swarm. No specialist-as-speaker.

Industry mapping (agents-as-tools / Magentic-One ledgers / Anthropic isolated
workers) is already agreed. This note only sequences the hard-cuts so later
specs do not relitigate it.

---

## Pinned (do not relitigate in a phase spec)

1. **One speaker.** Companion owns the user reply. Specialists never take the
   mic (OpenAI *handoffs* / swarm are out).
2. **One conductor.** Only companion lists `delegate_to_agent`. Research loses
   it; specialists do not re-delegate. One-level only.
3. **Haiku decompose is a hint**, never an executable DAG. The conductor may
   throw the hint away after a specialist returns.
4. **Parallel independent compound stays graph-level** (`asyncio.gather` +
   `synthesize`). Sequential / mixed / dependent work routes to companion.
5. **`plan_sequential` dies** in the routing hard-cut, not as a later cleanup.
   No wrap-then-replace; `dynamic_plan_steps` is not a product surface.
6. **Workers stay isolated.** Fat brief in, structured result + nested
   `tool_calls` out. Do not dump specialist transcripts into session
   `messages`.
7. **Gate the invocation, not the pre-plan.** Each delegate evaluates
   specialist + intent. Confirmations stay `request_id`-keyed (phase 113).
8. **Durable escape is 157.** Promote-to-workflow/goal is not in 151–156.
   Promote is a **workflow or goal instance**, never a procedure
   (`memory_procedures` / 135–139).

---

## Ordered phases

Numbers are the spec-kit slots after 150. Specs live under
`specs/phases/151-*` … `157-*`. Do not start N+1 **implementation** in N’s tree.
Phase **151** here is the conductor series, not memory-honesty roadmap item 151
(already bundled into directory 150).

### 151 — Fat delegate ACI — M — Implemented

Upgrade `delegate_to_agent` so a conductor *can* brief a specialist. Objective,
prior outputs / inputs, output shape, stop condition. Structured result keeps
nested `tool_calls` (146 honesty still earns domain confirmations from those).
Hard-cut: only companion may call it; max depth 1; specialists cannot list it.
Research’s calendar-guess line becomes “say you need the calendar agent” or a
user-visible limitation until 153 routes mixed turns to companion.

Do not change the conversation graph, companion `description` embeddings, or
`plan_sequential` here. Speech-act one-shot delegates must keep working.

Do not start 152 in the 151 tree.

### 152 — Per-delegate capability and confirmation — M — Implemented

Stop inheriting the parent turn’s `gate_decision` wholesale. At each
`run_delegate`, evaluate that specialist + inferred/declared intent against
`CapabilityGate` (and spend budget). A write confirmation pauses the
conductor loop and resumes it; a calendar lookup in the same turn is not held
because a later send would be. Graph **parallel** compound may keep
strictest-wins until a later pass — this phase is the nested-tool path.

Do not start 153 in the 152 tree.

### 153 — Sequential routing hard-cut — L — Implemented

This is the first product routing change. Router sends sequential / dependent
turns to companion as `primary_agent` when `is_sequential && len(subtasks)>1`.
Companion `description` and instructions match that job. Independent multi-read
stays fan-out + synthesize. Single-domain stays the specialist.

Hard-cut: delete `plan_sequential`, the `after_decompose` sequential edge to
END, and unused `dynamic_plan_steps` plumbing. Haiku `is_sequential` means
“conductor,” not “workflow planner.” Companion prompt gains the inner loop:
short plan, fat briefs, judge done/next/ask-user; scale effort. Turn-local
progress ledger in graph/agent state, recorded on `MessageTrace`.

Do not start 154 in the 153 tree. Mixed gather+act when Haiku leaves sequential
false is **155**, not a silent extra in 153.

### 154 — Conductor observability and eval — S/M — Implemented

Trace panel shows the plan, each specialist, confirmation ids, stall/ask.
Progress keys for “checking calendar…” / “drafting the mail…” so the user
sees sequence, not a mute wait. Eval scenarios: sequential dependent
(calendar then email with the event id in the brief), independent parallel
still not going through companion, speech-act one-shot still 146-honest,
confirmation mid-sequence resumes the next specialist.

### 155 — Mixed gather+act → conductor — S — Implemented

`apply_conductor_rewrite` today is only sequential multi-subtask. Dependent
gather+act (“research X and email Y”) often has `sequential: false`, so graph
fan-out runs research and messenger together. **155:** more than one specialist
**and** mixed gather+act intents (read/lookup/search vs create/update/delete/send
— not a `{research, messenger}` name list) rewrite to companion the same way
153 does. Independent multi-read still fans out. Single-domain stays the
specialist. Do **not** split parallel capability gates. Do not stall. Do not
promote.

Do not start 156 in the 155 tree.

### 156 — Stall / replan — M — Implemented

153/companion judge is prompt-only. Add a **turn-local** Magentic-One-style
outer loop: stall detector, one silent same-specialist retry with new
`prior_outputs`, caps, ledger `stalled` / `replanned`, then user-visible ask.
Engine-enforced in `delegate_to_agent`, not only a prompt. No durable
workflow/goal rows. Depends on 155.

Do not start 157 in the 156 tree.

### 157 — Promote this instance to workflow/goal — L — Implemented

When the job must outlive the turn (unfinished close, abort, confirmation that
never returns, “keep going on this”, clearly multi-session), companion offers
or creates a **workflow or goal instance**. Not a procedure, not
`memory_procedures`, not 135–139 activation. Goals/workflows are not the
in-chat conductor (pin holds). No swarm. Depends on 155/156.

---

## After 157 (not these three)

- Per-subtask gate on the **parallel** graph path (if strictest-wins still
  hurts independent read+write fan-out).
- Procedures / procedure activation (135–139) — **not** a promote substitute.
- Feeding prior outputs inside `_execute_compound` sequential — **do not do
  this**; that path is deleted in 153.
- Swarm / specialist-as-speaker.

## Explicitly not this series

- Specialist-as-speaker / peer swarm / shared chat blackboard.
- Anthropic-style 15× parallel research fan-out for personal-assistant turns.
- Rewriting goals/workflows to be the in-chat conductor.
- Bundling 151–157 into one spec-kit directory.
- Treating promote as procedure learning.

---

## Why this split

| If we bundled | Failure |
|---|---|
| ACI + routing together | Router sends mixed turns to companion before briefs are good enough; speech-act regressions hide in a large PR |
| Routing before per-delegate gate | Conductor can look up the calendar then send mail under a single inherited EXECUTE |
| Observability inside 153 | Trace/eval slip, or 153 never ships because the panel is unfinished |
| Killing `plan_sequential` later | Wrap-then-replace; two sequence owners in production |
| Mixed rewrite inside 153 | 153 ships without the sequential-false gather+act hole, or never ships |
| Stall inside 155 | Routing PR blocked on Magentic caps |
| Promote inside 156 | Stall-ask becomes silent durable jobs |

151 is the smallest change that makes 142/146 handoffs *better* even before
mixed routing exists. 153 is the first user-visible collaboration. 154 is
how we know 153 is true. 155 is how mixed gather+act actually reaches the
conductor. 156 is how flailing stops. 157 is how a job survives the turn.
