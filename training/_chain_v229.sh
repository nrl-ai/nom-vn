#!/usr/bin/env bash
# Chained v0.2.29 training launcher — runs sequentially on the remote
# GPU host while a single process holds the GPU. Each stage:
#
#   1. waits for the previous training pid to die (60s polls)
#   2. records start time
#   3. invokes train.py with the v2 corpus paths
#   4. logs to <stage>.log
#
# Stages:
#   A. spell-correction-base (vit5-base) on v2 corpus     — already running
#   B. spell-correction-small (BARTpho)  on v2 corpus
#   C. diacritic-base (vit5-base)        on v2 corpus
#
# Triggered by ./scripts/queue_v229_chain.sh from local — that script
# rsyncs corpora + this script then kicks it off via nohup.
#
# All paths are relative to ~/nom-vn-train (the rsync target on the
# remote host).

set -euo pipefail

WORKDIR="$HOME/nom-vn-train"
cd "$WORKDIR"

source ~/miniconda3/etc/profile.d/conda.sh
conda activate nom-train

LOG="training/v229_chain.log"

log() {
    printf '[%s] %s\n' "$(date +%FT%T%z)" "$*" | tee -a "$LOG"
}

wait_for_pid_file() {
    local pidfile="$1"
    if [ ! -f "$pidfile" ]; then
        log "no pidfile at $pidfile — assuming nothing running"
        return 0
    fi
    local pid
    pid="$(cat "$pidfile")"
    log "waiting for pid=$pid (from $pidfile) to exit ..."
    while kill -0 "$pid" 2>/dev/null; do
        sleep 60
    done
    log "pid=$pid exited"
}

###############################################################################
# Stage B — spell-correction-small (BARTpho-syllable) on v2 corpus
###############################################################################

stage_b() {
    log "=== stage B: spell-correction-small on v2 corpus ==="
    wait_for_pid_file training/spell_correction/run.pid

    local out="training/spell_correction/checkpoints/bartpho-syllable-v2-500k"
    log "launching train.py -> $out"
    nohup python training/spell_correction/train.py \
        --model-id vinai/bartpho-syllable-base \
        --train-jsonl training/spell_correction/data/train_v2.jsonl \
        --val-jsonl training/spell_correction/data/val_v2.jsonl \
        --epochs 5 --batch-size 32 --bf16 \
        --lr 5e-4 --lr-scheduler cosine \
        --warmup-steps 500 --early-stopping-patience 0 \
        --eval-steps 2000 --save-steps 2000 --logging-steps 200 \
        --eval-samples 1000 \
        --output-dir "$out" \
        > training/spell_correction/run.log 2>&1 &
    echo $! > training/spell_correction/run.pid
    log "stage B launched pid=$(cat training/spell_correction/run.pid)"

    # block until this stage finishes before moving on.
    wait_for_pid_file training/spell_correction/run.pid
}

###############################################################################
# Stage C — diacritic-base (vit5-base) on v2 multi-register corpus
###############################################################################

stage_c() {
    log "=== stage C: diacritic-base (ViT5) on v2 corpus ==="
    wait_for_pid_file training/diacritic/run.pid 2>/dev/null || true
    wait_for_pid_file training/spell_correction/run.pid

    local out="training/diacritic/checkpoints/vit5-base-v2-600k"
    log "launching train.py -> $out"
    nohup python training/diacritic/train.py \
        --model-id VietAI/vit5-base \
        --train-jsonl training/diacritic/data/train_v2_nfc.jsonl \
        --val-jsonl training/diacritic/data/val_v2_nfc.jsonl \
        --epochs 5 --batch-size 32 --bf16 \
        --lr 5e-4 --lr-scheduler cosine \
        --warmup-steps 500 --early-stopping-patience 0 \
        --eval-steps 2000 --save-steps 2000 --logging-steps 200 \
        --eval-samples 1000 \
        --output-dir "$out" \
        > training/diacritic/run.log 2>&1 &
    echo $! > training/diacritic/run.pid
    log "stage C launched pid=$(cat training/diacritic/run.pid)"

    wait_for_pid_file training/diacritic/run.pid
}

log "=============================================================="
log "chain start (stages B + C — A is the in-flight spell-base)"
log "=============================================================="
stage_b
stage_c
log "=============================================================="
log "chain done — three stages complete."
log "=============================================================="
