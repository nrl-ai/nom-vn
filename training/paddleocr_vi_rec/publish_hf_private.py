"""Push the fine-tuned PaddleOCR rec checkpoint + 30 k training corpus
to private HuggingFace repos under nrl-ai.

Two artifacts:

  nrl-ai/vn-paddleocr-rec-finetune-v1   (model, private)
    PaddleOCR PP-OCRv5_mobile_rec fine-tuned on 30 k synthetic VN
    line crops. Rec accuracy on val 78.9 %, edit-dist score 0.962.
    Eval on real chinhphu/hanoi.gov.vn scans: 15.08 % mean CER —
    beats default lang='vi' (20.74 %) by 5.7 pp but trails Tesseract
    vie+eng (12.62 %) by 2.5 pp. Negative result, useful for the
    methodology paper.

  nrl-ai/vn-ocr-rec-train-30k           (dataset, private)
    30 000 synthetic VN line crops at 48 px height with light JPEG
    augmentation. 21 170 unique sentences from in-tree corpora
    (UDHR, wiki_vi, tatoeba, wikisource, business templates).
    689-char dictionary including all VN tone-vowel combinations.

Both repos start PRIVATE; flip to public after model card review.

Run::

    python training/paddleocr_vi_rec/publish_hf_private.py --dry-run
    python training/paddleocr_vi_rec/publish_hf_private.py
"""

from __future__ import annotations

import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODEL_REPO = "nrl-ai/vn-paddleocr-rec-finetune-v1"
DATASET_REPO = "nrl-ai/vn-ocr-rec-train-30k"

MODEL_CARD = """\
---
license: apache-2.0
language:
- vi
tags:
- ocr
- vietnamese
- paddleocr
- pp-ocrv5
- text-recognition
library_name: paddleocr
base_model: PaddlePaddle/latin_PP-OCRv5_mobile_rec
private: true
---

# vn-paddleocr-rec-finetune-v1

PaddleOCR PP-OCRv5_mobile_rec fine-tuned for Vietnamese text recognition.

## Quick numbers (real-scan eval, n=9)

| Engine | Mean CER | Median CER | Speed (CPU) |
|---|---:|---:|---:|
| Tesseract `vie+eng` (production default) | **12.62 %** | **11.99 %** | ~1.3 s/doc |
| PaddleOCR PP-OCRv5 default `lang='vi'` | 20.74 % | 19.33 % | ~60 s/doc |
| **This model** | **15.08 %** | **13.28 %** | ~53 s/doc |

Eval corpus: 9 real chinhphu.vn + hanoi.gov.vn signed scans from
`nrl-ai/vn-ocr-documents-eval` v0.4 / config=real.

**Honest result: this fine-tune beat default PaddleOCR `lang='vi'`
by 5.7 pp (confirms the diacritic-stripping in the latin recognizer
was fixable) but still trails Tesseract by 2.5 pp.** Acceptance gate
(median < 11.99 %) not met. Tesseract stays the production default
in `nom-vn`.

## Why PaddleOCR default fails on Vietnamese

`lang='vi'` loads `latin_PP-OCRv5_mobile_rec` — a generic Latin
recognizer that drops every Vietnamese tone mark. Sample output:

```text
Gold:      THỦ TƯỚNG CHÍNH PHỦ
                Độc lập - Tự do - Hạnh phúc
PP default:  TH TƯNG CHÍNH PH
                Đc lp - T do - Hnh phúc
```

This fine-tune fixes that — diacritics are preserved.

## Why we don't beat Tesseract (yet)

- **Synthetic-only training data** — 30 k DejaVuSans crops with light
  JPEG augmentation. Real chinhphu.vn scans have stamps, signatures,
  watermarks, multi-font headers we don't model.
- **Mobile-tier rec architecture** — `PP-OCRv5_mobile_rec` is the
  smaller variant; the server-tier (`PP-OCRv5_server_rec`) would help.
- **Undertrained** — val acc 78.9 % at 25 epochs suggests room.
- **Detection failures cascade** — PaddleOCR runs det → rec; if det
  misses lines, all rec quality is lost. Tesseract reads the whole
  page natively.

## Training details

- Base: `latin_PP-OCRv5_mobile_rec_pretrained.pdparams` (8 MB, Apache 2.0)
- Architecture: SVTR_LCNet, PPLCNetV3 backbone (scale=0.95), MultiHead
  with CTC + NRTR heads
- Training data: 28 500 synthetic VN line crops (48 px height, light
  JPEG augmentation) — see `nrl-ai/vn-ocr-rec-train-30k`
- Validation: 1 500 lines (5 % held-out)
- Dictionary: 689 chars (full VN tone-vowel matrix + Latin + digits +
  punctuation)
- Optimizer: Adam, β1=0.9, β2=0.999, L2 reg 3e-5
- LR: Cosine, peak 5e-5, warmup 1 epoch
- Batch: 64 with multi-scale sampler (32x320, 48x320, 64x320 height)
- Hardware: single RTX 3090 24 GB
- Time: ~70 minutes wall-clock for 25 epochs (15 525 iters)
- Best val: epoch 25, acc 0.789, norm_edit_dist 0.962

## Roadmap

For v2 (target: beat Tesseract on real-scan median CER):

1. Add real VN line crops from
   [`brianhuster/VietnameseOCRdataset`](https://huggingface.co/datasets/brianhuster/VietnameseOCRdataset)
   (Apache 2.0, 7 296 images)
2. Synthesize 50 k more crops with stamp/watermark/multi-font overlays
   to model real-scan artifacts
3. Train 50+ epochs with more aggressive augmentation (`RecConAug`
   prob=0.7, `RecAug` defaults)
4. Try `PP-OCRv5_server_rec` (larger arch, +3-5 pp typical lift)
5. Stretch: fine-tune the detector too on VN page layouts

## Reproduction

Full pipeline (data gen → training → eval) in the
[`nom-vn` repo](https://github.com/nrl-ai/nom-vn):

```
training/paddleocr_vi_rec/
  _generate_lines.py    — generate 30 k VN line crops
  PP-OCRv5_vi_rec_finetune.yml — training config
  launch_remote.sh       — rsync + nohup launch on remote GPU
  export_inference.sh    — export trainable .pdparams to inference fmt
  eval_on_real.py        — bench on the 9 real-scan corpus
```

## Citation

```bibtex
@misc{nguyen_vn_paddleocr_rec_v1_2026,
  author = {Nguyen, Viet-Anh and {Neural Research Lab}},
  title  = {{vn-paddleocr-rec-finetune-v1: Vietnamese fine-tune of
             PP-OCRv5_mobile_rec, methodology study}},
  year   = {2026},
  url    = {https://huggingface.co/nrl-ai/vn-paddleocr-rec-finetune-v1}
}
```
"""

