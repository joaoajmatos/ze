import asyncio
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_plugin.contribution import (
    Contribution,
    SourceFunction,
    TargetFace,
    validate_and_submit,
)

from ze_collision import detect
from ze_collision.detect import submit_and_detect_collisions


@pytest.fixture(autouse=True)
def _clear_window():
    detect._window.clear()
    yield
    detect._window.clear()


def _contribution(
    *,
    source_function: SourceFunction,
    claim_kind: ClaimKind = ClaimKind.FACT,
    target_face: TargetFace = TargetFace.WORLD,
    content: str | None = "some content",
    entity_ids: list | None = None,
    evidence: list | None = None,
) -> Contribution:
    if evidence is None and claim_kind in (ClaimKind.INFERENCE, ClaimKind.SUSPICION):
        from ze_plugin.contribution import EvidenceRef

        evidence = [EvidenceRef(kind="fact", id=uuid4())]

    return Contribution(
        claim_kind=claim_kind,
        provenance=Provenance.SYNTHESIZED,
        confidence=Confidence(value=0.7, decay_profile=DecayProfile.TIME_LINEAR),
        target_face=target_face,
        source_function=source_function,
        evidence=evidence or [],
        content=content,
        entity_ids=entity_ids or [],
    )


async def _write_ok():
    return uuid4()


def _nli_client(contradiction_score: float | None) -> AsyncMock:
    client = AsyncMock()
    if contradiction_score is None:
        client.scores.return_value = [None]
    else:
        client.scores.return_value = [
            {"contradiction": contradiction_score, "entailment": 0.0}
        ]
    return client


async def _always_exists(_id):
    return True


async def _submit(contribution, store, nli_client, write=None, evidence_checks=None):
    write = write or _write_ok
    checks = {"check_fact_exists": _always_exists}
    checks.update(evidence_checks or {})

    result = await submit_and_detect_collisions(
        contribution,
        write,
        result_id=lambda r: r,
        producer_kind="test_producer",
        collision_store=store,
        nli_client=nli_client,
        **checks,
    )
    # flush any scheduled background collision-check task
    pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    if pending:
        await asyncio.gather(*pending, return_exceptions=True)
    return result


async def test_conflicting_cross_function_pair_logs_one_collision() -> None:
    entity_id = uuid4()
    store = AsyncMock()
    nli = _nli_client(0.9)

    a = _contribution(
        source_function=SourceFunction.PERCEPTION,
        content="X moved to Berlin",
        entity_ids=[entity_id],
    )
    await _submit(a, store, nli)

    b = _contribution(
        source_function=SourceFunction.REFLECTION,
        claim_kind=ClaimKind.INFERENCE,
        content="X is still in Lisbon",
        entity_ids=[entity_id],
    )
    await _submit(b, store, nli)

    assert store.log.await_count == 1


async def test_same_source_function_pair_never_becomes_candidate() -> None:
    entity_id = uuid4()
    store = AsyncMock()
    nli = _nli_client(0.9)

    a = _contribution(
        source_function=SourceFunction.PERCEPTION,
        content="X moved to Berlin",
        entity_ids=[entity_id],
    )
    await _submit(a, store, nli)

    b = _contribution(
        source_function=SourceFunction.PERCEPTION,
        content="X moved to Lisbon",
        entity_ids=[entity_id],
    )
    await _submit(b, store, nli)

    nli.scores.assert_not_called()
    store.log.assert_not_called()


async def test_write_result_and_exceptions_pass_through_unchanged() -> None:
    contribution = _contribution(source_function=SourceFunction.PERCEPTION)

    async def _write():
        return "sentinel-result"

    result_direct = await validate_and_submit(contribution, _write)

    async def _write2():
        return "sentinel-result"

    result_wrapped = await submit_and_detect_collisions(
        contribution,
        _write2,
        result_id=lambda r: uuid4(),
        producer_kind="test_producer",
    )
    assert result_direct == result_wrapped == "sentinel-result"

    from ze_agents.errors import UnlicensedClaimKindError

    bad = _contribution(
        source_function=SourceFunction.MEMORY, claim_kind=ClaimKind.FACT
    )
    with pytest.raises(UnlicensedClaimKindError):
        await validate_and_submit(bad, _write)
    with pytest.raises(UnlicensedClaimKindError):
        await submit_and_detect_collisions(
            bad, _write, result_id=lambda r: uuid4(), producer_kind="test_producer"
        )


