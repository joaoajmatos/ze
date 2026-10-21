"""Screen-pressed tool actions over the socket (Phase 191a, T006)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

import ze_agents.registry as registry
import ze_agents.tool as tool_module
from ze_agents.base_agent import BaseAgent
from ze_agents.reversibility import ToolReversibility
from ze_agents.tool import ToolAccess, tool
from ze_agents.types import AgentResult
from ze_api.api.ws.connection import ConnectionManager
from ze_api.api.ws.ui_actions import (
    handle_ui_action,
    handle_ui_confirm,
    supersede_ui_gates,
)

runs: list[tuple[str, dict]] = []


class FakeWS:
    def __init__(self) -> None:
        self.frames: list[dict] = []

    async def send_json(self, frame: dict) -> None:
        self.frames.append(frame)

    async def close(self, code: int = 1000) -> None:
        pass

    def of(self, kind: str) -> list[dict]:
        return [f for f in self.frames if f["type"] == kind]


class FakeLedger:
    def __init__(self, fail: bool = False) -> None:
        self.drafts: list = []
        self.fail = fail

    async def append(self, contribution):
        if self.fail:
            raise RuntimeError("ledger down")
        self.drafts.append(contribution.action_record)
        return contribution.action_record

    async def get(self, record_id):
        return None

    async def list(self, **kwargs):
        return []


@pytest.fixture(autouse=True)
def tools_and_agents():
    saved_tools = dict(tool_module._tools)
    saved_instances = dict(registry._instances)

    def _register(name, access, rev=None, **kw):
        async def _impl(source_id: str) -> str:
            runs.append((name, {"source_id": source_id}))
            if name == "boom_write":
                raise RuntimeError("secret internals")
            return "ok"

        _impl.__name__ = name
        tool(access=access, description=name, reversibility=rev, **kw)(_impl)

    runs.clear()
    _register(
        "mark_source_read",
        ToolAccess.WRITE,
        ToolReversibility.REVERSIBLE,
        undo_tool="unmark_source_read",
        undo_note="Mark unread",
        effect_phrase="marked a source as read",
        ui_action=True,
        done_phrase="Marked as read.",
    )
    _register(
        "unmark_source_read",
        ToolAccess.WRITE,
        ToolReversibility.IRREVERSIBLE,
        effect_phrase="marked a source as unread",
        asks_first=False,
        no_ask_reason="test",
    )
    _register(
        "archive_source",
        ToolAccess.WRITE,
        ToolReversibility.IRREVERSIBLE,
        effect_phrase="archived a source",
        ui_action=True,
    )
    _register(
        "boom_write",
        ToolAccess.WRITE,
        ToolReversibility.REVERSIBLE,
        undo_tool="unmark_source_read",
        undo_note="n",
        effect_phrase="marked a source as broken",
        ui_action=True,
    )
    _register(
        "internal_write",
        ToolAccess.WRITE,
        ToolReversibility.REVERSIBLE,
        undo_tool="unmark_source_read",
        undo_note="n",
        effect_phrase="changed something",
    )
    _register("look_up", ToolAccess.READ)

    class _News(BaseAgent):
        name = "news"
        description = "d"
        tools = [
            "mark_source_read",
            "archive_source",
            "boom_write",
            "internal_write",
            "look_up",
        ]

        async def run(self, ctx):
            return AgentResult(agent=self.name, response="ok")

    class _Other(BaseAgent):
        name = "other"
        description = "d"
        tools: list[str] = []

        async def run(self, ctx):
            return AgentResult(agent=self.name, response="ok")

    registry._instances["news"] = _News()
    registry._instances["other"] = _Other()
    yield
    tool_module._tools.clear()
    tool_module._tools.update(saved_tools)
    registry._instances.clear()
    registry._instances.update(saved_instances)


@pytest.fixture
def env():
    ws = FakeWS()
    conn = ConnectionManager()
    conn._ws = ws
    ledger = FakeLedger()
    container = SimpleNamespace(
        settings=SimpleNamespace(confirm_timeout_seconds=900),
        action_record_store=ledger,
    )

    # A fake clock: every sleep waits for `tick`, then returns at once.
    tick = asyncio.Event()

    async def _sleep(seconds: float) -> None:
        await tick.wait()

    conn.ui_gates.sleep = _sleep
    return SimpleNamespace(
        ws=ws, conn=conn, ledger=ledger, container=container, tick=tick
    )


def _press(tool_name="mark_source_read", owner="news", rid="u1", thread="t1", **args):
    return {
        "type": "ui_action",
        "id": rid,
        "thread_id": thread,
        "action": {
            "kind": "tool",
            "owner": owner,
            "tool": tool_name,
            "args": args or {"source_id": "s1"},
        },
    }


def _confirm(rid="u1", choice="approve", thread="t1", **extra):
    return {
        "type": "confirm",
        "id": rid,
        "thread_id": thread,
        "choice": choice,
        **extra,
    }


def _results(env) -> list[dict]:
    return env.ws.of("ui_action_result")


async def test_reversible_write_runs_once_and_reports_done_phrase(env) -> None:
    await handle_ui_action(_press(), env.container, env.conn)
    assert runs == [("mark_source_read", {"source_id": "s1"})]
    (result,) = _results(env)
    assert (result["id"], result["thread_id"], result["ok"]) == ("u1", "t1", True)
    assert result["line"] == "Marked as read."
    assert env.conn.is_busy("t1") is False


async def test_a_failing_write_says_couldnt_and_never_raw_error(env) -> None:
    await handle_ui_action(_press("boom_write"), env.container, env.conn)
    (result,) = _results(env)
    assert result["ok"] is False
    assert result["line"] == "Couldn't mark a source as broken."
    assert "secret" not in str(env.ws.frames)


async def test_irreversible_write_asks_through_a_confirm_request(env) -> None:
    await handle_ui_action(_press("archive_source"), env.container, env.conn)
    assert runs == []
    (card,) = env.ws.of("confirm_request")
    assert (card["id"], card["thread_id"], card["kind"]) == ("u1", "t1", "write")
    (item,) = card["items"]
    assert item["summary"] == "source_id: s1"
    assert item["effect_phrase"] == "archived a source"
    assert item["editable_field"] is None
    assert _results(env) == []
    assert env.conn.is_busy("t1") is False
    env.conn.ui_gates.pop("u1").timer.cancel()


async def test_approve_runs_it_once_and_two_confirms_run_it_once(env) -> None:
    await handle_ui_action(_press("archive_source"), env.container, env.conn)
    assert await handle_ui_confirm(_confirm(), env.container, env.conn) is True
    await handle_ui_confirm(_confirm(), env.container, env.conn)
    assert runs == [("archive_source", {"source_id": "s1"})]
    results = _results(env)
    assert results[0]["ok"] is True and results[0]["line"] == "Done."
    assert results[1]["line"] == "That request expired."


async def test_confirm_edits_run_the_original_args(env) -> None:
    await handle_ui_action(_press("archive_source"), env.container, env.conn)
    await handle_ui_confirm(
        _confirm(edits={"source_id": "evil"}), env.container, env.conn
    )
    assert runs == [("archive_source", {"source_id": "s1"})]


async def test_deny_says_okay_i_didnt(env) -> None:
    await handle_ui_action(_press("archive_source"), env.container, env.conn)
    await handle_ui_confirm(_confirm(choice="deny"), env.container, env.conn)
    assert runs == []
    (result,) = _results(env)
    assert result["ok"] is False
    assert result["line"] == "Okay, I didn't archive a source."
    assert env.ws.of("confirm_cancel")[0]["id"] == "u1"


async def test_timeout_declines_and_a_later_confirm_is_expired(env) -> None:
    await handle_ui_action(_press("archive_source"), env.container, env.conn)
    gate_timer = env.conn.ui_gates._open["u1"].timer
    env.tick.set()
    await gate_timer
    assert runs == []
    (result,) = _results(env)
    assert result["line"] == "Okay, I didn't archive a source."
    assert await handle_ui_confirm(_confirm(), env.container, env.conn) is True
    assert _results(env)[-1]["line"] == "That request expired."
    assert runs == []


async def test_a_confirm_for_a_gate_nobody_knows_is_left_to_the_graph_path(env) -> None:
    assert (
        await handle_ui_confirm(_confirm("graph-1"), env.container, env.conn) is False
    )
    assert _results(env) == []


async def test_a_new_turn_supersedes_an_open_gate(env) -> None:
    await handle_ui_action(_press("archive_source"), env.container, env.conn)
    timer = env.conn.ui_gates._open["u1"].timer
    await supersede_ui_gates(env.container, env.conn, "t1")
    assert (await handle_ui_confirm(_confirm(), env.container, env.conn)) is True
    assert [r["line"] for r in _results(env)] == [
        "Okay, I didn't archive a source.",
        "That request expired.",
    ]
    await asyncio.sleep(0)
    assert timer.cancelled()
    assert runs == []


async def test_supersede_leaves_other_threads_alone(env) -> None:
    await handle_ui_action(
        _press("archive_source", thread="t2"), env.container, env.conn
    )
    await supersede_ui_gates(env.container, env.conn, "t1")
    assert "u1" in env.conn.ui_gates._open
    env.conn.ui_gates.pop("u1").timer.cancel()


async def test_reconnect_replays_the_open_gate_and_disconnect_keeps_it(env) -> None:
    await handle_ui_action(_press("archive_source"), env.container, env.conn)
    await env.conn.disconnect(env.ws)
    assert "u1" in env.conn.ui_gates._open
    ws2 = FakeWS()
    msg_store = SimpleNamespace(list_unread=AsyncMock(return_value=[]))
    await env.conn.connect(ws2, msg_store)
    (card,) = ws2.of("confirm_request")
    assert card["id"] == "u1"
    env.conn.ui_gates.pop("u1").timer.cancel()


@pytest.mark.parametrize(
    "press",
    [
        _press(owner="nobody"),
        _press(owner="other"),
        _press("look_up"),
        _press("internal_write"),
        _press("missing_tool"),
        _press("mark_source_read", extra="x", source_id="s1"),
        {"type": "ui_action", "id": "u1", "thread_id": "t1", "action": {"kind": "ask"}},
    ],
)
async def test_unavailable_actions_run_nothing(env, press) -> None:
    await handle_ui_action(press, env.container, env.conn)
    assert runs == []
    (result,) = _results(env)
    assert (result["ok"], result["line"]) == (False, "That action is not available.")
    assert env.ws.of("confirm_request") == []


async def test_a_busy_thread_says_so(env) -> None:
    env.conn.try_set_busy("t1")
    await handle_ui_action(_press(), env.container, env.conn)
    assert runs == []
    (result,) = _results(env)
    assert result["code"] == "busy" and result["ok"] is False


async def test_a_graph_gates_confirm_is_unaffected(env) -> None:
    await handle_ui_action(_press("archive_source"), env.container, env.conn)
    assert (
        await handle_ui_confirm(_confirm("graph-9"), env.container, env.conn) is False
    )
    assert "u1" in env.conn.ui_gates._open
    env.conn.ui_gates.pop("u1").timer.cancel()


async def test_every_run_writes_one_ledger_record(env) -> None:
    await handle_ui_action(_press(rid="a"), env.container, env.conn)
    await handle_ui_action(_press(rid="b"), env.container, env.conn)
    await handle_ui_action(_press("boom_write", rid="c"), env.container, env.conn)
    await handle_ui_action(_press("archive_source", rid="d"), env.container, env.conn)
    await handle_ui_confirm(_confirm("d", "deny"), env.container, env.conn)
    await handle_ui_action(_press("archive_source", rid="e"), env.container, env.conn)
    await handle_ui_confirm(_confirm("e"), env.container, env.conn)
    await handle_ui_action(_press("archive_source", rid="f"), env.container, env.conn)
    timer = env.conn.ui_gates._open["f"].timer
    env.tick.set()
    await timer

    drafts = env.ledger.drafts
    assert [d.authoritative_ref.record_id for d in drafts] == list("abcdef")
    assert [d.lifecycle.value for d in drafts] == [
        "succeeded",
        "succeeded",
        "failed",
        "cancelled",
        "succeeded",
        "timed_out",
    ]
    first = drafts[0]
    assert first.action_type == "ui.tool_action"
    assert first.actor == "user"
    assert "news.mark_source_read" in first.summary
    assert "mark a source as read" in first.summary
    assert first.producer_plugin
    # the same press twice: two records, no idempotency collision
    assert drafts[0].idempotency_key != drafts[1].idempotency_key


async def test_a_ledger_that_raises_never_changes_the_result(env) -> None:
    env.ledger.fail = True
    await handle_ui_action(_press(), env.container, env.conn)
    (result,) = _results(env)
    assert (result["ok"], result["line"]) == (True, "Marked as read.")


async def test_no_ledger_configured_is_fine(env) -> None:
    env.container.action_record_store = None
    await handle_ui_action(_press(), env.container, env.conn)
    assert _results(env)[0]["ok"] is True