DATASET_CARD = """\
---
license: cc-by-4.0
language:
- vi
task_categories:
- image-to-text
tags:
- ocr
- vietnamese
- training-data
- text-recognition
- paddleocr
size_categories:
- 10K<n<100K
private: true
---

# vn-ocr-rec-train-30k

30 000 synthetic Vietnamese line crops for fine-tuning OCR rec models.
Built for PaddleOCR PP-OCRv5_mobile_rec but format-agnostic.

## Source content

21 170 unique Vietnamese sentences sampled from in-tree corpora:

| Source | Sentences | Domain | License |
|---|---:|---|---|
| wiki_vi (Wikipedia VN article extracts) | 17 592 | Encyclopedia / news | CC-BY-SA 4.0 |
| tatoeba_vi | 3 078 | Conversational | CC-BY 2.0 FR |
| business_tpl (synthetic VN forms) | 2 335 | Receipt / contract / form | CC0 |
| wikisource Truyện Kiều | 181 | Classical literary | Public Domain |
| UDHR-vie | 168 | Formal / legal | Public Domain |

## Render specifics

- Height: 48 px (matches PaddleOCR PP-OCRv5 mobile rec input)
- Variable width: 80-1 200 px proportional to text length
- Fonts: DejaVuSans / DejaVuSans-Bold / DejaVuSerif / DejaVuSansMono
  (rotated per crop)
- Augmentation: JPEG round-trip at 78-92 % quality (PaddleOCR's
  `RecAug` adds the rest at training time)
- Format: PNG, RGB

## Files

```text
images/00000000.png … 00029999.png  — 30 000 line crops, ~600 MB total
train_list.txt                       — 28 500 lines: "images/<id>.png\\t<label>"
val_list.txt                         — 1 500 lines (5 % held-out)
vi_dict.txt                          — 689-char dictionary (one char/line)
```

## Why ground truth is perfect

The labels are the rendering inputs — there's no OCR-to-gold step
that could introduce noise. Every char in the label is the char that
was drawn on the canvas, in NFC form.

## Limitations

- **Synthetic only** — clean DejaVuSans rendering is easier than real
  chinhphu.vn scans (the eval set in `nrl-ai/vn-ocr-documents-eval`
  v0.4 / config=real). The model trained on this set hits 78.9 % val
  acc but only 15.08 % CER on real scans.
- **No layout** — line-level only, no page structure / multi-column
  / table / form layout.
- **No handwriting** — printed text only.

For v2 corpus expansion, see the model card of
`nrl-ai/vn-paddleocr-rec-finetune-v1`.

## Reproduction

```bash
git clone https://github.com/nrl-ai/nom-vn
cd nom-vn
pip install -e ".[dev]"  # PIL + reportlab
python training/paddleocr_vi_rec/_generate_lines.py --target-images 30000
```

The generator is deterministic — same seed → same bytes.

## Citation

```bibtex
@dataset{nguyen_vn_ocr_rec_train_30k_2026,
  author = {Nguyen, Viet-Anh and {Neural Research Lab}},
  title  = {{vn-ocr-rec-train-30k: Synthetic Vietnamese line-crop OCR
             training corpus}},
  year   = {2026},
  url    = {https://huggingface.co/datasets/nrl-ai/vn-ocr-rec-train-30k}
}
```
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Stage only, don't push.")
    args = parser.parse_args()

    from huggingface_hub import HfApi, create_repo

    api = HfApi()

    # ---------- MODEL ----------
    print(f"=== {MODEL_REPO} (private) ===")
    model_files: list[tuple[Path, str]] = []
    inference_dir = REPO / "training/paddleocr_vi_rec/checkpoints/vi_rec_finetune/inference"
    for fn in ("inference.json", "inference.pdiparams", "inference.yml"):
        src = inference_dir / fn
        if src.exists():
            model_files.append((src, fn))

    # Also ship the dictionary file alongside the model so users can
    # use it as a drop-in
    dict_src = REPO / "training/paddleocr_vi_rec/data/vi_dict.txt"
    if dict_src.exists():
        model_files.append((dict_src, "vi_dict.txt"))

    # README + eval JSON
    readme_path = Path("/tmp/vn_paddleocr_model_readme.md")
    readme_path.write_text(MODEL_CARD, encoding="utf-8")
    model_files.append((readme_path, "README.md"))

    eval_src = REPO / "benchmarks/results/baseline_paddleocr_v5_vi_finetune.json"
    if eval_src.exists():
        model_files.append((eval_src, "eval_real_scan_n9.json"))

    print(f"  staged {len(model_files)} files")
    for src, dst in model_files:
        print(f"    {dst} ({src.stat().st_size} B)")

    if not args.dry_run:
        try:
            create_repo(MODEL_REPO, repo_type="model", exist_ok=True, private=True)
        except Exception as exc:
            print(f"create_repo: {exc}")
        for src, dst in model_files:
            api.upload_file(
                path_or_fileobj=str(src),
                path_in_repo=dst,
                repo_id=MODEL_REPO,
                repo_type="model",
            )
        print(f"  pushed → https://huggingface.co/{MODEL_REPO}")

    # ---------- DATASET ----------
    print(f"\n=== {DATASET_REPO} (private) ===")
    data_dir = REPO / "training/paddleocr_vi_rec/data"
    if not data_dir.exists():
        print(f"error: {data_dir} missing — run _generate_lines.py first")
        return 1

    img_count = len(list((data_dir / "images").glob("*.png")))
    train_n = sum(1 for _ in (data_dir / "train_list.txt").open(encoding="utf-8"))
    val_n = sum(1 for _ in (data_dir / "val_list.txt").open(encoding="utf-8"))
    print(f"  images: {img_count}, train: {train_n}, val: {val_n}")

    dataset_readme = Path("/tmp/vn_ocr_train_30k_readme.md")
    dataset_readme.write_text(DATASET_CARD, encoding="utf-8")

    if args.dry_run:
        print(f"  would push {data_dir} (~{img_count} pngs + 3 metadata files + README)")
        print("\nDRY RUN — nothing pushed. Re-run without --dry-run to publish.")
        return 0

    try:
        create_repo(DATASET_REPO, repo_type="dataset", exist_ok=True, private=True)
    except Exception as exc:
        print(f"create_repo: {exc}")

    # Bulk upload via upload_folder
    api.upload_folder(
        folder_path=str(data_dir),
        repo_id=DATASET_REPO,
        repo_type="dataset",
        commit_message="v1.0: 30 k synthetic VN line crops + dict + train/val splits",
    )
    api.upload_file(
        path_or_fileobj=str(dataset_readme),
        path_in_repo="README.md",
        repo_id=DATASET_REPO,
        repo_type="dataset",
    )
    print(f"  pushed → https://huggingface.co/datasets/{DATASET_REPO}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