async def test_compatible_content_same_entity_logs_nothing() -> None:
    entity_id = uuid4()
    store = AsyncMock()
    nli = _nli_client(0.1)

    a = _contribution(
        source_function=SourceFunction.PERCEPTION,
        content="X likes coffee",
        entity_ids=[entity_id],
    )
    await _submit(a, store, nli)

    b = _contribution(
        source_function=SourceFunction.REFLECTION,
        claim_kind=ClaimKind.INFERENCE,
        content="X probably drinks coffee often",
        entity_ids=[entity_id],
    )
    await _submit(b, store, nli)

    store.log.assert_not_called()


async def test_same_target_face_no_shared_entity_unrelated_content_logs_nothing() -> (
    None
):
    store = AsyncMock()
    nli = _nli_client(0.05)

    a = _contribution(
        source_function=SourceFunction.PERCEPTION,
        content="unrelated fact one",
        target_face=TargetFace.WORLD,
        entity_ids=[],
    )
    await _submit(a, store, nli)

    b = _contribution(
        source_function=SourceFunction.REFLECTION,
        claim_kind=ClaimKind.INFERENCE,
        content="unrelated fact two",
        target_face=TargetFace.WORLD,
        entity_ids=[],
    )
    await _submit(b, store, nli)

    nli.scores.assert_called()
    store.log.assert_not_called()


async def test_only_genuinely_conflicting_pair_logged_among_three() -> None:
    entity_id = uuid4()
    store = AsyncMock()

    calls: list = []

    async def scores(pairs):
        calls.append(pairs)
        premise, hypothesis = pairs[0]
        cities = {"Berlin", "Lisbon"}
        mentioned = {c for c in cities if c in premise or c in hypothesis}
        if mentioned == cities:
            return [{"contradiction": 0.9}]
        return [{"contradiction": 0.05}]

    nli = AsyncMock()
    nli.scores.side_effect = scores

    a = _contribution(
        source_function=SourceFunction.PERCEPTION,
        content="X moved to Berlin",
        entity_ids=[entity_id],
    )
    await _submit(a, store, nli)

    b = _contribution(
        source_function=SourceFunction.REFLECTION,
        claim_kind=ClaimKind.INFERENCE,
        content="X likes museums",
        entity_ids=[entity_id],
    )
    await _submit(b, store, nli)

    c = _contribution(
        source_function=SourceFunction.EXECUTIVE,
        claim_kind=ClaimKind.FACT,
        content="X still lives in Lisbon",
        entity_ids=[entity_id],
    )
    await _submit(c, store, nli)

    assert store.log.await_count == 1


async def test_nli_failure_is_fail_open() -> None:
    entity_id = uuid4()
    store = AsyncMock()
    nli = AsyncMock()
    nli.scores.side_effect = RuntimeError("nli backend down")

    a = _contribution(
        source_function=SourceFunction.PERCEPTION,
        content="X moved to Berlin",
        entity_ids=[entity_id],
    )
    result_a = await _submit(a, store, nli)
    assert result_a is not None

    b = _contribution(
        source_function=SourceFunction.REFLECTION,
        claim_kind=ClaimKind.INFERENCE,
        content="X is still in Lisbon",
        entity_ids=[entity_id],
    )
    result_b = await _submit(b, store, nli)
    assert result_b is not None

    store.log.assert_not_called()


async def test_nli_timeout_is_fail_open() -> None:
    entity_id = uuid4()
    store = AsyncMock()
    nli = AsyncMock()

    async def _hang(_pairs):
        await asyncio.sleep(10)
        return [{"contradiction": 0.9}]

    nli.scores.side_effect = _hang

    original_timeout = detect._NLI_TIMEOUT_SECONDS
    detect._NLI_TIMEOUT_SECONDS = 0.05
    try:
        a = _contribution(
            source_function=SourceFunction.PERCEPTION,
            content="X moved to Berlin",
            entity_ids=[entity_id],
        )
        await _submit(a, store, nli)

        b = _contribution(
            source_function=SourceFunction.REFLECTION,
            claim_kind=ClaimKind.INFERENCE,
            content="X is still in Lisbon",
            entity_ids=[entity_id],
        )
        await _submit(b, store, nli)
    finally:
        detect._NLI_TIMEOUT_SECONDS = original_timeout

    store.log.assert_not_called()


async def test_unwired_collision_store_or_nli_is_noop() -> None:
    a = _contribution(source_function=SourceFunction.PERCEPTION)
    result = await submit_and_detect_collisions(
        a, _write_ok, result_id=lambda r: r, producer_kind="test_producer"
    )
    assert result is not None
