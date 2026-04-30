#!/usr/bin/env bash
# Post-training pipeline for spell-correction tier:
#   1. rsync the remote GPU host -> local
#   2. local re-eval against the 8-split synthetic grid (sanity check)
#   3. OOD real-world bench (150 sentences, 6 slices) — head-to-head
#      vs Toshiiiii1 + the previous shipped tier so the gain is visible
#   4. dry-run publish_hf.py to print the upload plan + gate status
#
# Mirror of training/diacritic/post_train.sh but reads
# benchmarks/data/spell_correction_eval/ instead of the diacritic
# 4-register grid, and uses spell_correction/eval_checkpoint.py.
#
# The remote SSH host MUST be set via $TRAIN_HOST (matching
# launch_remote_train.sh).
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

TRAIN_HOST="${TRAIN_HOST:?TRAIN_HOST env var must be set, e.g. TRAIN_HOST=mybox}"
LOCAL_DIR="$1"
HF_REPO_ID="$2"
REMOTE_DIR="nom-vn-train/$LOCAL_DIR"

CHECKPOINT_DIR="$LOCAL_DIR/final"
SUMMARY_JSON="$LOCAL_DIR/training_summary.json"
LOCAL_EVAL_JSON="training/spell_correction/results/$(basename "$LOCAL_DIR")_eval_local.json"

# Prefer the project venv (has sentencepiece + datasets installed).
# Falls back to system python only if no venv.
if [ -x ".venv/bin/python" ]; then
    PY=".venv/bin/python"
else
    PY="python"
fi

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
"$PY" -c "
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
"$PY" training/spell_correction/eval_checkpoint.py \
    --checkpoint "$CHECKPOINT_DIR" \
    --output-json "$LOCAL_EVAL_JSON" \
    --examples 0

echo
echo "  Comparison (remote vs local re-eval):"
"$PY" -c "
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

# --- Step 3: OOD real-world bench (the load-bearing eval) ---
echo
echo "==> [3/4] OOD real-world bench on $CHECKPOINT_DIR (150 sentences, 6 slices)"
LOCAL_OOD_JSON="training/spell_correction/results/$(basename "$LOCAL_DIR")_eval_real.json"
"$PY" benchmarks/accuracy/bench_spell_correction_real.py \
    "$CHECKPOINT_DIR" \
    --json "$LOCAL_OOD_JSON" \
    --examples 0

echo
echo "  OOD vs the public landscape (and prior shipped tier):"
"$PY" -c "
import json
ours = json.load(open('$LOCAL_OOD_JSON'))['eval']
others = {
    'Toshiiiii1 (public)': 'benchmarks/results/baseline_real_toshiiiii1.json',
    'spell-base v0.2.28 (prev)': 'benchmarks/results/baseline_real_spell_correction_base.json',
}
loaded = {k: json.load(open(p))['eval'] for k, p in others.items() if __import__('os').path.exists(p)}
slices = ['forum_25', 'mobile_25', 'telex_real_25', 'ocr_25', 'legal_real_25', 'news_real_25', '__all_real__']
header = ['this run'] + list(loaded)
print(f'  {\"slice\":<22s} ' + ' '.join(f'{h:>20s}' for h in header))
for sl in slices:
    row = [f'  {sl:<22s}']
    for src in ['this'] + list(loaded):
        d = ours if src == 'this' else loaded[src]
        wa = d.get(sl, {}).get('word_accuracy', 0) * 100
        row.append(f'{wa:>20.2f}')
    print(' '.join(row))
"

# --- Step 4: dry-run publish ---
echo
echo "==> [4/4] publish dry-run (check gate, generate model card)"
"$PY" training/spell_correction/publish_hf.py \
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
