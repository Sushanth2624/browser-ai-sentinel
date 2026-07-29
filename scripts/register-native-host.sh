#!/usr/bin/env bash
# Registers (or re-registers) the native messaging host manifest for the current user's
# Google Chrome profile.
#
# NOTE on how the extension ID is determined: manifest.json includes a pinned "key" field, which
# is Chrome's documented mechanism for giving an unpacked extension a stable ID. Empirically, on
# this machine's Chrome build (150.0.7871.46), loading via --load-extension did NOT honor that
# key — Chrome assigned an ID derived from the extension directory's absolute path instead
# (verified by loading the same dist/ dir into two independent fresh profiles and observing the
# identical ID both times). Rather than trust the theoretical key-derived ID, this script
# discovers the REAL ID empirically every time: it launches headless Chrome with the extension
# loaded, reads the ID off the live service-worker DevTools target, and registers exactly that.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EXT_DIST="$REPO_ROOT/extension/dist"
NM_BINARY="$REPO_ROOT/agent/bin/nmhost"
NM_DIR="$HOME/.config/google-chrome/NativeMessagingHosts"
NM_MANIFEST="$NM_DIR/com.browseraisentinel.nmhost.json"
SYSTEM_NM_DIR="/etc/opt/chrome/native-messaging-hosts"
SYSTEM_NM_MANIFEST="$SYSTEM_NM_DIR/com.browseraisentinel.nmhost.json"
EXT_ID_FILE="$REPO_ROOT/extension/extension_id.txt"
DEBUG_PORT=9424
PROBE_PROFILE="$(mktemp -d)"

if [[ ! -d "$EXT_DIST" ]]; then
  echo "error: $EXT_DIST not found — run 'make extension-build' first" >&2
  exit 1
fi
if [[ ! -x "$NM_BINARY" ]]; then
  echo "error: $NM_BINARY not built — run 'make agent-build' first" >&2
  exit 1
fi

cleanup() {
  if [[ -n "${CHROME_PID:-}" ]]; then
    kill "$CHROME_PID" 2>/dev/null || true
    wait "$CHROME_PID" 2>/dev/null || true
  fi
  rm -rf "$PROBE_PROFILE"
}
trap cleanup EXIT

google-chrome-stable \
  --headless=new --disable-gpu --no-first-run --no-default-browser-check \
  --user-data-dir="$PROBE_PROFILE" \
  --load-extension="$EXT_DIST" \
  --disable-extensions-except="$EXT_DIST" \
  --remote-debugging-port=$DEBUG_PORT --remote-allow-origins=* \
  about:blank >/tmp/bas-probe-chrome.log 2>&1 &
CHROME_PID=$!

EXT_ID=""
for _ in $(seq 1 20); do
  sleep 0.5
  EXT_ID="$(curl -s "http://127.0.0.1:$DEBUG_PORT/json/list" 2>/dev/null \
    | python3 -c "
import json, sys
try:
    targets = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for t in targets:
    if t.get('type') == 'service_worker' and 'chrome-extension://' in t.get('url', ''):
        print(t['url'].split('/')[2])
        break
" || true)"
  [[ -n "$EXT_ID" ]] && break
done

if [[ -z "$EXT_ID" ]]; then
  echo "error: could not discover the extension's service-worker target — check /tmp/bas-probe-chrome.log" >&2
  exit 1
fi

echo "$EXT_ID" > "$EXT_ID_FILE"

manifest_json() {
  cat <<EOF
{
  "name": "com.browseraisentinel.nmhost",
  "description": "Browser AI Sentinel native messaging host (relays to local Go daemon on :8090)",
  "path": "$NM_BINARY",
  "type": "stdio",
  "allowed_origins": ["chrome-extension://${EXT_ID}/"]
}
EOF
}

mkdir -p "$NM_DIR"
manifest_json > "$NM_MANIFEST"
echo "Registered native messaging host (user-level) at $NM_MANIFEST"

# Also register system-wide. Empirically necessary: on this machine's Chrome build, a profile
# launched with a custom --user-data-dir (e.g. this script's own probe, or any automated test)
# does NOT discover user-level (~/.config/google-chrome/NativeMessagingHosts) registrations —
# only the system-wide path is reliably found regardless of which profile launched Chrome.
# Real day-to-day use of the default profile may not need this, but registering both costs
# nothing and removes an entire class of "works on my machine" failure.
if mkdir -p "$SYSTEM_NM_DIR" 2>/dev/null && [[ -w "$SYSTEM_NM_DIR" ]]; then
  manifest_json > "$SYSTEM_NM_MANIFEST"
  echo "Registered native messaging host (system-wide) at $SYSTEM_NM_MANIFEST"
elif command -v sudo >/dev/null 2>&1; then
  sudo mkdir -p "$SYSTEM_NM_DIR" && manifest_json | sudo tee "$SYSTEM_NM_MANIFEST" >/dev/null
  echo "Registered native messaging host (system-wide, via sudo) at $SYSTEM_NM_MANIFEST"
else
  echo "warning: could not write $SYSTEM_NM_MANIFEST (no write access, no sudo) — native" >&2
  echo "messaging may fail for any Chrome profile other than the default one." >&2
fi

echo "Extension ID (empirically discovered): $EXT_ID"
echo "Restart Chrome for it to pick up this registration."
