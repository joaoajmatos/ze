"""WS /scripts: handshake, spawn, frame relay and end statuses (contracts/scripts.md)."""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

import pytest
from starlette.websockets import WebSocketDisconnect

import main
import scripts

TOKEN = "tok"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
STUB = """from ze_tools_base import ToolError, _call, _finish


def echo(**kwargs):
    return _call("echo", kwargs)


def propose(tool, **args):
    return {"tool": tool, "args": args}


def finish(result, writes=None):
    _finish(result, list(writes or []))
"""


def start_frame(source: str, *, stub: str = STUB, timeout: int = 10) -> dict:
    return {
        "type": "start",
        "id": "11111111-1111-1111-1111-111111111111",
        "source": textwrap.dedent(source),
        "stub": stub,
        "timeout_seconds": timeout,
    }


def run_to_end(client, source: str, replies=None, **kwargs) -> tuple[list[dict], dict]:
    """Start a script, answer each call from `replies(frame)`, return (calls, end)."""
    calls: list[dict] = []
    with client.websocket_connect("/scripts", headers=HEADERS) as ws:
        ws.send_json(start_frame(source, **kwargs))
        while True:
            frame = ws.receive_json()
            if frame["type"] == "end":
                return calls, frame
            assert frame["type"] == "call"
            calls.append(frame)
            value = replies(frame) if replies else frame["args"]
            ws.send_json(
                {"type": "reply", "seq": frame["seq"], "ok": True, "value": value}
            )


@pytest.mark.parametrize(
    "headers",
    [{}, {"Authorization": "Bearer nope"}, {"Authorization": TOKEN}],
)
def test_handshake_refused_without_the_right_token(scripts_client, headers) -> None:
    with pytest.raises(WebSocketDisconnect) as exc:
        with scripts_client.websocket_connect("/scripts", headers=headers):
            pass
    assert exc.value.code == 1008


def test_handshake_refused_when_no_token_is_configured(
    scripts_client, monkeypatch
) -> None:
    monkeypatch.setattr(main, "API_TOKEN", "")
    with pytest.raises(WebSocketDisconnect) as exc:
        with scripts_client.websocket_connect(
            "/scripts", headers={"Authorization": "Bearer "}
        ):
            pass
    assert exc.value.code == 1008


def test_start_writes_the_three_files_and_spawns_isolated_python(
    scripts_client, monkeypatch
) -> None:
    spawned: dict = {}
    real = scripts._spawn

    async def spy(argv, **kwargs):
        spawned["argv"] = list(argv)
        spawned["cwd"] = kwargs["cwd"]
        spawned["files"] = sorted(p.name for p in Path(kwargs["cwd"]).iterdir())
        return await real(argv, **kwargs)

    monkeypatch.setattr(scripts, "_spawn", spy)
    _, end = run_to_end(scripts_client, "import ze_tools\nze_tools.finish(1)\n")

    assert end["status"] == "ok"
    assert spawned["argv"][1:] == ["-I", "-X", "utf8", "_ze_main.py"]
    assert {"ze_tools.py", "ze_tools_base.py", "main.py", "_ze_main.py"} <= set(
        spawned["files"]
    )


def test_a_call_frame_is_relayed_and_the_reply_comes_back(scripts_client) -> None:
    calls, end = run_to_end(
        scripts_client,
        """
        import ze_tools as z
        got = z.echo(x=1)
        z.finish({"got": got})
        """,
        replies=lambda frame: {"seen": frame["args"]},
    )
    assert calls == [{"type": "call", "seq": 1, "tool": "echo", "args": {"x": 1}}]
    assert end["status"] == "ok"
    assert end["value"] == {"got": {"seen": {"x": 1}}}
    assert end["writes"] == []


def test_a_failed_reply_raises_tool_error_in_the_script(scripts_client) -> None:
    with scripts_client.websocket_connect("/scripts", headers=HEADERS) as ws:
        ws.send_json(
            start_frame(
                """
                import ze_tools as z
                try:
                    z.echo()
                except z.ToolError as exc:
                    z.finish(str(exc))
                """
            )
        )
        call = ws.receive_json()
        ws.send_json(
            {"type": "reply", "seq": call["seq"], "ok": False, "error": "refused"}
        )
        end = ws.receive_json()
    assert (end["status"], end["value"]) == ("ok", "refused")


def test_finish_carries_value_and_writes(scripts_client) -> None:
    _, end = run_to_end(
        scripts_client,
        """
        import ze_tools as z
        z.finish([1, 2], writes=[z.propose("send_email", to="a@b.c")])
        """,
    )
    assert end["status"] == "ok"
    assert end["value"] == [1, 2]
    assert end["writes"] == [{"tool": "send_email", "args": {"to": "a@b.c"}}]


def test_a_malformed_writes_entry_ends_bad_request(scripts_client) -> None:
    _, end = run_to_end(
        scripts_client,
        """
        import ze_tools as z
        z.finish(1, writes=[{"args": {}}])
        """,
    )
    assert end["status"] == "bad_request"


def test_no_finish_gives_a_none_value(scripts_client) -> None:
    _, end = run_to_end(scripts_client, "x = 1\n")
    assert (end["status"], end["value"]) == ("ok", None)


def test_an_uncaught_exception_ends_exception_with_the_stderr_tail(
    scripts_client,
) -> None:
    _, end = run_to_end(
        scripts_client,
        """
        import sys
        for i in range(30):
            print(f"line {i}", file=sys.stderr)
        raise ValueError("boom")
        """,
    )
    assert end["status"] == "exception"
    assert end["exception"] == "ValueError: boom"
    tail = end["stderr_tail"].splitlines()
    assert len(tail) == 20
    assert tail[-1] == "ValueError: boom"


def test_huge_stdout_does_not_block(scripts_client) -> None:
    _, end = run_to_end(
        scripts_client,
        """
        import ze_tools as z
        print("x" * 10_000_000)
        z.finish("done")
        """,
    )
    assert (end["status"], end["value"]) == ("ok", "done")


def test_the_scratch_dir_is_gone_after_end(scripts_client) -> None:
    run_to_end(scripts_client, "x = 1\n")
    assert list(scripts_client.scratch_root.iterdir()) == []


@pytest.mark.skipif(os.geteuid() != 0, reason="uid switch needs root")
def test_script_runs_as_the_script_user(scripts_client) -> None:
    _, end = run_to_end(
        scripts_client,
        "import os, ze_tools as z\nz.finish(os.getuid())\n",
    )
    import pwd

    assert end["value"] == pwd.getpwnam("zescript").pw_uid
