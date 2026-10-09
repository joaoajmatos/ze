"""Skills judgment — System One questions, state, surface config and the decision table.

E5 stays the shortlist. One batched request asks a Choice over the shortlisted skills
plus ``none`` and a Noul ("does this request need a skill?"). Pure code turns the
answers into apply / drop / abstain / skip (specs/phases/166-.../contracts/skills-judgment.md).
"""

from __future__ import annotations

import math
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal

from ze_agents.system_one import SystemOneAnswer, SystemOneQuestion, SystemOneResult
from ze_logging import get_logger

from ze_skills.types import Skill

log = get_logger(__name__)

DEFAULT_SHORTLIST_K = 5
DEFAULT_SHORTLIST_FLOOR = 0.35
DESCRIPTION_CAP = 300
SKILLS_STATE_CAP = 1500

NONE_KEY = "none"
Q_SKILL = "skill"
Q_NEEDS = "needs_skill"

_JUDGE_SUFFIX = "Judge the user's words; history and context are background only."
_NONE_CRITERION = "No listed skill is needed for this request."
_SKILL_INSTRUCTIONS = (
    "Which one skill should be applied to this request? Answer none if no listed "
    "skill is needed. " + _JUDGE_SUFFIX
)
_NEEDS_INSTRUCTIONS = (
    "Does answering this request well depend on one of the listed skills? "
    + _JUDGE_SUFFIX
)


@dataclass(frozen=True)
class SkillsSurfaceConfig:
    enabled: bool = False
    choice_trust: float | None = None
    needs_skill_hold: float | None = None
    shortlist_k: int = DEFAULT_SHORTLIST_K
    shortlist_floor: float = DEFAULT_SHORTLIST_FLOOR

    @property
    def calibrated(self) -> bool:
        return (
            self.enabled
            and self.choice_trust is not None
            and self.needs_skill_hold is not None
        )


def _bar(value: Any, name: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        log.warning("skills_bar_invalid", bar=name)
        return None
    if math.isnan(value) or not 0.0 <= value <= 1.0:
        log.warning("skills_bar_invalid", bar=name)
        return None
    return float(value)


def _shortlist_k(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        if value is not None:
            log.warning("skills_shortlist_k_invalid")
        return DEFAULT_SHORTLIST_K
    return value


def _shortlist_floor(value: Any) -> float:
    parsed = _bar(value, "shortlist_floor")
    return DEFAULT_SHORTLIST_FLOOR if parsed is None else parsed


def skills_surface_config(settings: Any) -> SkillsSurfaceConfig:
    config = (
        settings if isinstance(settings, dict) else getattr(settings, "config", None)
    )
    if not isinstance(config, dict):
        return SkillsSurfaceConfig()
    system_one = config.get("system_one")
    surfaces = system_one.get("surfaces") if isinstance(system_one, dict) else None
    block = surfaces.get("skills") if isinstance(surfaces, dict) else None
    if not isinstance(block, dict):
        return SkillsSurfaceConfig()
    return SkillsSurfaceConfig(
        enabled=block.get("enabled") is True,
        choice_trust=_bar(block.get("choice_trust"), "choice_trust"),
        needs_skill_hold=_bar(block.get("needs_skill_hold"), "needs_skill_hold"),
        shortlist_k=_shortlist_k(block.get("shortlist_k", DEFAULT_SHORTLIST_K)),
        shortlist_floor=_shortlist_floor(block.get("shortlist_floor")),
    )


def shortlist(
    scored: Sequence[tuple[Skill, float]], *, floor: float, k: int
) -> list[tuple[Skill, float]]:
    """Skills at or above ``floor``, best cosine first (stable on id), at most ``k``."""
    kept = [(skill, sim) for skill, sim in scored if sim >= floor]
    kept.sort(key=lambda pair: (-pair[1], str(pair[0].id)))
    return kept[:k]


def skill_keys(skills: Sequence[Skill]) -> dict[str, Skill]:
    """Choice option key → skill; slug, or ``slug (source)`` when two share a slug."""
    counts = Counter(s.slug for s in skills)
    keys: dict[str, Skill] = {}
    for skill in skills:
        key = skill.slug
        if counts[key] > 1:
            key = f"{skill.slug} ({skill.source.value})"
        keys[key] = skill
    return keys


def _capped(description: str) -> str:
    return description.strip()[:DESCRIPTION_CAP]


def build_questions(keys: Mapping[str, Skill]) -> dict[str, SystemOneQuestion]:
    criteria = {key: _capped(skill.description) for key, skill in keys.items()}
    criteria[NONE_KEY] = _NONE_CRITERION
    return {
        Q_SKILL: SystemOneQuestion(
            type="choice", instructions=_SKILL_INSTRUCTIONS, criteria=criteria
        ),
        Q_NEEDS: SystemOneQuestion(type="noul", instructions=_NEEDS_INSTRUCTIONS),
    }


def build_judgment_state_skills(
    base: Mapping[str, str], skills: Sequence[Skill]
) -> dict[str, str]:
    """``base`` plus a capped ``skills`` line list so the Noul knows what "a skill" is."""
    lines = "\n".join(f"{s.name}: {_capped(s.description)}" for s in skills)
    return {**base, "skills": lines[:SKILLS_STATE_CAP]}


DecisionKind = Literal["apply", "drop", "abstain", "skip"]


@dataclass(frozen=True)
class SkillsDecision:
    kind: DecisionKind
    reason: str
    skill_key: str | None = None
    confidence: float | None = None
    consumed: frozenset[str] = frozenset()


def _valid_choice(answer: SystemOneAnswer | None, allowed: Sequence[str]) -> bool:
    return (
        answer is not None
        and answer.type == "choice"
        and answer.choice is not None
        and answer.confidence is not None
        and (answer.choice == NONE_KEY or answer.choice in allowed)
    )


def _valid_noul(answer: SystemOneAnswer | None) -> bool:
    return (
        answer is not None
        and answer.type == "noul"
        and isinstance(answer.noul, (int, float))
        and not isinstance(answer.noul, bool)
        and not math.isnan(answer.noul)
    )


def decide(
    result: SystemOneResult, cfg: SkillsSurfaceConfig, keys: Sequence[str]
) -> SkillsDecision:
    """Pure decision over one result (contract order: skip, abstain, drop, apply). Never raises."""
    if result.outcome == "skip":
        return SkillsDecision("skip", result.skip_reason or "error")
    trust_bar, hold_bar = cfg.choice_trust, cfg.needs_skill_hold
    if trust_bar is None or hold_bar is None:
        return SkillsDecision("skip", "uncalibrated")

    choice = result.answers.get(Q_SKILL)
    if choice is None or not _valid_choice(choice, keys):
        return SkillsDecision("skip", "invalid_answer")
    peakedness = float(choice.confidence or 0.0)

    if peakedness < trust_bar:
        return SkillsDecision("abstain", "choice_unsure", confidence=peakedness)
    if choice.choice == NONE_KEY:
        return SkillsDecision(
            "drop",
            "choice_none",
            confidence=peakedness,
            consumed=frozenset({Q_SKILL}),
        )

    noul = result.answers.get(Q_NEEDS)
    if noul is None or not _valid_noul(noul):
        return SkillsDecision("skip", "invalid_answer")
    consumed = frozenset({Q_SKILL, Q_NEEDS})
    if float(noul.noul or 0.0) < hold_bar:
        return SkillsDecision(
            "drop", "not_needed", confidence=peakedness, consumed=consumed
        )
    return SkillsDecision(
        "apply",
        "chosen",
        skill_key=choice.choice,
        confidence=peakedness,
        consumed=consumed,
    )
