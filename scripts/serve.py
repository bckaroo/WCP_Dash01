#!/usr/bin/env python3
"""Serve the static dashboard using the project port source of truth."""
from __future__ import annotations

import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]


def parse_port(value: str, source: str) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(f"SERVICE_PORT from {source} must be an integer") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError(f"SERVICE_PORT from {source} must be between 1 and 65535")
    return port


def configured_port() -> int:
    environment_value = os.environ.get("SERVICE_PORT")
    if environment_value:
        return parse_port(environment_value, "environment")
    env_file = ROOT / ".env.PORT"
    if not env_file.exists():
        raise RuntimeError("SERVICE_PORT is missing and .env.PORT does not exist")
    values = {}
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            if "=" not in line:
                raise RuntimeError(f"Malformed line in {env_file}: expected KEY=VALUE")
            key, value = line.split("=", 1)
            values[key.strip()] = value.split("#", 1)[0].strip()
    value = values.get("SERVICE_PORT")
    if value is None:
        raise RuntimeError("SERVICE_PORT is missing from environment and .env.PORT")
    return parse_port(value, str(env_file))


def should_disable_cache(request_target: str) -> bool:
    """Return whether a prototype asset should be revalidated by browsers."""
    path = urlsplit(request_target).path
    return path == "/" or path.endswith((".html", ".css", ".js", ".json", ".geojson"))


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def do_GET(self):
        if self.path == "/healthz":
            payload = b'{"status":"ok","service":"wcp-dashboard"}\n'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        super().do_GET()

    def end_headers(self):
        # This is a working prototype: force revalidation so browser QA and
        # stakeholder reviews do not retain stale HTML, CSS, JS, or data.
        if should_disable_cache(self.path):
            self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        super().end_headers()


if __name__ == "__main__":
    port = configured_port()
    print(f"WCP Community Profiles: http://localhost:{port}", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), Handler).serve_forever()
