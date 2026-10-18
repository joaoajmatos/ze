from __future__ import annotations

import asyncio

from ze_agents.errors import AudioToolMissingError, AudioUnreadableError
from ze_logging import get_logger

log = get_logger(__name__)

PROBE_TIMEOUT_S = 10.0
CONVERT_TIMEOUT_S = 30.0

_PROBE_BASE = ("-v", "error", "-protocol_whitelist", "pipe")


def normalise_audio_format(fmt: str) -> str:
    """Extract a bare format string from a MIME type or format hint."""
    fmt = fmt.lower()
    for known in ("ogg", "mp3", "wav", "flac", "m4a"):
        if known in fmt:
            return known
    if "mpeg" in fmt:
        return "mp3"
    if "mp4" in fmt:
        return "m4a"
    return fmt.split("/")[-1].split(";")[0].strip()


def container_format(mime: str) -> str:
    """ffmpeg demuxer name for a validated audio type."""
    fmt = normalise_audio_format(mime)
    return "mp4" if fmt == "m4a" else fmt


async def _run(
    argv: tuple[str, ...], data: bytes, timeout: float
) -> tuple[int, bytes]:
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError as exc:
        raise AudioToolMissingError(f"{argv[0]} is not installed") from exc
    try:
        stdout, _ = await asyncio.wait_for(
            proc.communicate(input=data), timeout=timeout
        )
    except asyncio.TimeoutError as exc:
        proc.kill()
        await proc.wait()
        log.warning("audio_subprocess_timeout", tool=argv[0], timeout=timeout)
        raise AudioUnreadableError(f"{argv[0]} timed out") from exc
    return proc.returncode or 0, stdout


def _positive_float(text: str) -> float | None:
    try:
        value = float(text.strip())
    except ValueError:
        return None
    return value if value > 0 else None


def _last_packet_end(output: str) -> float | None:
    end: float | None = None
    for line in output.splitlines():
        pts, _, dur = line.partition(",")
        try:
            start = float(pts)
        except ValueError:
            continue
        try:
            length = float(dur)
        except ValueError:
            length = 0.0
        end = start + length
    return end


async def probe_duration(
    data: bytes, mime: str, *, timeout: float = PROBE_TIMEOUT_S
) -> float:
    """Length in seconds of an untrusted recording.

    Step 1 reads the container duration. MediaRecorder WebM and OGG carry none
    (``N/A``), so step 2 scans packets and returns the last pts + duration.
    """
    demuxer = ("-f", container_format(mime))
    step1 = (
        "ffprobe",
        *_PROBE_BASE,
        *demuxer,
        "-show_entries",
        "format=duration",
        "-of",
        "default=nw=1:nk=1",
        "pipe:0",
    )
    code, out = await _run(step1, data, timeout)
    if code == 0:
        duration = _positive_float(out.decode(errors="replace"))
        if duration is not None:
            return duration

    step2 = (
        "ffprobe",
        *_PROBE_BASE,
        *demuxer,
        "-select_streams",
        "a:0",
        "-show_entries",
        "packet=pts_time,duration_time",
        "-of",
        "csv=p=0",
        "pipe:0",
    )
    code, out = await _run(step2, data, timeout)
    end = _last_packet_end(out.decode(errors="replace")) if code == 0 else None
    if end is None or end <= 0:
        raise AudioUnreadableError("Could not read the recording length")
    return end


async def to_mp3(
    audio_bytes: bytes,
    source_format: str | None = None,
    *,
    timeout: float = CONVERT_TIMEOUT_S,
) -> bytes:
    argv: tuple[str, ...] = ("ffmpeg", "-v", "error", "-protocol_whitelist", "pipe")
    if source_format:
        argv += ("-f", container_format(source_format))
    argv += ("-i", "pipe:0", "-f", "mp3", "-q:a", "4", "pipe:1")
    code, out = await _run(argv, audio_bytes, timeout)
    if code != 0:
        raise AudioUnreadableError("ffmpeg conversion failed")
    return out
