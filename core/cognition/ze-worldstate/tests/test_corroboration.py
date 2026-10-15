from __future__ import annotations

from uuid import uuid4

import pytest
from ze_plugin.contribution import EvidenceRef

from ze_worldstate.corroboration import (
    CORROBORATED_CAP,
    CORROBORATION_WEIGHT,
    PROMOTED_CONFIDENCE,
    PROMOTED_WINDOW_DAYS,
    corroborated_confidence,
    is_independent,
)
from ze_worldstate.drift import DEFAULT_DRIFT_WINDOW_DAYS
from ze_worldstate.types import LoopSource, LoopSourceRole, SourceKey


def _src(inflow: str, ref: str, role=LoopSourceRole.ORIGIN) -> LoopSource:
    return LoopSource(loop_id=uuid4(), role=role, key=SourceKey(inflow, ref))


# ---- independence ---------------------------------------------------------


def test_no_key_for_none_and_empty_ref():
    assert is_independent(None, [], [], [], []) == (False, "no_key")
    assert is_independent(SourceKey("email", ""), [], [], [], []) == (False, "no_key")


def test_same_source_as_origin():
    key = SourceKey("email", "T1")
    assert is_independent(key, [], [_src("email", "T1")], [], []) == (
        False,
        "same_source",
    )


def test_same_source_as_an_earlier_corroboration():
    key = SourceKey("email", "T2")
    sources = [
        _src("conversation", "c1"),
        _src("email", "T2", LoopSourceRole.CORROBORATION),
    ]
    assert is_independent(key, [], sources, [], []) == (False, "same_source")


def test_same_ref_in_another_inflow_is_independent():
    key = SourceKey("ingestion", "T1")
    assert is_independent(key, [], [_src("email", "T1")], [], []) == (
        True,
        "independent",
    )


def test_same_evidence():
    ref = EvidenceRef(kind="episode", id=uuid4())
    other = EvidenceRef(kind="episode", id=uuid4())
    key = SourceKey("email", "T9")
    assert is_independent(key, [other, ref], [_src("conversation", "c1")], [ref], []) == (
        False,
        "same_evidence",
    )


def test_dropped_source():
    key = SourceKey("email", "G1")
    assert is_independent(
        key, [], [_src("conversation", "c1")], [], [_src("email", "G1")]
    ) == (False, "dropped_source")


def test_other_source_than_the_dropped_one_is_independent():
    key = SourceKey("email", "G2")
    assert is_independent(
        key, [], [_src("conversation", "c1")], [], [_src("email", "G1")]
    ) == (True, "independent")


def test_independent():
    key = SourceKey("email", "T1")
    new = EvidenceRef(kind="episode", id=uuid4())
    old = EvidenceRef(kind="episode", id=uuid4())
    assert is_independent(key, [new], [_src("conversation", "c1")], [old], []) == (
        True,
        "independent",
    )


def test_loop_without_origin_row_checks_corroboration_rows_and_evidence_only():
    key = SourceKey("email", "T1")
    corroboration = _src("calendar", "e1", LoopSourceRole.CORROBORATION)
    assert is_independent(key, [], [corroboration], [], []) == (True, "independent")
    assert is_independent(key, [], [], [], []) == (True, "independent")
    ref = EvidenceRef(kind="ingestion", id=uuid4())
    assert is_independent(key, [ref], [], [ref], []) == (False, "same_evidence")


# ---- constants and arithmetic ---------------------------------------------


def test_constants():
    assert (CORROBORATION_WEIGHT, CORROBORATED_CAP, PROMOTED_CONFIDENCE) == (
        0.5,
        0.6,
        0.7,
    )
    assert PROMOTED_WINDOW_DAYS == DEFAULT_DRIFT_WINDOW_DAYS == 7


def test_corroborated_confidence_noisy_or():
    assert corroborated_confidence(0.3, 0.8) == pytest.approx(0.58)


def test_corroborated_confidence_is_capped():
    assert corroborated_confidence(0.58, 0.8) == CORROBORATED_CAP
    assert corroborated_confidence(0.6, 1.0) == CORROBORATED_CAP


def test_corroborated_confidence_never_lowers():
    assert corroborated_confidence(0.6, 0.0) == pytest.approx(0.6)
    assert corroborated_confidence(0.3, 0.0) == pytest.approx(0.3)


def test_higher_score_counts_more():
    assert corroborated_confidence(0.3, 0.98) > corroborated_confidence(0.3, 0.76)
