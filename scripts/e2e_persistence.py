"""Persistence test orchestrator — drives two server boots in sequence.

Companion to ``scripts/e2e_smoke.py``. Where ``e2e_smoke`` hits a
running server, this one starts and stops servers itself to prove
that ``--data-dir`` survives a process restart.

Flow:
  1. Clean data dir
  2. Start ``nom serve --data-dir <DATA>`` (boot A)
  3. Health check
  4. Create space + upload material
  5. Kill A, start fresh with same data dir (boot B)
  6. List spaces — assert created space + material survived

Usage::

    python scripts/e2e_persistence.py [--data-dir /tmp/nom-e2e-data] [--port 8088]

Returns 0 on full pass, 1 otherwise.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen


def _http(base: str, method: str, path: str, *, body=None, timeout: float = 15.0):
    h = {"accept": "application/json"}
    if body is not None and not isinstance(body, bytes):
        h.setdefault("content-type", "application/json")
        body = json.dumps(body).encode("utf-8")
    r = urlopen(Request(base + path, data=body, headers=h, method=method), timeout=timeout)
    raw = r.read()
    return r.status, json.loads(raw) if raw else None


def _wait_up(base: str, *, timeout: float = 25.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(f"{base}/api/health", timeout=2) as r:
                if r.status == 200:
                    return True
        except (URLError, ConnectionError, TimeoutError):
            time.sleep(0.5)
    return False


def _start(data: Path, port: int) -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        ["nom", "serve", "--data-dir", str(data), "--port", str(port), "--no-browser"],
        env={**os.environ, "NOM_LLM_MODEL": os.environ.get("NOM_LLM_MODEL", "qwen3:1.7b")},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )


def _stop(proc: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(ProcessLookupError):
        os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
    with contextlib.suppress(subprocess.TimeoutExpired):
        proc.wait(timeout=5)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default="/tmp/nom-e2e-data", type=Path)
    parser.add_argument("--port", default=8088, type=int)
    parser.add_argument(
        "--sample",
        default="benchmarks/data/diacritic_eval_v0.txt",
        type=Path,
        help="File to upload during boot A.",
    )
    args = parser.parse_args(argv)

    base = f"http://127.0.0.1:{args.port}"

    print("=== Phase 3: SQLite persistence ===")
    if args.data_dir.exists():
        shutil.rmtree(args.data_dir)

    if not args.sample.is_file():
        print(f"  ! sample file not found: {args.sample}", file=sys.stderr)
        return 1

    # Boot A
    print("3a. boot A — create space + upload")
    a = _start(args.data_dir, args.port)
    try:
        if not _wait_up(base):
            print("  ✗ server did not come up", file=sys.stderr)
            return 1

        _, h = _http(base, "GET", "/api/health")
        print(f"  ✓ health: store={h['store']} version={h['version']}")
        if h["store"] != "SqliteStore":
            print(f"  ✗ expected SqliteStore, got {h['store']}", file=sys.stderr)
            return 1

        code, sp = _http(base, "POST", "/api/spaces", body={"name": "PersistedSpace"})
        if code != 201:
            print(f"  ✗ create space failed: {code}", file=sys.stderr)
            return 1
        sid = sp["id"]
        print(f"  ✓ created space {sid}")

        boundary = "----nomboundary"
        body = (
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="t.txt"\r\n'
                f"Content-Type: text/plain\r\n\r\n"
            ).encode()
            + args.sample.read_bytes()
            + f"\r\n--{boundary}--\r\n".encode()
        )
        with urlopen(
            Request(
                f"{base}/api/spaces/{sid}/materials",
                data=body,
                headers={"content-type": f"multipart/form-data; boundary={boundary}"},
                method="POST",
            ),
            timeout=20,
        ) as r:
            mat = json.loads(r.read())
        print(f"  ✓ uploaded {mat['n_bytes']} bytes")

        _, mats = _http(base, "GET", f"/api/spaces/{sid}/materials")
        print(f"  ✓ list before restart: {len(mats)} materials")
    finally:
        _stop(a)
        time.sleep(1)

    print("3b. boot B — relaunch with same data-dir")
    b = _start(args.data_dir, args.port)
    try:
        if not _wait_up(base):
            print("  ✗ server B did not come up", file=sys.stderr)
            return 1

        _, spaces = _http(base, "GET", "/api/spaces")
        print(f"  ✓ {len(spaces)} space(s) after restart:")
        for s in spaces:
            print(f"      · {s['name']:30} id={s['id'][:10]}…  {s['n_materials']} materials")

        match = next((s for s in spaces if s["name"] == "PersistedSpace"), None)
        if not match:
            print("  ✗ PersistedSpace did not survive restart", file=sys.stderr)
            return 1
        if match["n_materials"] != 1:
            print(f"  ✗ expected 1 material, got {match['n_materials']}", file=sys.stderr)
            return 1
        print("  ✓ PersistedSpace + material survived restart")
    finally:
        _stop(b)

    print("\n  data dir layout:")
    for p in sorted(args.data_dir.iterdir()):
        size = p.stat().st_size if p.is_file() else "<dir>"
        print(f"    {p.name:30} {size}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
