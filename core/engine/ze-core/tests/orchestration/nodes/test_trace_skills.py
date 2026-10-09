from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace

from ze_core.orchestration.nodes.trace import _extract_skills_used


@dataclass
class _Match:
    skill: object
    trigger: str = "automatic"
    similarity: float | None = 0.43
    below_floor: bool = False


def _skill(name: str = "A") -> SimpleNamespace:
    return SimpleNamespace(id="1", name=name, source=SimpleNamespace(value="imported"))


def test_below_floor_copied():
    [row] = _extract_skills_used([_Match(_skill(), below_floor=True)])
    assert row.below_floor is True and row.similarity == 0.43


def test_below_floor_default_false_when_match_lacks_field():
    match = SimpleNamespace(skill=_skill(), trigger="explicit", similarity=None)
    [row] = _extract_skills_used([match])
    assert row.below_floor is False
