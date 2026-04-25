"""Upload nom-vn RAG benchmarks (fixtures + baselines) to nrl-ai/vn-rag-bench.

Pushes:
  - benchmarks/rag/fixtures/*.json  -> repo root
  - benchmarks/rag/baselines/*.json -> repo root
  - The fixture builder script + a minimal README so the repo is reproducible.

Requires: ``hf auth login`` (or ``HF_TOKEN`` env var) with write access to
the ``nrl-ai`` org.

Run::

    python scripts/upload_bench_to_hf.py
    python scripts/upload_bench_to_hf.py --dry-run    # plan only, no push
    python scripts/upload_bench_to_hf.py --repo-id nrl-ai/vn-rag-bench-staging
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_REPO_ID = "nrl-ai/vn-rag-bench"

README_TEMPLATE = """\
---
license: mit
language: vi
tags:
  - vietnamese
  - retrieval
  - rag
  - legal
  - benchmark
---

# nom-vn RAG benchmarks

Reproducible benchmark fixtures and baseline results for the
[`nom-vn`](https://github.com/nrl-ai/nom-vn) Vietnamese RAG toolkit.

## Contents

### Fixtures (`fixtures/`)

JSON corpora + held-out queries used by `benchmarks/rag/bench_rag_vn.py`.
Each fixture is shaped:

```json
{
  "name": "...",
  "corpus":    [{"id": "...", "text": "..."}, ...],
  "questions": [{"q": "...", "gold_ids": ["...", ...]}, ...]
}
```

| File | Articles | Questions | Source |
|---|---|---|---|
| `vn_legal_tiny.json` | 12 | 12 | Hand-curated VN legal articles |
| `vn_legal_zalo_2k.json` | ~1.5k | 50 | Sample of [GreenNode/zalo-ai-legal-text-retrieval-vn](https://huggingface.co/datasets/GreenNode/zalo-ai-legal-text-retrieval-vn) (MIT) |
| `vn_legal_zalo_5k.json` | ~5k | 80 | Same source, larger sample |

### Baselines (`baselines/`)

Per-fixture, per-config bench result JSONs from
`benchmarks/rag/bench_rag_vn.py`. Each entry records the embedder,
reranker, hardware (`device`), warmup / timing protocol, and the full
metric block — so the numbers are auditable and re-runnable.

### Builder (`fixture_builder.py`)

Script that samples the GreenNode Zalo Legal QA mirror down to a
benchmark-ready fixture. See its docstring for usage. Lets anyone with
`pip install datasets` reproduce the fixtures bit-for-bit (seed=42 by
default).

## Reproducing

```bash
git clone https://github.com/nrl-ai/nom-vn
cd nom-vn
pip install -e ".[chat,otel]" datasets

# rebuild a fixture:
python benchmarks/rag/fixtures/_build_zalo_legal.py \\
    --n-questions 50 --n-distractors 1500 --seed 42 \\
    --out benchmarks/rag/fixtures/vn_legal_zalo_2k.json

# run the bench with real models on GPU:
python benchmarks/rag/bench_rag_vn.py \\
    --fixture benchmarks/rag/fixtures/vn_legal_zalo_2k.json \\
    --embedder vietnamese \\
    --reranker BAAI/bge-reranker-v2-m3 \\
    --retrievers bm25,dense,hybrid,hybrid+rerank \\
    --device auto \\
    --json benchmarks/rag/baselines/zalo_2k__dangvantuan__bge_v2_m3.json
```

## Licenses

This repo: **MIT**. Fixture corpora derive from
[GreenNode/zalo-ai-legal-text-retrieval-vn](https://huggingface.co/datasets/GreenNode/zalo-ai-legal-text-retrieval-vn)
(MIT), originally from the
[Zalo AI Challenge 2021 Legal Text Retrieval](https://challenge.zalo.ai/)
public corpus.

Bench results may reference embedder / reranker model IDs; consult each
upstream model card for that model's license (we standardise on
Apache-2.0 + safetensors per
[`CLAUDE.md`](https://github.com/nrl-ai/nom-vn/blob/main/CLAUDE.md)
file-format trust ladder).
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-id", default=DEFAULT_REPO_ID)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    fixtures_dir = REPO / "benchmarks" / "rag" / "fixtures"
    baselines_dir = REPO / "benchmarks" / "rag" / "baselines"
    builder = fixtures_dir / "_build_zalo_legal.py"

    fixtures = sorted(fixtures_dir.glob("*.json"))
    baselines = sorted(baselines_dir.glob("*.json"))

    print(f"target repo: {args.repo_id}")
    print(f"fixtures   : {len(fixtures)} files, {sum(f.stat().st_size for f in fixtures):,} bytes")
    print(f"baselines  : {len(baselines)} files")
    print(f"builder    : {builder.name}")
    if args.dry_run:
        print("\n--dry-run: not pushing")
        return 0

    try:
        from huggingface_hub import HfApi, create_repo
    except ImportError:
        print("huggingface_hub missing. pip install huggingface_hub", file=sys.stderr)
        return 2

    api = HfApi()
    create_repo(args.repo_id, repo_type="dataset", exist_ok=True)

    # README
    api.upload_file(
        path_or_fileobj=README_TEMPLATE.encode("utf-8"),
        path_in_repo="README.md",
        repo_id=args.repo_id,
        repo_type="dataset",
        commit_message="bench: README",
    )

    # Builder script
    api.upload_file(
        path_or_fileobj=str(builder),
        path_in_repo="fixture_builder.py",
        repo_id=args.repo_id,
        repo_type="dataset",
        commit_message="bench: fixture builder",
    )

    # Fixtures
    for f in fixtures:
        api.upload_file(
            path_or_fileobj=str(f),
            path_in_repo=f"fixtures/{f.name}",
            repo_id=args.repo_id,
            repo_type="dataset",
            commit_message=f"bench: fixture {f.name}",
        )

    # Baselines
    for b in baselines:
        api.upload_file(
            path_or_fileobj=str(b),
            path_in_repo=f"baselines/{b.name}",
            repo_id=args.repo_id,
            repo_type="dataset",
            commit_message=f"bench: baseline {b.name}",
        )

    print(f"\n→ pushed to https://huggingface.co/datasets/{args.repo_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
