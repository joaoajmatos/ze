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
