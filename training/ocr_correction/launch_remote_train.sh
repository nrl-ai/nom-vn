#!/bin/bash
# Fine-tune nrl-ai/vn-spell-correction-base on a (OCR output, GT) corpus
# for OCR post-correction. Mirrors training/{diacritic,spell_correction}/
# launch_remote_train.sh but starts from the spell-correction-base
# checkpoint (lower LR, fewer epochs) and reads the OCR-pair corpus
# under training/ocr_correction/data/.
#
# Pre-reqs:
#   - $TRAIN_HOST set
#   - prep_data.py has produced training/ocr_correction/data/{train,val}.jsonl
#
# Usage:
#   TRAIN_HOST=mybox ./training/ocr_correction/launch_remote_train.sh
#   TRAIN_HOST=mybox ./training/ocr_correction/launch_remote_train.sh --epochs 5

set -euo pipefail

TRAIN_HOST="${TRAIN_HOST:?TRAIN_HOST env var must be set, e.g. TRAIN_HOST=mybox}"

# Defaults: continue training from the shipped spell-correction model,
# 3 epochs (the OCR corpus is ~10K pairs vs 459K for the original
# spell-correction run — fewer epochs avoid overfitting), LR 1e-5
# (low — fine-tuning, not from scratch).
ARGS="${*:---model-id nrl-ai/vn-spell-correction-base \
    --train-jsonl training/ocr_correction/data/train.jsonl \
    --val-jsonl training/ocr_correction/data/val.jsonl \
    --epochs 3 --batch-size 16 --bf16 \
    --lr 1e-5 --lr-scheduler cosine \
    --warmup-steps 100 --early-stopping-patience 0 \
    --eval-steps 500 --save-steps 500 --logging-steps 100 \
    --eval-samples 1000 \
    --output-dir training/ocr_correction/checkpoints/vit5-ocr-correct}"

echo "rsync -> $TRAIN_HOST ..."
rsync -a training/ocr_correction/ "$TRAIN_HOST":nom-vn-train/training/ocr_correction/
# spell_correction's train.py is the trainer we reuse.
rsync -a training/spell_correction/train.py \
    "$TRAIN_HOST":nom-vn-train/training/spell_correction/train.py
# Diacritic train.py is imported as a sibling for metric helpers.
rsync -a training/diacritic/train.py "$TRAIN_HOST":nom-vn-train/training/diacritic/train.py
# Eval set the trainer reads for monitoring (orthogonal to OCR but
# trainer expects it to exist).
rsync -a benchmarks/data/spell_correction_eval/ \
    "$TRAIN_HOST":nom-vn-train/benchmarks/data/spell_correction_eval/
rsync -a src/nom "$TRAIN_HOST":nom-vn-train/src/

ssh "$TRAIN_HOST" "
  source ~/miniconda3/etc/profile.d/conda.sh
  conda activate nom-train
  cd ~/nom-vn-train

  if [ -f training/ocr_correction/run.pid ] && kill -0 \$(cat training/ocr_correction/run.pid) 2>/dev/null; then
    echo 'Previous OCR-correction training still running.' >&2; exit 1
  fi

  nohup python training/spell_correction/train.py $ARGS \
    > training/ocr_correction/run.log 2>&1 &
  echo \$! > training/ocr_correction/run.pid
  echo 'launched pid='\$(cat training/ocr_correction/run.pid)
"

echo
echo "Tail log:    ssh \"$TRAIN_HOST\" 'tail -f ~/nom-vn-train/training/ocr_correction/run.log'"
echo "Stop:        ssh \"$TRAIN_HOST\" 'kill \$(cat ~/nom-vn-train/training/ocr_correction/run.pid)'"
