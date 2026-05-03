"""Generate the synthetic-scan corpus for vn-ocr-documents-eval v0.3.

Pulls clean public-domain Vietnamese text from existing repo sources
(wikisource_vi, udhr_vi, wiki_vi, tatoeba_vi), renders each excerpt
as a clean page, applies the comprehensive scan-artifact pipeline,
and emits an image-only PDF + page PNG + metadata record.

The clean source text is the perfect ground truth — no manual
transcription needed. This trades real-scan fidelity for register
diversity and corpus scale.

Categories produced:

  literary      — wikisource Truyện Kiều excerpts (classical VN)
  formal        — UDHR articles (declarative, legal-formal)
  news_business — wiki_vi article openings (encyclopedia / news)
  conversational — tatoeba VN sentence groups (everyday)

Per-category target: 20+ documents.

Each excerpt is rendered with one of three scan profiles
(office_scan / old_photocopy / clean_digital) selected
deterministically by hash so different docs in the same category
look distinguishable.

Run from the corpus dir::

    python benchmarks/data/vn_documents_ocr_v2/_synth_corpus.py
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from hashlib import md5
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas as rl_canvas

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from _scan_artifacts import ScanProfile, apply_scan_artifacts  # noqa: E402

REPO = ROOT.parents[2]
OUT_PAGES = ROOT / "pages"
OUT_DOCS = ROOT / "docs"

DEJAVU_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
DEJAVU_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
DEJAVU_SERIF = Path("/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf")

PAGE_W = 1700
PAGE_H = 2200
MARGIN = 130


@dataclass(frozen=True, slots=True)
class SynthRecipe:
    doc_id: str
    category: str
    title: str
    text: str  # canonical ground truth
    font_path: Path
    font_size: int
    profile: ScanProfile


def _pick_profile(seed: str) -> ScanProfile:
    h = int(md5(seed.encode("utf-8")).hexdigest()[:6], 16)
    return list(ScanProfile)[h % 3]


def _render_clean_page(
    text: str,
    *,
    title: str,
    font_path: Path,
    font_size: int,
) -> Image.Image:
    """Render `text` as a clean page with `title` as a centred bold header."""
    img = Image.new("RGB", (PAGE_W, PAGE_H), color="white")
    draw = ImageDraw.Draw(img)

    body_font = ImageFont.truetype(str(font_path), font_size)
    title_font = ImageFont.truetype(str(DEJAVU_BOLD), int(font_size * 1.3))

    y = MARGIN
    if title:
        bbox = draw.textbbox((0, 0), title, font=title_font)
        title_w = bbox[2] - bbox[0]
        draw.text(((PAGE_W - title_w) // 2, y), title, fill="black", font=title_font)
        y += int(font_size * 1.8)
        # Underline the title
        draw.line(
            [(MARGIN, y - int(font_size * 0.5)), (PAGE_W - MARGIN, y - int(font_size * 0.5))],
            fill=(120, 120, 120),
            width=1,
        )

    # Wrap body text per render width
    line_h = int(font_size * 1.45)
    max_w = PAGE_W - 2 * MARGIN
    for paragraph in text.split("\n\n"):
        for paragraph_line in paragraph.split("\n"):
            words = paragraph_line.split()
            line: list[str] = []
            for w in words:
                trial = (" ".join([*line, w])).strip()
                bbox = draw.textbbox((0, 0), trial, font=body_font)
                if (bbox[2] - bbox[0]) > max_w and line:
                    if y > PAGE_H - MARGIN:
                        return img
                    draw.text((MARGIN, y), " ".join(line), fill="black", font=body_font)
                    y += line_h
                    line = [w]
                else:
                    line.append(w)
            if line and y <= PAGE_H - MARGIN:
                draw.text((MARGIN, y), " ".join(line), fill="black", font=body_font)
                y += line_h
        y += int(line_h * 0.6)  # paragraph break
    return img


def _save_doc(recipe: SynthRecipe) -> dict:
    """Render → apply artifacts → save PDF + PNG → return metadata record."""
    clean = _render_clean_page(
        recipe.text,
        title=recipe.title,
        font_path=recipe.font_path,
        font_size=recipe.font_size,
    )
    # Stable seed so re-runs are deterministic
    seed = int(md5(recipe.doc_id.encode("utf-8")).hexdigest()[:8], 16)
    scanned = apply_scan_artifacts(clean, profile=recipe.profile, seed=seed)

    png_path = OUT_PAGES / f"{recipe.doc_id}_p1.png"
    scanned.save(png_path, format="PNG", optimize=True)

    pdf_path = OUT_DOCS / f"{recipe.doc_id}.pdf"
    pw = scanned.size[0] * 72 / 200
    ph = scanned.size[1] * 72 / 200
    # Embed JPEG to keep PDF size small
    tmp = pdf_path.with_suffix(".tmp.jpg")
    scanned.save(tmp, format="JPEG", quality=84, optimize=True)
    c = rl_canvas.Canvas(str(pdf_path), pagesize=(pw, ph))
    c.drawImage(str(tmp), 0, 0, pw, ph)
    c.showPage()
    c.save()
    tmp.unlink(missing_ok=True)

    return {
        "doc_id": recipe.doc_id,
        "config": "synthetic_scan",
        "category": recipe.category,
        "title": recipe.title,
        "issuer": "synthetic — rendered from PD source",
        "source_url": None,
        "license": "CC0 1.0 (rendered) — upstream source PD",
        "gen_method": f"render_dejavu+scan_artifacts:{recipe.profile.value}",
        "n_pages": 1,
        "pdf": f"docs/{recipe.doc_id}.pdf",
        "image": f"pages/{recipe.doc_id}_p1.png",
        "text": recipe.text.strip(),
    }


def _split_paragraphs(text: str, *, min_words: int = 40, max_words: int = 200) -> list[str]:
    """Cut a long text into paragraph-shaped chunks of min_words..max_words."""
    out: list[str] = []
    buf: list[str] = []
    n = 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            if buf and n >= min_words:
                out.append(" ".join(buf))
                buf = []
                n = 0
            continue
        words = line.split()
        if n + len(words) > max_words and buf:
            out.append(" ".join(buf))
            buf = []
            n = 0
        buf.extend(words)
        n += len(words)
    if buf and n >= min_words:
        out.append(" ".join(buf))
    return out


# ---------- Source loaders ----------


def _load_wikisource_paragraphs() -> list[tuple[str, str]]:
    """Return list of (title, text) — Truyện Kiều related literary."""
    out = []
    for fn in [
        "bai_tua_truyen_kieu.txt",
        "tua_truyen_kieu.txt",
        "tong_vinh_truyen_kieu.txt",
    ]:
        path = REPO / "benchmarks" / "data" / "wikisource_vi" / fn
        if not path.exists():
            continue
        text = path.read_text(encoding="utf-8")
        # Take the first body paragraph block past the metadata
        chunks = _split_paragraphs(text, min_words=60, max_words=180)
        for i, chunk in enumerate(chunks):
            title = f"Trích {fn.replace('_', ' ').replace('.txt', '').title()} ({i + 1})"
            out.append((title, chunk))
    return out


def _load_udhr_articles() -> list[tuple[str, str]]:
    """UDHR Vietnamese — split into article-shaped chunks."""
    path = REPO / "benchmarks" / "data" / "udhr_vi" / "udhr_vi.txt"
    if not path.exists():
        return []
    text = path.read_text(encoding="utf-8")
    chunks = _split_paragraphs(text, min_words=50, max_words=160)
    return [(f"Tuyên ngôn QTNQ — Đoạn {i + 1}", c) for i, c in enumerate(chunks)]


def _load_wiki_articles() -> list[tuple[str, str]]:
    """wiki_vi article openings — encyclopedia/news register."""
    path = REPO / "benchmarks" / "data" / "wiki_vi" / "articles.jsonl"
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except Exception:
            continue
        # The opening of the article extract — keep ~80-160 words
        text = (d.get("extract") or "").strip()
        if not text:
            continue
        words = text.split()
        if len(words) < 80:
            continue
        chunk = " ".join(words[:160])
        out.append((d.get("title", "Bài bách khoa"), chunk))
    return out


def _load_tatoeba_groups() -> list[tuple[str, str]]:
    """Tatoeba VN — group ~6-12 sentences per doc to make a paragraph."""
    candidates = [
        REPO / "benchmarks" / "data" / "tatoeba_vi" / "vie_sentences_sample_3k.tsv",
    ]
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return []
    sentences: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        # tatoeba TSV: id\tlang\ttext OR similar — take last column
        parts = line.split("\t")
        if not parts:
            continue
        s = parts[-1].strip()
        if 5 <= len(s.split()) <= 25:
            sentences.append(s)
    out = []
    group_size = 8
    for i in range(0, min(len(sentences), 240), group_size):
        chunk = sentences[i : i + group_size]
        if len(chunk) < group_size:
            break
        out.append((f"Hội thoại — Nhóm {i // group_size + 1}", "\n".join(chunk)))
    return out


def main() -> int:
    OUT_PAGES.mkdir(parents=True, exist_ok=True)
    OUT_DOCS.mkdir(parents=True, exist_ok=True)

    # ----- Build the recipe list -----
    recipes: list[SynthRecipe] = []

    # literary — DejaVuSerif, slightly larger font
    for i, (title, text) in enumerate(_load_wikisource_paragraphs()[:24]):
        rid = f"synth_literary_{i:03d}"
        recipes.append(
            SynthRecipe(
                doc_id=rid,
                category="literary",
                title=title,
                text=text,
                font_path=DEJAVU_SERIF,
                font_size=28,
                profile=_pick_profile(rid),
            )
        )

    # formal (UDHR articles) — DejaVuSans
    for i, (title, text) in enumerate(_load_udhr_articles()[:24]):
        rid = f"synth_formal_{i:03d}"
        recipes.append(
            SynthRecipe(
                doc_id=rid,
                category="formal",
                title=title,
                text=text,
                font_path=DEJAVU_REGULAR,
                font_size=28,
                profile=_pick_profile(rid),
            )
        )

    # news_business (wiki_vi)
    for i, (title, text) in enumerate(_load_wiki_articles()[:24]):
        rid = f"synth_news_{i:03d}"
        recipes.append(
            SynthRecipe(
                doc_id=rid,
                category="news_business",
                title=title[:60],
                text=text,
                font_path=DEJAVU_REGULAR,
                font_size=28,
                profile=_pick_profile(rid),
            )
        )

    # conversational (tatoeba)
    for i, (title, text) in enumerate(_load_tatoeba_groups()[:24]):
        rid = f"synth_conversational_{i:03d}"
        recipes.append(
            SynthRecipe(
                doc_id=rid,
                category="conversational",
                title=title,
                text=text,
                font_path=DEJAVU_REGULAR,
                font_size=28,
                profile=_pick_profile(rid),
            )
        )

    # ----- Render each -----
    by_cat: dict[str, int] = {}
    records: list[dict] = []
    for r in recipes:
        rec = _save_doc(r)
        records.append(rec)
        by_cat[r.category] = by_cat.get(r.category, 0) + 1

    # Append to existing metadata.jsonl (which has the 12 v0.2 records)
    meta_path = ROOT / "metadata.jsonl"
    existing: list[dict] = []
    if meta_path.exists():
        for line in meta_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            d = json.loads(line)
            # Drop any prior synth_* records to keep this generator idempotent
            if not d["doc_id"].startswith("synth_") or d["doc_id"].startswith("synth_scan_receipt"):
                existing.append(d)

    all_records = existing + records
    with meta_path.open("w", encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    print(f"\nGenerated {len(records)} new synthetic-scan documents.")
    for cat, n in sorted(by_cat.items()):
        print(f"  {cat:<16s} n={n}")
    print(f"\nTotal corpus: {len(all_records)} records")
    print(f"  metadata: {meta_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
