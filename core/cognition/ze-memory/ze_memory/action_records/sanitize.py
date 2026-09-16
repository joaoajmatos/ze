from __future__ import annotations

import re

MAX_SUMMARY_LEN = 500
MAX_FAILURE_CODE_LEN = 80

_UNSAFE_PATTERNS = (
    re.compile(r"traceback \(most recent call last\)", re.IGNORECASE),
    re.compile(r'file "[^"]+", line \d+', re.IGNORECASE),
    re.compile(
        r"(password|passwd|secret|token|api[_-]?key)\s*[:=]\s*\S+", re.IGNORECASE
    ),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\bsk-[A-Za-z0-9]{8,}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/]+=*", re.IGNORECASE),
)


def sanitize_summary(text: str) -> str:
    cleaned = " ".join((text or "").split())
    if len(cleaned) > MAX_SUMMARY_LEN:
        cleaned = cleaned[: MAX_SUMMARY_LEN - 1].rstrip() + "…"
    return cleaned


def sanitize_failure_code(text: str | None) -> str | None:
    if text is None:
        return None
    cleaned = " ".join(text.split())
    if len(cleaned) > MAX_FAILURE_CODE_LEN:
        cleaned = cleaned[: MAX_FAILURE_CODE_LEN - 1].rstrip() + "…"
    return cleaned


def assert_safe_text(text: str, *, field: str) -> None:
    from ze_memory.action_records.errors import UnsafeActionRecordSummaryError

    for pattern in _UNSAFE_PATTERNS:
        if pattern.search(text):
            raise UnsafeActionRecordSummaryError(
                f"{field} contains forbidden sensitive or unbounded content"
            )
