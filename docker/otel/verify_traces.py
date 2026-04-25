"""Smoke-verify that the OTel-instrumented Nôm server emits spans
visible to a running Jaeger.

Usage::

    docker compose -f docker/otel/docker-compose.yml up -d
    # in another terminal, with OTEL_* env vars exported:
    nom serve --in-memory --port 8090

    python docker/otel/verify_traces.py

Exit code 0 = traces landed in Jaeger. Non-zero = something's wrong.

Pure stdlib — no extra deps.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request

NOM_URL = os.environ.get("NOM_URL", "http://127.0.0.1:8090")
JAEGER_URL = os.environ.get("JAEGER_URL", "http://127.0.0.1:16686")
SERVICE = os.environ.get("OTEL_SERVICE_NAME", "nom-chat")


def _http(method: str, url: str, body: bytes | None = None, ctype: str | None = None) -> bytes:
    headers = {"Accept": "application/json"}
    if ctype:
        headers["Content-Type"] = ctype
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def _post_json(url: str, body: dict) -> dict:
    return json.loads(_http("POST", url, json.dumps(body).encode(), "application/json"))


def _get_json(url: str) -> dict:
    return json.loads(_http("GET", url))


def _step(label: str, fn) -> None:
    sys.stdout.write(f"→ {label} ... ")
    sys.stdout.flush()
    fn()
    print("ok")


def main() -> int:
    # Reach both services up front so we fail fast on misconfig.
    try:
        _http("GET", f"{NOM_URL}/api/health")
    except urllib.error.URLError as e:
        print(f"✗ nom server at {NOM_URL} not reachable: {e}", file=sys.stderr)
        return 2
    try:
        _http("GET", f"{JAEGER_URL}/api/services")
    except urllib.error.URLError as e:
        print(f"✗ jaeger at {JAEGER_URL} not reachable: {e}", file=sys.stderr)
        return 2

    # Drive a few requests so traces land in Jaeger.
    _step("create space", lambda: _post_json(f"{NOM_URL}/api/spaces", {"name": "OTel verify"}))
    _step("list spaces (x3)", lambda: [_get_json(f"{NOM_URL}/api/spaces") for _ in range(3)])
    _step("hit /api/health (x3)", lambda: [_get_json(f"{NOM_URL}/api/health") for _ in range(3)])

    # Jaeger flushes every 1s by default; give it a beat.
    time.sleep(2)

    # Look up our service in Jaeger and confirm at least one trace landed.
    services = _get_json(f"{JAEGER_URL}/api/services").get("data", [])
    if SERVICE not in services:
        print(f"✗ service {SERVICE!r} not found in Jaeger. Known: {services}", file=sys.stderr)
        print("  → check OTEL_SERVICE_NAME and OTEL_EXPORTER_OTLP_ENDPOINT", file=sys.stderr)
        return 1
    print(f"✓ service registered: {SERVICE}")

    traces = _get_json(f"{JAEGER_URL}/api/traces?service={SERVICE}&limit=10").get("data", [])
    if not traces:
        print(f"✗ service {SERVICE!r} reported but no traces yet", file=sys.stderr)
        return 1
    print(f"✓ {len(traces)} trace(s) visible in Jaeger")
    print(f"  open: {JAEGER_URL}/search?service={SERVICE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
