"""Unprivileged exec supervisor: mutex, timeout, stripped env, isolation."""

from __future__ import annotations

import asyncio
import os
import pwd
import shutil
import signal
import time
from pathlib import Path

WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/workspace")).resolve()
OUTPUT_PREVIEW_CHARS = int(os.environ.get("WORKSPACE_OUTPUT_PREVIEW_CHARS", "8000"))
RUN_LOCK_WAIT_SECONDS = float(os.environ.get("WORKSPACE_RUN_LOCK_WAIT_SECONDS", "30"))
DEFAULT_TIMEOUT = int(os.environ.get("WORKSPACE_RUN_TIMEOUT_SECONDS", "120"))
STORAGE_CEILING = int(
    os.environ.get("WORKSPACE_STORAGE_CEILING_BYTES", str(1024 * 1024 * 1024))
)

_DENIED_ENV_EXACT = {
    "DATABASE_URL",
    "OPENROUTER_API_KEY",
    "ZE_API_KEY",
    "WORKSPACE_API_TOKEN",
}

_CLEAN_ENV_KEYS = ("PATH", "HOME", "LANG")

_lock = asyncio.Lock()
_current_proc: asyncio.subprocess.Process | None = None


def bytes_used(root: Path | None = None) -> int:
    base = root or WORKSPACE_ROOT
    total = 0
    if not base.exists():
        return 0
    for dirpath, _dirnames, filenames in os.walk(base):
        for name in filenames:
            fp = Path(dirpath) / name
            try:
                total += fp.stat().st_size
            except OSError:
                continue
    return total


def snapshot_tree(root: Path) -> dict[str, tuple[int, float]]:
    snaps: dict[str, tuple[int, float]] = {}
    if not root.exists():
        return snaps
    for dirpath, _dirnames, filenames in os.walk(root):
        for name in filenames:
            fp = Path(dirpath) / name
            try:
                st = fp.stat()
            except OSError:
                continue
            rel = str(fp.relative_to(root))
            snaps[rel] = (st.st_size, st.st_mtime)
    return snaps


def diff_snapshots(
    before: dict[str, tuple[int, float]], after: dict[str, tuple[int, float]]
) -> list[dict[str, str]]:
    touches: list[dict[str, str]] = []
    for path, meta in after.items():
        if path not in before:
            touches.append({"path": path, "op": "created"})
        elif before[path] != meta:
            touches.append({"path": path, "op": "updated"})
    for path in before:
        if path not in after:
            touches.append({"path": path, "op": "deleted"})
    return touches


def child_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """Clean env: PATH, HOME=/workspace, LANG. Extra cannot set secret keys."""
    path = os.environ.get("PATH", "/usr/bin:/bin")
    env = {
        "PATH": path,
        "HOME": str(WORKSPACE_ROOT),
        "LANG": os.environ.get("LANG", "C.UTF-8"),
    }
    for key, value in (extra or {}).items():
        upper = key.upper()
        if upper in _DENIED_ENV_EXACT:
            continue
        if upper.endswith(("_SECRET", "_TOKEN", "_PASSWORD")):
            continue
        if key in _CLEAN_ENV_KEYS:
            continue
        env[key] = value
    return env


def _workspace_uids() -> tuple[int | None, int | None]:
    try:
        pw = pwd.getpwnam("workspace")
        return pw.pw_uid, pw.pw_gid
    except KeyError:
        return None, None


def apply_network_isolation() -> None:
    """Deny the workspace uid RFC1918, loopback, and Fly 6PN. Best-effort."""
    uid, _gid = _workspace_uids()
    if uid is None:
        return
    nft = shutil.which("nft")
    iptables = shutil.which("iptables")
    ip6tables = shutil.which("ip6tables")
    v4 = [
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "127.0.0.0/8",
        "169.254.0.0/16",
    ]
    if nft:
        os.system("nft add table inet workspace_filter 2>/dev/null")
        os.system(
            "nft add chain inet workspace_filter output "
            "{ type filter hook output priority 0 \\; } 2>/dev/null"
        )
        for cidr in v4:
            os.system(
                f"nft add rule inet workspace_filter output meta skuid {uid} "
                f"ip daddr {cidr} drop 2>/dev/null"
            )
        os.system(
            f"nft add rule inet workspace_filter output meta skuid {uid} "
            "ip6 daddr fd00::/8 drop 2>/dev/null"
        )
        os.system(
            f"nft add rule inet workspace_filter output meta skuid {uid} "
            "ip6 daddr fdaa::/16 drop 2>/dev/null"
        )
        os.system(
            f"nft add rule inet workspace_filter output meta skuid {uid} "
            "ip6 daddr ::1 drop 2>/dev/null"
        )
        return
    if iptables:
        for cidr in v4:
            os.system(
                f"iptables -I OUTPUT -m owner --uid-owner {uid} "
                f"-d {cidr} -j DROP 2>/dev/null"
            )
    if ip6tables:
        os.system(
            f"ip6tables -I OUTPUT -m owner --uid-owner {uid} "
            "-d fd00::/8 -j DROP 2>/dev/null"
        )
        os.system(
            f"ip6tables -I OUTPUT -m owner --uid-owner {uid} "
            "-d fdaa::/16 -j DROP 2>/dev/null"
        )


