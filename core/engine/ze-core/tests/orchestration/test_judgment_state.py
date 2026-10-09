from __future__ import annotations

import time

from ze_core.orchestration.judgment_state import (
    HISTORY_HINT_CHARS,
    HISTORY_HINT_TURNS,
    build_judgment_state,
    history_hint,
)
from ze_core.routing.judge import CONTEXT_CAP, HISTORY_CAP, USER_CAP


def _msgs(n: int, content: str = "hello") -> list[dict]:
    return [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"{content}{i}"}
        for i in range(n)
    ]


def test_no_messages_no_hint():
    assert history_hint({}) is None
    assert history_hint({"messages": []}) is None


def test_hint_keeps_last_turns_and_truncates():
    state = {"messages": _msgs(10, "x" * 500)}
    hint = history_hint(state)
    assert hint.startswith("[Recent conversation]\n")
    lines = hint.splitlines()[1:]
    assert len(lines) == HISTORY_HINT_TURNS
    assert all(len(line.split(": ", 1)[1]) == HISTORY_HINT_CHARS for line in lines)


def test_hint_dropped_after_inactivity():
    state = {"messages": _msgs(2), "last_active_at": time.time() - 31 * 60}
    assert history_hint(state) is None


def test_hint_kept_when_recently_active():
    state = {"messages": _msgs(2), "last_active_at": time.time() - 60}
    assert history_hint(state) is not None


def test_blank_messages_skipped():
    assert history_hint({"messages": [{"role": "user", "content": "  "}]}) is None


def test_build_state_maps_routing_hints_to_context():
    state = {
        "prompt": "hi",
        "messages": _msgs(2),
        "routing_hints": "goal: x",
    }
    out = build_judgment_state(state)
    assert out["user"] == "hi"
    assert out["context"] == "goal: x"
    assert out["history"].startswith("[Recent conversation]")


def test_build_state_prefers_image_caption_and_omits_empty_keys():
    out = build_judgment_state({"prompt": "p", "image_caption": "caption"})
    assert out == {"user": "caption"}


def test_build_state_caps():
    out = build_judgment_state(
        {
            "prompt": "u" * 5000,
            "messages": _msgs(4, "m" * 400),
            "routing_hints": "c" * 5000,
        }
    )
    assert len(out["user"]) == USER_CAP
    assert len(out["history"]) <= HISTORY_CAP
    assert len(out["context"]) == CONTEXT_CAP
