"""Generate a multi-page Vietnamese PDF with proper Unicode text layer.

Why: the public-domain UDHR PDF in ``udhr_vi/udhr_vie.pdf`` uses a custom
font without a ToUnicode CMap, so any extractor (pdfplumber, pypdfium2,
PyMuPDF) returns CIDs / garbled bytes — useless for measuring extraction
fidelity on Vietnamese.

This generator builds a Unicode-clean Vietnamese PDF from real, public-
domain VN legal/literary text (sourced from ``benchmarks/data/legal_vi/``
and ``wikisource_vi/``) using fpdf2 + DejaVuSans. The ground-truth text
is committed alongside; the .pdf is regeneratable and gitignored.

Run:
    python benchmarks/data/synthetic_pdf_vi/_generate.py

Outputs:
    benchmarks/data/synthetic_pdf_vi/vn_legal.pdf      (~7-10 pages)
    benchmarks/data/synthetic_pdf_vi/vn_legal.gt.txt   (committed)
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent
REPO_ROOT = ROOT.parents[2]

# DejaVuSans is system-installed on Linux (apt: ttf-dejavu). It's the
# de-facto choice for fpdf2 + non-Latin scripts including VN diacritics.
DEJAVU_REGULAR = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
DEJAVU_BOLD = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")

# Source texts (real VN, public-domain or CC-BY-SA per their per-folder LICENSE)
SOURCES = [
    REPO_ROOT / "benchmarks" / "data" / "udhr_vi" / "udhr_vi.txt",
    REPO_ROOT / "benchmarks" / "data" / "wikisource_vi" / "bai_tua_truyen_kieu.txt",
    REPO_ROOT / "benchmarks" / "data" / "wikisource_vi" / "tua_truyen_kieu.txt",
    REPO_ROOT / "benchmarks" / "data" / "wikisource_vi" / "tong_vinh_truyen_kieu.txt",
]


def _read_sources() -> str:
    """Concatenate first-N chars of each source for a multi-register corpus."""
    parts: list[str] = []
    per_source_chars = 8000
    for src in SOURCES:
        if not src.exists():
            print(f"  skip (missing): {src.relative_to(REPO_ROOT)}")
            continue
        text = src.read_text(encoding="utf-8")[:per_source_chars]
        title = src.stem.replace("_", " ").title()
        parts.append(f"=== {title} ===\n\n{text}")
    return "\n\n".join(parts)


def main() -> int:
    from fpdf import FPDF

    if not DEJAVU_REGULAR.exists():
        print(
            f"DejaVuSans.ttf not at {DEJAVU_REGULAR}.\n"
            "Install: sudo apt install fonts-dejavu (Debian/Ubuntu) "
            "or `brew install --cask font-dejavu` (macOS)."
        )
        return 1

    raw = _read_sources()
    if not raw.strip():
        print("No source texts found — run benchmarks/data/_fetch_all.py first.")
        return 1

    pdf = FPDF(unit="pt", format="A4")
    pdf.add_font("DejaVu", "", str(DEJAVU_REGULAR))
    if DEJAVU_BOLD.exists():
        pdf.add_font("DejaVu", "B", str(DEJAVU_BOLD))
    pdf.set_auto_page_break(auto=True, margin=40)
    pdf.add_page()
    pdf.set_font("DejaVu", "", 11)

    # Use multi_cell for paragraph wrapping. Split on blank lines so headings
    # land on their own lines.
    for para in raw.split("\n\n"):
        para = para.strip()
        if not para:
            continue
        if para.startswith("===") and para.endswith("==="):
            pdf.set_font("DejaVu", "B", 13)
            pdf.multi_cell(w=0, h=18, text=para.strip("= "))
            pdf.ln(6)
            pdf.set_font("DejaVu", "", 11)
        else:
            pdf.multi_cell(w=0, h=14, text=para)
            pdf.ln(4)

    out_pdf = ROOT / "vn_legal.pdf"
    out_gt = ROOT / "vn_legal.gt.txt"
    pdf.output(str(out_pdf))
    out_gt.write_text(raw, encoding="utf-8")

    print(f"Wrote {out_pdf} ({out_pdf.stat().st_size:,} bytes, {pdf.pages_count} pages)")
    print(f"Wrote {out_gt} ({len(raw):,} chars)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
