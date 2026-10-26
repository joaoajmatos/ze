"""SC-001: one scripted day through the real ProactiveNotifier.

Quiet hours 23:00-08:00 Europe/Lisbon, discretionary budget 5 per 24 h.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from itertools import count
from zoneinfo import ZoneInfo

from ze_agents.interface.types import Notification
from ze_proactive.notifier import ProactiveNotifier
from ze_proactive.testing import InMemoryPushLog
from ze_proactive.types import (
    NotificationRow,
    OncePer,
    PushKind,
    QuietHoursSetting,
)

LISBON = ZoneInfo("Europe/Lisbon")
REQ = PushKind("acc_req", "requested", "high", "tests")
ACC = PushKind("acc_acc", "accountability", "normal", "tests")
DIS = PushKind("acc_dis", "discretionary", "normal", "tests")


def at(h: int, m: int = 0) -> datetime:
    return datetime(2026, 6, 15, h, m, tzinfo=LISBON).astimezone(timezone.utc)


class Clock:
    now = at(0)

    def __call__(self) -> datetime:
        return self.now


class FakeSettings:
    async def get(self) -> QuietHoursSetting:
        return QuietHoursSetting(True, time(23), time(8), "Europe/Lisbon", None)


class FakeStore:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self.rows: dict[str, NotificationRow] = {}
        self._ids = count(1)

    async def create(self, **kw) -> NotificationRow:
        row = NotificationRow(
            id=f"n{next(self._ids)}",
            event_type=kw["event_type"],
            source=kw["source"],
            title=kw["title"],
            body=kw["body"],
            target_type=kw["target_type"],
            target_id=kw["target_id"],
            target_parent_id=kw.get("target_parent_id"),
            created_at=self._clock(),
            read_at=None,
            push_class=kw["push_class"],
            urgency=kw["urgency"],
            format=kw["format"],
            actions=kw["actions"],
            delivery=kw["delivery"],
        )
        self.rows[row.id] = row
        return row

    async def list_held(self) -> list[NotificationRow]:
        rank = {"high": 0, "normal": 1, "low": 2}
        held = [r for r in self.rows.values() if r.delivery == "held"]
        return sorted(held, key=lambda r: (rank[r.urgency], r.created_at))

    async def mark_released(self, id_: str) -> None:
        self.rows[id_].delivery = "released"

    async def mark_failed(self, id_: str) -> None:
        self.rows[id_].delivery = "failed"


class RecordingInterface:
    def __init__(self, clock: Clock) -> None:
        self._clock = clock
        self.pushes: list[tuple[datetime, Notification]] = []

    async def push(self, notification: Notification) -> None:
        self.pushes.append((self._clock(), notification))


async def test_one_scripted_day():
    clock = Clock()
    store = FakeStore(clock)
    interface = RecordingInterface(clock)
    notifier = ProactiveNotifier(
        interface,  # type: ignore[arg-type]
        store,  # type: ignore[arg-type]
        push_log=InMemoryPushLog(clock),  # type: ignore[arg-type]
        settings_store=FakeSettings(),  # type: ignore[arg-type]
        max_discretionary_per_day=5,
        clock=clock,
    )

    script = (
        [(REQ, t) for t in [(6, 30), (15, 0)]]
        + [(ACC, t) for t in [(1, 0), (3, 0), (10, 0), (12, 0), (18, 0), (23, 30)]]
        + [
            (DIS, t)
            for t in [
                (0, 30),
                (2, 0),
                (9, 0),
                (10, 30),
                (11, 0),
                (13, 0),
                (14, 0),
                (16, 0),
                (17, 0),
            ]
        ]
    )
    events: list[tuple[datetime, str, object]] = [
        (at(*t), "push", kind) for kind, t in script
    ] + [
        (at(7, 55), "release", None),
        (at(8, 5), "release", None),
        (at(23, 59), "release", None),
    ]
    events.sort(key=lambda e: e[0])

    outcomes: dict[str, list[str]] = {
        "requested": [],
        "accountability": [],
        "discretionary": [],
    }
    released_at: dict[str, int] = {}
    for when, op, kind in events:
        clock.now = when
        if op == "release":
            released_at[
                when.astimezone(LISBON).strftime("%H:%M")
            ] = await notifier.deliver_held()
            continue
        assert isinstance(kind, PushKind)
        outcomes[kind.push_class].append(
            await notifier.notify(
                kind,
                "t",
                "b",
                once_per=OncePer(f"{when.isoformat()}") if kind is DIS else None,
            )
        )

    assert outcomes["requested"] == ["delivered", "delivered"]
    assert outcomes["accountability"] == [
        "held",
        "held",
        "delivered",
        "delivered",
        "delivered",
        "held",
    ]
    assert outcomes["discretionary"] == [
        "held",
        "held",
        "delivered",
        "delivered",
        "delivered",
        "suppressed_budget",
        "suppressed_budget",
        "suppressed_budget",
        "suppressed_budget",
    ]
    assert released_at == {"07:55": 0, "08:05": 4, "23:59": 0}

    discretionary_sent = [
        o for o in outcomes["discretionary"] if o in ("delivered", "held")
    ]
    assert len(discretionary_sent) <= 5

    def local(t: datetime) -> time:
        return t.astimezone(LISBON).time()

    for when, n in interface.pushes:
        if n.delivery not in (None, "delivered", "released"):
            continue
        if n.buzz and (local(when) >= time(23) or local(when) < time(8)):
            assert n.event_type == REQ.event_type, (
                "only requested may buzz in quiet hours"
            )

    summaries = [
        (when, n)
        for when, n in interface.pushes
        if n.event_type == "quiet_hours_summary"
    ]
    assert len(summaries) == 1
    assert local(summaries[0][0]) == time(8, 5)
    assert summaries[0][1].buzz is True
    assert "held 4 updates" in summaries[0][1].content

    released = [n for _, n in interface.pushes if n.delivery == "released"]
    assert len(released) == 4 and all(not n.buzz for n in released)
    assert [r for r in store.rows.values() if r.delivery == "held"][
        0
    ].push_class == "accountability"
    assert sum(1 for r in store.rows.values() if r.delivery == "suppressed") == 4
