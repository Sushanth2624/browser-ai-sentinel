##! Browser AI Sentinel — standalone Zeek sensor script.
##!
##! Deliberately NOT loading capstone-1's local.zeek or touching its config — this is a fresh,
##! independent invocation of the same shared Zeek install (/opt/zeek), run via `zeek -C -i ens18
##! sensor/zeek/bas.zeek` (see deploy/bas-zeek.service). Only loads what this project needs:
##! JA3/JA4 TLS fingerprinting (zkg packages already installed system-wide by capstone-1's setup,
##! but these are just shared Zeek script libraries — reusable by any invocation).
##!
##! The `-C` flag is REQUIRED on this VM: ens18 is a virtio NIC with checksum offloading, so Zeek
##! sees "invalid" TCP checksums on every outbound packet and silently drops them without -C —
##! confirmed empirically (no ssl.log at all without it, despite conn.log/dns.log working fine).

@load ja3
@load ja4

# One continuously-growing ssl.log rather than hourly rotation — the Go daemon's tailer
# (agent/internal/sensor/zeek.go) tracks a byte offset into a single file; handling rotation is
# unnecessary complexity for Phase 2 and can be revisited if log volume ever demands it.
redef Log::default_rotation_interval = 0secs;

# JSON lines are trivial for the Go tailer to parse; ASCII/TSV would need a schema-aware reader.
redef LogAscii::use_json = T;
