#!/usr/bin/env bash
# Run in a fresh floor right after `maestri floor create`: it must fork from the tip of main with a clean tree.
# Usage: floor_check.sh [main-ref]
set -u
cd "$(git rev-parse --show-toplevel)" || exit 2
main="${1:-main}"
fail=0
if [ "$(git merge-base HEAD "$main")" != "$(git rev-parse "$main")" ]; then
  echo "floor forked from an old commit: merge-base is $(git merge-base HEAD "$main" | cut -c1-8), $main is $(git rev-parse --short "$main"). Recreate it or merge $main." >&2
  fail=1
fi
if [ -n "$(git status --porcelain --untracked-files=no)" ]; then
  echo "floor is not clean" >&2; fail=1
fi
[ "$fail" = 0 ] && echo "floor ok: forked from $(git rev-parse --short "$main"), clean"
exit $fail
