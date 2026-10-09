from __future__ import annotations

import re
from typing import Any

from ze_agents.system_one import SystemOneResult
from ze_logging import get_logger

from ze_skills.judge import (
    SkillsSurfaceConfig,
    build_judgment_state_skills,
    build_questions,
    decide,
    shortlist,
    skill_keys,
)

from ze_skills.store import SkillStore
from ze_skills.types import (
    Skill,
    SkillMatch,
    SkillMatchOutcome,
    SkillsJudgment,
    SkillTrigger,
)

log = get_logger(__name__)

_EXPLICIT_INVOCATION_RE = re.compile(r"(?<![\w/])/([a-z0-9][a-z0-9-]*)")

_DEFAULT_MATCH_THRESHOLD = 0.5


def _parse_explicit_slugs(message: str) -> set[str]:
    """Parse `/skill-name` tokens from raw message text (case-insensitive)."""
    if not message:
        return set()
    return {m.group(1) for m in _EXPLICIT_INVOCATION_RE.finditer(message.lower())}


class SkillMatcher:
    """Matches active skills to a turn's message.

    Two independent match paths, combined per turn (FR-019a, FR-019b):
    - automatic: cosine-similarity of the skill's `name + description` embedding
      against the message, above `match_threshold` (mirrors `EmbeddingRouter`'s
      `encode_query`/`encode_passage` pattern).
    - explicit: `/skill-name` tokens parsed from the raw message, resolved
      against active skills' slugs.

    When a calibrated `system_one` surface is wired (phase 166), E5 only shortlists
    the automatic candidates (down to `shortlist_floor`); one batched System One
    judgment then picks at most one automatic skill. Explicit skills bypass it. Off,
    uncalibrated, skipped or unsure, the 114 result is returned unchanged.

    Per-skill embeddings are cached, keyed by `(skill.id, skill.content_hash)` so
    the cache self-invalidates whenever a skill's content changes (approve/
    disable/enable naturally changes which skills `list_active()` returns; a
    content edit changes `content_hash`).
    """

    def __init__(
        self,
        store: SkillStore,
        embedder: Any,
        match_threshold: float = _DEFAULT_MATCH_THRESHOLD,
        *,
        system_one_client: Any = None,
        surface: SkillsSurfaceConfig | None = None,
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._threshold = match_threshold
        self._system_one = system_one_client
        self._surface = surface or SkillsSurfaceConfig()
        self._floor = self._surface.shortlist_floor
        if self._floor > match_threshold:
            log.warning(
                "skills_shortlist_floor_clamped",
                shortlist_floor=self._floor,
                match_threshold=match_threshold,
            )
            self._floor = match_threshold
        self._cache: dict[str, tuple[str, Any]] = {}

    async def match(
        self, message: str, *, judgment_state: dict[str, str] | None = None
    ) -> SkillMatchOutcome:
        skills = await self._store.list_active()
        if not skills:
            return SkillMatchOutcome(matches=[])

        explicit: list[SkillMatch] = []
        explicit_slugs = _parse_explicit_slugs(message)

        explicit_matched_ids: set[str] = set()
        if explicit_slugs:
            for skill in skills:
                if skill.slug in explicit_slugs:
                    explicit.append(
                        SkillMatch(skill=skill, trigger=SkillTrigger.EXPLICIT)
                    )
                    explicit_matched_ids.add(str(skill.id))

        remaining = [s for s in skills if str(s.id) not in explicit_matched_ids]
        scored: list[tuple[Skill, float]] = []
        if remaining and message and message.strip():
            try:
                query_vec = self._embedder.encode_query(
                    message, normalize_embeddings=True
                )
            except Exception as exc:
                log.warning("skill_matching_query_embed_failed", error=str(exc))
                query_vec = None

            if query_vec is not None:
                for skill in remaining:
                    similarity = self._similarity(skill, query_vec)
                    if similarity is not None:
                        scored.append((skill, similarity))

        legacy = explicit + [
            SkillMatch(
                skill=skill, trigger=SkillTrigger.AUTOMATIC, similarity=similarity
            )
            for skill, similarity in scored
            if similarity >= self._threshold
        ]

        if judgment_state is None or self._system_one is None or not scored:
            return SkillMatchOutcome(matches=legacy)
        if not self._surface.calibrated:
            if self._surface.enabled:
                log.warning("skills_surface_uncalibrated")
            return SkillMatchOutcome(matches=legacy)

        candidates = shortlist(scored, floor=self._floor, k=self._surface.shortlist_k)
        if not candidates:
            return SkillMatchOutcome(matches=legacy)

        keys = skill_keys([skill for skill, _ in candidates])
        similarities = {str(skill.id): sim for skill, sim in candidates}
        questions = build_questions(keys)
        state = build_judgment_state_skills(
            judgment_state, [skill for skill, _ in candidates]
        )
        try:
            result = await self._system_one.evaluate(state, questions, max_attempts=1)
        except Exception as exc:
            log.warning("skills_judgment_error", error=str(exc))
            result = SystemOneResult(outcome="skip", skip_reason="error")

        decision = decide(result, self._surface, list(keys))
        judgment = SkillsJudgment(
            result=result,
            question_kinds={qid: q.type for qid, q in questions.items()},
            consumed=decision.consumed,
            skip_reason=(
                decision.reason
                if decision.kind == "skip" and result.outcome == "ok"
                else None
            ),
        )

        if decision.kind == "apply" and decision.skill_key in keys:
            chosen = keys[decision.skill_key]
            similarity = similarities[str(chosen.id)]
            matches = explicit + [
                SkillMatch(
                    skill=chosen,
                    trigger=SkillTrigger.AUTOMATIC,
                    similarity=similarity,
                    below_floor=similarity < self._threshold,
                )
            ]
        elif decision.kind == "drop":
            matches = explicit
        else:
            matches = legacy
        return SkillMatchOutcome(matches=matches, judgment=judgment)

    def _similarity(self, skill: Skill, query_vec: Any) -> float | None:
        vec = self._embedding_for(skill)
        if vec is None:
            return None
        try:
            return float(vec @ query_vec)
        except Exception as exc:
            log.warning("skill_matching_similarity_failed", error=str(exc))
            return None

    def _embedding_for(self, skill: Skill) -> Any:
        cache_key = str(skill.id)
        cached = self._cache.get(cache_key)
        if cached is not None and cached[0] == skill.content_hash:
            return cached[1]
        text = f"{skill.name}: {skill.description}"
        try:
            vec = self._embedder.encode_passage([text], normalize_embeddings=True)[0]
        except Exception as exc:
            log.warning("skill_matching_passage_embed_failed", error=str(exc))
            return None
        self._cache[cache_key] = (skill.content_hash, vec)
        return vec
