"""Tool scripts: one Python script at a time, calling Ze's read tools over WS /scripts."""

from __future__ import annotations

import asyncio
import collections
import json
import os
import pwd
import resource
import shutil
import signal
import time
import uuid
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

SCRATCH_ROOT = Path(os.environ.get("ZE_SCRIPTS_ROOT", "/tmp/ze-scripts"))
RUNTIME_DIR = Path(__file__).resolve().parent / "script_runtime"
TICK_SECONDS = 0.1
STDERR_RING_BYTES = 64 * 1024
STDERR_TAIL_LINES = 20
MAX_REQUEST_BYTES = 256 * 1024
MAX_REPLY_BYTES = 1024 * 1024
MAX_FINISH_BYTES = 1024 * 1024
MAX_INNER_CALLS = 20
SCRATCH_CAP_BYTES = 32 * 1024 * 1024
WS_MAX_SIZE = 2 * 1024 * 1024


SCRIPT_USER = "zescript"
RLIMIT_AS_BYTES = 256 * 1024 * 1024
RLIMIT_NPROC_COUNT = 32
RLIMIT_FSIZE_BYTES = 16 * 1024 * 1024
RLIMIT_NOFILE_COUNT = 64
_LIMIT_SIGNALS = (signal.SIGKILL, signal.SIGXCPU, signal.SIGXFSZ)
_LIMIT_MARKERS = (
    "MemoryError",
    "Resource temporarily unavailable",
    "Cannot allocate memory",
    "File too large",
)


def script_env(scratch: Path, req_fd: int, rep_fd: int) -> dict[str, str]:
    return {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(scratch),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
        "ZE_REQ_FD": str(req_fd),
        "ZE_REP_FD": str(rep_fd),
    }


def script_rlimits(wall_seconds: int, nproc_base: int = 0) -> dict[int, int]:
    return {
        resource.RLIMIT_AS: RLIMIT_AS_BYTES,
        resource.RLIMIT_NPROC: nproc_base + RLIMIT_NPROC_COUNT,
        resource.RLIMIT_FSIZE: RLIMIT_FSIZE_BYTES,
        resource.RLIMIT_CPU: wall_seconds + 1,
        resource.RLIMIT_NOFILE: RLIMIT_NOFILE_COUNT,
    }


def is_resource_limit_exit(returncode: int | None, stderr_tail: str) -> bool:
    if returncode is not None and returncode < 0 and -returncode in _LIMIT_SIGNALS:
        return True
    return any(marker in stderr_tail for marker in _LIMIT_MARKERS)


def script_identity() -> tuple[int, int] | None:
    """The zescript uid and gid, only when the sidecar can switch to it (root)."""
    if os.geteuid() != 0:
        return None
    try:
        entry = pwd.getpwnam(SCRIPT_USER)
    except KeyError:
        return None
    return entry.pw_uid, entry.pw_gid


PROBE_WORKSPACE = "/workspace"
PROBE_BREACH_EXIT = 87
ALLOW_UNISOLATED_ENV = "ZE_SCRIPTS_ALLOW_UNISOLATED"


@dataclass
class Isolation:
    """Whether scripts are closed in: reject rule verified, /workspace closed, no breach."""

    rule_verified: bool = False
    mode_set: bool = False
    breached: bool = False

    @property
    def ok(self) -> bool:
        return self.rule_verified and self.mode_set and not self.breached


isolation = Isolation()


def probe_enabled() -> bool:
    return script_identity() is not None


def sandbox_refusal() -> str | None:
    """Why scripts must not run here, or None. The endpoint fails closed."""
    if script_identity() is not None:
        return None if isolation.ok else "sandbox not isolated"
    if os.geteuid() == 0:
        return "script user missing"
    if os.environ.get(ALLOW_UNISOLATED_ENV) != "1":
        return "sandbox not isolated"
    return None


