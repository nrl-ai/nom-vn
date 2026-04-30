#!/usr/bin/env bash
# Rsync v2 corpora + the chain runner to the remote GPU host, then kick
# off training/_chain_v229.sh under nohup so it survives SSH disconnect.
#
# Pre-reqs:
#   - $TRAIN_HOST set (e.g. exported in ~/.zshrc)
#   - The current spell-correction-base v0.2.29 run is already in flight
#     on the remote (the chain waits for that pid to clear before
#     starting stage B).
#
# Usage::
#
#   ./scripts/queue_v229_chain.sh

set -euo pipefail

TRAIN_HOST="${TRAIN_HOST:?TRAIN_HOST env var must be set, e.g. TRAIN_HOST=mybox}"

REMOTE="$TRAIN_HOST:nom-vn-train"

echo "==> rsync corpora -> $TRAIN_HOST"
# Spell-correction v2 train + val (already on remote from earlier
# launch but re-syncing is cheap and idempotent).
rsync -av --info=progress2 \
    training/spell_correction/data/train_v2.jsonl \
    training/spell_correction/data/val_v2.jsonl \
    training/spell_correction/data/stats_v2.json \
    "$REMOTE/training/spell_correction/data/"

# Diacritic v2 train + val (new, not yet on remote).
rsync -av --info=progress2 \
    training/diacritic/data/train_v2_nfc.jsonl \
    training/diacritic/data/val_v2_nfc.jsonl \
    "$REMOTE/training/diacritic/data/"

# Chain runner.
rsync -av training/_chain_v229.sh "$REMOTE/training/_chain_v229.sh"
ssh "$TRAIN_HOST" "chmod +x nom-vn-train/training/_chain_v229.sh"

echo
echo "==> launching chain under nohup"
ssh "$TRAIN_HOST" "
    cd nom-vn-train
    if [ -f training/v229_chain.pid ] && kill -0 \$(cat training/v229_chain.pid) 2>/dev/null; then
        echo 'chain already running pid='\$(cat training/v229_chain.pid)
        exit 1
    fi
    nohup ./training/_chain_v229.sh > training/v229_chain_runner.log 2>&1 &
    echo \$! > training/v229_chain.pid
    echo 'chain launched pid='\$(cat training/v229_chain.pid)
"

echo
echo "Tail chain log:"
echo "  ssh \"$TRAIN_HOST\" 'tail -f ~/nom-vn-train/training/v229_chain.log'"
echo
echo "Kill chain (and the active stage):"
echo "  ssh \"$TRAIN_HOST\" 'kill \$(cat ~/nom-vn-train/training/v229_chain.pid)'"
