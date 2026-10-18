#!/usr/bin/env python3
"""A brief must carry the rules agents otherwise forget. Exit 1 and name what is missing.

Usage: brief_lint.py <brief-file>
"""

import re
import sys
from pathlib import Path

REQUIRED = {
    "state-file path (journal/state/)": r"journal/state/",
    "scratchpad rule": r"scratchpad",
    "pre-review checklist (or make process-ready)": r"pre-review checklist|process-ready",
    "commit trailer (Co-Authored-By)": r"co-authored-by",
    "reviewer name": r"reviewer\b",
    "throwaway DB (ze_e2e_*)": r"ze_e2e_|throwaway",
}


def lint(text: str) -> list[str]:
    return [
        name for name, pattern in REQUIRED.items() if not re.search(pattern, text, re.I)
    ]


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    missing = lint(Path(argv[0]).read_text())
    if missing:
        print("brief is missing:\n  - " + "\n  - ".join(missing), file=sys.stderr)
        return 1
    print("brief ok")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
