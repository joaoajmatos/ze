# Research: Routing Choice Criteria (167)

Evidence from the 2026-10-12 scope note ("164 Research Scope") and offline measurements. Nothing here needed a live call.

## R1 — Why the Choice fails
- Companion `description` (`plugins/ze-personal/ze_personal/agents/companion/agent.py:102-113`) lists "explain X"; research (`research/agent.py:26-32`) lists "how does X work, explain X". The Choice uses descriptions as criteria (`judge.py` `build_questions`, `router.py:146`).
- Companion has no web search (`agent.py:17`) and no instruction to delegate facts (`:57-75`).
- `judge.py` `_AGENT_INSTRUCTIONS` is a bare "which one agent"; `_NONE_CRITERION` is one sentence.

## R2 — Where the criteria live
**Decision**: optional `routing_criteria: str = ""` on `BaseAgent`; `build_questions` receives `name → text`; the router passes `routing_criteria.strip() or description.strip()`.
**Rationale**: `ze_core` may not name plugin agents, so a table in `judge.py` is out. The attribute sits beside `description` (the single source of agent text), is optional (no registry change), and keeps E5 passages on `description`.
**Alternatives**: (a) table in `judge.py` — breaks the dependency rule; (b) YAML config — a second place to keep in sync, and config is not where agent lanes are declared (AGENTS.md: agent config lives on `@agent`); (c) extend `description` — it feeds E5 and Haiku decompose, and the scratch experiment shows richer descriptions made E5 recall worse (tuned 0.957 → 0.848).

## R3 — Shortlist size (offline, free)
Gold-agent recall by k (`routing.py --recall`, `eval/calibration/*.jsonl`, 2026-10-12):

| k | routing | routing_holdout | routing_holdout2 |
|---|---|---|---|
| 2 | 0.652 | 0.450 | 0.214 |
| 3 | 0.717 | 0.650 | 0.464 |
| 4 | 0.870 | 0.700 | 0.464 |
| 5 | 0.957 | 0.850 | 0.571 |
| 6 | 1.000 | 0.900 | 0.571 |
| 7 | 1.000 | 1.000 | 0.714 |
| 8 | 1.000 | 1.000 | 0.714 |
| 9 | 1.000 | 1.000 | 1.000 |
| 10 | 1.000 | 1.000 | 1.000 |

