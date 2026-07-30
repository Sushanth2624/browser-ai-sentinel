#!/usr/bin/env bash
# Idempotent install for the sensor services (Zeek x2 — ens18 + lo, Suricata watches both in one
# process). Root-only (packet capture). Mirrors
# the install-*.sh pattern used elsewhere on this VM: copy unit -> daemon-reload -> enable ->
# restart -> poll for active, rather than assuming success.
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "error: must run as root (packet capture needs it)" >&2
  exit 1
fi

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

for svc in bas-zeek bas-zeek-lo bas-suricata; do
  cp "$REPO_ROOT/deploy/${svc}.service" "/etc/systemd/system/${svc}.service"
done

systemctl daemon-reload
for svc in bas-zeek bas-zeek-lo bas-suricata; do
  systemctl enable "$svc" >/dev/null
  systemctl restart "$svc"
done

sleep 2
ok=true
for svc in bas-zeek bas-zeek-lo bas-suricata; do
  if systemctl is-active --quiet "$svc"; then
    echo "$svc: active"
  else
    echo "$svc: NOT active — check 'journalctl -u $svc -n 50'" >&2
    ok=false
  fi
done

$ok || exit 1
echo "All sensors running. Logs: $REPO_ROOT/sensor/logs/{zeek,zeek-lo,suricata}/"
