# One mind, not a router

Most multi-agent assistants work like a switchboard. A router reads your message and hands it to a specialist. The specialist answers in its own voice, with its own context. The assistant feels like a set of tools with a front desk.

Ze chose a different shape. This post explains the choice, the two layers that carry it, and the code Ze deleted to keep it honest.

## The commitment

[The doctrine](../../specs/arch/ze-doctrine.md) says it in one line: Ze is one mind writing to one world-state, not a router over specialists.

That has two parts.

**One world-state.** Agents and background jobs do not keep private truths that compete with each other. They propose changes to a shared model of you. A fixed order settles conflicts: governance first (consent, capability, reversibility), then what you stated, then grounded fact, then inference, then suspicion. A suspicion may be offered. It is never enacted.

**One voice.** The sense of unity does not come from a persona prompt. It comes from every part reading and writing the same world-state, and from one rule for resolving conflicts everywhere. The persona is the voice. The world-state is the self.

The second part is the one that shaped the agent graph.

## Companion is the conductor

Ze has thirteen agents, but only companion talks to you. When a request needs several specialists in sequence, the router sends it to companion. Companion calls the specialists through one tool, `delegate_to_agent`, and writes the reply.

[The conductor roadmap](../../specs/arch/companion-conductor-roadmap.md) pins the rules, so later specs do not reopen them:

1. **One speaker.** Specialists never take the microphone. Hand-offs and swarms are out.
2. **One conductor.** Only companion lists `delegate_to_agent`. Research lost it. Specialists do not delegate again, and nesting stops at one level.
3. **The decomposition is a hint.** A small model splits the request, but the conductor may throw that split away after the first specialist returns.
4. **Independent work stays parallel.** "Check my calendar and summarize the news" fans out in the graph and merges in a synthesize step. Sequential or dependent work goes to companion.
5. **Workers stay isolated.** A specialist gets a full brief and returns a structured result. Ze does not copy its transcript into the session.
6. **Gate the call, not the plan.** Each delegate call runs through the specialist's own write gates. An irreversible write parks and asks first (phases 152 and 181).
7. **Durable work leaves the turn.** If a job must outlive the chat, companion promotes it to a goal or a workflow.

## Eleven phases, in order

The roadmap ran as phases 151 to 161. Each phase had its own spec, and the rule was to finish one before starting the next.

| Phase | What it did |
|---|---|
| 151 | Made `delegate_to_agent` a real brief: objective, prior outputs, output shape, stop condition. |
| 152 | Stopped delegates from inheriting the turn's gate decision. A calendar lookup no longer waits because a later send needs approval. |
| 153 | Routed sequential and dependent turns to companion. Deleted `plan_sequential`. |
| 154 | Showed the plan, each specialist, and each confirmation in the trace panel. |
| 155 | Sent mixed read-and-write requests ("research X and email Y") to the conductor. |
| 156 | Added a stall detector, one silent retry, and a user-visible question as the last step. |
| 157 | Let companion promote a conductor run to a workflow or goal instance. |
| 158 | Gave independent parallel subtasks their own gates, so one approval does not block the rest. |
| 159 | Gave each concurrent thread its own identity for traces and cancel. |
| 160 | Retuned the routing confidence for the E5 embedding model. |
| 161 | Made the workspace chat-first. |

Phases 159 to 161 are neighbors rather than conductor mechanics. The first eight are the argument.

## The hard cut

Phase 153 is the one that matters most. It did not add the conductor beside the old planner. It deleted `plan_sequential`, the graph edge that ended a sequential plan early, and the unused plumbing for dynamic plan steps. The old path did not stay as a fallback.

This follows a rule the whole project uses before v1: [no shims, no dual-write, no wrap-then-replace](../../specs/arch/pre-v1-hard-cuts.md). If the design is wrong, change it. A second path that "also works" gives the next reader two designs to understand and a bug surface twice as wide.

The same phase redefined one flag. The decomposition step's `is_sequential` used to mean "build a workflow plan." It now means "send this to the conductor."

## What the conductor does not do

Three limits came from the same thinking.

- **No procedure promotion.** When a run must outlive the turn, companion creates a goal or workflow instance. It never writes a reusable procedure. Procedures have their own lifecycle and their own admission rules.
- **No stall without bounds.** The stall detector lives in the engine, in `delegate_to_agent`, not only in a prompt. It allows one silent retry of the same specialist with new prior outputs, then it asks you.
- **No hidden fan-out of approvals.** Confirmations stay keyed by request. Two gates on one thread cannot clobber or cancel each other (phase 113).

## The tradeoffs

The conductor design costs something.

- Companion becomes a bottleneck for multi-step turns. A sequential request adds companion's reasoning loop on top of each specialist's work.
- The conductor can be wrong about the plan. The stall detector and the trace panel exist because of that.

In return, you get one coherent reply, one place where consent is asked, and one trace that explains the sequence. For an assistant that acts on your calendar and your mail, those are worth the cost.

## What to take from this

- Decide who speaks to the user before you decide how agents communicate.
- Treat specialists as tools with a brief and a result, not as peers with their own memory.
- Gate each call, not the whole plan.
- Use one world-state as the place agents propose to. Peer-to-peer truth between agents will drift.
- When you change the design, delete the old path in the same phase.

Further reading: [architecture](../architecture.md), [cognitive architecture](../cognitive-architecture.md), and the specs for phases [151](../../specs/phases/151-fat-delegate-aci/spec.md) through [158](../../specs/phases/158-parallel-subtask-gates/spec.md).
