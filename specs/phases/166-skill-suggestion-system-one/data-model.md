# Data Model: System One Skill Gating

No tables, no migrations.

## `SkillsSurfaceConfig` (ze_skills/judge.py, frozen dataclass)
- `enabled: bool = False`
- `choice_trust: float | None = None`
- `needs_skill_hold: float | None = None`
- `shortlist_k: int` (default decided by task T-recall; min 1)
- `shortlist_floor: float` (default decided by the same report; parsed into [0, 1]; the matcher clamps it to `match_threshold` with a warning when it is higher)
- `calibrated` property: enabled and both bars set.

## `SkillsDecision` (frozen dataclass)
- `kind: "apply" | "drop" | "abstain" | "skip"`
- `reason: str`
- `skill_key: str | None` (apply only)
- `confidence: float | None` (Choice peakedness)
- `consumed: frozenset[str]` (`skill`, `needs_skill`)

## `SkillsJudgment` (ze_skills/types.py)
`result: SystemOneResult`, `question_kinds: dict[str, str]`, `consumed: frozenset[str]`, `skip_reason: str | None`.

## `SkillMatchOutcome` (ze_skills/types.py)
`matches: list[SkillMatch]`, `judgment: SkillsJudgment | None`.

## `SkillMatch` (changed)
Adds `below_floor: bool = False`.

## `SkillUsageTrace` (ze-core, changed)
Adds `below_floor: bool = False`. Old stored traces parse with the default.

## Judgment rows
Question ids `skill` (choice) and `needs_skill` (noul) become `JudgmentTrace` rows via `judgments_from_result`.

## Calibration row (eval/calibration/skills.jsonl)
`{id, lang: "en"|"pt", text, history?, gold: slug|"none", band: "above"|"below_floor"|"none", explicit: bool}`.
