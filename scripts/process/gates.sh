#!/usr/bin/env bash
# Run named make gates, capture each exit code, write a receipt keyed to HEAD. Exit 1 if any gate failed.
# Usage: gates.sh <receipt.json|-> <make-target>...
# Full-suite gates (test-py, test-web, test-pg, typecheck-web, web-build, check) take the machine-wide lock
# ZE_GATE_LOCK (default /tmp/ze-full-gates.lock, the one ~/.maestri-ze/gate-lock.sh uses): one full run at a time.
#   "-" writes .process/receipts/<HEAD sha>.json under the repo root.
set -u
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT" || exit 2
out="$1"; shift
sha="$(git rev-parse HEAD)"
[ "$out" = "-" ] && out=".process/receipts/$sha.json"
case "$out" in /*) ;; *) out="$ROOT/$out" ;; esac
# Uncommitted and untracked files count; the receipt's own .process/ and scratchpad paths do not.
dirty="$(git status --porcelain -- . ':(exclude).process' ':(exclude)*scratchpad*' | wc -l | tr -d ' ')"
logdir="$(dirname "$out")/logs/$sha"; mkdir -p "$logdir"
LOCK="${ZE_GATE_LOCK:-/tmp/ze-full-gates.lock}"
heavy() { case "$1" in test-py|test-web|test-all|test-pg|typecheck-web|web-build|check) return 0 ;; esac; return 1; }
# True when the lock holder is this process or one of its ancestors (we run under gate-lock.sh already).
held_by_ancestor() {
  holder="$(cat "$LOCK/pid" 2>/dev/null)"; [ -n "$holder" ] || return 1
  pid=$$
  while [ -n "$pid" ] && [ "$pid" -gt 1 ]; do
    [ "$pid" = "$holder" ] && return 0
    pid="$(ps -o ppid= -p "$pid" 2>/dev/null | tr -d ' ')"
  done
  return 1
}
acquired=0
acquire() {
  held_by_ancestor && return 0
  while ! mkdir "$LOCK" 2>/dev/null; do
    p="$(cat "$LOCK/pid" 2>/dev/null)"
    if [ -n "$p" ] && ! kill -0 "$p" 2>/dev/null; then rm -rf "$LOCK"; continue; fi
    echo "gates: waiting for the full-gate lock held by pid ${p:-?} ($(cat "$LOCK/who" 2>/dev/null))" >&2
    sleep "${ZE_GATE_LOCK_POLL:-20}"
  done
  echo $$ > "$LOCK/pid"; echo "$PWD gates.sh $*" > "$LOCK/who"; acquired=1
}
release() { [ "$acquired" = 1 ] && rm -rf "$LOCK"; acquired=0; }
trap release EXIT INT TERM
fail=0; entries=""
for t in "$@"; do
  heavy "$t" && acquire
  start=$(date +%s)
  make --no-print-directory "$t" >"$logdir/$t.log" 2>&1
  rc=$?
  release
  [ "$rc" -ne 0 ] && fail=1
  entries="$entries{\"gate\":\"$t\",\"rc\":$rc,\"secs\":$(( $(date +%s) - start )),\"log\":\"$logdir/$t.log\"},"
  echo "$t rc=$rc"
done
printf '{"sha":"%s","dirty_files":%s,"at":"%s","gates":[%s]}\n' \
  "$sha" "$dirty" "$(date -u +%FT%TZ)" "${entries%,}" >"$out"
echo "receipt: $out"
exit $fail
