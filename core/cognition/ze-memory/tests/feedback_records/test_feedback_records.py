from __future__ import annotations

import inspect
import pathlib
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from ze_agents.claims import ClaimKind, Confidence, DecayProfile, Provenance
from ze_agents.errors import (
    FeedbackRecordIdempotencyConflictError,
    FeedbackRecordValidationError,
    UnlicensedClaimKindError,
)
from ze_plugin.contribution import Contribution, SourceFunction, TargetFace

from ze_memory.feedback_records import (
    FeedbackKind,
    FeedbackRecordDraft,
    PostgresFeedbackStore,
    feedback_contribution,
    submit_feedback_record,
    validate_draft,
)
from ze_memory.feedback_records.types import RATING_KINDS


def _draft(**overrides) -> FeedbackRecordDraft:
    base = dict(
        idempotency_key="feedback:m1:k1",
        message_id=uuid4(),
        thread_id="thread-1",
        kind=FeedbackKind.THUMBS_DOWN,
        occurred_at=datetime.now(timezone.utc),
        trace_present=True,
    )
    base.update(overrides)
    return FeedbackRecordDraft(**base)


def _row(draft: FeedbackRecordDraft, **overrides) -> dict:
    row = {
        "id": uuid4(),
        "idempotency_key": draft.idempotency_key,
        "message_id": draft.message_id,
        "thread_id": draft.thread_id,
        "kind": draft.kind.value,
        "occurred_at": draft.occurred_at,
        "provenance": "prompt_supplied",
        "confidence": 1.0,
        "target_face": "world",
        "trace_present": draft.trace_present,
        "created_at": datetime.now(timezone.utc),
    }
    row.update(overrides)
    return row


def _pool(fetchrow=None, fetch=None):
    conn = AsyncMock()
    if callable(fetchrow):
        conn.fetchrow = AsyncMock(side_effect=fetchrow)
    else:
        conn.fetchrow = AsyncMock(return_value=fetchrow)
    conn.fetch = AsyncMock(return_value=fetch or [])
    conn.execute = AsyncMock()

    @asynccontextmanager
    async def acquire():
        yield conn

    pool = MagicMock()
    pool.acquire = acquire
    return pool, conn


# ── types ────────────────────────────────────────────────────────────────────


def test_kinds_are_closed() -> None:
    assert {k.value for k in FeedbackKind} == {
        "thumbs_up",
        "thumbs_down",
        "cleared",
        "retry_requested",
    }
    assert FeedbackKind.RETRY_REQUESTED not in RATING_KINDS
    assert RATING_KINDS == {
        FeedbackKind.THUMBS_UP,
        FeedbackKind.THUMBS_DOWN,
        FeedbackKind.CLEARED,
    }


def test_validate_draft_rejects_blank_key_and_thread() -> None:
    with pytest.raises(FeedbackRecordValidationError):
        validate_draft(_draft(idempotency_key="  "))
    with pytest.raises(FeedbackRecordValidationError):
        validate_draft(_draft(thread_id=""))


def test_validate_draft_rejects_naive_timestamp() -> None:
    with pytest.raises(FeedbackRecordValidationError):
        validate_draft(_draft(occurred_at=datetime(2026, 1, 1)))


def test_draft_has_no_free_text_field() -> None:
    names = set(FeedbackRecordDraft.__dataclass_fields__)
    assert names == {
        "idempotency_key",
        "message_id",
        "thread_id",
        "kind",
        "occurred_at",
        "trace_present",
    }


# ── contribution seam ────────────────────────────────────────────────────────


async def test_submit_appends_through_the_seam() -> None:
    draft = _draft()
    pool, conn = _pool(fetchrow=_row(draft))
    store = PostgresFeedbackStore(pool)
    record = await submit_feedback_record(store, feedback_contribution(draft))
    assert record.kind is FeedbackKind.THUMBS_DOWN
    assert record.provenance is Provenance.PROMPT_SUPPLIED
    assert record.confidence.value == 1.0
    assert record.target_face is TargetFace.WORLD
    args = conn.fetchrow.await_args.args
    assert "INSERT INTO feedback_records" in args[0]
    assert "ON CONFLICT (idempotency_key) DO NOTHING" in args[0]


async def test_contribution_is_perception_feedback_record() -> None:
    c = feedback_contribution(_draft())
    assert c.source_function is SourceFunction.PERCEPTION
    assert c.claim_kind is ClaimKind.FEEDBACK_RECORD
    assert c.target_face is TargetFace.WORLD
    assert c.provenance is Provenance.PROMPT_SUPPLIED
    assert c.confidence.value == 1.0


@pytest.mark.parametrize(
    "source",
    [s for s in SourceFunction if s is not SourceFunction.PERCEPTION],
)
async def test_other_source_functions_are_rejected(source) -> None:
    pool, conn = _pool()
    c = feedback_contribution(_draft())
    c.source_function = source
    with pytest.raises(FeedbackRecordValidationError):
        await submit_feedback_record(PostgresFeedbackStore(pool), c)
    conn.fetchrow.assert_not_awaited()


