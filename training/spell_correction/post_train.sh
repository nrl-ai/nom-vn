#!/usr/bin/env bash
# Post-training pipeline for spell-correction tier:
#   1. rsync the remote GPU host -> local
#   2. local re-eval against the 8-split grid (sanity check)
#   3. dry-run publish_hf.py to print the upload plan + gate status
#
# Mirror of training/diacritic/post_train.sh but reads
# benchmarks/data/spell_correction_eval/ instead of the diacritic
# 4-register grid, and uses spell_correction/eval_checkpoint.py.
#
# The remote SSH host is configurable via $TRAIN_HOST (default "genpc2").
#
# Usage::
#
#     ./training/spell_correction/post_train.sh \
#         training/spell_correction/checkpoints/bartpho-syllable-500k \
#         nrl-ai/vn-spell-correction-small

set -euo pipefail

if [ $# -lt 2 ]; then
    echo "Usage: $0 <local-output-dir> <hf-repo-id>" >&2
    echo "Example: $0 training/spell_correction/checkpoints/bartpho-syllable-500k nrl-ai/vn-spell-correction-small" >&2
    exit 2
fi

TRAIN_HOST="${TRAIN_HOST:-genpc2}"
LOCAL_DIR="$1"
HF_REPO_ID="$2"
REMOTE_DIR="nom-vn-train/$LOCAL_DIR"

CHECKPOINT_DIR="$LOCAL_DIR/final"
SUMMARY_JSON="$LOCAL_DIR/training_summary.json"
LOCAL_EVAL_JSON="training/spell_correction/results/$(basename "$LOCAL_DIR")_eval_local.json"

# --- Step 1: rsync ---
echo "==> [1/3] rsync $TRAIN_HOST:$REMOTE_DIR/ -> $LOCAL_DIR/"
mkdir -p "$LOCAL_DIR"
rsync -av --progress \
    "$TRAIN_HOST:$REMOTE_DIR/final/" \
    "$LOCAL_DIR/final/"
rsync -av \
    "$TRAIN_HOST:$REMOTE_DIR/training_summary.json" \
    "$LOCAL_DIR/"

if [ ! -f "$SUMMARY_JSON" ]; then
    echo "ERROR: $SUMMARY_JSON not found after rsync — did training finish?" >&2
    exit 1
fi

echo
echo "  Training summary:"
python -c "
import json
s = json.load(open('$SUMMARY_JSON'))
print(f'    base = {s[\"model_id\"]}')
print(f'    pairs = {s.get(\"train_pairs\", \"?\"):,}')
print(f'    minutes = {s.get(\"training_minutes\", \"?\")}')
for name, m in s.get('eval', {}).items():
    print(f'    {name:30s} word_acc = {m[\"word_accuracy\"]*100:.2f}%  ms/sent = {m.get(\"mean_ms_per_sentence\", 0):.0f}')
"

# --- Step 2: local re-eval ---
echo
echo "==> [2/3] local re-eval (sanity check that remote numbers reproduce)"
python training/spell_correction/eval_checkpoint.py \
    --checkpoint "$CHECKPOINT_DIR" \
    --output-json "$LOCAL_EVAL_JSON" \
    --examples 0

echo
echo "  Comparison (remote vs local re-eval):"
python -c "
import json
remote = json.load(open('$SUMMARY_JSON')).get('eval', {})
local = json.load(open('$LOCAL_EVAL_JSON')).get('eval', {})
print(f'  {\"register\":<30s} {\"remote\":>8s} {\"local\":>8s} {\"delta\":>8s}')
diverged = False
for name in sorted(set(remote) | set(local)):
    r = remote.get(name, {}).get('word_accuracy')
    l = local.get(name, {}).get('word_accuracy')
    if r is None or l is None:
        print(f'  {name:<30s} {str(r):>8s} {str(l):>8s}    -- ')
        continue
    delta_pp = (l - r) * 100
    flag = '' if abs(delta_pp) <= 0.5 else '  *DIVERGED*'
    if abs(delta_pp) > 0.5:
        diverged = True
    print(f'  {name:<30s} {r*100:>7.2f}% {l*100:>7.2f}% {delta_pp:>+7.2f}pp{flag}')
import sys
if diverged:
    print()
    print('FAIL: at least one register diverged by >0.5 pp. Investigate before publishing.', file=sys.stderr)
    sys.exit(1)
"

# --- Step 3: dry-run publish ---
echo
echo "==> [3/3] publish dry-run (check gate, generate model card)"
python training/spell_correction/publish_hf.py \
    --checkpoint-dir "$CHECKPOINT_DIR" \
    --summary-json "$SUMMARY_JSON" \
    --repo-id "$HF_REPO_ID" \
    --dry-run

echo
echo "==> All steps green."
echo "    To actually publish, re-run without --dry-run:"
echo
echo "    python training/spell_correction/publish_hf.py \\"
echo "        --checkpoint-dir $CHECKPOINT_DIR \\"
echo "        --summary-json $SUMMARY_JSON \\"
echo "        --repo-id $HF_REPO_ID"
