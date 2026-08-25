from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from ze_agents.claims import ClaimKind, DecayProfile
from ze_agents.errors import UnlicensedClaimKindError
from ze_plugin.contribution import SourceFunction, TargetFace

from ze_memory.dream.dream_pass import DreamPass
from ze_memory.dream.types import ArtifactType


class _async_ctx:
    def __init__(self, conn):
        self._conn = conn

    async def __aenter__(self):
        return self._conn

    async def __aexit__(self, *_):
        pass


def _make_pool(fetchval_result: object = 1) -> MagicMock:
    conn = AsyncMock()
    conn.fetchval = AsyncMock(return_value=fetchval_result)
    pool = MagicMock()
    pool.acquire = MagicMock(return_value=_async_ctx(conn))
    return pool


def _make_dream_pass(pool: MagicMock | None = None) -> tuple[DreamPass, AsyncMock]:
    dream_store = AsyncMock()
    dream_store.save_artifact = AsyncMock(return_value=uuid4())
    dream_pass = DreamPass(
        pool=pool or _make_pool(),
        dream_store=dream_store,
        client=AsyncMock(),
        embedder=AsyncMock(),
    )
    return dream_pass, dream_store


def _artifact_kwargs(**overrides) -> dict:
    defaults = dict(
        run_id=uuid4(),
        artifact_type=ArtifactType.SYNTHESIZED_INSIGHT.value,
        content="Ze noticed a recurring pattern.",
        source_episode_ids=[uuid4()],
        source_fact_ids=[],
        support_count=3,
        distinct_session_count=2,
        temporal_spread_days=5,
        user_asserted_source_count=0,
    )
    defaults.update(overrides)
    return defaults


# ── FR-005: claim_kind=FACT is always rejected ──────────────────────────────────


async def test_fact_claim_kind_rejected_before_save():
    dream_pass, dream_store = _make_dream_pass()

    with pytest.raises(UnlicensedClaimKindError):
        await dream_pass._save_artifact_via_seam(
            **_artifact_kwargs(), claim_kind=ClaimKind.FACT
        )

    dream_store.save_artifact.assert_not_awaited()


async def test_inference_claim_kind_persists_with_neutral_confidence():
    dream_pass, dream_store = _make_dream_pass()

    await dream_pass._save_artifact_via_seam(**_artifact_kwargs())

    dream_store.save_artifact.assert_awaited_once()
    kwargs = dream_store.save_artifact.await_args.kwargs
    assert kwargs["artifact_type"] == ArtifactType.SYNTHESIZED_INSIGHT.value


async def test_save_artifact_via_seam_uses_neutral_confidence_and_self_face():
    """Confidence and target_face used at submission time, per research.md §11/§13."""
    from ze_plugin import contribution as contribution_module

    captured = {}
    original = contribution_module.validate_and_submit

    async def _spy(contribution, write, **checkers):
        captured["contribution"] = contribution
        return await original(contribution, write, **checkers)

    dream_pass, _ = _make_dream_pass()
    dream_pass_module_validate = "ze_memory.dream.dream_pass.validate_and_submit"

    import unittest.mock as mock

    with mock.patch(dream_pass_module_validate, new=_spy):
        await dream_pass._save_artifact_via_seam(**_artifact_kwargs())

    contribution = captured["contribution"]
    assert contribution.confidence.value == 0.5
    assert contribution.confidence.decay_profile == DecayProfile.TIME_LINEAR
    assert contribution.target_face == TargetFace.SELF
    assert contribution.source_function == SourceFunction.REFLECTION


# ── HINDSIGHT_FACT naming trap (research.md §6) ─────────────────────────────────


async def test_hindsight_fact_artifact_type_with_inference_claim_kind_succeeds():
    dream_pass, dream_store = _make_dream_pass()

    await dream_pass._save_artifact_via_seam(
        **_artifact_kwargs(artifact_type=ArtifactType.HINDSIGHT_FACT.value)
    )

    dream_store.save_artifact.assert_awaited_once()


async def test_hindsight_fact_artifact_type_with_fact_claim_kind_is_rejected():
    """The artifact_type's name ('hindsight_fact') must never leak into claim_kind."""
    dream_pass, dream_store = _make_dream_pass()

    with pytest.raises(UnlicensedClaimKindError):
        await dream_pass._save_artifact_via_seam(
            **_artifact_kwargs(artifact_type=ArtifactType.HINDSIGHT_FACT.value),
            claim_kind=ClaimKind.FACT,
        )

    dream_store.save_artifact.assert_not_awaited()


# ── FR-010: promotion gate (NLI/critic) pipeline is unaffected ─────────────────


async def test_scoring_pipeline_still_invokes_gates_and_critic_unchanged():
    pool = _make_pool()
    dream_store = AsyncMock()
    artifact_id = uuid4()
    dream_store.save_artifact = AsyncMock(return_value=artifact_id)
    dream_store.get_artifact_row = AsyncMock(
        return_value={
            "content": "Ze noticed a recurring pattern.",
            "source_episode_ids": [],
            "support_count": 3,
        }
    )
    dream_store.update_artifact_gate1 = AsyncMock()
    dream_store.update_artifact_gate2 = AsyncMock()
    dream_store.update_artifact_gate3 = AsyncMock()
    dream_store.update_artifact_critics = AsyncMock()
    dream_store.update_artifact_status = AsyncMock()

    dream_pass = DreamPass(
        pool=pool,
        dream_store=dream_store,
        client=AsyncMock(),
        embedder=AsyncMock(),
    )

    await dream_pass._save_artifact_via_seam(**_artifact_kwargs())

    gates = AsyncMock()
    gates.gate1_nli = AsyncMock(return_value=(True, 0.9))
    gates.gate2_novelty = AsyncMock(return_value=(True, 0.1))
    gates.gate3_retrievability = AsyncMock(return_value=True)
    critic = AsyncMock()
    critic.critique_artifact = AsyncMock(return_value=("PASS", "ok", "PASS", "ok"))

    await dream_pass._run_scoring_pipeline([artifact_id], gates, critic, "some-model")

    gates.gate1_nli.assert_awaited_once_with(
        "Ze noticed a recurring pattern.", [], "some-model"
    )
    gates.gate2_novelty.assert_awaited_once_with("Ze noticed a recurring pattern.")
    gates.gate3_retrievability.assert_awaited_once_with(
        "Ze noticed a recurring pattern.", [], 3
    )
    critic.critique_artifact.assert_awaited_once_with(
        "Ze noticed a recurring pattern.", []
    )
