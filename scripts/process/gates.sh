#!/usr/bin/env bash
# Run named make gates, capture each exit code, write a receipt keyed to HEAD. Exit 1 if any gate failed.
# Usage: gates.sh <receipt.json|-> <make-target>...
#   "-" writes .process/receipts/<HEAD sha>.json under the repo root.
set -u
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT" || exit 2
out="$1"; shift
sha="$(git rev-parse HEAD)"
[ "$out" = "-" ] && out=".process/receipts/$sha.json"
case "$out" in /*) ;; *) out="$ROOT/$out" ;; esac
dirty="$(git status --porcelain --untracked-files=no | wc -l | tr -d ' ')"
logdir="$(dirname "$out")/logs/$sha"; mkdir -p "$logdir"
fail=0; entries=""
for t in "$@"; do
  start=$(date +%s)
  make --no-print-directory "$t" >"$logdir/$t.log" 2>&1
  rc=$?
  [ "$rc" -ne 0 ] && fail=1
  entries="$entries{\"gate\":\"$t\",\"rc\":$rc,\"secs\":$(( $(date +%s) - start )),\"log\":\"$logdir/$t.log\"},"
  echo "$t rc=$rc"
done
printf '{"sha":"%s","dirty_files":%s,"at":"%s","gates":[%s]}\n' \
  "$sha" "$dirty" "$(date -u +%FT%TZ)" "${entries%,}" >"$out"
echo "receipt: $out"
exit $fail
