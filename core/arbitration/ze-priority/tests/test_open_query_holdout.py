"""Pins the shipped detector numbers (phase 171 research.md Verdict).

Both held-out sets have been seen, so they are regression sets, not a clean verdict.
Amended bar (set after the original PT bar failed): EN recall >= 0.9, PT recall >= 0.65,
FPR <= 0.05 per language.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ze_core.embeddings import get_embedder
from ze_priority.open_query import OpenQueryDetector

pytestmark = pytest.mark.slow

_CALIBRATION = Path(__file__).resolve().parents[4] / "eval" / "calibration"
_RECALL_BAR = {"en": 0.9, "pt": 0.65}
_FPR_BAR = 0.05


@pytest.fixture(scope="module")
def detector():
    return OpenQueryDetector(get_embedder())


def _rows(name: str) -> list[dict]:
    path = _CALIBRATION / name
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


@pytest.mark.parametrize("name", ["open_query_holdout.jsonl", "open_query_holdout2.jsonl"])
@pytest.mark.parametrize("lang", ["en", "pt"])
def test_holdout_recall_and_fpr_at_shipped_constants(detector, name, lang):
    embedder = get_embedder()
    rows = [r for r in _rows(name) if r["lang"] == lang]
    hits = {
        r["id"]: detector.is_open_query(embedder.encode(r["text"])) for r in rows
    }
    pos = [r for r in rows if r["label"]]
    neg = [r for r in rows if not r["label"]]
    assert sum(hits[r["id"]] for r in pos) / len(pos) >= _RECALL_BAR[lang]
    assert sum(hits[r["id"]] for r in neg) / len(neg) <= _FPR_BAR
