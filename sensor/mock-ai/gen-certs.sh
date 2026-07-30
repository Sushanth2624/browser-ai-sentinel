#!/usr/bin/env bash
# Self-signed certs for two mock "unknown AI-like" endpoints — same technique capstone-1 used for
# its local openssl s_server C2 target (fresh certs, fresh script, no shared code). These exist
# purely to give the shadow-AI clustering heuristic (agent/internal/store's
# UpsertShadowAICluster — see db/schema.sql) two distinct, controllable, non-known-AI domains to
# be tested against, without touching any real third-party service.
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/certs"
mkdir -p "$DIR"

for name in shadowmail-ai quicknotes-ai; do
  if [[ -f "$DIR/$name.pem" ]]; then continue; fi
  openssl req -x509 -newkey rsa:2048 -nodes -days 365 \
    -keyout "$DIR/$name.key" -out "$DIR/$name.pem" \
    -subj "/CN=$name.internal" \
    -addext "subjectAltName=DNS:$name.internal" 2>/dev/null
  echo "generated cert for $name.internal"
done
