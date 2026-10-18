"""Shared helpers: call the Maestri CLI and append a line to a floor's Handoffs note."""

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def cli() -> str:
    return os.environ.get("MAESTRI_CLI") or "maestri"


def maestri(*args: str, timeout: float | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            [cli(), *args], capture_output=True, text=True, timeout=timeout
        )
    except subprocess.TimeoutExpired as exc:
        return subprocess.CompletedProcess(
            exc.cmd,
            124,
            (exc.stdout or b"").decode()
            if isinstance(exc.stdout, bytes)
            else exc.stdout or "",
            "timeout",
        )
    except FileNotFoundError:
        return subprocess.CompletedProcess(
            [cli(), *args], 127, "", f"{cli()} not found"
        )


def append_handoff(repo: Path, note: str, line: str) -> None:
    """Add a timestamped line to the Handoffs note; keep a local copy in .process/handoffs.log either way."""
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%MZ")
    entry = f"{stamp} {line}"
    log = repo / ".process" / "handoffs.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a") as fh:
        fh.write(entry + "\n")
    if not note:
        return
    current = maestri("note", "read", note)
    if current.returncode == 0:
        maestri(
            "note", "write", note, current.stdout.rstrip("\n") + "\n" + entry + "\n"
        )