async def test_wrong_claim_kind_is_rejected() -> None:
    pool, conn = _pool()
    c = Contribution(
        claim_kind=ClaimKind.FACT,
        provenance=Provenance.PROMPT_SUPPLIED,
        confidence=Confidence(1.0, DecayProfile.TIME_LINEAR),
        target_face=TargetFace.USER,
        source_function=SourceFunction.PERCEPTION,
    )
    with pytest.raises(FeedbackRecordValidationError):
        await submit_feedback_record(PostgresFeedbackStore(pool), c)
    conn.fetchrow.assert_not_awaited()


async def test_missing_payload_is_rejected() -> None:
    pool, _ = _pool()
    c = feedback_contribution(_draft())
    c.feedback_record = None
    with pytest.raises(FeedbackRecordValidationError):
        await submit_feedback_record(PostgresFeedbackStore(pool), c)


async def test_seam_licence_still_enforced() -> None:
    from ze_plugin.contribution import validate_and_submit

    c = feedback_contribution(_draft())
    c.source_function = SourceFunction.ACTION
    with pytest.raises(UnlicensedClaimKindError):
        await validate_and_submit(c, AsyncMock())


# ── store ────────────────────────────────────────────────────────────────────


async def test_repeat_key_returns_existing_without_duplicate() -> None:
    draft = _draft()
    existing = _row(draft)
    calls = {"n": 0}

    async def fetchrow(sql, *args):
        calls["n"] += 1
        if "INSERT" in sql:
            return None
        return existing

    pool, _ = _pool(fetchrow=fetchrow)
    record = await PostgresFeedbackStore(pool).append(feedback_contribution(draft))
    assert record.id == existing["id"]


async def test_reused_key_with_different_observation_conflicts() -> None:
    draft = _draft()
    existing = _row(draft, kind="thumbs_up")

    async def fetchrow(sql, *args):
        return None if "INSERT" in sql else existing

    pool, _ = _pool(fetchrow=fetchrow)
    with pytest.raises(FeedbackRecordIdempotencyConflictError):
        await PostgresFeedbackStore(pool).append(feedback_contribution(draft))


async def test_latest_rating_ignores_retry_requested() -> None:
    draft = _draft()
    pool, conn = _pool(fetchrow=_row(draft))
    record = await PostgresFeedbackStore(pool).latest_rating(draft.message_id)
    assert record is not None
    sql = conn.fetchrow.await_args.args[0]
    assert "kind IN ('thumbs_up', 'thumbs_down', 'cleared')" in sql
    assert "ORDER BY occurred_at DESC, created_at DESC" in sql


async def test_latest_rating_none_when_unrated() -> None:
    pool, _ = _pool(fetchrow=None)
    assert await PostgresFeedbackStore(pool).latest_rating(uuid4()) is None


async def test_list_for_messages_groups_oldest_first() -> None:
    m1, m2 = uuid4(), uuid4()
    t0 = datetime.now(timezone.utc)
    rows = [
        _row(_draft(message_id=m1, occurred_at=t0, idempotency_key="a")),
        _row(
            _draft(
                message_id=m1,
                kind=FeedbackKind.CLEARED,
                occurred_at=t0 + timedelta(seconds=5),
                idempotency_key="b",
            )
        ),
        _row(_draft(message_id=m2, idempotency_key="c")),
    ]
    pool, conn = _pool(fetch=rows)
    grouped = await PostgresFeedbackStore(pool).list_for_messages([m1, m2])
    assert [r.kind for r in grouped[m1]] == [
        FeedbackKind.THUMBS_DOWN,
        FeedbackKind.CLEARED,
    ]
    assert len(grouped[m2]) == 1
    assert "ORDER BY occurred_at ASC, created_at ASC" in conn.fetch.await_args.args[0]


async def test_list_for_messages_empty_input_skips_query() -> None:
    pool, conn = _pool()
    assert await PostgresFeedbackStore(pool).list_for_messages([]) == {}
    conn.fetch.assert_not_awaited()


async def test_history_returns_all_kinds() -> None:
    draft = _draft(kind=FeedbackKind.RETRY_REQUESTED)
    pool, _ = _pool(fetch=[_row(draft)])
    history = await PostgresFeedbackStore(pool).history(draft.message_id)
    assert history[0].kind is FeedbackKind.RETRY_REQUESTED


def test_store_has_no_update_or_delete_api() -> None:
    public = {n for n in dir(PostgresFeedbackStore) if not n.startswith("_")}
    assert public == {"append", "history", "latest_rating", "list_for_messages"}


# ── boundaries ───────────────────────────────────────────────────────────────


def test_package_never_touches_fact_paths() -> None:
    root = (
        pathlib.Path(__file__).resolve().parents[2] / "ze_memory" / "feedback_records"
    )
    for path in root.rglob("*.py"):
        text = path.read_text()
        assert "memory_facts" not in text
        assert "propose_facts" not in text
        assert "_write_fact_with_contradiction_check" not in text


def test_submit_does_not_call_fact_writers() -> None:
    source = inspect.getsource(submit_feedback_record)
    assert "memory_facts" not in source
    assert "propose_facts" not in source
