"""Unprivileged exec supervisor: run journal, timeout, stripped env, isolation."""

from __future__ import annotations

import asyncio
import os
import pwd
import shutil
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID, uuid4

WORKSPACE_ROOT = Path(os.environ.get("WORKSPACE_ROOT", "/workspace")).resolve()
OUTPUT_PREVIEW_CHARS = int(os.environ.get("WORKSPACE_OUTPUT_PREVIEW_CHARS", "8000"))
RUN_LOCK_WAIT_SECONDS = float(os.environ.get("WORKSPACE_RUN_LOCK_WAIT_SECONDS", "30"))
DEFAULT_TIMEOUT = int(os.environ.get("WORKSPACE_RUN_TIMEOUT_SECONDS", "120"))
STORAGE_CEILING = int(
    os.environ.get("WORKSPACE_STORAGE_CEILING_BYTES", str(1024 * 1024 * 1024))
)
# Retention (Phase 129 research.md Decision 3): the running entry (if any) plus
# the last N terminal entries. Not scale-driven — this is a margin against a
# restart/reconciliation/debugging window, not a growth bound.
JOURNAL_RETAIN_TERMINAL = int(os.environ.get("WORKSPACE_JOURNAL_RETAIN_TERMINAL", "5"))

_DENIED_ENV_EXACT = {
    "DATABASE_URL",
    "OPENROUTER_API_KEY",
    "ZE_API_KEY",
    "WORKSPACE_API_TOKEN",
}

_CLEAN_ENV_KEYS = ("PATH", "HOME", "LANG")


class RunBusyError(Exception):
    """Raised by RunJournal.create when one entry is already running (the
    one-slot invariant, Phase 129 FR-007 backstop)."""

    def __init__(self, running: "JournalEntry") -> None:
        super().__init__("busy")
        self.running = running


@dataclass
class JournalEvent:
    seq: int
    type: str  # "stdout" | "stderr" | "exit"
    data: str
    exit_code: int | None = None
    timed_out: bool | None = None


@dataclass
class JournalEntry:
    id: UUID
    command: list[str]
    cwd: str = ""
    status: str = "running"  # running | succeeded | failed | timed_out | cancelled
    started_at: float = field(default_factory=time.time)
    ended_at: float | None = None
    exit_code: int | None = None
    timed_out: bool = False
    events: list[JournalEvent] = field(default_factory=list)
    stdout_preview: str = ""
    stderr_preview: str = ""
    output_file_path: str | None = None
    files_touched: list[dict[str, str]] = field(default_factory=list)
    proc: asyncio.subprocess.Process | None = None
    watchers: list[asyncio.Event] = field(default_factory=list)
    cancel_requested: bool = False
    terminal_event: asyncio.Event = field(default_factory=asyncio.Event)
    _emitted_chars: int = 0

    def is_running(self) -> bool:
        return self.status == "running"

    def to_status_dict(self) -> dict:
        return {
            "id": str(self.id),
            "status": self.status,
            "exit_code": self.exit_code,
            "timed_out": self.timed_out,
            "stdout_preview": self.stdout_preview,
            "stderr_preview": self.stderr_preview,
            "output_file_path": self.output_file_path,
            "files_touched": self.files_touched,
        }


