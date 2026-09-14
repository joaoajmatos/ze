from __future__ import annotations

from ze_agents.claims import DecayProfile, decay
from ze_logging import get_logger
from ze_proactive.job import proactive_job

from ze_correlation.store import PostgresHypothesisStore

log = get_logger(__name__)

DEFAULT_DECAY_WINDOW_DAYS = 30


@proactive_job
class HypothesisDecayJob:
    job_id = "hypothesis_decay_sweep"

    def __init__(
        self,
        hypothesis_store: PostgresHypothesisStore,
        window_days: int = DEFAULT_DECAY_WINDOW_DAYS,
    ) -> None:
        self._hypothesis_store = hypothesis_store
        self._window_days = window_days

    async def run(self) -> None:
        candidates = await self._hypothesis_store.list_decay_candidates(
            self._window_days
        )
        for hypothesis in candidates:
            new_confidence = decay(
                hypothesis.confidence,
                DecayProfile.TIME_LINEAR,
                elapsed_days=self._window_days,
            )
            if new_confidence == hypothesis.confidence:
                continue
            await self._hypothesis_store.set_confidence(hypothesis.id, new_confidence)
            log.info(
                "hypothesis_confidence_decayed",
                hypothesis_id=str(hypothesis.id),
                new_confidence=new_confidence,
            )
