"""The labeled EN+PT calibration set stays complete and consistent with the closed sets."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import yaml

from ze_memory.extractor import KEEP_FAMILIES
from ze_memory.types import SpeechAct

_ROOT = Path(__file__).resolve().parents[4]
_ROWS = [
    json.loads(line)
    for line in (_ROOT / "eval/calibration/speech_act.jsonl").read_text().splitlines()
    if line.strip()
]


def test_ids_unique_and_fields_valid():
    assert len({r["id"] for r in _ROWS}) == len(_ROWS)
    for r in _ROWS:
        assert r["lang"] in {"en", "pt"}
        assert r["gold_act"] in {a.value for a in SpeechAct}
        assert len(r["assistant"]) <= 1000
        if r["gold_act"] == "fact":
            assert r["gold_family"] in KEEP_FAMILIES
        else:
            assert r["gold_family"] == "drop"
            assert r["gold_persist"] is False


def test_each_act_has_three_rows_per_language():
    counts = Counter((r["gold_act"], r["lang"]) for r in _ROWS)
    for act in SpeechAct:
        for lang in ("en", "pt"):
            assert counts[(act.value, lang)] >= 3, (act.value, lang)


def test_covers_every_memory_eval_admission_prompt():
    scenarios = yaml.safe_load((_ROOT / "eval/scenarios/memory.yaml").read_text())
    rows = scenarios["scenarios"] if isinstance(scenarios, dict) else scenarios
    prompts = {
        s["prompt"]
        for s in rows
        if s["id"].startswith(("memory_speech_act_", "memory_admission_"))
    }
    assert prompts
    assert prompts <= {r["user"] for r in _ROWS}


def test_includes_dentist_cancel_and_aisle_retract_pair_in_both_languages():
    by_user = {r["user"]: r for r in _ROWS}
    assert by_user["Forget the dentist."]["gold_act"] == "reminder"
    assert by_user["Esquece o dentista."]["gold_act"] == "reminder"
    assert by_user["Forget that I like aisle seats."]["gold_act"] == "forget"
    assert by_user["Esquece que prefiro lugar no corredor."]["gold_act"] == "forget"
