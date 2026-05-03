#!/usr/bin/env bash
# Launch PaddleOCR PP-OCRv5_mobile_rec fine-tune for Vietnamese on a
# remote GPU host. Set TRAIN_HOST to your SSH alias.
#
# Pre-reqs (one-time on the remote):
#   - python3.12+ available as `python3`
#   - ~/nom-vn-train/.venv-paddle exists with paddlepaddle-gpu + paddleocr
#   - PaddleOCR repo cloned to ~/nom-vn-train/PaddleOCR (training tools)
#
# What this script does:
#   1. rsync the local training corpus + config + dict to the remote
#   2. Extract the latin_PP-OCRv5_mobile_rec checkpoint from paddleocr's
#      auto-download cache (so the rec model has weights to start from)
#   3. Launch `python tools/train.py -c config.yml` under nohup
#   4. Print the pid + log location so the operator can tail it

set -euo pipefail

: "${TRAIN_HOST:?set TRAIN_HOST to your SSH alias for the GPU box}"
LOCAL_REPO="$(git rev-parse --show-toplevel)"
LOCAL_DATA="$LOCAL_REPO/training/paddleocr_vi_rec"
REMOTE_BASE='~/nom-vn-train/training/paddleocr_vi_rec'

echo "=== rsync corpus + config to $TRAIN_HOST ==="
rsync -av --info=progress2 \
    --exclude='__pycache__' \
    --exclude='checkpoints/' \
    --exclude='pretrained/' \
    "$LOCAL_DATA/" "$TRAIN_HOST:$REMOTE_BASE/"

echo "=== Setup pretrained checkpoint + clone PaddleOCR repo if missing ==="
ssh "$TRAIN_HOST" '
    cd ~/nom-vn-train/training/paddleocr_vi_rec
    source ~/nom-vn-train/.venv-paddle/bin/activate

    # Clone PaddleOCR repo for training tools (if not already there).
    if [ ! -d ~/nom-vn-train/PaddleOCR ]; then
        git clone --depth 1 https://github.com/PaddlePaddle/PaddleOCR.git ~/nom-vn-train/PaddleOCR
    fi

    # Extract pretrained latin checkpoint from paddleocr cache. The
    # paddleocr CLI auto-downloads when you instantiate PaddleOCR(lang="vi").
    if [ ! -d pretrained/latin_PP-OCRv5_mobile_rec ]; then
        python -c "from paddleocr import PaddleOCR; PaddleOCR(lang=\"vi\")" || true
        mkdir -p pretrained
        cp -r ~/.paddlex/official_models/latin_PP-OCRv5_mobile_rec pretrained/
    fi
'

echo "=== Launch training under nohup ==="
ssh "$TRAIN_HOST" '
    cd ~/nom-vn-train/training/paddleocr_vi_rec
    source ~/nom-vn-train/.venv-paddle/bin/activate
    nohup python ~/nom-vn-train/PaddleOCR/tools/train.py \
        -c PP-OCRv5_vi_rec_finetune.yml \
        > train.log 2>&1 &
    PID=$!
    echo "Launched PaddleOCR training with PID=$PID"
    echo "Log: ~/nom-vn-train/training/paddleocr_vi_rec/train.log"
    echo "Tail: ssh $TRAIN_HOST tail -f ~/nom-vn-train/training/paddleocr_vi_rec/train.log"
'
