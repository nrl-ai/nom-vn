"""Bench OCR engines on synthetic_ocr_vi printed registers.

Companion to ``bench_ocr_engines.py`` (which targets handwriting from
brianhuster). Runs the same engine wrappers across the three printed
registers (clean / noisy / hard) so the per-register matrix in
``docs/tasks/ocr.md`` can fill every cell rather than leaving "—".

Usage::

    python benchmarks/accuracy/bench_ocr_engines_printed.py \\
        --engines easyocr,trocr-handwritten \\
        --json benchmarks/results/baseline_ocr_engines_printed.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "benchmarks" / "accuracy"))
from bench_ocr_engines import _build_engine  # noqa: E402
from bench_ocr_post_correct import _cer, _wer  # noqa: E402


def _load_register(base: Path, register: str) -> list[tuple[Path, str]]:
    """Return [(image_path, gold)] for a printed register."""
    if register == "hard":
        gt = base / "ground_truth_hard.jsonl"
        key = "image"
    else:
        gt = base / "ground_truth.jsonl"
        key = register
    samples: list[tuple[Path, str]] = []
    with gt.open() as f:
        for line in f:
            r = json.loads(line)
            img_rel = r.get(key)
            if not img_rel:
                continue
            img = base / img_rel
            if img.exists():
                samples.append((img, r["text"]))
    return samples


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--data-root",
        type=Path,
        default=REPO / "benchmarks" / "data" / "synthetic_ocr_vi",
    )
    p.add_argument(
        "--engines",
        default="tesseract,easyocr,vietocr,trocr-handwritten,paddleocr,rapidocr",
        help="Comma-separated. Missing engines skip cleanly.",
    )
    p.add_argument(
        "--registers",
        default="clean,noisy,hard",
        help="Comma-separated synthetic_ocr_vi registers.",
    )
    p.add_argument("--json", type=Path, default=None)
    args = p.parse_args()

    engine_runners: dict = {}
    for name in (e.strip() for e in args.engines.split(",")):
        try:
            t0 = time.perf_counter()
            r = _build_engine(name)
            if r is None:
                print(f"  [skip] {name}: package not installed")
                continue
            engine_runners[name] = r
            print(f"  [load] {name}: {time.perf_counter() - t0:.1f}s")
        except Exception as exc:
            print(f"  [skip] {name}: {exc!r}")

    if not engine_runners:
        print("no engines loaded", file=sys.stderr)
        return 2

    out: dict = {"data_root": str(args.data_root), "results": {}}
    registers = [r.strip() for r in args.registers.split(",") if r.strip()]
    for register in registers:
        samples = _load_register(args.data_root, register)
        print(f"\n== register={register} (n={len(samples)}) ==")
        out["results"][register] = {"n": len(samples), "engines": {}}
        for ename, run in engine_runners.items():
            cers, wers, lats = [], [], []
            for img, gold in samples:
                t0 = time.perf_counter()
                try:
                    pred = run(img)
                except Exception:
                    pred = ""
                lats.append(time.perf_counter() - t0)
                pred = unicodedata.normalize("NFC", pred or "").strip()
                gold_n = unicodedata.normalize("NFC", gold).strip()
                cers.append(_cer(pred, gold_n))
                wers.append(_wer(pred, gold_n))
            cer_mean = statistics.mean(cers) if cers else 0.0
            wer_mean = statistics.mean(wers) if wers else 0.0
            ms_mean = statistics.mean(lats) * 1000 if lats else 0.0
            print(
                f"  {ename:<22s} CER={cer_mean * 100:6.2f}%  WER={wer_mean * 100:6.2f}%  {ms_mean:7.0f} ms"
            )
            out["results"][register]["engines"][ename] = {
                "cer_mean": round(cer_mean, 4),
                "wer_mean": round(wer_mean, 4),
                "latency_ms_mean": round(ms_mean, 1),
            }

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n")
        print(f"\nResults: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
