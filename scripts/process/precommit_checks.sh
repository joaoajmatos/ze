#!/usr/bin/env bash
# Repo-state rules every harness hits at commit time (OpenCode and Cursor skip Claude Code hooks).
# A no-op unless MAESTRI_TERMINAL_ID is set. Bypass: SKIP=1.
set -u
[[ -n "${MAESTRI_TERMINAL_ID:-}" && "${SKIP:-}" != "1" ]] || exit 0

fail=0

new_arch="$(git diff --cached --name-only --diff-filter=A -- 'specs/arch/' || true)"
if [[ -n "$new_arch" && "${ZE_ROLE:-}" != "architect" && "${ZE_ROLE:-}" != "maestro" ]]; then
  echo "process: new files under specs/arch/ need the architect or Maestro (no working notes there):" >&2
  echo "$new_arch" >&2
  fail=1
fi

exit $fail