E5 cosines are flat (0.76–0.82; gaps 0.00–0.03), so the ranking carries little signal for research prompts. **Decision**: sweep and take the smallest k ≥ 0.95 on all three sets (measured by T002 on 2026-10-12 with the extended `--recall` sweep: **k=9** of a 10-agent roster; gate T003 passes). Scored rows per set: 46 / 20 / 28. **Alternatives**: fixed k=6 (user's number) — cannot pass; a code guard that always includes named agents — breaks the dependency rule.
**Risk**: with k=9/10 the Choice sees almost the whole roster, so E5 no longer shortlists. Cost is prompt tokens only. The `shortlist_k` clamp (`judge.py` `shortlist`) already handles k ≥ roster.

## R4 — Choice wording
**Decision**: generic instruction: prefer an agent that can search the web or use tools over one that would answer from its own knowledge when the request needs facts, comparisons, recent information or step-by-step help; `none` when no listed agent can do it alone, the capability does not exist (device control), or more than one agent is needed. No agent names. Agent-specific lanes go in `routing_criteria`.
**Verify at implement**: tune on `routing.jsonl` only; read `routing_holdout*.jsonl` results as pass/fail checks.

## R5 — Calibration must use production criteria
`eval/calibration/routing.py` builds questions from `{name: description}` (`shuffled_questions`). It must call the same criterion lookup as the router so the printed bars are the bars production sees. Roster loading returns both description and criteria.

## R6 — Companion live check
Opt-in script (`--live` required) runs the 6 research prompts of `routing_holdout.jsonl` through the real companion via the existing eval/graph entry points and reports: delegated to research, LLM call count, cost, wall time, cited sources. Informs the later "companion as front door" question (option E, out of scope).

## R7 — Acceptance and fallback
Rule (spec FR-009): per set and language ≥ 0.95 accuracy, ECE ≤ 0.10, zero research→companion misses. Otherwise option F: `enabled: false`, null bars, dated comment, 164 spec status note, docs.

## R8 — Companion live check result (2026-10-12, `companion_research_check.py --live`, dev-eval on this floor)
Six research prompts from `routing_holdout.jsonl` through `/eval/chat` with the 167 criteria and surface enabled: **all 6 routed to research, none to companion; delegated: no** (nothing to delegate, research answered directly); wall time 10.7–17.5 s; **cited sources: no on all 6**; LLM calls and cost read 0 (see below).

Evidence for option E (companion as front door): the Choice now keeps research prompts out of companion, so the check could not measure what companion does with them. `/eval/chat` has no agent override. To measure companion, option E needs a forced-agent hook.

Follow-up findings (not fixed in 167):
- **Citation "no" is unexplained.** The detector counts any `http(s)://` URL in the reply text. Research is told to cite, but nothing in `ze_core/openrouter` reads OpenRouter's `url_citation` annotations, so sources reach the user only if the model writes URLs into the text. Offline I cannot tell whether research did not search or searched and cited by name. Next step: read the six replies and the `openrouter:web_search` tool-call count from a dev-eval run.
- **Calls/cost 0.** The script queried `llm_cost_log` by `eval-<id>` only; `/eval/chat` sets the cost context with the raw id. The script now matches both ids. Cost is also backfilled later by the reconciler.

## R9 — Loops vs companion (System One Tuning floor, 2026-10-12)
Baseline on the shipped criteria: `ho-loops-en` ("keep that on my radar") went to companion at 0.29, and the training row `single-loops-pt` ("fecha a preocupação sobre a mudança de emprego") also went to companion, so the gap was a category gap, not one phrase. Neither the loops nor the companion text said that an undecided matter the user wants kept in mind is a loop.
Change: `routing_criteria` on `LoopsAgent` (use for undecided or worrying matters held with no date and for closing/dropping them; not for reminders, goals, or talking it through now) and one clause in the companion criteria. Training rows added to `routing.jsonl`: two loops-hold rows and one talk-it-through companion row per language (the companion rows guard against over-pulling feelings chats into loops). Training set after the change: 26/26 EN, 26/26 PT, ECE 0.034.
Held-out, one run after the criteria were frozen (`routing_holdout`, `routing_holdout2`, nothing tuned on them): EN and PT accuracy 1.000 on both sets, ECE 0.041 and 0.014, zero research-to-companion misses, zero harmful trusts at `choice_trust` 0.5 / `multi_specialist_hold` 0.5. The bars stay as shipped.
Caveat: the loops agent has list/close/drop tools only; loops are created by the loop gate after the turn. Routing "keep it on my radar" to loops is the label this set asks for, but the agent can only list the open loops in reply. Whether such turns should instead stay with companion plus the gate is a product question, not a calibration one.

## R10 — Why `complexity_lookup_max` was 0.16/0.17 per set and 0.02 combined
It was not a mixing bug in the data. The Score does not separate lookup rows from harder rows: on the held-out sets a multi_hop row scores 0.02 and a single_tool row 0.04, below the lookup maximum of 0.33. `suggest_lookup_max` picked the bar with the most correct rows (lookups at or below it plus harder rows above it) and broke ties toward the lowest value. With few lookup rows and many harder rows, that objective accepts bars that send harder requests to the cheap tier, and the answer jumps between sets (0.16, 0.04, 0.02) with the overlap.
Fix: the suggestion is now the highest lookup score below every harder row, and `None` when the levels overlap. This mirrors the grid's zero-harm rule. Results: training set 0.17 (all harder rows score at least 0.21); held-out sets combined: null. Decision: keep `complexity_lookup_max: null`. A bar tuned on the training set alone would downgrade held-out harder requests.

## R11 — Two 2/5 eval judge scores (System One Tuning floor, 2026-10-12)
`retry_refused_after_goal` and `retry_text_only_lookup_turn` scored quality 2 on the first rerun. Both replies were right; the judge was wrong, because it saw only the reply text.
- Goal: the judge said Ze "fails to invoke create_goal". The trace shows `create_goal` as a draft with the turn waiting for the Start confirmation, which is how a confirmation-gated write appears.
- Lookup: the judge called "Python 3.15.0, released October 9, 2026" a hallucination with a future date. Today is 2026-10-12, and the judge model's knowledge ends earlier. Server-side web search also never shows in the tool call list.
Fix: the judge prompt now carries the tool calls (draft, ok, failed), the waiting-for-confirmation flag, today's date, and two notes explaining drafts and server-side search. After the fix the four `retry` scenarios score 5/5/5, 5/5/5, 5/4/5 and 4/5/5 and all pass. No change to the replies.
