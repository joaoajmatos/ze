"""Docker smoke test for WS /scripts (quickstart.md). Needs `make workspace-up`.

    python sidecar/workspace/tests/smoke_scripts.py

Set WORKSPACE_SMOKE_URL (default http://localhost:8081) and WORKSPACE_API_TOKEN
(default dev-workspace-token).
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import urllib.request

import pytest

BASE = os.environ.get("WORKSPACE_SMOKE_URL", "http://localhost:8081")
TOKEN = os.environ.get("WORKSPACE_API_TOKEN", "dev-workspace-token")
STUB = """from ze_tools_base import ToolError, _call, _finish


def echo(**kwargs):
    return _call("echo", kwargs)


def finish(result, writes=None):
    _finish(result, list(writes or []))
"""

websockets = pytest.importorskip("websockets")


def reachable() -> bool:
    try:
        urllib.request.urlopen(f"{BASE}/health", timeout=2)
    except OSError:
        return False
    return True


pytestmark = [
    pytest.mark.docker,
    pytest.mark.skipif(not reachable(), reason="workspace not up"),
]


def _headers(token: str | None = TOKEN) -> dict:
    return {"Authorization": f"Bearer {token}"} if token is not None else {}


async def run_script(source: str, timeout: int = 20, reply=lambda a: a) -> dict:
    url = BASE.replace("http", "ws", 1) + "/scripts"
    async with websockets.connect(
        url, additional_headers=_headers(), max_size=2**21
    ) as ws:
        await ws.send(
            json.dumps(
                {
                    "type": "start",
                    "id": "smoke",
                    "source": source,
                    "stub": STUB,
                    "timeout_seconds": timeout,
                }
            )
        )
        while True:
            frame = json.loads(await asyncio.wait_for(ws.recv(), timeout + 10))
            if frame["type"] == "end":
                return frame
            await ws.send(
                json.dumps(
                    {
                        "type": "reply",
                        "seq": frame["seq"],
                        "ok": True,
                        "value": reply(frame["args"]),
                    }
                )
            )


def run(source: str, **kwargs) -> dict:
    return asyncio.run(run_script(source, **kwargs))


def test_stat_reports_isolated() -> None:
    req = urllib.request.Request(f"{BASE}/stat", headers=_headers())
    body = json.load(urllib.request.urlopen(req, timeout=5))
    assert body["scripts_isolated"] is True


def test_outbound_network_is_refused_fast() -> None:
    end = run(
        "import urllib.request, ze_tools as z\n"
        "try:\n    urllib.request.urlopen('https://example.com', timeout=5)\n    z.finish('reached')\n"
        "except Exception as exc:\n    z.finish(type(exc).__name__)\n"
    )
    assert end["status"] == "ok" and end["value"] != "reached"


def test_workspace_is_closed() -> None:
    end = run(
        "import os, ze_tools as z\nout = []\n"
        "for fn in (lambda: open('/workspace/x', 'w'), lambda: os.listdir('/workspace')):\n"
        "    try:\n        fn()\n        out.append('open')\n"
        "    except PermissionError:\n        out.append('denied')\n"
        "z.finish(out)\n"
    )
    assert end["status"] == "ok" and end["value"] == ["denied", "denied"]


@pytest.mark.parametrize(
    "source",
    [
        "x = bytearray(512 * 1024 * 1024)\n",
        "import os\nwhile True:\n    os.fork()\n",
        "open('big', 'wb').write(b'x' * (40 * 1024 * 1024))\n",
    ],
    ids=["memory", "fork", "file"],
)
def test_resource_limits(source: str) -> None:
    assert run(source)["status"] == "resource_limit"


def test_setsid_child_is_gone_after_the_script() -> None:
    end = run(
        "import subprocess, ze_tools as z\n"
        "p = subprocess.Popen(['sleep', '60'], start_new_session=True)\n"
        "z.finish(p.pid)\n"
    )
    pid = end["value"]
    probe = run(f"import os, ze_tools as z\nz.finish(os.path.exists('/proc/{pid}'))\n")
    assert probe["value"] is False


def test_big_stdout_does_not_hang() -> None:
    end = run(
        "import ze_tools as z\nprint('x' * 10_000_000)\nz.finish('done')\n", timeout=10
    )
    assert end["value"] == "done"


def test_echo_round_trip() -> None:
    end = run(
        "import ze_tools as z\nz.finish(z.echo(x=1))\n", reply=lambda args: args["x"]
    )
    assert end["value"] == 1


@pytest.mark.parametrize("token", [None, "wrong"])
def test_handshake_refused_without_the_right_token(token) -> None:
    async def attempt() -> int:
        url = BASE.replace("http", "ws", 1) + "/scripts"
        try:
            async with websockets.connect(url, additional_headers=_headers(token)):
                return 0
        except websockets.exceptions.InvalidStatus as exc:
            return exc.response.status_code

    assert asyncio.run(attempt()) in (401, 403)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q", "-m", "docker"]))
