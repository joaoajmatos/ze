# Held-out brief: `eval/calibration/complexity_holdout.jsonl` (182)

You are writing a blind check set. This brief is everything you need; read nothing else in the repo. Never open `eval/calibration/complexity.jsonl` (the tuned set), `eval/calibration/complexity.py`, `core/engine/ze-core/ze_core/routing/tier.py`, the `complexity` block of `apps/ze-api/config/config.yaml`, or anything under `specs/phases/182-complexity-routing/` other than this file.

Write `eval/calibration/complexity_holdout.jsonl`, check it by hand against the quotas below (count rows per language, tier, agent and kind), then commit only that file: `git add eval/calibration/complexity_holdout.jsonl && git commit -m "eval(calibration): blind held-out set for 182 complexity tier" -- eval/calibration/complexity_holdout.jsonl`. Never `git add -A`. Report the per-language counts to the ENG lead (Purlin) and stop.

## What the set measures

Ze is a personal assistant. Three of its agents can answer with a strong model (slower, about three times the price) or a light one:

- **companion**: chat, feelings, thinking through the user's own situation, and conducting other agents.
- **research**: questions that need facts from the web: explain, compare, how-to, current events.
- **goals**: multi-week goals: create, review, update, mark progress.

For each row, decide which model the turn **needs**, judging **the task the user is trying to get done**, not only the last message. "ok go ahead" after a long planning exchange is a big task; "ok thanks" after the same exchange is not.

## Label rule

- `full`: a strong model's reply would be clearly better. Reasoning, deciding between options, comparing or synthesising several sources, planning, long or careful writing, an emotional or personal conversation that needs care, or several dependent steps.
- `simple`: a light model would do as well. Greeting, thanks, acknowledgment, a single fact or status lookup, a short yes/no confirmation, one routine action, a short reformat.
- **When unsure, label `full`.** A wrong `full` costs a little money; a wrong `simple` gives the user a worse answer.

## Row format (one JSON object per line)

```json
{"id": "cxh-001", "lang": "en", "agent": "companion",
 "conversation": [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}],
 "recap": null, "memory": ["..."], "focus": null, "skill": null,
 "prompt": "...", "gold_tier": "full", "kind": ["multi_turn", "anaphoric"],
 "why": "user approves a 5-step plan defined in the previous turns"}
```

| Field | Type | Rule |
|---|---|---|
| `id` | string | unique; `cxh-001`, `cxh-002`, … |
| `lang` | `"en"` or `"pt"` | |
| `agent` | `"companion"`, `"research"` or `"goals"` | the agent the turn was routed to |
| `conversation` | list of `{"role": "user" or "assistant", "content": string}` | earlier turns, oldest first; may be empty. Use realistic assistant turns (they can be long; Ze writes paragraphs). |
| `recap` | string or `null` | a short "while you were away" summary; use only when `conversation` is empty |
| `memory` | list of strings | up to 5 short facts Ze remembered about the user that are relevant to this turn; may be empty |
| `focus` | string or `null` | an active goal (with its current step) or a workflow the user is looking at |
| `skill` | `{"name": string, "description": string}` or `null` | a skill Ze matched for this turn |
| `prompt` | string | the user's message this turn |
| `gold_tier` | `"simple"` or `"full"` | per the label rule above |
| `kind` | list of tags: `single`, `multi_turn`, `anaphoric`, `resumed`, `with_memory`, `with_focus`, `with_skill` | `single` = no context at all; `anaphoric` = the prompt only makes sense with the conversation; `resumed` = uses `recap` |
| `why` | string | one line explaining the label |

One JSON object per line, UTF-8, no trailing commas, no comments.

## Quotas (per language: `en` and `pt`, Portuguese from Portugal)

| Requirement | Minimum per language |
|---|---|
| Rows | 24 |
| `gold_tier: simple` | 10 |
| `gold_tier: full` | 10 |
| Each agent (companion, research, goals) in each tier | 2 |
| Rows with a non-empty `conversation` | 10 |
| `anaphoric` rows (the prompt only makes sense with the conversation) | 6, at least 3 `full` and 3 `simple` |
| Rows with `memory`, `focus`, `skill` or `recap` | 2 each |
| `single` rows (no context at all) | 4 |

## Situations to cover (write your own wording; do not reuse these sentences)

- A short prompt that hides a big task: approving or continuing a plan, "do the same for the others", "now write it properly".
- A long prompt that is still light: pasted text with "thanks, got it", a long greeting.
- A follow-up lookup: "and the other one?", "what about Lisbon?" after a single-fact answer.
- A goal check-in that is routine ("mark today's run done") versus one that needs rethinking ("I keep missing my runs, what should I change?").
- An emotional message that is short but needs care.
- A research question that is a one-line fact versus one that needs comparison.
- A turn where memory or the workflow in focus changes what the task is.
- Portuguese rows written natively, not translated from your English rows.

## Rules

- Do not tune anything and do not run any calibration. The ENG lead runs the offline check (counts only) and, later, one live run after the bar is frozen.
- Do not edit a row after the live run. If a label is wrong, report it; changing a gold label needs the user's decision.
