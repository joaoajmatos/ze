# Render follow-ups doc deltas (specialists render, consent, honesty guard, outreach, judge)

CF-16 applies these and deletes this file.

## AGENTS.md

- Chat inline UI line (render tools): the specialists render too. Research lists `render_table`
  and `render_chart`; finance adds `render_metric` and `render_chart` (it already had
  `render_confirm` and `render_list`); calendar lists `render_timeline` and `render_form`.
  Each agent's instructions say prose is the default.
- Layout, `ze-personal/agents` tree: the companion takes an `OutreachLog` Protocol
  (`agents/companion/outreach_log.py`) instead of a pool. `ze-prospecting` supplies it through
  `agent_deps` (the campaign store).
- Layout, `ze-agents` tree (after the `effects.py` line): add
  `honesty.py   # reply-honesty guards (enforce_memory_confirmations); a successful render that waits for the user (choice group, form, consent, confirm, review, connect account) lets "I'll remember your pick" stand; data renders (table, chart, metric, timeline) and past-tense save claims still strip`.
- Layout, `ze-core/container.py` line: agent constructor parameters typed `X | None` get `None`
  when no plugin registers `X` (the companion's `OutreachLog` is the first).

## docs/eval.md

- Already updated in the same change: the response table gains `components`. Mention in the
  judge section that the judge sees each rendered component's kind and data (styling keys
  removed, 700 characters per component).

## Eval scenarios

- `companion_render_table`, `_metric`, `_timeline`, `_form` expect research, finance, calendar,
  calendar. Their ids keep the `companion_` prefix; CF-16 may rename them if it renames the file.
