#!/usr/bin/env bash
# Container entrypoint: creates the endpoint's OS user (the fake-employee identity — see
# db/schema.sql's endpoints table, distinguished by hostname+os_user), registers the native
# messaging host under that user with the deterministic key-derived extension ID (confirmed in
# Phase 1: Extensions.loadUnpacked always produces infjoghmhbkbhohajodjccgphpgejkip for this
# repo's manifest.json key, regardless of path — no discovery script needed here), then runs the
# daemon in the foreground as that user. driver.py is run separately via `docker exec` (see
# Makefile's endpoints-test target) once the daemon is up — keeps "bring the fleet up" and "run
# the test traffic" as two distinct, individually-retriable steps.
set -euo pipefail

: "${OS_USERNAME:?must set OS_USERNAME}"
: "${DAEMON_PORT:?must set DAEMON_PORT}"

EXT_ID="infjoghmhbkbhohajodjccgphpgejkip"

if ! id "$OS_USERNAME" >/dev/null 2>&1; then
  useradd -m -s /bin/bash "$OS_USERNAME"
fi
HOME_DIR="/home/$OS_USERNAME"

nm_manifest() {
  cat <<EOF
{
  "name": "com.browseraisentinel.nmhost",
  "description": "Browser AI Sentinel native messaging host",
  "path": "/usr/local/bin/nmhost",
  "type": "stdio",
  "allowed_origins": ["chrome-extension://${EXT_ID}/"]
}
EOF
}

NM_DIR="$HOME_DIR/.config/google-chrome/NativeMessagingHosts"
mkdir -p "$NM_DIR"
nm_manifest > "$NM_DIR/com.browseraisentinel.nmhost.json"
chown -R "$OS_USERNAME:$OS_USERNAME" "$HOME_DIR"

# ALSO register system-wide — the same gap found and fixed on the host in Phase 1
# (scripts/register-native-host.sh's comment has the full story): a Chrome profile launched with
# a custom --user-data-dir (which driver.py always uses) does not discover user-level
# NativeMessagingHosts registrations, only the system-wide path is reliably found. Missing this
# here is exactly what silently broke the first Phase 3 fleet run (0 rows reached the daemon
# despite driver.py reporting every page "visited" — Chrome was navigating fine, native messaging
# just never connected).
mkdir -p /etc/opt/chrome/native-messaging-hosts
nm_manifest > /etc/opt/chrome/native-messaging-hosts/com.browseraisentinel.nmhost.json

export DATABASE_URL="postgres://aisentinel:changeme-local-dev-only@127.0.0.1:5433/aisentinel?sslmode=disable"
export AI_ENGINE_URL="http://127.0.0.1:8100"
export LISTEN_ADDR="127.0.0.1:${DAEMON_PORT}"
# No real sensor logs inside this container (the host's own bas-zeek/bas-suricata cover the
# fleet's network traffic already, since it all transits the host under --network host) — point
# SENSOR_LOG_DIR somewhere that will just never exist, so the daemon's tailers idle harmlessly
# (tailFile retries on open failure every 2s, by design — see agent/internal/sensor/tail.go)
# instead of accidentally double-tailing the real host sensor logs from inside a container.
export SENSOR_LOG_DIR="/nonexistent-in-container"

exec sudo -u "$OS_USERNAME" --preserve-env=DATABASE_URL,AI_ENGINE_URL,LISTEN_ADDR,SENSOR_LOG_DIR \
  /usr/local/bin/daemon
