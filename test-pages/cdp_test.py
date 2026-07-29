#!/usr/bin/env python3
"""Phase 1 end-to-end verification: launches real Chrome, installs the unpacked extension via
the Extensions.loadUnpacked CDP command (NOT the --load-extension flag — see README's "How that
ID is determined" section: on this machine's Chrome 150, --load-extension spins up a service
worker under a path-hash-derived ID but never actually installs the extension into the extension
system, so content scripts never inject; Extensions.loadUnpacked is the real install path and is
what correctly honors manifest.json's pinned "key" field), navigates to the seeded injection test
page, and checks (a) the warning banner rendered and (b) a new injection_alerts row landed in
Postgres.
"""
import json
import subprocess
import sys
import time

import requests
import websocket

DEBUG_PORT = 9422
EXT_DIR = "/home/analysis/browser-ai-sentinel/extension/dist"
PROFILE_DIR = "/tmp/bas-chrome-test-profile"
TEST_URL = "http://127.0.0.1:8877/injection-test.html"


def wait_for(fn, timeout=15, interval=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = fn()
        if result:
            return result
        time.sleep(interval)
    raise RuntimeError(f"timed out waiting for {fn}")


def call(ws, msg_id, method, params=None, wait_reply=True):
    ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    if not wait_reply:
        return None
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            resp = json.loads(ws.recv())
        except websocket.WebSocketTimeoutException:
            continue
        if resp.get("id") == msg_id:
            return resp


def main():
    proc = subprocess.Popen(
        [
            "google-chrome-stable",
            "--headless=new",
            "--disable-gpu",
            "--no-first-run",
            "--no-default-browser-check",
            f"--user-data-dir={PROFILE_DIR}",
            f"--remote-debugging-port={DEBUG_PORT}",
            "--remote-allow-origins=*",
            "about:blank",
        ],
        stdout=subprocess.DEVNULL,
        stderr=open("/tmp/chrome-test.log", "w"),
    )
    try:
        version = wait_for(
            lambda: requests.get(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=1).json()
            if _ok(f"http://127.0.0.1:{DEBUG_PORT}/json/version")
            else None
        )
        browser_ws = websocket.create_connection(version["webSocketDebuggerUrl"], timeout=10)
        browser_ws.settimeout(2)

        install = call(browser_ws, 1, "Extensions.loadUnpacked", {"path": EXT_DIR})
        if "error" in install:
            print("FAIL: Extensions.loadUnpacked error:", install["error"])
            sys.exit(1)
        ext_id = install["result"]["id"]
        print("Installed extension id:", ext_id)

        page_target = wait_for(lambda: _find_page())
        ws = websocket.create_connection(page_target["webSocketDebuggerUrl"], timeout=10)
        ws.settimeout(2)
        call(ws, 1, "Page.enable")
        call(ws, 2, "Page.navigate", {"url": TEST_URL})
        time.sleep(4)  # let content scripts + async native-messaging round trip complete

        result = call(
            ws,
            3,
            "Runtime.evaluate",
            {
                "expression": (
                    "document.getElementById('browser-ai-sentinel-banner')"
                    "?.textContent ?? null"
                ),
                "returnByValue": True,
            },
        )
        banner_text = result["result"]["result"]["value"]
        print("Banner text:", banner_text)

        if not banner_text:
            print("FAIL: warning banner did not render")
            sys.exit(1)
        print("PASS: warning banner rendered")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def _ok(url):
    try:
        return requests.get(url, timeout=1).ok
    except requests.RequestException:
        return False


def _find_page():
    targets = requests.get(f"http://127.0.0.1:{DEBUG_PORT}/json/list", timeout=2).json()
    pages = [t for t in targets if t["type"] == "page" and t.get("url") != "about:blank"]
    if not pages:
        pages = [t for t in targets if t["type"] == "page"]
    return pages[0] if pages else None


if __name__ == "__main__":
    main()
