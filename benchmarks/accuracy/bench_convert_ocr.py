"""Benchmark every OCR flow exposed by ``nom.convert``.

Three flows under test:

1. **image_to_docx** — single image → DOCX. Tested across
   ``synthetic_ocr_vi/clean`` (high-quality VN renders) and
   ``synthetic_ocr_vi/noisy`` (with noise injected).
2. **pdf_to_docx text-layer** — born-digital PDF (UDHR Vietnamese)
   where ``pdfplumber`` extracts directly without OCR.
3. **pdf_to_docx OCR fallback** — image-only PDF (rendered from a
   synthetic OCR fixture into a single-page PDF). Forces the OCR
   path that text-layer extraction triggers when ``pdfplumber``
   yields fewer than ``min_chars_text_layer`` characters.

Reports per-flow CER (Levenshtein over NFC chars), throughput
(chars / sec), and total runtime. Output JSON saved alongside the
existing baselines so we can track regressions per release.

Methodology:

- Per the project's verified-benchmarks rule, every number reported
  here comes from a real measurement on real corpora — no synthetic
  metric extrapolation.
- Warmup ≥ 1 call per flow before the timed loop to avoid cold-start
  artifacts (pytesseract initializes Tesseract on first call).
- ``--limit`` caps the per-corpus sample for fast smoke runs;
  ``--limit 0`` runs the full corpus.

Usage::

    # Full sweep
    python benchmarks/accuracy/bench_convert_ocr.py

    # Smoke (3 samples per corpus, ~30 s total)
    python benchmarks/accuracy/bench_convert_ocr.py --limit 3

    # Save JSON for regression tracking
    python benchmarks/accuracy/bench_convert_ocr.py \\
        --json benchmarks/results/baseline_convert_ocr.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import statistics
import sys
import time
import unicodedata
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))


def _cer(hyp: str, ref: str) -> float:
    """Character error rate via Levenshtein on NFC-normalized strings.

    Returns 0.0 for an exact match, 1.0 for completely different
    strings. Empty ref guards against div-by-zero.
    """
    hyp_n = unicodedata.normalize("NFC", hyp).strip()
    ref_n = unicodedata.normalize("NFC", ref).strip()
    if not ref_n:
        return 1.0 if hyp_n else 0.0

    # Standard Levenshtein DP
    m, n = len(hyp_n), len(ref_n)
    if m == 0:
        return 1.0
    prev = list(range(n + 1))
    for i in range(1, m + 1):
        cur = [i] + [0] * n
        for j in range(1, n + 1):
            cost = 0 if hyp_n[i - 1] == ref_n[j - 1] else 1
            cur[j] = min(
                cur[j - 1] + 1,  # insertion
                prev[j] + 1,  # deletion
                prev[j - 1] + cost,  # substitution
            )
        prev = cur
    return prev[n] / n


def _read_docx_text(path: Path) -> str:
    from docx import Document

    return "\n".join(p.text for p in Document(str(path)).paragraphs if p.text.strip())


def _bench_image_corpus(
    fixture_dir: Path,
    ground_truth: list[dict[str, str]],
    *,
    label: str,
    ocr_language: str,
    limit: int,
    workdir: Path,
) -> dict[str, Any]:
    """Run image_to_docx on every fixture, compute CER + throughput."""
    from nom.convert import image_to_docx

    samples = ground_truth[:limit] if limit > 0 else ground_truth
    cers: list[float] = []
    lats: list[float] = []
    chars = 0

    print(f"\n=== image_to_docx — {label} ({len(samples)} samples) ===")
    t_total = time.perf_counter()
    for i, entry in enumerate(samples):
        src = fixture_dir / Path(entry[label]).name
        if not src.exists():
            continue
        dst = workdir / f"{label}_{entry['id']}.docx"
        gold = entry["text"]

        t0 = time.perf_counter()
        try:
            image_to_docx(src, dst, ocr_language=ocr_language)
        except Exception as exc:
            print(f"  [{entry['id']}] error: {exc}")
            continue
        lats.append(time.perf_counter() - t0)

        hyp = _read_docx_text(dst)
        chars += len(gold)
        cers.append(_cer(hyp, gold))

        if (i + 1) % 5 == 0:
            mean_cer = statistics.mean(cers) if cers else 0.0
            print(f"  {i + 1}/{len(samples)} mean_cer={mean_cer * 100:.2f}%")

    total_s = time.perf_counter() - t_total
    return {
        "flow": "image_to_docx",
        "corpus": label,
        "n_samples": len(cers),
        "cer_mean": round(statistics.mean(cers), 4) if cers else None,
        "cer_median": round(statistics.median(cers), 4) if cers else None,
        "latency_ms_p50": round(statistics.median(lats) * 1000, 1) if lats else None,
        "latency_ms_mean": round(statistics.mean(lats) * 1000, 1) if lats else None,
        "throughput_chars_per_sec": round(chars / total_s, 1) if total_s > 0 else None,
        "total_seconds": round(total_s, 2),
    }


def _bench_pdf_text_layer(pdf_path: Path, *, workdir: Path) -> dict[str, Any]:
    """Bench the text-layer extraction path for born-digital PDFs."""
    from nom.convert import pdf_to_docx

    if not pdf_path.exists():
        return {"flow": "pdf_to_docx_text_layer", "skipped": "fixture absent"}

    dst = workdir / "udhr.docx"
    print(f"\n=== pdf_to_docx text-layer — {pdf_path.name} ===")

    # Warmup
    pdf_to_docx(pdf_path, dst, ocr_language="vie+eng")

    # Timed
    t0 = time.perf_counter()
    stats = pdf_to_docx(pdf_path, dst, ocr_language="vie+eng")
    elapsed = time.perf_counter() - t0
    out_text = _read_docx_text(dst)

    return {
        "flow": "pdf_to_docx_text_layer",
        "corpus": pdf_path.name,
        "n_pages": stats.n_pages,
        "pages_text_extracted": stats.pages_text_extracted,
        "pages_ocred": stats.pages_ocred,
        "chars_out": stats.chars_out,
        "elapsed_seconds": round(elapsed, 3),
        "throughput_chars_per_sec": round(stats.chars_out / elapsed, 1) if elapsed > 0 else None,
        "first_200_chars": out_text[:200],
    }


def _bench_pdf_ocr_fallback(
    image_dir: Path,
    ground_truth: list[dict[str, Any]],
    *,
    ocr_language: str,
    limit: int,
    workdir: Path,
) -> dict[str, Any]:
    """Embed each fixture image into a single-page PDF (no text layer)
    sized to match the image's native aspect, then measure
    ``pdf_to_docx``'s OCR fallback path. Reports mean CER + latency
    across ``limit`` samples (``limit=0`` → full corpus).

    The page size is computed from each image's pixel dimensions at
    96 dpi, so Tesseract sees the bitmap at native resolution after
    pdfium2 re-renders the page at the converter's ``ocr_dpi``. An
    earlier version of this bench used a fixed 640x200pt page, which
    stretched 1017x78px line crops into a wrong aspect and pushed
    measured CER to 68 % even though the production code path was
    fine — see commit fixing the regression.
    """
    from PIL import Image
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as rl_canvas

    from nom.convert import pdf_to_docx

    if not ground_truth:
        return {"flow": "pdf_to_docx_ocr_fallback", "skipped": "no ground truth"}

    samples = ground_truth if limit == 0 else ground_truth[:limit]
    cers: list[float] = []
    latencies_ms: list[float] = []
    n_ocred = 0
    n_text = 0
    examples: list[dict[str, Any]] = []
    print(f"\n=== pdf_to_docx OCR fallback — n={len(samples)} ===")

    for s in samples:
        png = image_dir / Path(s["clean"]).name
        if not png.exists():
            continue
        with Image.open(png) as im:
            w_px, h_px = im.size
            page_w = w_px * 72 / 96
            page_h = h_px * 72 / 96
            pdf_src = workdir / f"scan_{s['id']}.pdf"
            c = rl_canvas.Canvas(str(pdf_src), pagesize=(page_w, page_h))
            c.drawImage(ImageReader(im), 0, 0, page_w, page_h)
            c.showPage()
            c.save()

        dst = workdir / f"scan_{s['id']}.docx"
        t0 = time.perf_counter()
        stats = pdf_to_docx(pdf_src, dst, ocr_language=ocr_language)
        latencies_ms.append((time.perf_counter() - t0) * 1000)
        hyp = _read_docx_text(dst)
        cer = _cer(hyp, s["text"])
        cers.append(cer)
        n_ocred += stats.pages_ocred
        n_text += stats.pages_text_extracted
        if len(examples) < 3:
            examples.append({"id": s["id"], "cer": round(cer, 4), "first": hyp[:80]})

    if not cers:
        return {"flow": "pdf_to_docx_ocr_fallback", "skipped": "no fixtures rendered"}

    return {
        "flow": "pdf_to_docx_ocr_fallback",
        "corpus": "synthetic_ocr_vi/clean (rendered to single-page PDFs)",
        "n_samples": len(cers),
        "cer_mean": round(statistics.mean(cers), 4),
        "cer_median": round(statistics.median(cers), 4),
        "latency_ms_p50": round(statistics.median(latencies_ms), 1),
        "latency_ms_mean": round(statistics.mean(latencies_ms), 1),
        "pages_ocred_total": n_ocred,
        "pages_text_extracted_total": n_text,
        "examples": examples,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0, help="Cap samples per corpus (0 = full).")
    parser.add_argument("--ocr-language", default="vie+eng")
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args()

    if shutil.which("tesseract") is None:
        print("error: tesseract not installed", file=sys.stderr)
        return 2

    workdir = REPO / "benchmarks" / "data" / "_bench_convert_ocr_tmp"
    workdir.mkdir(exist_ok=True)

    synth = REPO / "benchmarks" / "data" / "synthetic_ocr_vi"
    gt_path = synth / "ground_truth.jsonl"
    ground_truth = [json.loads(line) for line in gt_path.read_text(encoding="utf-8").splitlines()]

    results = {
        "config": {
            "ocr_language": args.ocr_language,
            "limit": args.limit,
            "tesseract": shutil.which("tesseract"),
        },
        "flows": [],
    }

    # 1. Image OCR — clean
    results["flows"].append(
        _bench_image_corpus(
            synth / "clean",
            ground_truth,
            label="clean",
            ocr_language=args.ocr_language,
            limit=args.limit,
            workdir=workdir,
        )
    )
    # 2. Image OCR — noisy
    results["flows"].append(
        _bench_image_corpus(
            synth / "noisy",
            ground_truth,
            label="noisy",
            ocr_language=args.ocr_language,
            limit=args.limit,
            workdir=workdir,
        )
    )
    # 3. PDF text-layer (UDHR)
    results["flows"].append(
        _bench_pdf_text_layer(
            REPO / "benchmarks" / "data" / "udhr_vi" / "udhr_vie.pdf",
            workdir=workdir,
        )
    )
    # 4. PDF OCR fallback (synthetic image-only PDF) — N samples
    results["flows"].append(
        _bench_pdf_ocr_fallback(
            synth / "clean",
            ground_truth,
            ocr_language=args.ocr_language,
            limit=args.limit,
            workdir=workdir,
        )
    )

    # Print summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)
    for f in results["flows"]:
        if "skipped" in f:
            print(f"  {f['flow']}: skipped — {f['skipped']}")
            continue
        if "cer_mean" in f:
            print(
                f"  {f['flow']:35} {f['corpus']:8} "
                f"CER={f['cer_mean'] * 100:.2f}% "
                f"p50={f['latency_ms_p50']:.0f}ms"
            )
        elif "elapsed_seconds" in f:
            print(
                f"  {f['flow']:35} {f.get('corpus', ''):8} "
                f"{f['elapsed_seconds']:.2f}s "
                f"{f.get('chars_out', 0)} chars"
            )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(results, indent=2, ensure_ascii=False) + "\n")
        print(f"\nResults: {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
