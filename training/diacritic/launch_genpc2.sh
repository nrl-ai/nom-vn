#!/bin/bash
# Launch a training run on genpc2 in the background, immune to SSH timeouts.
#
# Usage:
#   ./training/diacritic/launch_genpc2.sh                      # full default run
#   ./training/diacritic/launch_genpc2.sh --epochs 5           # custom args forwarded to train.py
#
# Side effects on genpc2:
#   ~/nom-vn-train/training/diacritic/run.log   -- stdout+stderr
#   ~/nom-vn-train/training/diacritic/run.pid   -- PID of the python process
#
# Tail the log:
#   ssh genpc2 'tail -f ~/nom-vn-train/training/diacritic/run.log'
#
# Stop:
#   ssh genpc2 'kill $(cat ~/nom-vn-train/training/diacritic/run.pid)'

set -euo pipefail

REMOTE_DIR="\$HOME/nom-vn-train"
ARGS="${*:---epochs 3 --batch-size 32 --bf16 --output-dir training/diacritic/checkpoints/mt5-small-200k}"

# Sync code + data first.
echo "rsync -> genpc2..."
rsync -a training/diacritic/ genpc2:nom-vn-train/training/diacritic/
rsync -a benchmarks/data/diacritic_eval_v0.txt genpc2:nom-vn-train/benchmarks/data/
rsync -a benchmarks/data/ud_vi_vtb/test.conllu genpc2:nom-vn-train/benchmarks/data/ud_vi_vtb/
rsync -a benchmarks/data/tatoeba_vi/diacritic_eval_300.txt \
    genpc2:nom-vn-train/benchmarks/data/tatoeba_vi/
rsync -a benchmarks/data/udhr_vi/diacritic_eval_udhr.txt \
    genpc2:nom-vn-train/benchmarks/data/udhr_vi/
rsync -a src/nom genpc2:nom-vn-train/src/

# Kick off via nohup so SSH disconnect doesn't kill it.
ssh genpc2 "
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
echo "Tail log:    ssh genpc2 'tail -f ~/nom-vn-train/training/diacritic/run.log'"
echo "Stop:        ssh genpc2 'kill \$(cat ~/nom-vn-train/training/diacritic/run.pid)'"
echo "Status:      ssh genpc2 'ps -p \$(cat ~/nom-vn-train/training/diacritic/run.pid) || echo not running'"
