"""The labeled EN+PT routing calibration set stays complete and consistent with the roster."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

from ze_agents.registry import get_enabled_agents

_ROOT = Path(__file__).resolve().parents[5]
_PATH = _ROOT / "eval/calibration/routing.jsonl"
_ROWS = [json.loads(line) for line in _PATH.read_text().splitlines() if line.strip()]
_LEVELS = {"lookup", "single_tool", "multi_hop"}


def test_ids_unique_and_fields_valid():
    assert len({r["id"] for r in _ROWS}) == len(_ROWS)
    for r in _ROWS:
        assert r["lang"] in {"en", "pt"}
        assert isinstance(r["prompt"], str) and r["prompt"].strip()
        assert isinstance(r["gold_multi"], bool)
        assert r["gold_complexity"] in _LEVELS
        assert "history" not in r or isinstance(r["history"], str)


def test_gold_agents_exist_in_the_registry_or_are_none():
    roster = set(get_enabled_agents())
    for r in _ROWS:
        assert r["gold_agent"] == "none" or r["gold_agent"] in roster, r["id"]


def test_both_languages_cover_every_complexity_level():
    seen = {(r["lang"], r["gold_complexity"]) for r in _ROWS}
    for lang in ("en", "pt"):
        for level in _LEVELS:
            assert (lang, level) in seen, (lang, level)


def test_each_language_has_none_and_mixed_rows():
    for lang in ("en", "pt"):
        scoped = [r for r in _ROWS if r["lang"] == lang]
        assert any(r["gold_agent"] == "none" for r in scoped), lang
        assert any(r["gold_multi"] for r in scoped), lang
        assert any(r["gold_agent"] != "none" and not r["gold_multi"] for r in scoped)


def test_none_rows_are_never_marked_multi():
    assert all(not r["gold_multi"] for r in _ROWS if r["gold_agent"] == "none")


def test_every_roster_agent_has_a_clear_single_in_each_language():
    counts = Counter(
        (r["gold_agent"], r["lang"])
        for r in _ROWS
        if r["id"].startswith("single-") and not r["gold_multi"]
    )
    for name in get_enabled_agents():
        for lang in ("en", "pt"):
            assert counts[(name, lang)] >= 1, (name, lang)
