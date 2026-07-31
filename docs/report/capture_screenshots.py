#!/usr/bin/env python3
"""Dev-only helper: installs the real unpacked extension into a real headless Chrome via CDP
(same Extensions.loadUnpacked technique as test-pages/cdp_test.py — the DevTools Protocol command
chrome://extensions' "Load unpacked" button uses internally, since --load-extension does not
reliably install a Manifest V3 extension on this Chrome build), navigates to a real page from the
Phase 3 labelled dataset (already being served on :8877 by `make dataset-serve`), and screenshots
the rendered warning banner for use as report evidence — not a mockup, the actual DOM the real
extension produces against a real page.
"""
import base64
import json
import subprocess
import sys
import time

import requests
import websocket

DEBUG_PORT = 9433
EXT_DIR = "/home/analysis/browser-ai-sentinel/extension/dist"
PROFILE_DIR = "/tmp/bas-report-shot-profile"
TEST_URL = "http://127.0.0.1:8877/injected-00.html"
OUT_PATH = "assets/fig_9_1_banner.png"


def wait_for(fn, timeout=15, interval=0.5):
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = fn()
        if result:
            return result
        time.sleep(interval)
    raise RuntimeError(f"timed out waiting for {fn}")


def call(ws, msg_id, method, params=None):
    ws.send(json.dumps({"id": msg_id, "method": method, "params": params or {}}))
    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            resp = json.loads(ws.recv())
        except websocket.WebSocketTimeoutException:
            continue
        if resp.get("id") == msg_id:
            return resp


def _ok(url):
    try:
        return requests.get(url, timeout=1).ok
    except requests.RequestException:
        return False


def _find_page(port):
    targets = requests.get(f"http://127.0.0.1:{port}/json/list", timeout=2).json()
    pages = [t for t in targets if t["type"] == "page" and t.get("url") != "about:blank"]
    if not pages:
        pages = [t for t in targets if t["type"] == "page"]
    return pages[0] if pages else None


def main():
    proc = subprocess.Popen(
        [
            "google-chrome-stable", "--headless=new", "--disable-gpu", "--no-first-run",
            "--no-sandbox", "--no-default-browser-check", f"--user-data-dir={PROFILE_DIR}",
            f"--remote-debugging-port={DEBUG_PORT}", "--remote-allow-origins=*",
            "--window-size=1280,320", "about:blank",
        ],
        stdout=subprocess.DEVNULL, stderr=open("/tmp/bas-report-shot-chrome.log", "w"),
    )
    try:
        wait_for(lambda: requests.get(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=1).json()
                  if _ok(f"http://127.0.0.1:{DEBUG_PORT}/json/version") else None)
        version = requests.get(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=2).json()
        browser_ws = websocket.create_connection(version["webSocketDebuggerUrl"], timeout=10)
        browser_ws.settimeout(2)

        install = call(browser_ws, 1, "Extensions.loadUnpacked", {"path": EXT_DIR})
        if "error" in install:
            print("FAIL: Extensions.loadUnpacked error:", install["error"])
            sys.exit(1)
        print("Installed extension id:", install["result"]["id"])

        page_target = wait_for(lambda: _find_page(DEBUG_PORT))
        ws = websocket.create_connection(page_target["webSocketDebuggerUrl"], timeout=10)
        ws.settimeout(5)
        call(ws, 1, "Page.enable")
        call(ws, 2, "Page.navigate", {"url": TEST_URL})
        time.sleep(4)  # content scripts + native-messaging round trip

        banner = call(ws, 3, "Runtime.evaluate", {
            "expression": "document.getElementById('browser-ai-sentinel-banner')?.textContent ?? null",
            "returnByValue": True,
        })
        banner_text = banner["result"]["result"]["value"]
        print("Banner text:", banner_text)
        if not banner_text:
            print("FAIL: warning banner did not render")
            sys.exit(1)

        shot = call(ws, 4, "Page.captureScreenshot", {"format": "png"})
        with open(OUT_PATH, "wb") as f:
            f.write(base64.b64decode(shot["result"]["data"]))
        print(f"PASS: saved {OUT_PATH}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == "__main__":
    main()
