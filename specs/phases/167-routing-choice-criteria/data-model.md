# Data Model: Routing Choice Criteria (167)

No database change. No migration.

| Item | Where | Shape |
|---|---|---|
| `routing_criteria` | `BaseAgent` class attribute (`ze-agents`) | `str`, default `""`; use-for / not-for text for the routing Choice only |
| `criterion_for(agent_cls)` | `ze_core/routing/judge.py` | `routing_criteria.strip() or description.strip()` |
| `build_questions(criteria)` | `ze_core/routing/judge.py` | `Mapping[str, str]` (shortlist name → criterion), in option order; adds `none` |
| Calibration roster | `eval/calibration/routing.py` | name → (description for E5, criterion for the Choice) |
| `routing_holdout2.jsonl` | `eval/calibration/` | same row shape as `routing.jsonl`: `id, lang, prompt, gold_agent, gold_multi, gold_complexity[, history]` |

Trace: unchanged. `MessageTrace.judgments` already stores the question definition and answers.
