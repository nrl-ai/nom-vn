"""End-to-end smoke test of a running Nôm server.

Hits every public surface and reports a green/red matrix. Designed to
run against any deployment — install from PyPI, source clone,
container, etc. — by pointing it at the URL.

Usage::

    # Start a server somewhere
    nom serve --in-memory --port 8080 --no-browser &

    # Run the suite
    python scripts/e2e_smoke.py http://localhost:8080

    # With bearer-token auth
    NOM_AUTH_TOKEN=secret-xyz nom serve --in-memory --port 8080 --no-browser &
    python scripts/e2e_smoke.py http://localhost:8080 secret-xyz

Returns 0 on full pass, 1 on any failure. Tests covered:
  1. /api/health + version reflection
  2. /api/llm/backends — all 6 adapters listed
  3. /api/tools/* — diacritic restore/strip, tokenize word/sentence,
     normalize, detect, noise (incl. determinism)
  4. validation — 422 on empty / unknown values
  5. spaces — create + multipart upload + list + index + delete
  6. UI surface — / serves index.html with brand mark, /favicon.svg,
     /docs (Swagger), /redoc

For a separate persistence test (kill server, restart with same
data dir, verify state survives) see ``scripts/e2e_persistence.py``.
"""

from __future__ import annotations

import json
import sys
from urllib.error import HTTPError
from urllib.request import Request, urlopen


def _green(s: str) -> str:
    return f"\033[32m{s}\033[0m"


def _red(s: str) -> str:
    return f"\033[31m{s}\033[0m"


def _gray(s: str) -> str:
    return f"\033[2m{s}\033[0m"


