"""Every declared effect_phrase converts to an imperative (Phase 181)."""

from __future__ import annotations

import importlib

from ze_agents.effects import effect_imperative
from ze_agents.tool import registered_tools

from tests.support.agent_modules import ALL_AGENT_MODULE_PATHS

# Verbs whose past and base forms are the same word.
_INVARIANT = {"set", "reset"}


def _load_all() -> None:
    for path in ALL_AGENT_MODULE_PATHS:
        importlib.import_module(path)


def test_every_registered_effect_phrase_has_an_imperative() -> None:
    _load_all()
    checked = 0
    for name, spec in registered_tools().items():
        if not spec.effect_phrase:
            continue
        head = spec.effect_phrase.split(" ", 1)[0].lower()
        imperative = effect_imperative(spec.effect_phrase)
        if head not in _INVARIANT:
            assert imperative != spec.effect_phrase, (
                f"{name}: {spec.effect_phrase!r} has no imperative form; "
                "add its verb to _PAST_TO_BASE in ze_agents/effects.py"
            )
        assert imperative.split(" ", 1)[0].isalpha()
        checked += 1
    assert checked > 20
