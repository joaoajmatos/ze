"""Fail-closed sandbox, limits without the script user, disconnect kill, forged breach."""

from __future__ import annotations

import sys
import time

import pytest

import scripts
from tests.test_scripts_relay import HEADERS, run_to_end, start_frame

linux_only = pytest.mark.skipif(
    sys.platform != "linux", reason="rlimits are enforced on Linux"
)


def test_without_the_opt_in_an_unswitchable_sandbox_is_unavailable(
    scripts_client, monkeypatch
) -> None:
    monkeypatch.delenv("ZE_SCRIPTS_ALLOW_UNISOLATED")
    monkeypatch.setattr(scripts, "script_identity", lambda: None)
    _, end = run_to_end(scripts_client, "x = 1\n")
    assert end["status"] == "unavailable"


def test_root_without_the_script_user_always_refuses(
    scripts_client, monkeypatch
) -> None:
    monkeypatch.setattr(scripts.os, "geteuid", lambda: 0)
    monkeypatch.setattr(
        scripts.pwd, "getpwnam", lambda _name: (_ for _ in ()).throw(KeyError())
    )
    _, end = run_to_end(scripts_client, "x = 1\n")
    assert end["status"] == "unavailable"


def test_the_opt_in_lets_a_non_root_test_run_proceed(scripts_client) -> None:
    _, end = run_to_end(scripts_client, "x = 1\n")
    assert end["status"] == "ok"


@linux_only
def test_memory_limit_applies_without_the_script_user(scripts_client) -> None:
    _, end = run_to_end(scripts_client, "x = bytearray(512 * 1024 * 1024)\n")
    assert end["status"] == "resource_limit"


@linux_only
def test_process_limit_applies_without_the_script_user(scripts_client) -> None:
    _, end = run_to_end(
        scripts_client, "import os\nwhile True:\n    os.fork()\n", timeout=20
    )
    assert end["status"] == "resource_limit"


def test_closing_the_ze_socket_frees_the_slot_within_a_second(scripts_client) -> None:
    with scripts_client.websocket_connect("/scripts", headers=HEADERS) as ws:
        ws.send_json(
            start_frame("import ze_tools as z\nz.echo()\nimport time\ntime.sleep(60)\n")
        )
        ws.receive_json()
        assert scripts.slot.busy()
        ws.close()
        deadline = time.monotonic() + 1
        while scripts.slot.busy() and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not scripts.slot.busy()


def test_a_script_cannot_forge_an_isolation_breach(scripts_client) -> None:
    _, end = run_to_end(
        scripts_client,
        'import ze_tools_base as b\nb._REQ.write(\'{"isolation_breach": "x"}\\n\')\nb._REQ.flush()\n',
    )
    assert end["status"] == "bad_request"
    assert scripts.isolation.breached is False


def test_exiting_87_from_user_code_does_not_latch_the_sandbox_off(
    scripts_client,
) -> None:
    _, end = run_to_end(scripts_client, "import sys\nsys.exit(87)\n")
    assert end["status"] == "exception"
    assert scripts.isolation.breached is False
