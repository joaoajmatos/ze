"""Dataset shape and offline mode of eval/calibration/skills.py (phase 166). No network."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pytest

_SCRIPT = Path(__file__).resolve().parents[4] / "eval/calibration/skills.py"


@pytest.fixture(scope="module")
def calib():
    spec = importlib.util.spec_from_file_location("skills_calibration", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    yield module
    sys.modules.pop(spec.name, None)


def test_dataset_shape(calib):
    rows = calib.load_rows(calib.DATASET)
    roster = {s.slug for s in calib.load_roster()}
    assert len(rows) >= 80
    assert len({r.id for r in rows}) == len(rows)
    assert {r.lang for r in rows} == {"en", "pt"}
    assert sum(r.lang == "pt" for r in rows) / len(rows) >= 0.30
    for r in rows:
        assert r.gold in roster or r.gold == "none", r.id
        assert r.band in calib.BANDS, r.id
        assert (r.gold == "none") == (r.band == "none"), r.id
        if r.explicit:
            assert r.text.startswith(f"/{r.gold}"), r.id
    bands = Counter(r.band for r in rows)
    assert all(bands[b] >= 5 for b in calib.BANDS)
    assert any(r.history for r in rows)


def test_roster_has_distinct_slugs_and_enough_skills(calib):
    skills = calib.load_roster()
    assert len(skills) >= 12
    assert len({s.slug for s in skills}) == len(skills)


class _HashEmbedder:
    """Deterministic fake: no model, no network."""

    def _vec(self, text: str) -> np.ndarray:
        seed = int(hashlib.sha256(text.encode()).hexdigest()[:8], 16)
        v = np.random.default_rng(seed).standard_normal(16).astype(np.float32)
        return v / np.linalg.norm(v)

    def encode_query(self, text, **kw):
        return self._vec("q:" + text)

    def encode_passage(self, texts, **kw):
        return np.stack([self._vec("p:" + t) for t in texts])


async def test_recall_mode_is_offline(calib, capsys, monkeypatch):
    def _no_client(*a, **kw):
        raise AssertionError("live client must not be built in --recall")

    monkeypatch.setenv("OPENROUTER_API_KEY", "")
    args = calib.parser().parse_args(["--recall"])
    code = await calib.main_async(args, embedder=_HashEmbedder())

    out = capsys.readouterr().out
    assert code == 0
    assert "gold recall by k" in out
    for k in range(3, 9):
        assert f"k={k}" in out
    for lang in ("en", "pt", "all"):
        assert any(line.startswith(lang) for line in out.splitlines())


def test_live_client_not_imported_by_default(calib):
    assert not hasattr(calib, "OpenRouterSystemOneClient")


def test_recall_counts_gold_in_shortlist(calib):
    skills = calib.load_roster()
    rows = [r for r in calib.load_rows(calib.DATASET) if not r.explicit][:10]
    scored = {r.id: calib.score(_HashEmbedder(), skills, r.text) for r in rows}
    hits, total = calib.recall_at(scored, rows, k=len(skills), floor=-1.0)
    assert hits == total > 0
