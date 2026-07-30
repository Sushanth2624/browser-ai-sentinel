#!/usr/bin/env python3
"""Phase 3 endpoint driver — extends test-pages/cdp_test.py's proven pattern (real Chrome, real
extension installed via the Extensions.loadUnpacked CDP command, NOT --load-extension, which
Phase 1 established doesn't actually work on this Chrome build) to drive one "employee" endpoint
through a battery of real traffic:

  1. Every page in the labeled injection dataset (eval/dataset/) — exercises the real DOM scanner
     end to end, for every endpoint, so the A/B/C eval in eval/evaluate.py has full coverage.
  2. Known AI domains' public pages — exercises real platform ID.
  3. (BEHAVIOR_PROFILE=shadow_ai only) the two mock "unknown AI" endpoints (sensor/mock-ai) via
     Chrome's --host-resolver-rules flag (maps the fake hostnames to 127.0.0.1 without touching
     /etc/hosts) — exercises shadow-AI clustering.
  4. (BEHAVIOR_PROFILE=risky only) the same safe DLP-test pattern manually verified in Phase 1's
     README: fetch() with synthetic PII to a nonexistent path on a real AI domain.

Run via `docker exec` against an already-running endpoint container (see Makefile's
endpoints-test target) — the container's entrypoint.sh already has the daemon running as the
right OS user; this script just needs to launch Chrome as that same user.
"""
import json
import os
import subprocess
import sys
import time

import requests
import websocket

DEBUG_PORT = int(os.environ.get("CHROME_DEBUG_PORT", "9222"))
EXT_DIR = "/opt/browser-ai-sentinel/extension"
PROFILE_DIR = "/tmp/chrome-profile"
DATASET_BASE_URL = os.environ.get("DATASET_BASE_URL", "http://127.0.0.1:8877")
BEHAVIOR_PROFILE = os.environ.get("BEHAVIOR_PROFILE", "normal")
ENDPOINT_NAME = os.environ.get("ENDPOINT_NAME", "unknown-endpoint")

KNOWN_AI_PAGES = ["https://claude.ai/", "https://chatgpt.com/"]
MOCK_AI_TARGETS = [
    ("shadowmail-ai.internal", 8543),
    ("quicknotes-ai.internal", 8544),
]


def call(ws, msg_id, method, params=None):
    ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    deadline = time.time() + 15
    while time.time() < deadline:
        try:
            resp = json.loads(ws.recv())
        except websocket.WebSocketTimeoutException:
            continue
        if resp.get("id") == msg_id:
            return resp
    raise TimeoutError(f"no reply to {method}")


def wait_for(fn, timeout=15, interval=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = fn()
        if result:
            return result
        time.sleep(interval)
    raise RuntimeError(f"timed out waiting for {fn}")


def launch_chrome(extra_host_rules=None):
    args = [
        "google-chrome-stable",
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--no-sandbox",  # standard for containerized headless Chrome (no setuid sandbox helper)
        "--disable-dev-shm-usage",  # avoid Docker's small default /dev/shm crashing Chrome
        f"--user-data-dir={PROFILE_DIR}",
        f"--remote-debugging-port={DEBUG_PORT}",
        "--remote-allow-origins=*",
    ]
    if extra_host_rules:
        args.append(f"--host-resolver-rules={extra_host_rules}")
    args.append("about:blank")
    # nmhost (spawned by Chrome as a child process, inheriting Chrome's environment) defaults to
    # port 8090, but each container's own daemon listens on its assigned DAEMON_PORT
    # (8091-8094 — see docker-compose.yml) since they share the host's network namespace under
    # --network host. Without this, nmhost silently tries to reach a daemon that doesn't exist in
    # this container at all — exactly what caused the first Phase 3 fleet run to log 0 rows
    # despite every page reporting a successful visit.
    daemon_port = os.environ["DAEMON_PORT"]
    env = {**os.environ, "DAEMON_NM_URL": f"http://127.0.0.1:{daemon_port}/nm"}
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=open("/tmp/chrome.log", "w"), env=env)


def get_version():
    def _try():
        try:
            r = requests.get(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=1)
            return r.json() if r.ok else None
        except requests.RequestException:
            return None
    return wait_for(_try, timeout=20)


def get_page_target():
    def _try():
        targets = requests.get(f"http://127.0.0.1:{DEBUG_PORT}/json/list", timeout=2).json()
        pages = [t for t in targets if t["type"] == "page"]
        return pages[0] if pages else None
    return wait_for(_try, timeout=15)


def visit(page_ws, url, wait_s=1.5):
    call(page_ws, 1, "Page.navigate", {"url": url})
    time.sleep(wait_s)


def run_dlp_test(page_ws):
    """Same safe pattern as Phase 1's manually-verified README instructions: a fetch with
    synthetic PII to a nonexistent same-origin path on a real AI domain — 404s harmlessly, no
    real data reaches anyone. Exercises the approval-gate flow end to end."""
    call(page_ws, 1, "Page.navigate", {"url": "https://claude.ai/"})
    time.sleep(2)
    call(page_ws, 2, "Runtime.evaluate", {
        "expression": (
            "fetch('/bas-phase3-test-endpoint', {method:'POST', "
            "body:'contact me at test@example.com, card 4111 1111 1111 1111'})"
            ".catch(e => e.message)"
        ),
    })
    time.sleep(3)  # approval flow: ai-engine classify + (auto-deny after timeout if unattended)


def main():
    print(f"[{ENDPOINT_NAME}] profile={BEHAVIOR_PROFILE}")

    host_rules = None
    if BEHAVIOR_PROFILE == "shadow_ai":
        maps = ",".join(f"MAP {name} 127.0.0.1" for name, _ in MOCK_AI_TARGETS)
        host_rules = maps

    proc = launch_chrome(extra_host_rules=host_rules)
    try:
        version = get_version()
        browser_ws = websocket.create_connection(version["webSocketDebuggerUrl"], timeout=10)
        browser_ws.settimeout(3)
        install = call(browser_ws, 1, "Extensions.loadUnpacked", {"path": EXT_DIR})
        if "error" in install:
            print("FATAL: extension install failed:", install["error"])
            sys.exit(1)
        print(f"[{ENDPOINT_NAME}] extension installed: {install['result']['id']}")

        page = get_page_target()
        page_ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)
        page_ws.settimeout(3)
        call(page_ws, 1, "Page.enable")
        call(page_ws, 2, "Runtime.enable")

        manifest = json.load(open("/opt/browser-ai-sentinel/eval-dataset/manifest.json"))
        print(f"[{ENDPOINT_NAME}] visiting {len(manifest)} dataset pages")
        for i, row in enumerate(manifest):
            visit(page_ws, f"{DATASET_BASE_URL}/{row['filename']}", wait_s=1.2)
            if i % 10 == 0:
                print(f"[{ENDPOINT_NAME}]   {i}/{len(manifest)}")

        print(f"[{ENDPOINT_NAME}] visiting known AI domains")
        for url in KNOWN_AI_PAGES:
            visit(page_ws, url, wait_s=2.0)

        if BEHAVIOR_PROFILE == "shadow_ai":
            print(f"[{ENDPOINT_NAME}] visiting mock AI endpoints")
            for name, port in MOCK_AI_TARGETS:
                visit(page_ws, f"https://{name}:{port}/", wait_s=2.0)

        if BEHAVIOR_PROFILE == "risky":
            print(f"[{ENDPOINT_NAME}] running DLP test")
            run_dlp_test(page_ws)

        print(f"[{ENDPOINT_NAME}] done")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
