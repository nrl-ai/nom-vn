# PaddleOCR PP-OCRv5 Vietnamese rec — fine-tune

## Why

Default PaddleOCR `lang='vi'` loads `latin_PP-OCRv5_mobile_rec`, a generic
Latin recognizer that **drops Vietnamese tone marks**. Measured on the
9 real chinhphu / hanoi.gov.vn scans in `nrl-ai/vn-ocr-documents-eval`
v0.4 / config=real:

| Engine | Mean CER | Median CER |
|---|---:|---:|
| Tesseract `vie+eng` | 12.62 % | 11.99 % |
| PaddleOCR PP-OCRv5 `lang='vi'` (default) | 20.74 % | 19.33 % |

Goal: fine-tune the recognizer on a Vietnamese character dictionary so
diacritic-stripping is gone, then beat Tesseract.

## Pipeline

```text
_generate_lines.py           — render 30 k VN line-crops with light scan noise
                                (uses 21 k unique sentences from in-tree corpora)
PP-OCRv5_vi_rec_finetune.yml — config: SVTR_LCNet rec, batch=64, lr=5e-5,
                                25 epochs, fine-tune from latin checkpoint
launch_remote.sh             — rsync corpus to TRAIN_HOST, kick off
                                tools/train.py under nohup
export_inference.sh          — after training, export trainable .pdparams
                                to inference format + rsync back
eval_on_real.py              — load fine-tuned checkpoint into PaddleOCR
                                pipeline, bench on the 9 real-scan docs
```

## How to run end-to-end

```bash
# 1. Generate training data (locally, ~25 min on CPU)
python training/paddleocr_vi_rec/_generate_lines.py --target-images 30000

# 2. Sync + launch on remote GPU (TRAIN_HOST is your SSH alias)
TRAIN_HOST=mygpu ./training/paddleocr_vi_rec/launch_remote.sh

# 3. Tail training log on the remote
ssh $TRAIN_HOST tail -f ~/nom-vn-train/training/paddleocr_vi_rec/train.log

# 4. After training (~3-4 h on RTX 3090), export + sync back
TRAIN_HOST=mygpu ./training/paddleocr_vi_rec/export_inference.sh

# 5. Eval locally on the real-scan corpus
python training/paddleocr_vi_rec/eval_on_real.py \
    --checkpoint training/paddleocr_vi_rec/checkpoints/vi_rec_finetune/inference
```

## Hardware required

Per upstream PaddleOCR config, `batch_size_per_card=128` is the default
on 8× A100. We scale to a **single 24 GB GPU** at `batch=64` with
`lr=5e-5` (linearly scaled down 16×). Fits comfortably in RTX 3090 /
A10 / RTX 4090 with mixed precision.

| Setup | Batch / card | Effective LR | Time / 25 epochs on 30 k samples |
|---|---:|---:|---|
| RTX 3090 / 4090 (24 GB) | 64 | 5e-5 | ~3-5 hours |
| A100 80 GB | 128 | 1e-4 (default) | 1-2 hours |
| Consumer 12 GB (e.g. RTX 4070) | 24 | 1.5e-5 | 8-12 hours |
| Consumer 8 GB | 8-12 | 5e-6 | proof-of-concept only |

## Acceptance gate

The fine-tuned recognizer ships only when median CER on the 9 real-scan
docs **beats Tesseract's 11.99 %**. Otherwise we keep Tesseract as the
default and document the negative result.

## Honest limitations

- 30 k synthetic line-crops is the floor for fine-tuning. Real production
  models train on 100 k-1 M lines. For a publishable artifact, expand by
  pulling from `tmnam20/Vietnamese-News-dedup` (1 M+ sentences) and
  rendering across more font variations + handwriting glyph fonts.
- The pretrained latin checkpoint already handles French / Spanish /
  Portuguese well, so we expect rapid convergence in the first few
  epochs (the rec backbone learns Latin character shapes that share
  most of VN's character set; only tone-mark heads need to learn).
- No detection fine-tune — we keep `PP-OCRv5_server_det` as-is. The
  detector generalizes to VN page layouts well; the bottleneck is the
  recognizer.
