"""Script user, environment, rlimits and exit classification (unit level)."""

from __future__ import annotations

import resource
import signal
from pathlib import Path

import pytest

import scripts


def test_script_env_has_exactly_the_allowed_keys(monkeypatch) -> None:
    monkeypatch.setenv("WORKSPACE_API_TOKEN", "secret")
    env = scripts.script_env(Path("/tmp/ze-scripts/x"), 5, 6)
    assert set(env) == {"PATH", "HOME", "LANG", "ZE_REQ_FD", "ZE_REP_FD"}
    assert env["HOME"] == "/tmp/ze-scripts/x"
    assert (env["ZE_REQ_FD"], env["ZE_REP_FD"]) == ("5", "6")


def test_script_rlimits_has_the_five_limits() -> None:
    mib = 1024 * 1024
    assert scripts.script_rlimits(30) == {
        resource.RLIMIT_AS: 256 * mib,
        resource.RLIMIT_NPROC: 32,
        resource.RLIMIT_FSIZE: 16 * mib,
        resource.RLIMIT_CPU: 31,
        resource.RLIMIT_NOFILE: 64,
    }


@pytest.mark.parametrize(
    ("code", "stderr", "expected"),
    [
        (-signal.SIGKILL, "", True),
        (-signal.SIGXCPU, "", True),
        (-signal.SIGXFSZ, "", True),
        (1, "Traceback\nMemoryError", True),
        (1, "BlockingIOError: [Errno 11] Resource temporarily unavailable", True),
        (1, "OSError: [Errno 27] File too large", True),
        (1, "ValueError: boom", False),
        (0, "", False),
    ],
)
def test_resource_limit_exits(code, stderr, expected) -> None:
    assert scripts.is_resource_limit_exit(code, stderr) is expected
