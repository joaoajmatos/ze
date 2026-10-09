# Contract: Matcher, node and trace

## Matcher
`SkillMatcher(store, embedder, match_threshold, *, system_one_client=None, surface=None)`.
`await matcher.match(message, *, judgment_state=None) -> SkillMatchOutcome`.
No client, no state, empty message, no skills, or an uncalibrated surface → `SkillMatchOutcome(matches=<114 result>, judgment=None)`.
Client exceptions are caught: 114 result plus a skip judgment (reason `error`).

## Node (`match_skills`)
1. Resolve matcher, agent context, prompt (unchanged guards).
2. Build `judgment_state` with the shared helper (user = caption or prompt, history hint, `routing_hints`).
3. `outcome = await matcher.match(prompt, judgment_state=...)`; an exception returns `{}` as today.
4. Rows = `judgments_from_result(outcome.judgment.result, question_kinds=..., consumed=..., skip_reason=...)` when a judgment exists.
5. Return `judgments = [*state.get("judgments", []), *rows]` — append-only — plus the existing context fields when matches exist. When matches are empty but a judgment exists, still return the judgments.
6. Tool narrowing: `_combined_tool_names(outcome.matches)` unchanged.

## Trace
`_extract_skills_used` copies `below_floor`. REST/WS `SkillUsageTraceResponse` gains `below_floor: bool = false`. Panel shows a "below floor" mark beside the similarity.
