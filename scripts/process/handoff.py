"""Shared helpers: call the Maestri CLI and append a line to a floor's Handoffs note."""

import os
import re
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
    current = maestri("note", "read", note, timeout=30)
    text = note_text(current.stdout) if current.returncode == 0 else None
    if text is not None:
        maestri("note", "write", note, text.rstrip("\n") + "\n" + entry + "\n")


def note_text(raw: str) -> str | None:
    """The note's content from `maestri note read` output, or None when the read failed.

    The CLI prints a `[N lines total]` header and an `N<tab>` prefix on every line; both are
    stripped so a write-back does not nest them. A read without the header (a timeout can
    exit 0 with empty output) is a failed read: writing then would wipe the note, as it did
    to the Web Overhaul Specs Handoffs note on 2026-10-21.
    """
    lines = raw.splitlines()
    if not lines or not re.fullmatch(r"\[\d+ lines? total\]", lines[0].strip()):
        return None
    return "\n".join(re.sub(r"^\d+\t", "", line, count=1) for line in lines[1:])
