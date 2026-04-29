#!/usr/bin/env bash
# Post-training pipeline: rsync genpc2 → local re-eval → dry-run publish.
#
# Run this AFTER ./launch_genpc2.sh has produced a final checkpoint on
# genpc2. Sequence:
#
#   1. rsync the checkpoint dir + training_summary.json back to local.
#   2. Re-eval the checkpoint locally; fail loudly if word-acc diverges
#      from the genpc2 numbers by more than ±0.5 pp on any register.
#   3. Run publish_hf.py --dry-run to print the upload plan and gate
#      status. If the gate passes, the operator can rerun without
#      --dry-run to actually push.
#
# Usage::
#
#     ./training/diacritic/post_train.sh \
#         training/diacritic/checkpoints/vit5-base-500k-cosine \
#         nrl-ai/vn-diacritic-restoration
#
# The two args are: (a) the local output-dir from launch_genpc2.sh, and
# (b) the target HF repo id. The remote path is derived as the same
# relative path under ~/nom-vn-train/ on genpc2.

set -euo pipefail

if [ $# -lt 2 ]; then
    echo "Usage: $0 <local-output-dir> <hf-repo-id>" >&2
    echo "Example: $0 training/diacritic/checkpoints/vit5-base-500k-cosine nrl-ai/vn-diacritic-restoration" >&2
    exit 2
fi

LOCAL_DIR="$1"
HF_REPO_ID="$2"
REMOTE_DIR="nom-vn-train/$LOCAL_DIR"

CHECKPOINT_DIR="$LOCAL_DIR/final"
SUMMARY_JSON="$LOCAL_DIR/training_summary.json"
LOCAL_EVAL_JSON="training/diacritic/results/$(basename "$LOCAL_DIR")_eval_local.json"

# --- Step 1: rsync ---
echo "==> [1/3] rsync $REMOTE_DIR/ -> $LOCAL_DIR/"
mkdir -p "$LOCAL_DIR"
rsync -av --progress \
    "genpc2:$REMOTE_DIR/final/" \
    "$LOCAL_DIR/final/"
rsync -av \
    "genpc2:$REMOTE_DIR/training_summary.json" \
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
    print(f'    {name:24s} word_acc = {m[\"word_accuracy\"]*100:.2f}%  ms/sent = {m.get(\"mean_ms_per_sentence\", 0):.0f}')
"

# --- Step 2: local re-eval ---
echo
echo "==> [2/3] local re-eval (sanity check that genpc2 numbers reproduce)"
python training/diacritic/eval_checkpoint.py \
    --checkpoint "$CHECKPOINT_DIR" \
    --output-json "$LOCAL_EVAL_JSON" \
    --examples 0

echo
echo "  Comparison (genpc2 vs local re-eval):"
python -c "
import json
remote = json.load(open('$SUMMARY_JSON')).get('eval', {})
local = json.load(open('$LOCAL_EVAL_JSON')).get('eval', {})
print(f'  {\"register\":<24s} {\"genpc2\":>8s} {\"local\":>8s} {\"delta\":>8s}')
diverged = False
for name in sorted(set(remote) | set(local)):
    r = remote.get(name, {}).get('word_accuracy')
    l = local.get(name, {}).get('word_accuracy')
    if r is None or l is None:
        print(f'  {name:<24s} {str(r):>8s} {str(l):>8s}    -- ')
        continue
    delta_pp = (l - r) * 100
    flag = '' if abs(delta_pp) <= 0.5 else '  *DIVERGED*'
    if abs(delta_pp) > 0.5:
        diverged = True
    print(f'  {name:<24s} {r*100:>7.2f}% {l*100:>7.2f}% {delta_pp:>+7.2f}pp{flag}')
import sys
if diverged:
    print()
    print('FAIL: at least one register diverged by >0.5 pp. Investigate before publishing.', file=sys.stderr)
    sys.exit(1)
"

# --- Step 3: dry-run publish ---
echo
echo "==> [3/3] publish dry-run (check gate, generate model card)"
python training/diacritic/publish_hf.py \
    --checkpoint-dir "$CHECKPOINT_DIR" \
    --summary-json "$SUMMARY_JSON" \
    --repo-id "$HF_REPO_ID" \
    --dry-run

echo
echo "==> All steps green."
echo "    To actually publish, re-run without --dry-run:"
echo
echo "    python training/diacritic/publish_hf.py \\"
echo "        --checkpoint-dir $CHECKPOINT_DIR \\"
echo "        --summary-json $SUMMARY_JSON \\"
echo "        --repo-id $HF_REPO_ID"