def _own_process_count() -> int:
    """Processes of the current user, so RLIMIT_NPROC leaves room when not switching uid."""
    import subprocess

    if Path("/proc/self/stat").exists():
        return len(_uid_pids(os.getuid()))
    try:
        out = subprocess.run(
            ["ps", "-U", str(os.getuid()), "-o", "pid="],
            capture_output=True,
            text=True,
            timeout=5,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    return len(out.split())


class ScriptSlot:
    """The one script slot, separate from the workspace run journal."""

    def __init__(self) -> None:
        self._running = False

    def busy(self) -> bool:
        return self._running

    def acquire(self) -> bool:
        if self._running:
            return False
        self._running = True
        return True

    def release(self) -> None:
        self._running = False


slot = ScriptSlot()


def _parent_links() -> list[tuple[int, int]]:
    """(pid, ppid) for every process: /proc on Linux, ps elsewhere."""
    import subprocess

    links: list[tuple[int, int]] = []
    if Path("/proc/self/stat").exists():
        for entry in Path("/proc").glob("[0-9]*"):
            try:
                tail = (entry / "stat").read_text().rsplit(")", 1)[1].split()
                links.append((int(entry.name), int(tail[1])))
            except (OSError, IndexError, ValueError):
                pass
        return links
    try:
        out = subprocess.run(
            ["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True, timeout=5
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 2:
            links.append((int(parts[0]), int(parts[1])))
    return links


def _descendants(root_pid: int) -> list[int]:
    """Every descendant of root_pid by parent links (a setsid child is still one)."""
    children: dict[int, list[int]] = collections.defaultdict(list)
    for pid, ppid in _parent_links():
        children[ppid].append(pid)
    found: list[int] = []
    stack = [root_pid]
    while stack:
        for child in children.get(stack.pop(), []):
            found.append(child)
            stack.append(child)
    return found


def _uid_pids(uid: int) -> list[int]:
    found = []
    for entry in Path("/proc").glob("[0-9]*"):
        try:
            if entry.stat().st_uid == uid:
                found.append(int(entry.name))
        except OSError:
            pass
    return found


def kill_script_processes(root_pid: int) -> None:
    """SIGKILL the script and everything it started, however it detached."""
    pids = [root_pid, *_descendants(root_pid)]
    identity = script_identity()
    if identity and Path("/proc/self").exists():
        pids += _uid_pids(identity[0])
    for pid in reversed(pids):
        try:
            os.kill(pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass


async def _spawn(argv: list[str], **kwargs: Any) -> asyncio.subprocess.Process:
    return await asyncio.create_subprocess_exec(*argv, **kwargs)


def scratch_bytes(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def _tail(ring: bytearray) -> str:
    text = bytes(ring).decode("utf-8", errors="replace")
    return "\n".join(text.splitlines()[-STDERR_TAIL_LINES:])


def _end(status: str, **extra: Any) -> dict:
    return {
        "type": "end",
        "status": status,
        "value": extra.get("value"),
        "writes": extra.get("writes", []),
        "stderr_tail": extra.get("stderr_tail", ""),
        "exception": extra.get("exception", ""),
    }


def _valid_writes(writes: Any) -> bool:
    return isinstance(writes, list) and all(
        isinstance(w, dict)
        and isinstance(w.get("tool"), str)
        and isinstance(w.get("args"), dict)
        for w in writes
    )


class ScriptRun:
    def __init__(self, ws: WebSocket, start: dict) -> None:
        self.ws = ws
        self.start = start
        self.id = str(start.get("id") or uuid.uuid4())
        self.timeout = max(1, int(start.get("timeout_seconds") or 30))
        self.done = asyncio.Event()
        self.result: dict | None = None
        self.finish_line: dict | None = None
        self.stderr = bytearray()
        self.pending: dict[int, asyncio.Future] = {}
        self.proc: asyncio.subprocess.Process | None = None
        self.scratch = Path()

    def end(self, status: str, **extra: Any) -> None:
        if self.result is None:
            self.result = _end(status, **extra)
            self.done.set()

    def _prepare(self) -> Path:
        scratch = SCRATCH_ROOT / self.id
        SCRATCH_ROOT.mkdir(parents=True, exist_ok=True, mode=0o711)
        scratch.mkdir(parents=True, exist_ok=True)
        scratch.chmod(0o700)
        shutil.copyfile(RUNTIME_DIR / "ze_tools_base.py", scratch / "ze_tools_base.py")
        (scratch / "ze_tools.py").write_text(
            str(self.start.get("stub", "")), encoding="utf-8"
        )
        (scratch / "main.py").write_text(
            str(self.start.get("source", "")), encoding="utf-8"
        )
        shutil.copyfile(RUNTIME_DIR / "_ze_main.py", scratch / "_ze_main.py")
        identity = script_identity()
        if identity:
            os.chown(scratch, *identity)
            for child in scratch.iterdir():
                os.chown(child, *identity)
        return scratch

    async def run(self) -> dict:
        scratch = self.scratch = self._prepare()
        loop = asyncio.get_running_loop()
        req_r, req_w = os.pipe()
        rep_r, rep_w = os.pipe()
        env = script_env(scratch, req_w, rep_r)
        identity = script_identity()
        limits = script_rlimits(self.timeout, 0 if identity else _own_process_count())

        def _preexec() -> None:
            for which, value in limits.items():
                try:
                    resource.setrlimit(which, (value, value))
                except (OSError, ValueError):
                    if identity is not None:
                        raise
            if identity is not None:
                os.setgroups([])
                os.setgid(identity[1])
                os.setuid(identity[0])

        if probe_enabled():
            breach = await self._probe(scratch, env, _preexec)
            if breach:
                isolation.breached = True
                for fd in (req_r, req_w, rep_r, rep_w):
                    os.close(fd)
                shutil.rmtree(scratch, ignore_errors=True)
                self.end("unavailable", exception=breach)
                assert self.result is not None
                return self.result

        try:
            self.proc = await _spawn(
                [
                    shutil.which("python3") or "python3",
                    "-I",
                    "-X",
                    "utf8",
                    "_ze_main.py",
                ],
                cwd=str(scratch),
                env=env,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE,
                pass_fds=(req_w, rep_r),
                preexec_fn=_preexec,
                start_new_session=True,
            )
        finally:
            os.close(req_w)
            os.close(rep_r)
        req_reader = asyncio.StreamReader(limit=MAX_FINISH_BYTES + MAX_REQUEST_BYTES)
        await loop.connect_read_pipe(
            lambda: asyncio.StreamReaderProtocol(req_reader), os.fdopen(req_r, "rb", 0)
        )
        w_transport, w_protocol = await loop.connect_write_pipe(
            lambda: asyncio.streams.FlowControlMixin(loop=loop),
            os.fdopen(rep_w, "wb", 0),
        )
        rep_writer = asyncio.StreamWriter(w_transport, w_protocol, None, loop)
        tasks = [
            asyncio.create_task(self._drain_stderr()),
            asyncio.create_task(self._relay_requests(req_reader, rep_writer)),
            asyncio.create_task(self._read_ws()),
            asyncio.create_task(self._tick(scratch)),
        ]
        try:
            await self.done.wait()
        finally:
            if self.proc is not None:
                kill_script_processes(self.proc.pid)
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            rep_writer.close()
            if self.proc is not None:
                await self.proc.wait()
            shutil.rmtree(scratch, ignore_errors=True)
        assert self.result is not None
        return self.result

    async def _probe(self, scratch: Path, env: dict[str, str], preexec: Any) -> str:
        """Run the isolation probe as its own process, so user code can never forge a breach."""
        proc = await _spawn(
            [
                shutil.which("python3") or "python3",
                "-I",
                "-X",
                "utf8",
                "_ze_main.py",
                "--probe-only",
                PROBE_WORKSPACE,
            ],
            cwd=str(scratch),
            env={k: v for k, v in env.items() if not k.startswith("ZE_")},
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
            preexec_fn=preexec,
            start_new_session=True,
        )
        try:
            code = await asyncio.wait_for(proc.wait(), timeout=10)
        except asyncio.TimeoutError:
            kill_script_processes(proc.pid)
            await proc.wait()
            return "isolation probe timed out"
        if code == PROBE_BREACH_EXIT:
            return "isolation probe found a breach"
        return "" if code == 0 else f"isolation probe failed ({code})"

    async def _drain_stderr(self) -> None:
        assert self.proc is not None and self.proc.stderr is not None
        while chunk := await self.proc.stderr.read(4096):
            self.stderr += chunk
            if len(self.stderr) > STDERR_RING_BYTES:
                del self.stderr[: len(self.stderr) - STDERR_RING_BYTES]

    async def _relay_requests(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        lines = 0
        while True:
            try:
                line = await reader.readline()
            except ValueError:
                self.end("bad_request", exception="request line too long")
                return
            if not line:
                break
            lines += 1
            if lines > 2 * MAX_INNER_CALLS:
                self.end("bad_request", exception="too many request lines")
                return
            cap = (
                MAX_FINISH_BYTES if line.startswith(b'{"finish"') else MAX_REQUEST_BYTES
            )
            if len(line) > cap:
                self.end("bad_request", exception="request line too long")
                return
            try:
                msg = json.loads(line)
            except ValueError:
                self.end("bad_request", exception="malformed request line")
                return
            if not isinstance(msg, dict):
                self.end("bad_request", exception="malformed request line")
                return
            if "finish" in msg:
                self.finish_line = msg
                continue
            tool, args, seq = msg.get("tool"), msg.get("args"), msg.get("seq")
            if not (
                isinstance(tool, str)
                and isinstance(args, dict)
                and isinstance(seq, int)
            ):
                self.end("bad_request", exception="malformed request line")
                return
            waiter: asyncio.Future = asyncio.get_running_loop().create_future()
            self.pending[seq] = waiter
            await self.ws.send_json(
                {"type": "call", "seq": seq, "tool": tool, "args": args}
            )
            reply = await waiter
            if len(json.dumps(reply)) > MAX_REPLY_BYTES:
                reply = {"seq": seq, "ok": False, "error": "result_too_large"}
            writer.write((json.dumps(reply) + "\n").encode("utf-8"))
            await writer.drain()
        await self.proc.wait()  # type: ignore[union-attr]
        await asyncio.sleep(0)
        self._natural_end()

    def _natural_end(self) -> None:
        assert self.proc is not None
        code = self.proc.returncode
        tail = _tail(self.stderr)
        if scratch_bytes(self.scratch) > SCRATCH_CAP_BYTES:
            self.end("resource_limit", exception="scratch size", stderr_tail=tail)
            return
        if code == 0:
            finish = self.finish_line
            if finish is None:
                self.end("ok", stderr_tail=tail)
            elif not _valid_writes(finish.get("writes", [])):
                self.end("bad_request", exception="writes entries need tool and args")
            else:
                self.end(
                    "ok",
                    value=finish.get("finish"),
                    writes=finish.get("writes", []),
                    stderr_tail=tail,
                )
            return
        if is_resource_limit_exit(code, tail):
            self.end("resource_limit", exception="resource limit", stderr_tail=tail)
            return
        lines = [ln for ln in tail.splitlines() if ln.strip()]
        self.end("exception", exception=lines[-1] if lines else "", stderr_tail=tail)

    async def _read_ws(self) -> None:
        while True:
            try:
                frame = await self.ws.receive_json()
            except (WebSocketDisconnect, RuntimeError):
                self.end("killed", exception="connection closed")
                return
            kind = frame.get("type")
            if kind == "reply":
                waiter = self.pending.pop(frame.get("seq"), None)
                if waiter is not None and not waiter.done():
                    ok = bool(frame.get("ok"))
                    reply = {"seq": frame.get("seq"), "ok": ok}
                    reply["value" if ok else "error"] = frame.get(
                        "value" if ok else "error"
                    )
                    waiter.set_result(reply)
            elif kind == "cancel":
                self.end("killed")
                return

    async def _tick(self, scratch: Path) -> None:
        deadline = time.monotonic() + self.timeout
        while True:
            await asyncio.sleep(TICK_SECONDS)
            if time.monotonic() >= deadline:
                self.end("timeout", stderr_tail=_tail(self.stderr))
                return
            if scratch_bytes(scratch) > SCRATCH_CAP_BYTES:
                self.end(
                    "resource_limit",
                    exception="scratch size",
                    stderr_tail=_tail(self.stderr),
                )
                return


async def handle(ws: WebSocket) -> None:
    await ws.accept()
    if not slot.acquire():
        await ws.send_json(_end("busy"))
        await ws.close()
        return
    try:
        start = await ws.receive_json()
        if not isinstance(start, dict) or start.get("type") != "start":
            await ws.send_json(_end("bad_request"))
        elif (reason := sandbox_refusal()) is not None:
            await ws.send_json(_end("unavailable", exception=reason))
        else:
            result = await ScriptRun(ws, start).run()
            try:
                await ws.send_json(result)
            except (WebSocketDisconnect, RuntimeError):
                pass
        try:
            await ws.close()
        except (WebSocketDisconnect, RuntimeError):
            pass
    finally:
        slot.release()
