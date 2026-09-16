#!/usr/bin/env python3
"""
Headless UI verification for the WCP dashboard.

Drives Chrome over the DevTools Protocol (no Playwright/puppeteer needed) to
prove that every profile x theme route actually RENDERS content in a real
browser, rather than merely returning HTTP 200.

Catches the failure mode that HTTP checks miss entirely:
  - a renderer throwing, leaving the tab blank
  - `undefined` / `NaN` / `[object Object]` leaking into the UI because a
    renderer referenced a field the collector never wrote
  - console errors during render

Usage: .venv/bin/python scripts/verify_ui.py [--port 9010]
"""

from __future__ import annotations

import argparse
import json
import shutil
import socket
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

try:
    import websocket  # websocket-client
except ImportError:
    print("ERROR: websocket-client is required (.venv/bin/python -m pip install websocket-client)")
    raise SystemExit(3)

REPO = Path(__file__).resolve().parents[1]

THEMES = ["population", "housing", "commute", "land-use", "economy",
          "employment", "transit", "property", "methods"]

# Tab -> acceptable markers. A tab passes if ANY marker is present. The second
# entry for transit/property is the documented empty-state heading, which is the
# correct rendering for a village that has no rail station or no roll record.
THEME_MARKERS = {
    "population": ["Age profile"],
    "housing": ["Occupancy and tenure"],
    "commute": ["How residents get to work"],
    "land-use": ["Assessment parcel acres"],
    "economy": ["Regional inflation context"],
    "employment": ["Covered employment and wages"],
    "transit": ["Scheduled weekday station calls", "No Metro-North station inside"],
    "property": ["Parcels by broad use class", "No ORPTS assessment-roll record matched"],
    "methods": ["Requirements coverage"],
}

BAD_TOKENS = ["undefined", "NaN", "[object Object]", "null%"]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Chrome:
    def __init__(self, port: int):
        self.port = port
        binary = next((b for b in ("google-chrome", "google-chrome-stable",
                                   "chromium-browser", "chromium")
                       if shutil.which(b)), None)
        if not binary:
            raise RuntimeError("no Chrome/Chromium binary found")
        self.proc = subprocess.Popen(
            [binary, "--headless=new", "--no-sandbox", "--disable-gpu",
             "--disable-dev-shm-usage", f"--remote-debugging-port={port}",
             "--remote-allow-origins=*",
             "--user-data-dir=/tmp/wcp-verify-profile", "about:blank"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.ws = None
        self.msg_id = 0
        self._wait_for_devtools()

    def _wait_for_devtools(self, timeout: float = 30) -> None:
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                    f"http://127.0.0.1:{self.port}/json/version", timeout=2
                ) as resp:
                    if resp.status == 200:
                        return
            except Exception:
                time.sleep(0.4)
        raise RuntimeError("Chrome DevTools endpoint never became ready")

    def connect(self, url: str) -> None:
        # Newer Chrome requires PUT for /json/new; GET returns 405.
        request = urllib.request.Request(
            f"http://127.0.0.1:{self.port}/json/new?{urllib.parse.quote(url, safe='')}",
            method="PUT",
        )
        with urllib.request.urlopen(request, timeout=10) as resp:
            target = json.load(resp)
        self.ws = websocket.create_connection(target["webSocketDebuggerUrl"],
                                              timeout=30)
        self.send("Runtime.enable")
        self.send("Log.enable")
        self.send("Page.enable")

    def send(self, method: str, **params):
        self.msg_id += 1
        mid = self.msg_id
        self.ws.send(json.dumps({"id": mid, "method": method, "params": params}))
        while True:
            raw = json.loads(self.ws.recv())
            if raw.get("id") == mid:
                if "error" in raw:
                    raise RuntimeError(f"{method}: {raw['error']}")
                return raw.get("result", {})

    def evaluate(self, expression: str):
        result = self.send("Runtime.evaluate", expression=expression,
                           returnByValue=True, awaitPromise=True)
        if "exceptionDetails" in result:
            raise RuntimeError(f"JS exception: {result['exceptionDetails']}")
        return result.get("result", {}).get("value")

    def drain_console(self) -> list[str]:
        """Collect queued console/log messages without blocking."""
        out = []
        self.ws.settimeout(0.15)
        try:
            while True:
                raw = json.loads(self.ws.recv())
                method = raw.get("method")
                if method == "Runtime.exceptionThrown":
                    detail = raw["params"]["exceptionDetails"]
                    out.append("EXCEPTION: " + str(detail.get("text")))
                elif method == "Runtime.consoleAPICalled":
                    if raw["params"]["type"] == "error":
                        args = [str(a.get("value", "")) for a in raw["params"]["args"]]
                        out.append("console.error: " + " ".join(args))
                elif method == "Log.entryAdded":
                    entry = raw["params"]["entry"]
                    if entry.get("level") == "error":
                        out.append("log: " + str(entry.get("text")))
        except Exception:
            pass
        finally:
            self.ws.settimeout(30)
        return out

    def close(self) -> None:
        try:
            if self.ws:
                self.ws.close()
        except Exception:
            pass
        self.proc.terminate()
        try:
            self.proc.wait(timeout=10)
        except Exception:
            self.proc.kill()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=9010)
    parser.add_argument("--profiles", default="westchester-county,yonkers,ardsley")
    args = parser.parse_args()

    base = f"http://localhost:{args.port}/"
    port = free_port()
    chrome = Chrome(port)
    failures: list[str] = []
    checks = 0

    try:
        chrome.connect(base)

        # Wait for the app to reach its ready state.
        info: dict = {}
        deadline = time.time() + 40
        while time.time() < deadline:
            state = chrome.evaluate(
                "JSON.stringify({s:document.getElementById('status')?.hidden,"
                "d:document.getElementById('dashboard')?.hidden,"
                "t:document.querySelectorAll('#themeTabs button').length})"
            )
            info = json.loads(state) if state else {}
            if info.get("s") is True and info.get("d") is False:
                break
            time.sleep(0.5)
        else:
            failures.append("dashboard never reached ready state")

        print(f"ready; tabs={info.get('t')}")
        if info.get("t") != len(THEMES):
            failures.append(f"expected {len(THEMES)} tabs, found {info.get('t')}")

        # Did the optional external datasets load at all?
        loaded = json.loads(chrome.evaluate(
            "JSON.stringify(window.__wcpLoaded||{})") or "{}")

        for profile_id in [p.strip() for p in args.profiles.split(",") if p.strip()]:
            for theme in THEMES:
                checks += 1
                chrome.evaluate(
                    f"location.hash = '#/profile/{profile_id}/theme/{theme}'"
                )
                time.sleep(0.28)
                text = chrome.evaluate(
                    "document.getElementById('themeContent')?.innerText || ''"
                ) or ""
                markers = THEME_MARKERS[theme]
                if not any(m in text for m in markers):
                    failures.append(
                        f"{profile_id}/{theme}: none of {markers!r} rendered "
                        f"(len={len(text)})"
                    )
                for bad in BAD_TOKENS:
                    if bad in text:
                        failures.append(
                            f"{profile_id}/{theme}: bad token {bad!r} in rendered output"
                        )
                if theme in ("employment", "transit", "property") and text.strip():
                    print(f"  {profile_id:<22} {theme:<11} rendered {len(text):>5} chars")

        for msg in chrome.drain_console():
            failures.append(f"console: {msg}")

    finally:
        chrome.close()

    print(f"\n{checks} route/theme render checks")
    if failures:
        print(f"\nFAILURES ({len(failures)}):")
        for f in failures:
            print("  -", f)
        return 1
    print("all render checks passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
