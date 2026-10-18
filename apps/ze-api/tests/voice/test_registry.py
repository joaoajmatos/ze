from __future__ import annotations

from ze_api.voice.registry import TranscriptionRegistry


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_register_returns_32_char_hex_id():
    reg = TranscriptionRegistry(clock=_Clock())
    tid = reg.register("hello", 3.4)
    assert len(tid) == 32
    int(tid, 16)


def test_lookup_within_ttl_returns_text_and_duration():
    clock = _Clock()
    reg = TranscriptionRegistry(clock=clock)
    tid = reg.register("hello", 3.4)
    clock.now += 599
    assert reg.lookup(tid) == ("hello", 3.4)


def test_lookup_is_reusable():
    reg = TranscriptionRegistry(clock=_Clock())
    tid = reg.register("hello", 1.0)
    assert reg.lookup(tid) == reg.lookup(tid)


def test_lookup_after_ttl_returns_none():
    clock = _Clock()
    reg = TranscriptionRegistry(clock=clock)
    tid = reg.register("hello", 3.4)
    clock.now += 601
    assert reg.lookup(tid) is None


def test_unknown_id_returns_none():
    assert TranscriptionRegistry(clock=_Clock()).lookup("nope") is None


def test_expired_entries_are_swept_on_each_call():
    clock = _Clock()
    reg = TranscriptionRegistry(clock=clock)
    reg.register("old", 1.0)
    clock.now += 601
    reg.register("new", 1.0)
    assert len(reg) == 1


def test_past_max_entries_oldest_is_dropped():
    clock = _Clock()
    reg = TranscriptionRegistry(clock=clock, max_entries=100)
    first = reg.register("first", 1.0)
    ids = []
    for i in range(100):
        clock.now += 1
        ids.append(reg.register(f"t{i}", 1.0))
    assert len(reg) == 100
    assert reg.lookup(first) is None
    assert reg.lookup(ids[0]) is not None
