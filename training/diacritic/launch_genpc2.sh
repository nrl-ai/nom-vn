#!/bin/bash
# Launch a training run on the remote GPU host in the background, immune to
# SSH timeouts.
#
# The remote host is configurable via $TRAIN_HOST (default: "genpc2", our
# in-house workstation). Override to point at any reachable SSH host that
# has the conda env "nom-train" prepared.
#
# Usage:
#   ./training/diacritic/launch_genpc2.sh                       # default args
#   ./training/diacritic/launch_genpc2.sh --epochs 5            # forward to train.py
#   TRAIN_HOST=otherbox ./training/diacritic/launch_genpc2.sh   # different remote
#
# Side effects on the remote host:
#   ~/nom-vn-train/training/diacritic/run.log   -- stdout+stderr
#   ~/nom-vn-train/training/diacritic/run.pid   -- PID of the python process
#
# Tail the log:
#   ssh "$TRAIN_HOST" 'tail -f ~/nom-vn-train/training/diacritic/run.log'
#
# Stop:
#   ssh "$TRAIN_HOST" 'kill $(cat ~/nom-vn-train/training/diacritic/run.pid)'

set -euo pipefail

TRAIN_HOST="${TRAIN_HOST:-genpc2}"
REMOTE_DIR="\$HOME/nom-vn-train"
ARGS="${*:---epochs 3 --batch-size 32 --bf16 --output-dir training/diacritic/checkpoints/mt5-small-200k}"

# Sync code + data first.
echo "rsync -> $TRAIN_HOST ..."
rsync -a training/diacritic/ "$TRAIN_HOST":nom-vn-train/training/diacritic/
rsync -a benchmarks/data/diacritic_eval_v0.txt "$TRAIN_HOST":nom-vn-train/benchmarks/data/
rsync -a benchmarks/data/ud_vi_vtb/test.conllu "$TRAIN_HOST":nom-vn-train/benchmarks/data/ud_vi_vtb/
rsync -a benchmarks/data/tatoeba_vi/diacritic_eval_300.txt \
    "$TRAIN_HOST":nom-vn-train/benchmarks/data/tatoeba_vi/
rsync -a benchmarks/data/udhr_vi/diacritic_eval_udhr.txt \
    "$TRAIN_HOST":nom-vn-train/benchmarks/data/udhr_vi/
rsync -a src/nom "$TRAIN_HOST":nom-vn-train/src/

# Kick off via nohup so SSH disconnect doesn't kill it.
ssh "$TRAIN_HOST" "
  source ~/miniconda3/etc/profile.d/conda.sh
  conda activate nom-train
  cd ~/nom-vn-train

  # If a previous run is still alive, abort.
  if [ -f training/diacritic/run.pid ] && kill -0 \$(cat training/diacritic/run.pid) 2>/dev/null; then
    echo 'Previous training still running (pid '\$(cat training/diacritic/run.pid)'). Aborting.' >&2
    exit 1
  fi

  nohup python training/diacritic/train.py $ARGS \
    > training/diacritic/run.log 2>&1 &
  echo \$! > training/diacritic/run.pid
  echo 'launched pid='\$(cat training/diacritic/run.pid)
"

echo
echo "Tail log:    ssh \"$TRAIN_HOST\" 'tail -f ~/nom-vn-train/training/diacritic/run.log'"
echo "Stop:        ssh \"$TRAIN_HOST\" 'kill \$(cat ~/nom-vn-train/training/diacritic/run.pid)'"
echo "Status:      ssh \"$TRAIN_HOST\" 'ps -p \$(cat ~/nom-vn-train/training/diacritic/run.pid) || echo not running'"
