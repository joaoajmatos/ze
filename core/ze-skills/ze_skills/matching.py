from __future__ import annotations

import re
from typing import Any

from ze_logging import get_logger

from ze_skills.store import SkillStore
from ze_skills.types import Skill, SkillMatch, SkillTrigger

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
    ) -> None:
        self._store = store
        self._embedder = embedder
        self._threshold = match_threshold
        self._cache: dict[str, tuple[str, Any]] = {}

    async def match(self, message: str) -> list[SkillMatch]:
        skills = await self._store.list_active()
        if not skills:
            return []

        matches: list[SkillMatch] = []
        explicit_slugs = _parse_explicit_slugs(message)

        explicit_matched_ids: set[str] = set()
        if explicit_slugs:
            for skill in skills:
                if skill.slug in explicit_slugs:
                    matches.append(
                        SkillMatch(skill=skill, trigger=SkillTrigger.EXPLICIT)
                    )
                    explicit_matched_ids.add(str(skill.id))

        remaining = [s for s in skills if str(s.id) not in explicit_matched_ids]
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
                    if similarity is not None and similarity >= self._threshold:
                        matches.append(
                            SkillMatch(
                                skill=skill,
                                trigger=SkillTrigger.AUTOMATIC,
                                similarity=similarity,
                            )
                        )

        return matches

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
