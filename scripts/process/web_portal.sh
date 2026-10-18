#!/usr/bin/env bash
# Serve ze-web from THIS checkout on a strict port so you can verify it in your own Maestri portal.
# Usage:
#   web_portal.sh <port> [name]    start vite, wait for HTTP 200, print the portal command
#   web_portal.sh --check <port>   exit 0 only if http://127.0.0.1:<port>/ answers 200
#   web_portal.sh --stop <port>    stop the vite this script started on <port>
# Logs and pid files go to .process/ (gitignored) in the checkout. Backend: shared test API on 8010.
set -u
ROOT="$(git rev-parse --show-toplevel)" || exit 2
state="$ROOT/.process"

status() { curl -s -o /dev/null -m 3 -w '%{http_code}' "http://127.0.0.1:$1/"; }

case "${1:-}" in
  --check)
    port="${2:?port required}"
    code="$(status "$port")"
    [ "$code" = "200" ] && { echo "portal ok $port"; exit 0; }
    echo "http://127.0.0.1:$port/ answered '$code', not 200" >&2; exit 1 ;;
  --stop)
    port="${2:?port required}"
    pid="$(cat "$state/vite-$port.pid" 2>/dev/null)" || { echo "no pid file for $port" >&2; exit 1; }
    kill "$pid" 2>/dev/null
    kill $(lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null) 2>/dev/null
    rm -f "$state/vite-$port.pid"; echo "stopped vite $port"; exit 0 ;;
  ""|-*) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//' >&2; exit 2 ;;
esac

port="$1"; name="${2:-Web}"
[[ "$port" =~ ^[0-9]+$ ]] || { echo "port must be a number" >&2; exit 2; }
web="$ROOT/apps/ze-web"
[ -x "$web/node_modules/.bin/vite" ] || { echo "node_modules missing: run make web-install first" >&2; exit 1; }
mkdir -p "$state"

# Vite 6 needs Node 20+; the default node on this machine can be v16.
node_major() { "$1" -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0; }
node_bin="$(command -v node || true)"
if [ "$(node_major "${node_bin:-/nonexistent}")" -lt 20 ]; then
  node_bin=""
  for cand in $(ls -d "$HOME"/.nvm/versions/node/v*/bin/node 2>/dev/null | sort -rV); do
    [ "$(node_major "$cand")" -ge 20 ] && { node_bin="$cand"; break; }
  done
  [ -n "$node_bin" ] || { echo "Node 20+ not found (default node is too old); install one with nvm" >&2; exit 1; }
  export PATH="$(dirname "$node_bin"):$PATH"
fi

if [ "$(status "$port")" = "200" ]; then
  echo "port $port already serves 200 (not started by this call)"
else
  (cd "$web" && nohup ./node_modules/.bin/vite --host 127.0.0.1 --port "$port" --strictPort \
    >"$state/vite-$port.log" 2>&1 & echo $! >"$state/vite-$port.pid")
  for _ in $(seq 1 60); do
    [ "$(status "$port")" = "200" ] && break
    sleep 1
  done
  if [ "$(status "$port")" != "200" ]; then
    echo "vite did not answer 200 on $port within 60s; see $state/vite-$port.log" >&2; exit 1
  fi
fi
echo "ok: http://127.0.0.1:$port/ serves $web"
echo "maestri portal create http://127.0.0.1:$port \"$name\""
echo "setup screen: Server URL http://127.0.0.1:8010, API key = ZE_API_KEY from ~/coding/ze/apps/ze-api/.env (never paste it into commits or notes)"
