#!/usr/bin/env bash
# Run the full RAG model grid against the 5k Zalo Legal QA fixture.
#
# Output goes to benchmarks/rag/baselines/zalo_5k__<embedder>__<reranker>.json
# so each (embedder × reranker) pair is one file. Re-run is idempotent
# (overwrites the matching baseline).
#
# Usage:
#   bash benchmarks/rag/run_grid.sh           # all 6 conditions
#   bash benchmarks/rag/run_grid.sh quick     # subset (skip 2GB AITeamVN)
#
# Per CLAUDE.md component build workflow rule #5: same fixture, same warmup
# protocol, same metrics across the grid — so cells are comparable.

set -euo pipefail

cd "$(dirname "$0")/../.."

FIXTURE="benchmarks/rag/fixtures/vn_legal_zalo_5k.json"
BASELINES="benchmarks/rag/baselines"
N_WARMUP=1
N_TIMED=2

run_one() {
  local embedder="$1"
  local emb_short="$2"
  local reranker="$3"
  local rr_short="$4"

  local retrievers="bm25,dense,hybrid"
  local extra=""
  if [ -n "$reranker" ]; then
    retrievers="bm25,dense,hybrid,hybrid+rerank"
    extra="--reranker $reranker"
  fi

  local out="$BASELINES/zalo_5k__${emb_short}__${rr_short}.json"
  echo
  echo "=== embedder=$emb_short reranker=$rr_short -> $out ==="
  python benchmarks/rag/bench_rag_vn.py \
    --fixture "$FIXTURE" \
    --embedder "$embedder" \
    --device auto \
    --retrievers "$retrievers" \
    $extra \
    --rerank-candidates 30 \
    --n-warmup $N_WARMUP --n-timed $N_TIMED \
    --json "$out"
}

QUICK="${1:-full}"

# Always run: dangvantuan with each reranker
run_one vietnamese dangvantuan "" no_rerank
run_one vietnamese dangvantuan BAAI/bge-reranker-v2-m3 bge_v2_m3
run_one vietnamese dangvantuan namdp-ptit/ViRanker viranker

if [ "$QUICK" != "quick" ]; then
  # AITeamVN/Vietnamese_Embedding is 2.3 GB — skip in quick mode.
  run_one aiteamvn aiteamvn "" no_rerank
  run_one aiteamvn aiteamvn BAAI/bge-reranker-v2-m3 bge_v2_m3
  run_one aiteamvn aiteamvn namdp-ptit/ViRanker viranker
fi

echo
echo "=== grid done ==="
ls -1 "$BASELINES"/zalo_5k__*.json
