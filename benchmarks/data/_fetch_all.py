"""Fetch / sample all Vietnamese benchmark corpora.

Idempotent — re-running overwrites outputs. Run from repo root:

    python benchmarks/data/_fetch_all.py

Sources are chosen for permissive licenses (Apache 2.0 / CC-BY / CC-BY-SA / CC0
/ public domain). See benchmarks/data/README.md and docs/datasets.md for the
full per-folder license + attribution.
"""

from __future__ import annotations

import bz2
import html as html_lib
import json
import random
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
UA = "nom-vn-bench/0.0 (https://github.com/vietanhdev/nom; benchmarks corpus fetch)"


def http_get(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def html_to_text(s: str) -> str:
    """Strip HTML → plain text. Loses formatting; keeps prose for our use."""
    # Drop <style>, <script>, and the <table class="metadata"> infobox
    s = re.sub(r"<style[^>]*>.*?</style>", "", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<script[^>]*>.*?</script>", "", s, flags=re.DOTALL | re.IGNORECASE)
    s = re.sub(r"<sup[^>]*class=\"reference\"[^>]*>.*?</sup>", "", s, flags=re.DOTALL)
    s = re.sub(
        r"<table[^>]*class=\"[^\"]*(?:metadata|infobox|navbox)[^\"]*\"[^>]*>.*?</table>",
        "",
        s,
        flags=re.DOTALL | re.IGNORECASE,
    )
    # Block-level tags → newlines
    s = re.sub(r"</(p|div|h[1-6]|li|tr|br)\s*>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<br\s*/?>", "\n", s, flags=re.IGNORECASE)
    s = re.sub(r"<li[^>]*>", "\n• ", s, flags=re.IGNORECASE)
    # All other tags
    s = re.sub(r"<[^>]+>", "", s)
    # Decode entities
    s = html_lib.unescape(s)
    # Drop residual CSS-rule lines (selector { … })
    s = re.sub(r"^\s*\.[^{\n]*\{[^}]*\}\s*$", "", s, flags=re.MULTILINE)
    s = re.sub(r"\.mw-parser-output[^\n]*", "", s)
    # Collapse whitespace
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def fetch_wikisource_text(title: str) -> str:
    """Fetch rendered HTML and strip to plain text — more robust than wikitext parsing."""
    url = (
        "https://vi.wikisource.org/w/api.php"
        "?action=parse&format=json&formatversion=2&prop=text"
        f"&page={urllib.parse.quote(title)}"
    )
    data = json.loads(http_get(url))
    html = data.get("parse", {}).get("text", "") or ""
    return html_to_text(html)


def fetch_wiki_extract(title: str) -> dict:
    """Full plaintext article extract (no markup) via MW extracts API."""
    url = (
        "https://vi.wikipedia.org/w/api.php"
        "?action=query&format=json&formatversion=2"
        "&prop=extracts|info&inprop=url&explaintext=true&redirects=1"
        f"&titles={urllib.parse.quote(title)}"
    )
    data = json.loads(http_get(url))
    page = (data.get("query", {}).get("pages", []) or [{}])[0]
    return {
        "title": page.get("title", title),
        "url": page.get("fullurl", ""),
        "extract": page.get("extract", "") or "",
        "missing": page.get("missing", False),
    }


# ---------- udhr_vi ----------


def build_udhr_vi() -> None:
    out = ROOT / "udhr_vi"
    out.mkdir(exist_ok=True)
    title = "Biên dịch:Tuyên ngôn Quốc tế Nhân quyền"
    text = fetch_wikisource_text(title)
    (out / "udhr_vi.txt").write_text(text + "\n", encoding="utf-8")
    print(f"  udhr_vi.txt: {len(text)} chars")


# ---------- wikisource_vi (classical literary) ----------


def build_wikisource_vi() -> None:
    out = ROOT / "wikisource_vi"
    out.mkdir(exist_ok=True)
    pieces = [
        ("Bài tựa Truyện Kiều", "bai_tua_truyen_kieu.txt"),
        ("Tựa Truyện Kiều", "tua_truyen_kieu.txt"),
        ("Tổng vịnh Truyện Kiều (Chu Mạnh Trinh)", "tong_vinh_truyen_kieu.txt"),
    ]
    manifest = []
    for title, fname in pieces:
        try:
            text = fetch_wikisource_text(title)
            if not text:
                print(f"  SKIP {title}: empty")
                continue
            (out / fname).write_text(text + "\n", encoding="utf-8")
            manifest.append({"title": title, "file": fname, "chars": len(text)})
            print(f"  {fname}: {len(text)} chars")
        except Exception as e:
            print(f"  ERR {title}: {e}")
        time.sleep(0.3)
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


# ---------- wiki_vi (modern encyclopedia) ----------

WIKI_TITLES = [
    "Việt Nam",
    "Hà Nội",
    "Thành phố Hồ Chí Minh",
    "Đà Nẵng",
    "Huế",
    "Phở",
    "Áo dài",
    "Tết Nguyên Đán",
    "Trống đồng Đông Sơn",
    "Vịnh Hạ Long",
    "Đồng bằng sông Cửu Long",
    "Tiếng Việt",
    "Chữ Quốc ngữ",
    "Chữ Nôm",
    "Lý Thường Kiệt",
    "Trần Hưng Đạo",
    "Nguyễn Du",
    "Hồ Xuân Hương",
    "Truyện Kiều",
    "Lục Vân Tiên",
    "Cà phê tại Việt Nam",
    "Bún bò Huế",
    "Bánh mì",
    "Giáo dục Việt Nam",
    "Y tế tại Việt Nam",
    "Kinh tế Việt Nam",
    "Đường sắt Việt Nam",
    "Sân bay quốc tế Nội Bài",
    "Đại học Quốc gia Hà Nội",
    "Trí tuệ nhân tạo",
]


def build_wiki_vi() -> None:
    out = ROOT / "wiki_vi"
    out.mkdir(exist_ok=True)
    rows = []
    for t in WIKI_TITLES:
        try:
            d = fetch_wiki_extract(t)
            if d.get("missing") or not d["extract"]:
                print(f"  MISSING {t}")
                continue
            rows.append(d)
        except Exception as e:
            print(f"  ERR {t}: {e}")
        time.sleep(0.2)
    fp = out / "articles.jsonl"
    with fp.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    total_chars = sum(len(r["extract"]) for r in rows)
    print(f"  articles.jsonl: {len(rows)} articles, {total_chars} chars")


# ---------- tatoeba_vi (conversational) ----------


def build_tatoeba_vi() -> None:
    out = ROOT / "tatoeba_vi"
    out.mkdir(exist_ok=True)
    src = out / "vie_sentences.tsv.bz2"
    if not src.exists():
        url = "https://downloads.tatoeba.org/exports/per_language/vie/vie_sentences.tsv.bz2"
        src.write_bytes(http_get(url, timeout=120))
    raw = bz2.decompress(src.read_bytes()).decode("utf-8")
    lines = [ln for ln in raw.splitlines() if ln.strip()]
    rng = random.Random(42)
    sample = sorted(rng.sample(lines, min(3000, len(lines))), key=lambda x: int(x.split("\t")[0]))
    (out / "vie_sentences_sample_3k.tsv").write_text("\n".join(sample) + "\n", encoding="utf-8")
    print(f"  vie_sentences_sample_3k.tsv: {len(sample)} lines (from {len(lines)} total)")


# ---------- udhr_vi PDF (UN OHCHR) ----------

UDHR_PDF_URLS = [
    "https://www.ohchr.org/sites/default/files/UDHR/Documents/UDHR_Translations/vie.pdf",
    "https://unicode.org/udhr/d/udhr_vie.pdf",
]


def fetch_udhr_pdf() -> None:
    out = ROOT / "udhr_vi" / "udhr_vie.pdf"
    out.parent.mkdir(exist_ok=True)
    for url in UDHR_PDF_URLS:
        try:
            data = http_get(url, timeout=60)
            if data[:4] == b"%PDF":
                out.write_bytes(data)
                print(f"  udhr_vie.pdf: {len(data)} bytes (from {url})")
                return
        except Exception as e:
            print(f"  PDF err {url}: {e}")
    print("  udhr_vie.pdf: NOT FETCHED — see README for manual download")


# ---------- legal_vi (constitutional + statutory excerpts from Wikisource) ----------
#
# Vietnamese government-authored legal texts are public domain in Vietnam under
# Article 15 of the Law on Intellectual Property (Luật Sở hữu trí tuệ, No.
# 50/2005/QH11): "legal documents, administrative documents, other documents
# in the judicial domain, and official translations of those documents" are
# not protected by copyright. Wikisource hosts machine-readable copies under
# this exemption.
#
# The full Hiến pháp 2013 + selected codes are too big to commit; we sample
# the chapters most useful for VN-language RAG demos (rights, governance,
# civil basics).

LEGAL_TITLES = [
    # Hiến pháp 2013 — the current constitution
    ("Hiến pháp nước Cộng hòa xã hội chủ nghĩa Việt Nam 2013", "hien_phap_2013.txt"),
    # Tuyên ngôn Độc lập (1945) — declaration of independence, public domain
    ("Tuyên ngôn Độc lập (Việt Nam Dân chủ Cộng hòa)", "tuyen_ngon_doc_lap_1945.txt"),
]


def build_legal_vi() -> None:
    out = ROOT / "legal_vi"
    out.mkdir(exist_ok=True)
    manifest = []
    for title, fname in LEGAL_TITLES:
        try:
            text = fetch_wikisource_text(title)
            if not text or len(text) < 200:
                print(f"  SKIP {title}: too short / empty")
                continue
            (out / fname).write_text(text + "\n", encoding="utf-8")
            manifest.append(
                {
                    "title": title,
                    "file": fname,
                    "chars": len(text),
                    "license": "Public domain (VN Law on IP §15: government legal texts)",
                    "source": f"https://vi.wikisource.org/wiki/{urllib.parse.quote(title)}",
                }
            )
            print(f"  {fname}: {len(text)} chars")
        except Exception as e:
            print(f"  ERR {title}: {e}")
        time.sleep(0.3)
    if not (out / "README.md").exists():
        (out / "README.md").write_text(
            "# `legal_vi/` — Vietnamese legal & governance texts (public domain)\n\n"
            "Government-authored Vietnamese legal text. Public domain under\n"
            "Article 15 of the Law on Intellectual Property (Luật SHTT 2005);\n"
            "see `manifest.json` for source URLs and titles.\n\n"
            "Used for: realistic legal-register RAG demos and benchmarks.\n",
            encoding="utf-8",
        )
    (out / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def main() -> None:
    print("[udhr_vi]")
    build_udhr_vi()
    print("[wikisource_vi]")
    build_wikisource_vi()
    print("[wiki_vi]")
    build_wiki_vi()
    print("[tatoeba_vi]")
    build_tatoeba_vi()
    print("[legal_vi]")
    build_legal_vi()
    print("[udhr_vi pdf]")
    fetch_udhr_pdf()


if __name__ == "__main__":
    main()