class _Suite:
    def __init__(self, base: str, token: str | None = None) -> None:
        self.base = base.rstrip("/")
        self.token = token
        self.passed = 0
        self.failed: list[str] = []

    def _req(self, method: str, path: str, *, body=None, headers=None, timeout: float = 15.0):
        url = self.base + path
        h = {"accept": "application/json", **(headers or {})}
        if self.token:
            h.setdefault("Authorization", f"Bearer {self.token}")
        if body is not None and not isinstance(body, bytes):
            h.setdefault("content-type", "application/json")
            body = json.dumps(body).encode("utf-8")
        try:
            r = urlopen(Request(url, data=body, headers=h, method=method), timeout=timeout)
            raw = r.read()
            if not raw:
                return r.status, None
            if r.headers.get("Content-Type", "").startswith("application/json"):
                return r.status, json.loads(raw)
            return r.status, raw.decode("utf-8", "replace")
        except HTTPError as e:
            data = e.read()
            try:
                return e.code, json.loads(data)
            except Exception:
                return e.code, data.decode("utf-8", "replace")

    def get(self, path, **kw):
        return self._req("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self._req("POST", path, body=body, **kw)

    def delete(self, path, **kw):
        return self._req("DELETE", path, **kw)

    def expect(self, name: str, cond: bool, detail: str = "") -> None:
        if cond:
            self.passed += 1
            print(_green(f"  ✓ {name}"))
        else:
            self.failed.append(f"{name} — {detail}")
            print(_red(f"  ✗ {name} — {detail}"))

    def section(self, title: str) -> None:
        print(f"\n{_gray('═══')} {title} {_gray('═' * (60 - len(title)))}")

    def report(self) -> int:
        print(f"\n{_green(self.passed)} passed · {_red(len(self.failed))} failed")
        for f in self.failed:
            print(f"  {_red('x')} {f}")
        return 1 if self.failed else 0


def run(base: str, token: str | None = None) -> int:
    s = _Suite(base, token=token)

    s.section("1. health + version coherence")
    code, h = s.get("/api/health")
    s.expect("/api/health 200", code == 200, f"got {code}")
    s.expect("version starts with 0.2", h.get("version", "").startswith("0.2"))
    s.expect("auth_required reflected", isinstance(h.get("auth_required"), bool))

    s.section("2. /api/llm/backends probe")
    code, b = s.get("/api/llm/backends")
    s.expect("backends 200", code == 200)
    ids = {x["id"] for x in b.get("available", [])}
    for backend_id in (
        "ollama",
        "llamacpp",
        "llamacpp-python",
        "huggingface",
        "openai",
        "anthropic",
    ):
        s.expect(f"{backend_id} listed", backend_id in ids)

    s.section("3. stateless tools — happy path")
    cases = [
        (
            "diacritic restore (rule)",
            "/api/tools/diacritic/restore",
            {"text": "Hop dong nay duoc lap", "backend": "rule"},
            lambda r: "Hợp đồng" in r["restored"],
        ),
        (
            "diacritic strip",
            "/api/tools/diacritic/strip",
            {"text": "Hợp đồng số 02/HĐ"},
            lambda r: r["stripped"] == "Hop dong so 02/HD",
        ),
        (
            "tokenize word",
            "/api/tools/tokenize/word",
            {"text": "Hợp đồng số 02 được lập"},
            lambda r: r["n_compounds"] >= 1 and "Hợp đồng" in r["tokens"],
        ),
        (
            "tokenize sentence",
            "/api/tools/tokenize/sentence",
            {"text": "Tôi yêu. Bạn có?"},
            lambda r: r["n_sentences"] == 2,
        ),
        (
            "normalize NFC",
            "/api/tools/text/normalize",
            {"text": "Tôi yêu Việt Nam"},
            lambda r: r["is_nfc"] is True,
        ),
        (
            "detect VN (ASCII)",
            "/api/tools/text/detect",
            {"text": "Hop dong duoc lap"},
            lambda r: r["is_vietnamese"] is True and r["has_diacritics"] is False,
        ),
        (
            "detect VN (with diacritics)",
            "/api/tools/text/detect",
            {"text": "Hợp đồng"},
            lambda r: r["is_vietnamese"] is True and r["has_diacritics"] is True,
        ),
        (
            "noise apply (light, seed=42)",
            "/api/tools/noise/apply",
            {"text": "Tôi yêu Việt Nam", "preset": "light", "seed": 42},
            lambda r: r["preset"] == "light" and r["seed"] == 42,
        ),
    ]
    for name, path, body, check in cases:
        code, r = s.post(path, body)
        s.expect(name, code == 200 and check(r), repr(r)[:120])

    code, r1 = s.post(
        "/api/tools/noise/apply",
        {"text": "Tôi yêu Việt Nam", "preset": "heavy", "seed": 7},
    )
    code, r2 = s.post(
        "/api/tools/noise/apply",
        {"text": "Tôi yêu Việt Nam", "preset": "heavy", "seed": 7},
    )
    s.expect("noise determinism (same seed)", code == 200 and r1 == r2)

    s.section("4. validation — should 422")
    code, _ = s.post("/api/tools/diacritic/restore", {"text": ""})
    s.expect("empty text → 422", code == 422)
    code, _ = s.post("/api/tools/diacritic/restore", {"text": "x", "backend": "magic"})
    s.expect("unknown backend → 422", code == 422)
    code, _ = s.post("/api/tools/tokenize/word", {"text": "x", "fmt": "json"})
    s.expect("unknown fmt → 422", code == 422)
    code, _ = s.post("/api/tools/noise/apply", {"text": "x", "preset": "extreme"})
    s.expect("unknown noise preset → 422", code == 422)

    s.section("5. spaces lifecycle (CRUD + multipart)")
    code, sp = s.post("/api/spaces", {"name": "E2E test"})
    s.expect("create space → 201", code == 201)
    sid = sp["id"] if code == 201 else None

    if sid:
        boundary = "----nom-e2e-boundary"
        text_body = (
            "Hợp đồng số HD-E2E-001 ngày 2026-05-02. "
            "Tổng giá trị 1.500.000.000 đồng. Bên A là Công ty Test."
        )
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="file"; filename="d.txt"\r\n'
            f"Content-Type: text/plain; charset=utf-8\r\n\r\n"
            f"{text_body}\r\n"
            f"--{boundary}--\r\n"
        ).encode()
        h = {"Content-Type": f"multipart/form-data; boundary={boundary}"}
        if s.token:
            h["Authorization"] = f"Bearer {s.token}"
        r = urlopen(
            Request(
                f"{s.base}/api/spaces/{sid}/materials",
                data=body,
                headers=h,
                method="POST",
            ),
            timeout=15,
        )
        s.expect("upload material → 201", r.status == 201)

        code, mats = s.get(f"/api/spaces/{sid}/materials")
        s.expect("list materials → 1", code == 200 and len(mats) == 1)

        code, idx = s.post(f"/api/spaces/{sid}/index")
        s.expect("index space succeeds", code == 200 and idx["n_indexed"] >= 1)

        code, _ = s.delete(f"/api/spaces/{sid}")
        s.expect("delete space → 204", code == 204)

        code, _ = s.get(f"/api/spaces/{sid}")
        s.expect("deleted space → 404", code == 404)

    s.section("6. UI surface (bundled in wheel)")
    code, body = s.get("/")
    s.expect("/ → 200", code == 200)
    body_str = body if isinstance(body, str) else (body or "")
    s.expect("title contains Nôm", "Nôm" in body_str)
    code, _ = s.get("/favicon.svg")
    s.expect("/favicon.svg → 200", code == 200)
    code, _ = s.get("/docs")
    s.expect("/docs (Swagger) → 200", code == 200)
    code, _ = s.get("/redoc")
    s.expect("/redoc → 200", code == 200)

    return s.report()


if __name__ == "__main__":
    base = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8080"
    token = sys.argv[2] if len(sys.argv) > 2 else None
    sys.exit(run(base, token))
