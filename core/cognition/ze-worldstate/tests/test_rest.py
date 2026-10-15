from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from ze_plugin.contribution import EvidenceRef
from ze_worldstate import rest
from ze_worldstate.types import (
    LoopClaimKind,
    LoopProvenance,
    LoopSource,
    LoopSourceRole,
    LoopState,
    OpenLoop,
    SourceKey,
)

NOW = datetime(2026, 10, 15, 9, 0, tzinfo=timezone.utc)


def _loop(**overrides) -> OpenLoop:
    defaults = dict(
        id=uuid4(),
        title="Sort out the deposit with the landlord",
        claim_kind=LoopClaimKind.SUSPICION,
        provenance=LoopProvenance.CONVERSATION,
        confidence=0.3,
        state=LoopState.SUSPECTED,
        created_at=NOW,
        updated_at=NOW,
    )
    defaults.update(overrides)
    return OpenLoop(**defaults)


def _source(
    loop_id,
    *,
    role=LoopSourceRole.CORROBORATION,
    inflow="email",
    ref="G1",
    evidence=None,
    same_concern=None,
    promoted=False,
    minutes=0,
) -> LoopSource:
    return LoopSource(
        loop_id=loop_id,
        role=role,
        key=SourceKey(inflow, ref),
        evidence=evidence,
        same_concern=same_concern,
        promoted=promoted,
        created_at=NOW + timedelta(minutes=minutes),
    )


async def test_list_loops_adds_promoted_and_source_inflows_in_one_query():
    loop = _loop()
    other = _loop(id=uuid4(), title="No sources here")
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[loop, other])
    loop_store.list_sources_for = AsyncMock(
        return_value={
            loop.id: [
                _source(loop.id, role=LoopSourceRole.ORIGIN, inflow="conversation", ref="T1"),
                _source(loop.id, inflow="email", ref="G1", same_concern=0.93, promoted=True),
            ]
        }
    )

    items = await rest.list_loops(loop_store)

    loop_store.list_sources_for.assert_awaited_once_with([loop.id, other.id])
    assert items[0]["promoted"] is True
    assert items[0]["source_inflows"] == ["conversation", "email"]
    assert items[1]["promoted"] is False
    assert items[1]["source_inflows"] == []


async def test_list_loops_source_inflows_are_distinct_and_first_seen_order():
    loop = _loop()
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[loop])
    loop_store.list_sources_for = AsyncMock(
        return_value={
            loop.id: [
                _source(loop.id, role=LoopSourceRole.ORIGIN, inflow="conversation", ref="T1"),
                _source(loop.id, inflow="email", ref="G1", minutes=1),
                _source(loop.id, inflow="conversation", ref="T2", minutes=2),
            ]
        }
    )

    items = await rest.list_loops(loop_store)

    assert items[0]["source_inflows"] == ["conversation", "email"]


async def test_list_loops_not_promoted_when_no_corroboration_promoted():
    loop = _loop()
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[loop])
    loop_store.list_sources_for = AsyncMock(
        return_value={
            loop.id: [
                _source(loop.id, role=LoopSourceRole.ORIGIN, inflow="conversation", ref="T1"),
                _source(loop.id, inflow="email", ref="G1", same_concern=0.8, promoted=False),
            ]
        }
    )

    items = await rest.list_loops(loop_store)

    assert items[0]["promoted"] is False


async def test_list_loops_empty_list_skips_the_source_query():
    loop_store = AsyncMock()
    loop_store.list = AsyncMock(return_value=[])
    loop_store.list_sources_for = AsyncMock(return_value={})

    items = await rest.list_loops(loop_store)

    assert items == []
    loop_store.list_sources_for.assert_awaited_once_with([])


async def test_get_loop_adds_sources_in_time_order():
    loop = _loop()
    loop_id = loop.id
    origin = _source(
        loop_id,
        role=LoopSourceRole.ORIGIN,
        inflow="conversation",
        ref="T1",
        evidence=EvidenceRef(kind="episode", id=uuid4()),
        minutes=0,
    )
    corroboration = _source(
        loop_id,
        inflow="email",
        ref="G1",
        evidence=EvidenceRef(kind="episode", id=uuid4()),
        same_concern=0.93,
        promoted=True,
        minutes=1,
    )
    loop_store = AsyncMock()
    loop_store.get = AsyncMock(return_value=loop)
    loop_store.list_sources = AsyncMock(return_value=[origin, corroboration])

    detail = await rest.get_loop(loop_store, loop_id)

    loop_store.list_sources.assert_awaited_once_with(loop_id)
    assert detail["promoted"] is True
    assert detail["source_inflows"] == ["conversation", "email"]
    assert detail["sources"] == [
        {
            "role": "origin",
            "inflow": "conversation",
            "evidence_kind": "episode",
            "same_concern": None,
            "promoted": False,
            "created_at": NOW.isoformat(),
        },
        {
            "role": "corroboration",
            "inflow": "email",
            "evidence_kind": "episode",
            "same_concern": 0.93,
            "promoted": True,
            "created_at": (NOW + timedelta(minutes=1)).isoformat(),
        },
    ]


async def test_get_loop_source_created_at_none_and_no_evidence():
    loop = _loop()
    loop_store = AsyncMock()
    loop_store.get = AsyncMock(return_value=loop)
    loop_store.list_sources = AsyncMock(
        return_value=[
            LoopSource(
                loop_id=loop.id,
                role=LoopSourceRole.CORROBORATION,
                key=SourceKey("calendar", "evt-1"),
            )
        ]
    )

    detail = await rest.get_loop(loop_store, loop.id)

    assert detail["sources"][0]["created_at"] is None
    assert detail["sources"][0]["evidence_kind"] is None


async def test_get_loop_raises_when_missing():
    from ze_worldstate.errors import LoopNotFoundError

    loop_store = AsyncMock()
    loop_store.get = AsyncMock(return_value=None)

    with pytest.raises(LoopNotFoundError):
        await rest.get_loop(loop_store, uuid4())
