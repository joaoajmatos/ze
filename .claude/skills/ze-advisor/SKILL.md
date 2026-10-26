---
name: ze-advisor
description: Consults an Opus advisor (read-only subagent) at a hard decision point, then carries on executing. Use when a Sonnet or Haiku agent on a floor hits a design gap the spec and plan do not answer, fails the same thing twice, is about to touch a migration, concurrency, the contribution seam, honesty enforcement, System One bars or security, or is about to declare a story done.
---

# Ask the advisor

You stay the executor: you run the tools, write the code and own the result. The advisor is Opus. It reads, thinks and answers in a few hundred words; it never edits. Based on Anthropic's advisor strategy (Sonnet executor + Opus advisor scored higher and cost less than Sonnet alone; Haiku + Opus advisor roughly doubled Haiku's score).

## When to call

Call at most **3 times per story** (Haiku juniors: 4). Call when:

1. **Before you start a story whose plan leaves a choice open.** One call on your approach, not on every step.
2. **After two failed attempts** at the same test failure, type error or behaviour.
3. **A design gap**: the spec, plan, contracts and Handoffs note do not decide it, and it is not a product decision.
4. **Risky ground**: a migration, concurrency or locks, the contribution seam, honesty or claim posture, System One bars or calibration, auth or anything that sends data out.
5. **Before you say "done"** on a story that touched risky ground: "Is this done, what did I miss?"

Do not call for things a grep, a test run or the spec answers. Do not call for product decisions: those go to the Maestro (`maestri ask "Claude Code"`), batched.

## How to call

Use the Agent tool with `subagent_type: "Plan"` (read-only) and `model: "opus"`. The prompt is a packet under ~2,500 tokens:

```
ADVISOR REQUEST (<your name>, <floor>, <task id>)
Question: <one or two sentences; what you must decide>
Context: <spec/plan paths and the requirement ids that apply>
Code: <file:line references, plus at most ~60 lines pasted where the detail matters>
Tried: <what you tried and how it failed, one line each>
Constraints: <lane file ownership, AGENTS.md rules that bind here>
Answer in under 300 words:
VERDICT: proceed | change course | stop and escalate
PLAN: numbered steps
RISKS: what will break or be missed
CHECK: the test or command that proves it
You may read the files named above, nothing else. Do not edit anything.
```

Never paste the whole conversation, tool logs or files that do not bear on the question.

## After the call

- Follow the verdict or say in one line why you did not. `stop and escalate` goes to your lead, then the Spec Architect, then the Maestro, with the advisor's answer attached.
- Log it in your state file (`journal/state/<terminal id>.md`) under **Advisor**: `<task> · <question in 8 words> · <verdict> · followed|overrode`.
- If Opus is unavailable (usage limit), do not quietly fall back: say so in the Handoffs note and escalate to your lead.

## Reviewers

A Floor Reviewer (Sonnet) calls the advisor once before a CHANGES verdict that holds a HIGH finding, or on any diff with a migration or concurrency change: "Here are my findings; try to disprove each one." Drop the findings the advisor refutes with evidence. This cuts review rounds.
