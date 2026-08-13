from __future__ import annotations

from ze_logging import get_logger
from ze_proactive.job import proactive_job

from ze_skills import review
from ze_skills.store import SkillStore
from ze_skills.types import SkillSource

log = get_logger(__name__)


@proactive_job
class SkillRecheckJob:
    """Daily sweep re-fetching every imported skill's `origin_url` and
    reverting it to `pending_review` on a content change (FR-015, FR-021).
    Sweeps regardless of `active`/`disabled` status, since both represent
    previously-approved content that could go stale."""

    job_id = "skills_recheck"

    def __init__(self, skill_store: SkillStore) -> None:
        self._skill_store = skill_store

    async def run(self) -> None:
        skills = await self._skill_store.list(source=SkillSource.IMPORTED)
        for skill in skills:
            try:
                await review.refresh_skill(self._skill_store, skill.id)
            except Exception:
                log.exception("skill_recheck_failed", skill_id=str(skill.id))
