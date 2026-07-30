#!/usr/bin/env bash
# Starts two local TLS listeners standing in for "unknown AI-like services" — reached in tests
# via `curl --resolve <name>.internal:<port>:127.0.0.1 https://<name>.internal:<port>/` (sets a
# real SNI without touching /etc/hosts). Ports chosen to avoid the used-port list from Phase 2's
# recon (25,53,631,4173,5173,5432,5601,8000,8443,9200,9300,45369) plus this project's own
# (5433,8090-8094,8100,3000).
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
"$DIR/gen-certs.sh"

start_one() {
  local name="$1" port="$2"
  if pgrep -f "s_server .*-accept $port " >/dev/null; then
    echo "$name.internal:$port already running"
    return
  fi
  # -HTTP mode's response body isn't meaningful here (it tries to serve a file matching the
  # request path and will often just return its own error text) — that's fine, the only thing
  # that matters for shadow-AI clustering testing is that the TLS handshake itself completes so
  # Zeek/Suricata can log SNI/JA3/JA4, which it does regardless of the HTTP-layer outcome.
  nohup openssl s_server -key "$DIR/certs/$name.key" -cert "$DIR/certs/$name.pem" \
    -accept "$port" -HTTP -naccept 1000 >"$DIR/$name.log" 2>&1 &
  disown
  echo "started $name.internal on :$port"
}

start_one shadowmail-ai 8543
start_one quicknotes-ai 8544
