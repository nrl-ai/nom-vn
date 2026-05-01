"""Compare Vietnamese OCR engines on brianhuster handwriting test split.

Per the OCR-correction post-mortem (docs/tasks/ocr.md), the right move
is to fix the OCR engine itself rather than try to post-correct
70 %-CER input. This script benchmarks every realistic VN OCR engine
on the same held-out 200-image sample and picks the best.

Engines tested (lazy-imported; missing ones skip cleanly):

  - tesseract `vie`           — current default
  - easyocr (Vietnamese)
  - vietocr (vgg_transformer, pbcquoc/vietocr Apache 2.0)
  - paddleocr PP-OCRv5        — if installed
  - rapidocr (ONNX-runtime port of PaddleOCR, Apache 2.0)
  - microsoft/trocr-base-handwritten — English handwriting
                                       reference baseline

Metric: CER + WER + p50 latency. Same NFC discipline as
`bench_ocr_post_correct_real.py`.

Usage::

    python benchmarks/accuracy/bench_ocr_engines.py \\
        --json benchmarks/results/baseline_ocr_engines.json
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
from bench_ocr_post_correct import _cer, _wer  # noqa: E402
from bench_ocr_post_correct_real import _load_annotations  # noqa: E402


def _build_engine(name: str):
    """Lazy-import. Returns (image_path) -> str callable, or None if engine missing."""
    if name == "tesseract":
        try:
            import pytesseract
            from PIL import Image
        except ImportError:
            return None

        def run(p: Path) -> str:
            with Image.open(p) as im:
                return pytesseract.image_to_string(im, lang="vie", config="--psm 7")

        return run

    if name == "easyocr":
        try:
            import easyocr
        except ImportError:
            return None
        reader = easyocr.Reader(["vi"], gpu=True, verbose=False)

        def run(p: Path) -> str:
            res = reader.readtext(str(p), detail=0, paragraph=True)
            return " ".join(res) if res else ""

        return run

    if name == "vietocr":
        try:
            from PIL import Image
            from vietocr.tool.config import Cfg
            from vietocr.tool.predictor import Predictor
        except ImportError:
            return None
        cfg = Cfg.load_config_from_name("vgg_transformer")
        cfg["device"] = "cuda"
        cfg["predictor"]["beamsearch"] = False
        predictor = Predictor(cfg)

        def run(p: Path) -> str:
            return predictor.predict(Image.open(p).convert("RGB"))

        return run

    if name == "paddleocr":
        try:
            from paddleocr import PaddleOCR
        except ImportError:
            return None
        # PP-OCRv5: lang='vi' selects latin_PP-OCRv5_mobile_rec under the
        # hood (PaddleOCR has no VN-specific recognizer; latin script
        # supports the Vietnamese alphabet). enable_mkldnn=False works
        # around a oneDNN ConvertPirAttribute crash on Python 3.13 + CPU
        # runtime that we hit on 2026-05-01.
        ocr = PaddleOCR(lang="vi", enable_mkldnn=False, device="cpu")

        def run(p: Path) -> str:
            res = ocr.predict(str(p))
            if not res:
                return ""
            texts = res[0].get("rec_texts", []) if isinstance(res[0], dict) else []
            return " ".join(t for t in texts if t)

        return run

    if name == "rapidocr":
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            return None
        # ONNX-runtime port of PaddleOCR. Apache 2.0, no VN-specific
        # recognizer either — uses the same generic Latin recognizer.
        # Docling delegates to this engine when ocr_engine='rapidocr'.
        reader = RapidOCR()

        def run(p: Path) -> str:
            res, _ = reader(str(p))
            if not res:
                return ""
            return " ".join(t[1] for t in res if len(t) >= 2)

        return run

    if name == "trocr-handwritten":
        try:
            import torch
            from PIL import Image
            from transformers import TrOCRProcessor, VisionEncoderDecoderModel
        except ImportError:
            return None
        device = "cuda" if torch.cuda.is_available() else "cpu"
        processor = TrOCRProcessor.from_pretrained("microsoft/trocr-base-handwritten")
        model = (
            VisionEncoderDecoderModel.from_pretrained("microsoft/trocr-base-handwritten")
            .to(device)
            .eval()
        )

        def run(p: Path) -> str:
            img = Image.open(p).convert("RGB")
            inputs = processor(images=img, return_tensors="pt").to(device)
            with torch.no_grad():
                out = model.generate(inputs.pixel_values, max_length=128)
            return processor.batch_decode(out, skip_special_tokens=True)[0]

        return run

    raise ValueError(f"unknown engine: {name}")


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--data-root",
        type=Path,
        default=Path("/tmp/brianhuster_ocr/data_line"),
    )
    p.add_argument(
        "--engines",
        default="tesseract,easyocr,vietocr,trocr-handwritten,paddleocr",
        help="Comma-separated. Missing engines skip cleanly.",
    )
    p.add_argument("--n-samples", type=int, default=200)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--json", type=Path, default=None)
    p.add_argument("--examples", type=int, default=4)
    args = p.parse_args()

    annotations = _load_annotations(args.data_root / "test_line_annotation.txt")
    import random

    rng = random.Random(args.seed)
    samples = rng.sample(annotations, k=min(args.n_samples, len(annotations)))
    print(f"sampled {len(samples)} from test split (seed={args.seed})")

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

    results: dict = {
        e: {"preds": [], "cers": [], "wers": [], "latencies": []} for e in engine_runners
    }
    examples_kept: list[dict] = []

    t0 = time.perf_counter()
    for idx, (img_rel, gold) in enumerate(samples):
        img_path = args.data_root / img_rel
        if not img_path.exists():
            continue
        per_image: dict = {"img": img_rel, "gold": gold}
        for ename, run in engine_runners.items():
            t_start = time.perf_counter()
            try:
                out = run(img_path)
            except Exception:
                out = ""
            latency = time.perf_counter() - t_start
            out = unicodedata.normalize("NFC", (out or "")).strip()
            cer = _cer(out, gold)
            wer = _wer(out, gold)
            results[ename]["preds"].append(out)
            results[ename]["cers"].append(cer)
            results[ename]["wers"].append(wer)
            results[ename]["latencies"].append(latency)
            per_image[ename] = out
            per_image[f"{ename}_cer"] = round(cer, 4)
        examples_kept.append(per_image)

        if (idx + 1) % 25 == 0:
            elapsed = time.perf_counter() - t0
            eta = (len(samples) - idx - 1) * elapsed / (idx + 1)
            print(f"  {idx + 1}/{len(samples)} ({elapsed:.0f}s elapsed, ETA {eta:.0f}s)")

    print()
    print(f"=== Aggregate (n={len(examples_kept)}) ===")
    print(f"  {'engine':<22s} {'CER':>7s} {'WER':>7s} {'mean ms/img':>14s}")
    rows_sorted = sorted(results.items(), key=lambda kv: statistics.mean(kv[1]["cers"]))
    for ename, d in rows_sorted:
        c = statistics.mean(d["cers"]) * 100
        w = statistics.mean(d["wers"]) * 100
        ms = statistics.mean(d["latencies"]) * 1000
        print(f"  {ename:<22s} {c:>6.2f}% {w:>6.2f}% {ms:>13.0f}")

    print()
    print(f"  --- {args.examples} sample outputs (gold + each engine) ---")
    if examples_kept:
        # Spread across CER buckets — pick examples by tesseract CER for
        # consistency, fall back to whichever engine ran first.
        sort_key = (
            "tesseract_cer"
            if "tesseract" in engine_runners
            else f"{next(iter(engine_runners))}_cer"
        )
        examples_kept.sort(key=lambda r: r.get(sort_key, 0))
        step = max(1, len(examples_kept) // args.examples)
        for r in examples_kept[::step][: args.examples]:
            print(f"\n    {r['img']}")
            print(f"      GOLD: {r['gold'][:120]}")
            for ename in engine_runners:
                txt = r.get(ename, "")
                print(
                    f"      {ename:<14s}: {txt[:120]}  (CER {r.get(f'{ename}_cer', 0) * 100:.0f}%)"
                )

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(
            json.dumps(
                {
                    "n_samples": len(examples_kept),
                    "seed": args.seed,
                    "engines": list(engine_runners),
                    "results": {
                        e: {
                            "cer_mean": round(statistics.mean(d["cers"]), 4),
                            "cer_p50": round(statistics.median(d["cers"]), 4),
                            "wer_mean": round(statistics.mean(d["wers"]), 4),
                            "latency_ms_mean": round(statistics.mean(d["latencies"]) * 1000, 1),
                            "latency_ms_p50": round(statistics.median(d["latencies"]) * 1000, 1),
                        }
                        for e, d in results.items()
                    },
                },
                indent=2,
                ensure_ascii=False,
            )
            + "\n"
        )
        print(f"\nResults: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