class RunJournal:
    """In-memory run journal (Phase 129 data-model.md). Never persisted — a
    sidecar restart loses it, which is an accepted failure mode (Edge Case 3)."""

    def __init__(self, retain_terminal: int = JOURNAL_RETAIN_TERMINAL) -> None:
        self._entries: dict[UUID, JournalEntry] = {}
        self._terminal_order: list[UUID] = []
        self._retain_terminal = retain_terminal

    def running(self) -> JournalEntry | None:
        for entry in self._entries.values():
            if entry.is_running():
                return entry
        return None

    def create(self, command: list[str], run_id: UUID | None, cwd: str = "") -> JournalEntry:
        current = self.running()
        if current is not None:
            raise RunBusyError(current)
        entry_id = run_id or uuid4()
        entry = JournalEntry(id=entry_id, command=command, cwd=cwd)
        self._entries[entry_id] = entry
        return entry

    def get(self, run_id: UUID) -> JournalEntry | None:
        return self._entries.get(run_id)

    def append_event(self, run_id: UUID, kind: str, data: str) -> None:
        entry = self._entries.get(run_id)
        if entry is None or not entry.is_running():
            return
        if entry._emitted_chars >= OUTPUT_PREVIEW_CHARS:
            return  # bounded — no unbounded wall of text (Edge Case)
        seq = len(entry.events)
        entry.events.append(JournalEvent(seq=seq, type=kind, data=data))
        entry._emitted_chars += len(data)
        self._notify(entry)

    def finish(
        self,
        run_id: UUID,
        *,
        status: str,
        exit_code: int | None,
        timed_out: bool,
        stdout_preview: str,
        stderr_preview: str,
        output_file_path: str | None,
        files_touched: list[dict[str, str]],
    ) -> JournalEntry | None:
        entry = self._entries.get(run_id)
        if entry is None or not entry.is_running():
            return None
        entry.status = status
        entry.exit_code = exit_code
        entry.timed_out = timed_out
        entry.stdout_preview = stdout_preview
        entry.stderr_preview = stderr_preview
        entry.output_file_path = output_file_path
        entry.files_touched = files_touched
        entry.ended_at = time.time()
        entry.proc = None
        seq = len(entry.events)
        entry.events.append(
            JournalEvent(seq=seq, type="exit", data="", exit_code=exit_code, timed_out=timed_out)
        )
        self._notify(entry)
        entry.terminal_event.set()
        self._terminal_order.append(run_id)
        self._evict_if_needed()
        return entry

    def request_cancel(self, run_id: UUID) -> tuple[JournalEntry | None, str]:
        """Returns (entry_or_None, outcome) where outcome is
        "running" (caller must signal the process; _execute is the sole
        writer of the terminal status once it observes cancel_requested) |
        "already_terminal" | "not_found". Setting cancel_requested here (not
        calling finish() directly) avoids a race between this call and
        _execute's own natural-completion finish() call racing to write the
        terminal status first."""
        entry = self._entries.get(run_id)
        if entry is None:
            return None, "not_found"
        if not entry.is_running():
            return entry, "already_terminal"
        entry.cancel_requested = True
        return entry, "running"

    def _notify(self, entry: JournalEntry) -> None:
        for ev in entry.watchers:
            ev.set()

    def _evict_if_needed(self) -> None:
        while len(self._terminal_order) > self._retain_terminal:
            oldest = self._terminal_order.pop(0)
            self._entries.pop(oldest, None)


journal = RunJournal()

_workspace_lock = asyncio.Lock()  # serializes create() calls only (race guard)


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
    return journal.running() is not None


async def _pump(stream: asyncio.StreamReader, kind: str, run_id: UUID, sink: list[bytes]) -> None:
    while True:
        chunk = await stream.read(4096)
        if not chunk:
            break
        sink.append(chunk)
        journal.append_event(run_id, kind, chunk.decode("utf-8", errors="replace"))


