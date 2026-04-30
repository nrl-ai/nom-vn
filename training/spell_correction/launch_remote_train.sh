#!/bin/bash
# Launch a spell-correction training run on a remote GPU host.
#
# Mirrors training/diacritic/launch_remote_train.sh but rsyncs the
# spell-correction tree + the spell-correction eval set.
#
# The remote host MUST be set via $TRAIN_HOST. Point at any reachable
# SSH host with the conda env "nom-train" prepared.

set -euo pipefail

TRAIN_HOST="${TRAIN_HOST:?TRAIN_HOST env var must be set, e.g. TRAIN_HOST=mybox}"
ARGS="${*:---epochs 5 --batch-size 32 --bf16 --output-dir training/spell_correction/checkpoints/vit5-base-500k}"

# Sync code + data + eval set first.
echo "rsync -> $TRAIN_HOST ..."
rsync -a training/spell_correction/ "$TRAIN_HOST":nom-vn-train/training/spell_correction/
# Eval corpora (the noisy/clean pairs across 8 splits).
rsync -a benchmarks/data/spell_correction_eval/ \
    "$TRAIN_HOST":nom-vn-train/benchmarks/data/spell_correction_eval/
# Diacritic train.py is imported as a sibling for the metric helpers.
rsync -a training/diacritic/train.py "$TRAIN_HOST":nom-vn-train/training/diacritic/train.py
rsync -a src/nom "$TRAIN_HOST":nom-vn-train/src/

# Kick off via nohup so SSH disconnect doesn't kill it.
ssh "$TRAIN_HOST" "
  source ~/miniconda3/etc/profile.d/conda.sh
  conda activate nom-train
  cd ~/nom-vn-train

  if [ -f training/diacritic/run.pid ] && kill -0 \$(cat training/diacritic/run.pid) 2>/dev/null; then
    echo 'Previous training (diacritic pid '\$(cat training/diacritic/run.pid)') still running. Aborting.' >&2
    exit 1
  fi
  if [ -f training/spell_correction/run.pid ] && kill -0 \$(cat training/spell_correction/run.pid) 2>/dev/null; then
    echo 'Previous training (spell pid '\$(cat training/spell_correction/run.pid)') still running. Aborting.' >&2
    exit 1
  fi

  nohup python training/spell_correction/train.py $ARGS \
    > training/spell_correction/run.log 2>&1 &
  echo \$! > training/spell_correction/run.pid
  echo 'launched pid='\$(cat training/spell_correction/run.pid)
"

echo
echo "Tail log:    ssh \"$TRAIN_HOST\" 'tail -f ~/nom-vn-train/training/spell_correction/run.log'"
echo "Stop:        ssh \"$TRAIN_HOST\" 'kill \$(cat ~/nom-vn-train/training/spell_correction/run.pid)'"
echo "Status:      ssh \"$TRAIN_HOST\" 'ps -p \$(cat ~/nom-vn-train/training/spell_correction/run.pid) || echo not running'"
