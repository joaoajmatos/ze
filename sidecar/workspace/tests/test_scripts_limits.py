"""Script slot, wall time, cancel and the pipe and scratch caps."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

import scripts
from tests.test_scripts_relay import HEADERS, run_to_end, scripts_client, start_frame  # noqa: F401


def pid_gone(pid: int) -> bool:
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.05)
    return False


def test_timeout_kills_a_spinning_script_and_its_setsid_child(scripts_client) -> None:
    source = """
        import subprocess, ze_tools as z
        child = subprocess.Popen(["sleep", "60"], start_new_session=True)
        z.echo(pid=child.pid)
        while True:
            pass
    """
    started = time.monotonic()
    calls, end = run_to_end(scripts_client, source, timeout=1)
    assert end["status"] == "timeout"
    assert time.monotonic() - started < 6
    assert pid_gone(calls[0]["args"]["pid"])


def test_cancel_ends_killed(scripts_client) -> None:
    with scripts_client.websocket_connect("/scripts", headers=HEADERS) as ws:
        ws.send_json(start_frame("import ze_tools as z\nz.echo()\nimport time\ntime.sleep(60)\n"))
        ws.receive_json()
        ws.send_json({"type": "cancel"})
        assert ws.receive_json()["status"] == "killed"


def test_malformed_json_ends_bad_request(scripts_client) -> None:
    _, end = run_to_end(
        scripts_client,
        "import ze_tools_base as b\nb._REQ.write('not json\\n')\nb._REQ.flush()\n",
    )
    assert end["status"] == "bad_request"


def test_a_request_line_over_256_kb_ends_bad_request(scripts_client) -> None:
    _, end = run_to_end(
        scripts_client, "import ze_tools as z\nz.echo(blob='x' * 300_000)\n"
    )
    assert end["status"] == "bad_request"


def test_a_finish_line_over_1_mib_ends_bad_request(scripts_client) -> None:
    _, end = run_to_end(
        scripts_client, "import ze_tools as z\nz.finish('x' * 1_100_000)\n"
    )
    assert end["status"] == "bad_request"


def test_more_than_forty_request_lines_end_bad_request(scripts_client) -> None:
    _, end = run_to_end(
        scripts_client,
        "import ze_tools as z\nfor _ in range(60):\n    z.echo()\n",
    )
    assert end["status"] == "bad_request"


def test_scratch_over_the_cap_during_the_run_ends_resource_limit(
    scripts_client, monkeypatch
) -> None:
    monkeypatch.setattr(scripts, "SCRATCH_CAP_BYTES", 24 * 1024 * 1024)
    started = time.monotonic()
    _, end = run_to_end(
        scripts_client,
        """
        import time
        for n in range(2):
            with open(f"big{n}", "wb") as f:
                f.write(b"x" * (15 * 1024 * 1024))
        time.sleep(30)
        """,
        timeout=20,
    )
    assert end["status"] == "resource_limit"
    assert time.monotonic() - started < 10


def test_scratch_over_the_cap_at_the_end_ends_resource_limit(
    scripts_client, monkeypatch
) -> None:
    monkeypatch.setattr(scripts, "SCRATCH_CAP_BYTES", 1024 * 1024)
    _, end = run_to_end(
        scripts_client,
        "with open('big', 'wb') as f:\n    f.write(b'x' * (2 * 1024 * 1024))\n",
    )
    assert end["status"] == "resource_limit"


def test_a_second_connection_during_a_run_is_busy(scripts_client) -> None:
    with scripts_client.websocket_connect("/scripts", headers=HEADERS) as first:
        first.send_json(start_frame("import ze_tools as z\nz.echo()\n"))
        first.receive_json()
        with scripts_client.websocket_connect("/scripts", headers=HEADERS) as second:
            assert second.receive_json()["status"] == "busy"
        first.send_json({"type": "cancel"})
        assert first.receive_json()["status"] == "killed"
    _, end = run_to_end(scripts_client, "x = 1\n")
    assert end["status"] == "ok"


def test_a_workspace_run_proceeds_while_a_script_runs(scripts_client) -> None:
    with scripts_client.websocket_connect("/scripts", headers=HEADERS) as ws:
        ws.send_json(start_frame("import ze_tools as z\nz.echo()\n"))
        ws.receive_json()
        response = scripts_client.post("/run", json={"command": ["echo", "hi"]}, headers=HEADERS)
        assert response.status_code == 200
        ws.send_json({"type": "cancel"})
        ws.receive_json()


def test_ws_max_size_is_2_mib() -> None:
    assert scripts.WS_MAX_SIZE == 2 * 1024 * 1024
    dockerfile = (Path(__file__).resolve().parent.parent / "Dockerfile").read_text()
    assert f'"--ws-max-size", "{scripts.WS_MAX_SIZE}"' in dockerfile