async def _execute(
    entry: JournalEntry,
    *,
    timeout_seconds: int,
    env: dict[str, str] | None,
    stdin_bytes: bytes | None,
) -> None:
    if entry.cancel_requested:
        journal.finish(
            entry.id,
            status="cancelled",
            exit_code=None,
            timed_out=False,
            stdout_preview="",
            stderr_preview="",
            output_file_path=None,
            files_touched=[],
        )
        return
    workdir = WORKSPACE_ROOT
    if entry.cwd:
        workdir = (WORKSPACE_ROOT / entry.cwd).resolve()
        if not str(workdir).startswith(str(WORKSPACE_ROOT)):
            journal.finish(
                entry.id,
                status="failed",
                exit_code=1,
                timed_out=False,
                stdout_preview="",
                stderr_preview="outside_workspace",
                output_file_path=None,
                files_touched=[],
            )
            return
    workdir.mkdir(parents=True, exist_ok=True)
    before = snapshot_tree(WORKSPACE_ROOT)
    child = child_env(env)
    uid, gid = _workspace_uids()

    def _preexec() -> None:
        if uid is not None and gid is not None and os.geteuid() == 0:
            os.setgid(gid)
            os.setuid(uid)

    proc = await asyncio.create_subprocess_exec(
        *entry.command,
        cwd=str(workdir),
        env=child,
        stdin=asyncio.subprocess.PIPE if stdin_bytes is not None else None,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        preexec_fn=_preexec if uid is not None else None,
    )
    entry.proc = proc

    if stdin_bytes is not None and proc.stdin is not None:
        proc.stdin.write(stdin_bytes)
        await proc.stdin.drain()
        proc.stdin.close()

    stdout_chunks: list[bytes] = []
    stderr_chunks: list[bytes] = []
    pump_out = asyncio.create_task(_pump(proc.stdout, "stdout", entry.id, stdout_chunks))
    pump_err = asyncio.create_task(_pump(proc.stderr, "stderr", entry.id, stderr_chunks))

    # _execute is the sole writer of terminal status (no race with cancel_handle,
    # which only sets entry.cancel_requested and signals — see request_cancel).
    # `cancelled` is decided from entry.cancel_requested AFTER the process has
    # actually exited (not inside the loop) so a cancel that lands in the same
    # tick the process would have exited anyway is still honored.
    timed_out = False
    sigterm_at: float | None = None
    if entry.cancel_requested:
        proc.send_signal(signal.SIGTERM)
        sigterm_at = time.monotonic()
    start = time.monotonic()
    proc_wait_task = asyncio.create_task(proc.wait())
    while True:
        done, _ = await asyncio.wait({proc_wait_task}, timeout=0.1)
        if proc_wait_task in done:
            break
        if entry.cancel_requested and sigterm_at is None:
            sigterm_at = time.monotonic()
            proc.send_signal(signal.SIGTERM)
        elif sigterm_at is None and time.monotonic() - start >= timeout_seconds:
            timed_out = True
            sigterm_at = time.monotonic()
            proc.send_signal(signal.SIGTERM)
        elif sigterm_at is not None and time.monotonic() - sigterm_at >= 2:
            proc.kill()
            sigterm_at = float("inf")  # avoid repeated kill signals
    cancelled = entry.cancel_requested

    await pump_out
    await pump_err

    combined = b"".join(stdout_chunks) + b"\n" + b"".join(stderr_chunks)
    text = combined.decode("utf-8", errors="replace")
    stdout_text = b"".join(stdout_chunks).decode("utf-8", errors="replace")
    stderr_text = b"".join(stderr_chunks).decode("utf-8", errors="replace")
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

    if cancelled:
        status = "cancelled"
        exit_code = proc.returncode if proc.returncode is not None else -1
    elif timed_out:
        status = "timed_out"
        exit_code = -1
    else:
        exit_code = proc.returncode or 0
        status = "succeeded" if exit_code == 0 else "failed"
    journal.finish(
        entry.id,
        status=status,
        exit_code=exit_code,
        timed_out=timed_out,
        stdout_preview=stdout_text,
        stderr_preview=stderr_text,
        output_file_path=output_file_path,
        files_touched=diff_snapshots(before, after),
    )


async def spawn_run(
    command: list[str],
    run_id: UUID | None,
    *,
    cwd: str = "",
    timeout_seconds: int = DEFAULT_TIMEOUT,
    env: dict[str, str] | None = None,
    stdin_bytes: bytes | None = None,
) -> JournalEntry:
    """Starts command as a background task and returns as soon as the entry is
    recorded — does not await process exit (FR-001). Raises RunBusyError if the
    one-slot invariant is already occupied."""
    entry = journal.create(command, run_id, cwd=cwd)
    asyncio.create_task(
        _execute(entry, timeout_seconds=timeout_seconds, env=env, stdin_bytes=stdin_bytes)
    )
    return entry


async def cancel_handle(run_id: UUID) -> tuple[JournalEntry | None, str]:
    """Signals cancellation and waits for _execute (the sole terminal-status
    writer) to observe it and finish the entry — see request_cancel's
    docstring for why this doesn't write the terminal status itself."""
    entry, outcome = journal.request_cancel(run_id)
    if outcome != "running" or entry is None:
        return entry, outcome
    proc = entry.proc
    if proc is not None and proc.returncode is None:
        proc.send_signal(signal.SIGTERM)
    try:
        await asyncio.wait_for(entry.terminal_event.wait(), timeout=15)
    except TimeoutError:
        pass
    return journal.get(run_id), "cancelled"


async def reset_workspace() -> None:
    current = journal.running()
    if current is not None:
        await cancel_handle(current.id)
    if WORKSPACE_ROOT.exists():
        for child in WORKSPACE_ROOT.iterdir():
            if child.is_dir():
                shutil.rmtree(child, ignore_errors=True)
            else:
                child.unlink(missing_ok=True)
    WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
