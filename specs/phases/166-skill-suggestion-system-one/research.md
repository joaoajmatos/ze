# Research: System One Skill Gating

## R1 — Shortlist and pre-floor
**Decision**: Candidates are active skills not matched explicitly, scored by the existing cosine, kept when `cosine >= shortlist_floor`, sorted descending, capped at `shortlist_k`. `shortlist_floor` starts near 0.35; `shortlist_k` has no pre-decided default.
**Why**: 164's first live run found gold agents outside the top-4 shortlist (recall 0.826 at k=4, 0.870 at k=5; 0.870 and 0.957 after a sharper description). A fixed k guessed up front repeats that. Skill rosters are user-made and variable, so recall depends on roster size and description quality.
**Consequence**: The calibration reports recall at k = 3..8 and floors 0.30..0.45. A task picks the shipped `shortlist_k` and `shortlist_floor` from the report, noted in the spec tuning note. Ask-Keel input: his 164 numbers are in `43f9c652` on the 164 Tuning floor (offline `--recall`, `RECALL_KS`); 166 reuses the idea, built independently so it does not depend on that branch landing.

## R2 — Decision table (normative: contracts/skills-judgment.md)
Order: skip, abstain, drop, apply. Abstain precedes drop so an unsure `none` cannot silently remove a skill 114 would have applied. An invalid Noul with a trusted named Choice is a skip (not an apply), because gating a tool-narrowing skill on a missing answer is the wrong default; this differs from 164, where an invalid Noul still trusted the Choice.

## R3 — One winner, explicit stacks
**Decision**: Choice picks one automatic skill; explicit skills are resolved before the shortlist and stack. Narrows 114's "all matched skills" only when a judgment is consumed; abstain and skip keep 114 exactly. Docs say so (FR-016).

## R4 — Embedding reuse (FR-012)
The router encodes `routing_text` = prompt + history hint + routing hints (`nodes/routing.py`, `embed_route`). The matcher needs the raw prompt (`state.image_caption or state.prompt`, `nodes/skills.py:35`). The vectors differ, so reuse would change matching. **Decision**: keep the matcher's own `encode_query` (one per call) and say so in docs. Reuse is rejected unless a later phase embeds the same text twice.

## R5 — Judgment state
`{user, history?, context?, skills}` where `skills` is a capped list of `name: description` lines for the shortlist, so the Noul can see what "a skill" means (a Choice carries them as criteria; a Noul sees only state). `user` capped 2000, history 1500, context 600 (164 constants). Shared helper builds history/context for both nodes.

## R6 — Choice keys
Key is the skill slug. If two shortlist entries share a slug (bundled and imported, 114 FR-017), both use `slug (source)`. The key map is built per call and answers map back through it; a key outside the map is an invalid answer (skip).

## R7 — Bar validator
Keep a local copy of the 164/163 `_bar` logic in `ze_skills/judge.py`. Hoisting it into `ze_agents.system_one` would touch routing and speech-act and widen blast radius; a follow-up can unify the three.

## R8 — Returning the judgment from the matcher
`SkillMatcher.match(message, *, judgment_state=None) -> SkillMatchOutcome(matches, judgment)`. `SkillsJudgment` mirrors `RoutingJudgment` (result, question_kinds, consumed, skip_reason). The node passes it to `judgments_from_result`. ze-core reads it duck-typed; it never imports ze_skills.

## R9 — Trace visibility (FR-006)
**Decision**: `SkillMatch.below_floor` and `SkillUsageTrace.below_floor` (default false). Set when an automatic skill applies with similarity under `match_threshold`. Also visible through the consumed `skill` judgment row and the existing similarity percentage. Web: one badge in `SkillsSection.tsx`; the cast `(s as { script_ran?: boolean })` there suggests client types lag, so regenerate `@ze/client`. Alternative rejected: a new trigger value fans out to filters and API consumers.

## R10 — Calibration roster and set
Real skills vary, so `skills_roster.yaml` fixes about 12 realistic skills (distinguishable and near-miss pairs, EN descriptions with a few PT-aware wordings). `skills.jsonl` rows carry `id`, `lang`, `text`, optional `history`, `gold` (slug or `none`), `band` (`above`, `below_floor`, `none`) and `explicit`. About 80 rows, at least 30% PT. Metrics mirror 164 plus recall at k = 3..8. Option order shuffled in eval only. Offline `--recall` uses the real E5 singleton and the production `shortlist()` helper.

## R11 — Scores and wire quirks
164 found the Score arrives as a level index, not [0,1]. 166 asks no Score. Noul and Choice need no normalisation; the live run must still print the raw answers once so a maintainer can confirm.

## R12 — Files not touched
`SkillRecheckJob`, review, importer, parser, REST routes, workspace scripts, `allowed_tools` intersection.
