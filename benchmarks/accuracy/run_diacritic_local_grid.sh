#!/bin/bash
# Run bench_diacritics.py across a grid of local quantized LLMs.
#
# Models are pulled via Ollama (Q4_K_M default). Target: identify
# the smallest local model that gets usable VN diacritic accuracy
# on user-machine hardware. CLAUDE.md §12 — warmup + per-call timing.
#
# Set OLLAMA_BASE_URL to point at a remote tunneled Ollama (e.g.
# http://localhost:11435 for an SSH tunnel to a beefier box).

set -uo pipefail
URL=${OLLAMA_BASE_URL:-http://localhost:11434}
WARMUP=${WARMUP:-3}
OUTDIR=${OUTDIR:-benchmarks/results/local_diacritic_grid}
mkdir -p "$OUTDIR"

MODELS=(
  "gemma4:e2b"
  "gemma4:e4b"
  "qwen3:4b"
  "qwen3:8b"
  "llama3.2:3b"
  "gemma3:4b"
)

echo "Diacritic bench grid · URL=$URL · warmup=$WARMUP · outdir=$OUTDIR"
echo

for m in "${MODELS[@]}"; do
  safe=$(echo "$m" | tr ':/' '__')
  out="$OUTDIR/diacritics_${safe}.json"
  echo "===== $m ====="
  python benchmarks/accuracy/bench_diacritics.py \
    --llm ollama \
    --llm-model "$m" \
    --ollama-base-url "$URL" \
    --warmup "$WARMUP" \
    --examples 0 \
    --json "$out" 2>&1 | grep -E 'Corpus|Overall|Latency|Warmup' || echo "[failed]"
  echo
done

echo "Done. JSON results in $OUTDIR/"
