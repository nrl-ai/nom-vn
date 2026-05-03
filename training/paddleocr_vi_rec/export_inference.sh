#!/usr/bin/env bash
# After training finishes, export the best checkpoint to PaddleOCR
# inference format. The eval script consumes that exported dir via
# `text_recognition_model_dir=...` parameter on the PaddleOCR pipeline.

set -euo pipefail

: "${TRAIN_HOST:?set TRAIN_HOST to your SSH alias for the GPU box}"
REMOTE_BASE='~/nom-vn-train/training/paddleocr_vi_rec'
LOCAL_REPO="$(git rev-parse --show-toplevel)"
LOCAL_DIR="$LOCAL_REPO/training/paddleocr_vi_rec"

echo "=== Export trainable checkpoint to inference format on $TRAIN_HOST ==="
ssh "$TRAIN_HOST" '
    cd ~/nom-vn-train/training/paddleocr_vi_rec
    source ~/nom-vn-train/.venv-paddle/bin/activate
    python ~/nom-vn-train/PaddleOCR/tools/export_model.py \
        -c PP-OCRv5_vi_rec_finetune.yml \
        -o Global.pretrained_model=./checkpoints/vi_rec_finetune/best_accuracy \
           Global.save_inference_dir=./checkpoints/vi_rec_finetune/inference
'

echo "=== rsync inference dir back to local ==="
mkdir -p "$LOCAL_DIR/checkpoints/vi_rec_finetune/inference"
rsync -av --info=progress2 \
    "$TRAIN_HOST:$REMOTE_BASE/checkpoints/vi_rec_finetune/inference/" \
    "$LOCAL_DIR/checkpoints/vi_rec_finetune/inference/"

echo
echo "=== Now eval locally ==="
echo "  python training/paddleocr_vi_rec/eval_on_real.py \\"
echo "      --checkpoint training/paddleocr_vi_rec/checkpoints/vi_rec_finetune/inference"
