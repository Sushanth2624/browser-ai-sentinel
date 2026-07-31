#!/usr/bin/env python3
"""Dev-only helper: screenshot the running dashboard for a visual sanity check (not part of the
shipped repo's runtime, just a verification tool — same headless-Chrome-via-CDP technique used
throughout this project's testing)."""
import json
import subprocess
import time

import requests
import websocket

DEBUG_PORT = 9455

proc = subprocess.Popen(
    [
        "google-chrome-stable", "--headless=new", "--disable-gpu", "--no-first-run",
        "--no-sandbox", "--no-default-browser-check", "--user-data-dir=/tmp/dash-shot-profile",
        f"--remote-debugging-port={DEBUG_PORT}", "--remote-allow-origins=*",
        "--window-size=1280,1400", "http://127.0.0.1:3000/",
    ],
    stdout=subprocess.DEVNULL, stderr=open("/tmp/dash-shot-chrome.log", "w"),
)
try:
    version = None
    for _ in range(30):
        try:
            r = requests.get(f"http://127.0.0.1:{DEBUG_PORT}/json/version", timeout=1)
            if r.ok:
                version = r.json()
                break
        except Exception:
            pass
        time.sleep(0.5)

    targets = requests.get(f"http://127.0.0.1:{DEBUG_PORT}/json/list").json()
    page = [t for t in targets if t["type"] == "page"][0]
    ws = websocket.create_connection(page["webSocketDebuggerUrl"], timeout=10)
    ws.settimeout(5)

    def call(mid, method, params=None):
        ws.send(json.dumps({"id": mid, "method": method, "params": params or {}}))
        while True:
            resp = json.loads(ws.recv())
            if resp.get("id") == mid:
                return resp

    time.sleep(3)  # let React render + first data fetch complete
    metrics = call(1, "Page.getLayoutMetrics")
    height = int(metrics["result"]["cssContentSize"]["height"])
    call(2, "Emulation.setDeviceMetricsOverride", {"width": 1280, "height": min(height, 3000), "deviceScaleFactor": 1, "mobile": False})
    res = call(3, "Page.captureScreenshot", {"format": "png", "captureBeyondViewport": True})
    import base64
    with open("/tmp/dashboard-screenshot.png", "wb") as f:
        f.write(base64.b64decode(res["result"]["data"]))
    print("saved /tmp/dashboard-screenshot.png")
finally:
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
