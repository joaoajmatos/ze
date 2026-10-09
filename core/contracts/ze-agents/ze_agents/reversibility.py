from __future__ import annotations

from enum import StrEnum


class ToolReversibility(StrEnum):
    """Declared on every WRITE tool. Unknown never means safe: there is no default."""

    REVERSIBLE = "reversible"
    IRREVERSIBLE = "irreversible"
