from __future__ import annotations

import re

_NAMED_KEYS = (
    "OPENROUTER_API_KEY",
    "DATABASE_URL",
    "ZE_API_KEY",
    "WORKSPACE_API_TOKEN",
)

_NAMED_PATTERN = re.compile(
    r"(?:" + "|".join(re.escape(k) for k in _NAMED_KEYS) + r")\s*[:=]\s*\S+",
    re.IGNORECASE,
)

_SECRETISH_PATTERN = re.compile(
    r"\b[A-Z][A-Z0-9_]*(?:SECRET|TOKEN|PASSWORD)\s*[:=]\s*\S+",
    re.IGNORECASE,
)


def redact(text: str | None) -> str:
    """Strip denylisted env-key assignments from a preview or error string (SC-004)."""
    if not text:
        return ""
    redacted = _NAMED_PATTERN.sub("[redacted]", text)
    return _SECRETISH_PATTERN.sub("[redacted]", redacted)
