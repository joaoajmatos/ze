#!/usr/bin/env bash
# After `maestri floor land`: refresh the graph, push main. Safe to re-run: each step skips when already done.
# Run from Ground (the main checkout) as the Maestro. Needs a green receipt for HEAD (make process-gates PROFILE=land).
# Usage: land_post.sh [--dry-run]
set -u
ROOT="$(git rev-parse --show-toplevel)" || exit 2
cd "$ROOT" || exit 2
dry=0; [ "${1:-}" = "--dry-run" ] && dry=1
step() { echo "== $*"; }
run() { if [ "$dry" = 1 ]; then echo "   (dry run) $*"; else "$@"; fi; }

head_sha="$(git rev-parse HEAD)"
head_time="$(git log -1 --format=%ct HEAD)"

step "graph"
graph="graphify-out/graph.json"
if [ -f "$graph" ] && [ "$(stat -f %m "$graph" 2>/dev/null || stat -c %Y "$graph")" -ge "$head_time" ]; then
  echo "   graph is newer than HEAD: skipped"
else
  run graphify update . || { echo "graphify update failed" >&2; exit 1; }
  run python3 scripts/graphify_reexports.py || { echo "graphify_reexports failed" >&2; exit 1; }
fi

step "push main"
git fetch -q remote main 2>/dev/null
if [ "$(git rev-parse remote/main 2>/dev/null)" = "$head_sha" ]; then
  echo "   remote/main already at HEAD: skipped"
else
  receipt=".process/receipts/$head_sha.json"
  [ -f "$receipt" ] || { echo "no receipt for HEAD: run make process-gates PROFILE=land first" >&2; exit 1; }
  python3 - "$receipt" <<'PY' || exit 1
import json, sys
r = json.load(open(sys.argv[1]))
bad = [g["gate"] for g in r["gates"] if g["rc"]]
if bad or r.get("dirty_files") or r.get("ok") is False:
    sys.exit(f"receipt is not green: failing={bad} dirty={r.get('dirty_files')}")
PY
  run git push remote main || exit 1
fi

step "by hand (judgment calls)"
cat <<'MSG'
   - score line and roadmap line
   - dismiss the floor's agents, delete the floor, remove lane worktrees, archive state files
MSG
