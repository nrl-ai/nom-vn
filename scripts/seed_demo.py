"""Seed a running Nôm server with representative VN demo spaces.

Pulls from `benchmarks/data/` (and `benchmarks/data/office_vi/` for the
synthetic Office fixtures) and uploads them via the FastAPI HTTP API
of a server already running at ``--url``.

Usage::

    nom serve --in-memory &        # in another terminal
    python scripts/seed_demo.py    # populates the running server

Idempotent: existing spaces with the same names are skipped (so
re-running never duplicates content).

The demo spaces are picked to exhibit different document types so
screenshots cover the breadth of the parser pipeline:

- "Pháp luật — Hiến pháp & Tuyên ngôn"  (text)
- "Văn học — Truyện Kiều"               (text — classical literature)
- "Bách khoa — Việt Nam"                (long-form Wikipedia)
- "Hợp đồng & Báo cáo (Office)"          (DOCX + XLSX + PPTX)
- "Hình ảnh — OCR Vietnamese"           (PNG via Tesseract)
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "benchmarks" / "data"


def _post_json(url: str, body: dict) -> dict:
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def _get_json(url: str) -> object:
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def _post_multipart(url: str, file_path: Path, name: str | None = None) -> dict:
    """Hand-rolled multipart upload — avoids requests / httpx dep."""
    boundary = "----nom-seed-boundary-2026"
    parts = []
    parts.append(f"--{boundary}".encode())
    fname = name or file_path.name
    parts.append(
        f'Content-Disposition: form-data; name="file"; filename="{fname}"'.encode(),
    )
    parts.append(b"Content-Type: application/octet-stream")
    parts.append(b"")
    parts.append(file_path.read_bytes())
    parts.append(f"--{boundary}".encode())
    parts.append(b'Content-Disposition: form-data; name="name"')
    parts.append(b"")
    parts.append(fname.encode("utf-8"))
    parts.append(f"--{boundary}--".encode())
    body = b"\r\n".join(parts) + b"\r\n"
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read().decode("utf-8"))


def _create_space(base: str, name: str) -> dict:
    return _post_json(f"{base}/api/spaces", {"name": name})


def _index(base: str, sid: str) -> dict:
    return _post_json(f"{base}/api/spaces/{sid}/index", {})


# ---------------------------------------------------------------------------
# Demo space recipes — each returns a list of (file_path, upload_name) pairs.
# A recipe returns [] if its source files aren't staged; the seeder skips it.
# ---------------------------------------------------------------------------


def recipe_legal() -> list[tuple[Path, str]]:
    legal = DATA / "legal_vi"
    if not legal.exists():
        return []
    return [(p, p.name) for p in sorted(legal.glob("*.txt"))]


def recipe_literature() -> list[tuple[Path, str]]:
    src = DATA / "wikisource_vi"
    return [(p, p.name) for p in sorted(src.glob("*.txt"))]


def recipe_encyclopedia() -> list[tuple[Path, str]]:
    src = DATA / "wiki_vi" / "articles.jsonl"
    if not src.exists():
        return []
    # Materialize the first 5 articles as separate .txt files for richer
    # multi-doc retrieval demos.
    out_dir = DATA / "wiki_vi" / "_seed_articles"
    out_dir.mkdir(exist_ok=True)
    files: list[tuple[Path, str]] = []
    with src.open(encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 5:
                break
            art = json.loads(line)
            slug = art["title"].lower().replace(" ", "_").replace("/", "_")
            p = out_dir / f"{slug}.txt"
            p.write_text(f"{art['title']}\n\n{art['extract']}\n", encoding="utf-8")
            files.append((p, p.name))
    return files


def recipe_office() -> list[tuple[Path, str]]:
    src = DATA / "office_vi"
    if not src.exists():
        return []
    return [
        (p, p.name)
        for p in sorted(src.iterdir())
        if p.suffix.lower() in {".docx", ".xlsx", ".pptx"}
    ]


def recipe_ocr() -> list[tuple[Path, str]]:
    src = DATA / "synthetic_ocr_vi" / "clean"
    if not src.exists():
        return []
    return [(p, p.name) for p in sorted(src.glob("*.png"))[:5]]


SPACES: list[tuple[str, callable]] = [
    ("Pháp luật — Hiến pháp & Tuyên ngôn", recipe_legal),
    ("Văn học — Truyện Kiều", recipe_literature),
    ("Bách khoa — Việt Nam", recipe_encyclopedia),
    ("Hợp đồng & Báo cáo (Office)", recipe_office),
    ("Hình ảnh — OCR Vietnamese", recipe_ocr),
]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", default="http://127.0.0.1:8090", help="server base URL")
    p.add_argument(
        "--no-index",
        action="store_true",
        help="upload only, skip the eager /index call",
    )
    args = p.parse_args(argv)

    try:
        existing = _get_json(f"{args.url}/api/spaces")
    except urllib.error.URLError as exc:
        print(f"cannot reach {args.url} — is `nom serve` running?  ({exc})", file=sys.stderr)
        return 2
    assert isinstance(existing, list)
    existing_names = {s["name"] for s in existing}

    for name, recipe in SPACES:
        files = recipe()
        if not files:
            print(f"⊘ {name} — source files not staged, skipping")
            continue
        if name in existing_names:
            print(f"⊘ {name} — already exists, skipping")
            continue
        print(f"+ {name}")
        sp = _create_space(args.url, name)
        for path, upload_name in files:
            _post_multipart(f"{args.url}/api/spaces/{sp['id']}/materials", path, upload_name)
            print(f"    ↑ {upload_name}")
        if not args.no_index:
            r = _index(args.url, sp["id"])
            print(f"    ✓ indexed {r.get('n_indexed', 0)}/{r.get('n_total', 0)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