def busy() -> bool:
    return _lock.locked()


async def cancel_run() -> bool:
    global _current_proc
    proc = _current_proc
    if proc is None or proc.returncode is not None:
        return False
    proc.send_signal(signal.SIGTERM)
    try:
        await asyncio.wait_for(proc.wait(), timeout=2)
    except TimeoutError:
        proc.kill()
        await proc.wait()
    return True


async def run_command(
    command: list[str],
    *,
    cwd: str = "",
    timeout_seconds: int = DEFAULT_TIMEOUT,
    env: dict[str, str] | None = None,
    stdin_bytes: bytes | None = None,
) -> dict:
    global _current_proc
    try:
        await asyncio.wait_for(_lock.acquire(), timeout=RUN_LOCK_WAIT_SECONDS)
    except TimeoutError:
        return {"error": "busy", "status": 409}

    try:
        workdir = WORKSPACE_ROOT
        if cwd:
            workdir = (WORKSPACE_ROOT / cwd).resolve()
            if not str(workdir).startswith(str(WORKSPACE_ROOT)):
                return {"error": "outside_workspace", "status": 400}
        workdir.mkdir(parents=True, exist_ok=True)
        before = snapshot_tree(WORKSPACE_ROOT)
        child = child_env(env)
        uid, gid = _workspace_uids()

        def _preexec() -> None:
            if uid is not None and gid is not None and os.geteuid() == 0:
                os.setgid(gid)
                os.setuid(uid)

        proc = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(workdir),
            env=child,
            stdin=asyncio.subprocess.PIPE if stdin_bytes is not None else None,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            preexec_fn=_preexec if uid is not None else None,
        )
        _current_proc = proc
        timed_out = False
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(input=stdin_bytes),
                timeout=timeout_seconds,
            )
        except TimeoutError:
            timed_out = True
            proc.send_signal(signal.SIGTERM)
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=2)
            except TimeoutError:
                proc.kill()
                stdout, stderr = await proc.communicate()

        combined = (stdout or b"") + b"\n" + (stderr or b"")
        text = combined.decode("utf-8", errors="replace")
        stdout_text = (stdout or b"").decode("utf-8", errors="replace")
        stderr_text = (stderr or b"").decode("utf-8", errors="replace")
        output_file_path = None
        if len(text) > OUTPUT_PREVIEW_CHARS:
            spill = WORKSPACE_ROOT / f".run-output-{int(time.time() * 1000)}.txt"
            spill.write_bytes(combined)
            if uid is not None:
                try:
                    os.chown(spill, uid, gid or -1)
                except OSError:
                    pass
            output_file_path = spill.name
            stdout_text = stdout_text[:OUTPUT_PREVIEW_CHARS]
            stderr_text = stderr_text[:OUTPUT_PREVIEW_CHARS]
        after = snapshot_tree(WORKSPACE_ROOT)
        return {
            "exit_code": -1 if timed_out else (proc.returncode or 0),
            "timed_out": timed_out,
            "stdout_preview": stdout_text,
            "stderr_preview": stderr_text,
            "output_file_path": output_file_path,
            "files_touched": diff_snapshots(before, after),
            "child_env": child,
        }
    finally:
        _current_proc = None
        if _lock.locked():
            _lock.release()


async def reset_workspace() -> None:
    await cancel_run()
    if WORKSPACE_ROOT.exists():
        for child in WORKSPACE_ROOT.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
