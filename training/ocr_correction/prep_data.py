"""Build a multi-engine (OCR output, GT) corpus for OCR post-correction.

Run multiple OCR engines (Tesseract `vie`, EasyOCR `vi`, optionally
PaddleOCR / VietOCR if installed) on each image in the **train split**
of `brianhuster/VietnameseOCRdataset`, pair every non-empty output
with its ground-truth line, filter out gibberish (CER > MAX_CER), and
emit JSONL training pairs.

Train / val / test discipline (this is load-bearing — the bench
script reads brianhuster's test split, so the test split must NEVER
be touched here):

  brianhuster split          what we do
  ------------------------   ------------------------------------
  train_line_annotation.txt  90/10 split → train.jsonl + val.jsonl
  test_line_annotation.txt   strictly held out; not opened here

Per-engine yield is added independently so the model sees the same
ground-truth paired with multiple distinct error distributions.

Usage::

    python training/ocr_correction/prep_data.py \\
        --engines tesseract,easyocr \\
        --max-cer 0.95 \\
        --output training/ocr_correction/data/

Writes:
    training/ocr_correction/data/train.jsonl   (90 percent of train split * n_engines * filter)
    training/ocr_correction/data/val.jsonl     (10 %)
    training/ocr_correction/data/stats.json
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
import time
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "benchmarks" / "accuracy"))
from bench_ocr_post_correct import _cer  # noqa: E402

KNOWN_ENGINES = ("tesseract", "easyocr", "paddleocr", "vietocr")


def _load_annotations(path: Path) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) != 2:
            continue
        img, txt = parts
        rows.append((img.strip(), unicodedata.normalize("NFC", txt.strip())))
    return rows


def _build_engine(name: str):
    """Lazy-import the requested engine and return a `(image_path) -> str` callable."""
    if name == "tesseract":
        import pytesseract
        from PIL import Image

        def run(img_path: Path) -> str:
            with Image.open(img_path) as im:
                return pytesseract.image_to_string(im, lang="vie", config="--psm 7")

        return run
    if name == "easyocr":
        import easyocr

        # Single shared reader; EasyOCR loads ~470 MB of weights — heavy.
        reader = easyocr.Reader(["vi"], gpu=True, verbose=False)

        def run(img_path: Path) -> str:
            res = reader.readtext(str(img_path), detail=0, paragraph=True)
            return " ".join(res) if res else ""

        return run
    if name == "paddleocr":
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(use_angle_cls=False, lang="vi", show_log=False)

        def run(img_path: Path) -> str:
            res = ocr.ocr(str(img_path), cls=False)
            if not res or not res[0]:
                return ""
            return " ".join(seg[1][0] for seg in res[0] if seg and seg[1])

        return run
    if name == "vietocr":
        from PIL import Image
        from vietocr.tool.config import Cfg
        from vietocr.tool.predictor import Predictor

        cfg = Cfg.load_config_from_name("vgg_transformer")
        cfg["device"] = "cuda"
        predictor = Predictor(cfg)

        def run(img_path: Path) -> str:
            return predictor.predict(Image.open(img_path).convert("RGB"))

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
        "--output",
        type=Path,
        default=REPO / "training" / "ocr_correction" / "data",
    )
    p.add_argument(
        "--engines",
        default="tesseract,easyocr",
        help=f"Comma-separated subset of {KNOWN_ENGINES}.",
    )
    p.add_argument(
        "--max-cer",
        type=float,
        default=0.95,
        help="Drop pairs where CER(ocr_raw, GT) exceeds this. Default 0.95 "
        "(keep heavily-corrupted training signal but drop pure-gibberish).",
    )
    p.add_argument(
        "--val-fraction",
        type=float,
        default=0.10,
        help="Fraction of the train split carved out as val.",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--max-images",
        type=int,
        default=0,
        help="Cap on number of TRAIN images to process (0 = all). Useful for smoke testing.",
    )
    args = p.parse_args()

    args.output.mkdir(parents=True, exist_ok=True)
    train_path = args.output / "train.jsonl"
    val_path = args.output / "val.jsonl"
    stats_path = args.output / "stats.json"

    annotations = _load_annotations(args.data_root / "train_line_annotation.txt")
    if not annotations:
        print(f"no train annotations found under {args.data_root}", file=sys.stderr)
        return 2

    rng = random.Random(args.seed)
    if args.max_images and args.max_images < len(annotations):
        annotations = rng.sample(annotations, k=args.max_images)
    print(
        f"using {len(annotations)} train images "
        f"(test split — {args.data_root / 'test_line_annotation.txt'} — held out)"
    )

    # 90/10 split BEFORE running OCR so we never leak val images into train
    # via different engines.
    rng.shuffle(annotations)
    n_val = max(1, int(len(annotations) * args.val_fraction))
    val_set = {img for img, _ in annotations[:n_val]}

    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    print(f"engines: {engines}")
    runners: dict = {}
    for e in engines:
        try:
            t0 = time.perf_counter()
            runners[e] = _build_engine(e)
            print(f"  loaded {e} in {time.perf_counter() - t0:.1f}s")
        except Exception as exc:
            print(f"  skip {e}: {exc!r}", file=sys.stderr)

    if not runners:
        print("no engines loaded; aborting", file=sys.stderr)
        return 2

    counts = {
        "kept": 0,
        "skipped_empty": 0,
        "skipped_high_cer": 0,
        "kept_identity": 0,
        "missing_image": 0,
    }
    per_engine_counts: dict[str, int] = dict.fromkeys(runners, 0)
    per_engine_cer_sum: dict[str, list[float]] = {e: [] for e in runners}

    with (
        train_path.open("w", encoding="utf-8") as f_train,
        val_path.open("w", encoding="utf-8") as f_val,
    ):
        t0 = time.perf_counter()
        for i, (img_rel, gt) in enumerate(annotations):
            full = args.data_root / img_rel
            if not full.exists():
                counts["missing_image"] += 1
                continue
            is_val = img_rel in val_set
            for eng, run in runners.items():
                try:
                    raw = run(full)
                except Exception:  # single-image failure shouldn't kill prep
                    continue
                raw = unicodedata.normalize("NFC", (raw or "")).strip()
                if not raw:
                    counts["skipped_empty"] += 1
                    continue
                cer = _cer(raw, gt)
                if cer > args.max_cer:
                    counts["skipped_high_cer"] += 1
                    continue
                if cer == 0.0:
                    counts["kept_identity"] += 1
                pair = {"input": raw, "target": gt, "engine": eng}
                (f_val if is_val else f_train).write(json.dumps(pair, ensure_ascii=False) + "\n")
                counts["kept"] += 1
                per_engine_counts[eng] += 1
                per_engine_cer_sum[eng].append(cer)

            if (i + 1) % 100 == 0:
                rate = (i + 1) / (time.perf_counter() - t0)
                eta = (len(annotations) - i - 1) / rate / 60
                print(
                    f"  {i + 1}/{len(annotations)} "
                    f"kept={counts['kept']} "
                    f"empty={counts['skipped_empty']} "
                    f"hi-CER={counts['skipped_high_cer']} "
                    f"id={counts['kept_identity']} "
                    f"— {rate:.1f} img/s ETA {eta:.0f} min"
                )

    stats = {
        "source": "brianhuster/VietnameseOCRdataset (line, handwriting, Apache 2.0)",
        "split_used": "train_line_annotation.txt (test split held out for bench)",
        "n_train_images": len(annotations) - n_val,
        "n_val_images": n_val,
        "engines": list(runners.keys()),
        "max_cer_kept": args.max_cer,
        "val_fraction": args.val_fraction,
        "seed": args.seed,
        "counts": counts,
        "per_engine": {
            e: {
                "pairs_kept": per_engine_counts[e],
                "cer_mean": (
                    round(statistics.mean(per_engine_cer_sum[e]), 4)
                    if per_engine_cer_sum[e]
                    else None
                ),
                "cer_median": (
                    round(statistics.median(per_engine_cer_sum[e]), 4)
                    if per_engine_cer_sum[e]
                    else None
                ),
            }
            for e in runners
        },
    }
    stats_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")
    print()
    print(f"wrote {train_path} ({sum(1 for _ in train_path.open())} pairs)")
    print(f"wrote {val_path}   ({sum(1 for _ in val_path.open())} pairs)")
    print(f"wrote {stats_path}")
    print()
    print("Per-engine corpus contribution:")
    for e, c in stats["per_engine"].items():
        print(f"  {e:12s} pairs={c['pairs_kept']:>6d}  mean CER={(c['cer_mean'] or 0) * 100:5.2f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
