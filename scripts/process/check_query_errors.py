#!/usr/bin/env python3
"""A changed entities/*/api/use*Query.ts must throw on an API error and have a test that reads isError.

Usage: check_query_errors.py <changed-file>...   exit 1 on a miss. Files that are not query hooks are ignored.
"""

import re
import sys
from pathlib import Path

HOOK = re.compile(r"entities/[^/]+/api/use\w+Query\.tsx?$")
WEB_SRC = Path("apps/ze-web/src")


def tests_reading_is_error() -> str:
    return "\n".join(
        p.read_text()
        for p in WEB_SRC.rglob("*.test.ts*")
        if "isError" in (text := p.read_text()) and text
    )


def check(files: list[str]) -> list[str]:
    errs: list[str] = []
    corpus = ""
    for name in files:
        if not HOOK.search(name) or not Path(name).exists():
            continue
        source = Path(name).read_text()
        hook_names = re.findall(r"export function (use\w+Query)\b", source)
        if not re.search(r"\bthrow\b", source):
            errs.append(
                f"{name}: no `throw` on the error path (an API error must not read as empty data)"
            )
        corpus = corpus or tests_reading_is_error()
        for hook in hook_names:
            if hook not in corpus:
                errs.append(
                    f"{name}: {hook} is not exercised by any test that asserts isError"
                )
    return errs


def main(argv: list[str]) -> int:
    errs = check(argv)
    print("\n".join(errs) or "query errors: ok")
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
