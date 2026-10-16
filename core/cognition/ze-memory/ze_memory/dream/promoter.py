"""Morning Integration: support validation, auto-promote, forgetting, rollback, confidence decay."""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from ze_agents.claims import DecayProfile, Provenance, decay
from ze_logging import get_logger
from ze_memory.dream.types import ArtifactStatus, ArtifactType
from ze_memory.procedures.errors import ProcedureLifecycleError
from ze_memory.procedures.types import ProcedureCandidate, ProcedureSourceKind
from ze_plugin.contribution import EvidenceRef

log = get_logger(__name__)

_DEFAULT_MIN_SUPPORT = 3
_DEFAULT_MIN_DISTINCT_SESSIONS = 2
_DEFAULT_MIN_TEMPORAL_SPREAD_DAYS = 7
_DEFAULT_MAX_USER_ASSERTED = 1
_DEFAULT_SYNTHETIC_FACT_VALID_DAYS = 90
_DEFAULT_DECAY_RATE = 0.1


class DreamPromoter:
    def __init__(
        self,
        pool: Any,
        dream_store: Any,
        embedder: Any | None = None,
        settings: Any = None,
        procedure_admission: Any | None = None,
    ) -> None:
        self._pool = pool
        self._dream_store = dream_store
        self._embedder = embedder
        self._settings = settings
        self._procedures = procedure_admission

    async def run_morning_integration(self, run_id: UUID) -> dict:
        start = time.monotonic()
        cfg = self._config()

        min_support = int(cfg.get("auto_promote_min_support", _DEFAULT_MIN_SUPPORT))
        min_sessions = int(
            cfg.get(
                "auto_promote_min_distinct_sessions", _DEFAULT_MIN_DISTINCT_SESSIONS
            )
        )
        min_spread = int(
            cfg.get(
                "auto_promote_min_temporal_spread_days",
                _DEFAULT_MIN_TEMPORAL_SPREAD_DAYS,
            )
        )
        max_user_asserted = int(
            cfg.get("auto_promote_max_user_asserted", _DEFAULT_MAX_USER_ASSERTED)
        )
        valid_days = int(
            cfg.get("synthetic_fact_valid_days", _DEFAULT_SYNTHETIC_FACT_VALID_DAYS)
        )
        decay_rate = float(cfg.get("decay_rate", _DEFAULT_DECAY_RATE))

        pending_artifacts = await self._dream_store.get_pending_artifacts_for_run(
            run_id
        )

        promoted = 0
        rejected = 0

        for row in pending_artifacts:
            artifact_id = row["id"]
            artifact_type = row["artifact_type"]

            # Already rejected by scoring pipeline
            if row["status"] == ArtifactStatus.REJECTED.value:
                rejected += 1
                continue

            # A hindsight_fact is never auto-promoted, and nobody reviews it by hand.
            if artifact_type == ArtifactType.HINDSIGHT_FACT.value:
                await self._dream_store.update_artifact_status(
                    artifact_id, ArtifactStatus.REJECTED.value
                )
                rejected += 1
                continue

            # Support validation
            passes_support = (
                row.get("support_count", 0) >= min_support
                and row.get("distinct_session_count", 0) >= min_sessions
                and row.get("temporal_spread_days", 0) >= min_spread
                and row.get("user_asserted_source_count", 0) <= max_user_asserted
            )

            # Critic must have passed (both a and b PASS)
            critic_passed = (
                row.get("critic_a_verdict") == "PASS"
                and row.get("critic_b_verdict") == "PASS"
            )

            if not critic_passed:
                await self._dream_store.update_artifact_status(
                    artifact_id, ArtifactStatus.REJECTED.value
                )
                await self._decay_source_episodes(
                    row.get("source_episode_ids") or [], decay_rate
                )
                rejected += 1
                continue

            if passes_support:
                await self._promote(row, run_id, valid_days)
                promoted += 1
            else:
                await self._dream_store.update_artifact_status(
                    artifact_id, ArtifactStatus.REJECTED.value
                )
                rejected += 1

        # Synthetic fact confidence decay + hard expiry at valid_until
        await self._run_confidence_decay()
        await self._expire_stale_synthetic_facts()

        duration_ms = int((time.monotonic() - start) * 1000)
        log.info(
            "morning_integration_complete",
            promoted=promoted,
            rejected=rejected,
            duration_ms=duration_ms,
        )
        return {
            "promoted": promoted,
            "rejected": rejected,
            "duration_ms": duration_ms,
        }

    async def _promote(self, row: dict, run_id: UUID, valid_days: int) -> None:
        artifact_id = row["id"]
        artifact_type = row["artifact_type"]
        content = row["content"]
        valid_until = datetime.now(tz=timezone.utc) + timedelta(days=valid_days)

        if artifact_type == ArtifactType.SYNTHESIZED_INSIGHT.value:
            fact_id = await self._insert_fact(
                content=content,
                run_id=run_id,
                source_fact_ids=row.get("source_fact_ids") or [],
                valid_until=valid_until,
            )
            await self._dream_store.mark_artifact_promoted(
                artifact_id,
                promoted_to="memory_facts",
                promoted_id=fact_id,
            )

        elif artifact_type in (
            ArtifactType.SYNTHESIZED_PROCEDURE.value,
            ArtifactType.PLAN_STRESS_TEST.value,
        ):
            proc_id = await self._insert_procedure(
                content=content, run_id=run_id, artifact_id=artifact_id
            )
            await self._dream_store.mark_artifact_promoted(
                artifact_id,
                promoted_to="procedure_candidates",
                promoted_id=proc_id,
            )
        else:
            # Unknown type — mark promoted without a target record
            await self._dream_store.mark_artifact_promoted(artifact_id)

    async def _insert_fact(
        self,
        content: str,
        run_id: UUID,
        source_fact_ids: list[Any],
        valid_until: datetime,
    ) -> UUID:
        embedding = None
        if self._embedder is not None:
            try:
                embedding = list(self._embedder.encode(content))
            except Exception:
                pass

        async with self._pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                INSERT INTO memory_facts (
                    predicate, value, embedding, confidence, reviewed,
                    provenance, valid_until, dream_run_id, derived_from,
                    corroborated, creation_method, agent, claim_kind
                ) VALUES (
                    'synthesized_insight', $1, $2::vector, 0.7, false,
                    'synthesized', $3, $4, $5,
                    false, 'synthesized', 'dream', 'inference'
                )
                RETURNING id
                """,
                content,
                embedding,
                valid_until,
                run_id,
                [str(fid) for fid in source_fact_ids],
            )
        return row["id"]

    async def _insert_procedure(
        self, content: str, run_id: UUID, artifact_id: UUID
    ) -> UUID:
        if self._procedures is None:
            raise ProcedureLifecycleError(
                "procedure admission is required for dream procedure promotion"
            )
        steps = [line.strip() for line in content.splitlines() if line.strip()] or [
            content[:200]
        ]
        saved = await self._procedures.submit_procedure_candidate(
            ProcedureCandidate(
                source_kind=ProcedureSourceKind.REFLECTION,
                provenance=Provenance.SYNTHESIZED,
                name=content[:200],
                trigger="reviewed dream procedure",
                preconditions=[],
                steps=steps[:20],
                success_criteria=["procedure remains useful after review"],
                evidence_refs=[EvidenceRef(kind="episode", id=artifact_id)],
            )
        )
        if saved.id is None:
            raise ProcedureLifecycleError("dream procedure candidate missing id")
        return saved.id

    async def _run_confidence_decay(self) -> None:
        """Decrement confidence on non-corroborated synthetic facts older than 30 days."""
        async with self._pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, confidence, reviewed, contradicted
                FROM memory_facts
                WHERE provenance = 'synthesized'
                  AND corroborated = false
                  AND created_at < now() - interval '30 days'
                  AND contradicted = false
                """
            )
            for row in rows:
                new_confidence = decay(
                    row["confidence"], DecayProfile.TIME_LINEAR, elapsed_days=30.0
                )
                reviewed = row["reviewed"] if new_confidence >= 0.50 else False
                contradicted = row["contradicted"] if new_confidence >= 0.25 else True
                await conn.execute(
                    """
                    UPDATE memory_facts SET
                        confidence = $2, reviewed = $3, contradicted = $4
                    WHERE id = $1
                    """,
                    row["id"],
                    new_confidence,
                    reviewed,
                    contradicted,
                )

    async def _expire_stale_synthetic_facts(self) -> None:
        """Contradict synthesized facts that have passed their valid_until deadline."""
        async with self._pool.acquire() as conn:
            result = await conn.execute(
                """
                UPDATE memory_facts SET
                    contradicted = true,
                    reviewed = false
                WHERE provenance = 'synthesized'
                  AND corroborated = false
                  AND contradicted = false
                  AND valid_until IS NOT NULL
                  AND valid_until < now()
                """
            )
        expired = int(result.split()[-1]) if result else 0
        if expired:
            log.info("synthetic_facts_expired", count=expired)

    async def _decay_source_episodes(
        self, episode_ids: list[Any], rate: float = _DEFAULT_DECAY_RATE
    ) -> None:
        if not episode_ids:
            return
        async with self._pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE memory_episode_metadata SET
                    retrieval_weight = GREATEST(0.0, retrieval_weight - $2),
                    updated_at = now()
                WHERE episode_id = ANY($1::uuid[])
                """,
                list(episode_ids),
                rate,
            )

    def _config(self) -> dict:
        if self._settings is None:
            return {}
        if isinstance(self._settings, dict):
            return self._settings.get("dream", {})
        cfg = getattr(self._settings, "config", None)
        if isinstance(cfg, dict):
            return cfg.get("dream", {})
        return {}
