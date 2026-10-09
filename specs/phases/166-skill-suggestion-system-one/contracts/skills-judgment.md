# Contract: Skills judgment

## Shortlist
`candidates` = active skills minus explicit matches, with cosine `s`. Keep `s >= shortlist_floor`, sort by `s` descending (stable on skill id), take `shortlist_k`. Empty → no request.

## Questions (one batched request, `max_attempts=1`)
- `skill` — Choice. Criteria: key → description (capped 300 chars), plus `none`: "No listed skill is needed for this request." Instructions: "Which one skill should be applied to this request? Answer none if no listed skill is needed. Judge the user's words; history and context are background only."
- `needs_skill` — Noul. Instructions: "Does answering this request well depend on one of the listed skills? Judge the user's words; history and context are background only."

## State
`{user (<=2000), history? (<=1500), context? (<=600), skills (<=1500, "name: description" lines)}`.

## Decision (pure `decide(result, cfg, keys)`; never raises)
1. `result.outcome == "skip"` → skip(reason).
2. Any bar `None` → skip("uncalibrated").
3. `skill` answer missing, wrong type, no confidence, or key not in `keys ∪ {none}` → skip("invalid_answer").
4. peakedness < `choice_trust` → abstain("choice_unsure"). consumed = {}.
5. choice == `none` → drop("choice_none"). consumed = {skill}.
6. `needs_skill` missing/invalid → skip("invalid_answer").
7. noul < `needs_skill_hold` → drop("not_needed"). consumed = {skill, needs_skill}.
8. else apply(key). consumed = {skill, needs_skill}.

## Outcome → matches
- apply: explicit matches + the chosen automatic skill (`below_floor = sim < match_threshold`).
- drop: explicit matches only.
- abstain, skip: explicit matches + every automatic skill with `sim >= match_threshold` (114).

## Config (`system_one.surfaces.skills`)
`enabled`, `choice_trust`, `needs_skill_hold`, `shortlist_k`, `shortlist_floor`. Invalid values → null/default + warning. Enabled with a null bar → warning, 114 path.
