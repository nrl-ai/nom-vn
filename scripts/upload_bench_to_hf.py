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
  - ocr
  - legal
  - benchmark
---

# nom-vn benchmarks

Reproducible benchmark fixtures and baseline results for the
[`nom-vn`](https://github.com/nrl-ai/nom-vn) Vietnamese AI toolkit.
Covers retrieval / RAG and Vietnamese OCR; more components arriving
in follow-up commits.

## Layout

```
fixtures/                  — input corpora (JSON) and tiny image sets
baselines/                 — bench result JSONs (small, version-controlled)
fixture_builder.py         — Zalo Legal QA sampler (regenerates fixtures)
```

## Why this exists

Per [`CLAUDE.md` principle 12](https://github.com/nrl-ai/nom-vn/blob/main/CLAUDE.md):
**every metric we publish must come from a committed-and-runnable
script with a baseline JSON we can re-measure on every change.** This
repo holds those baselines and the fixtures that produce them, so
anyone can re-run, audit, and compare.

---

## Component 1 — Vietnamese RAG retrieval

**Source dataset**: sampled from
[`GreenNode/zalo-ai-legal-text-retrieval-vn`](https://huggingface.co/datasets/GreenNode/zalo-ai-legal-text-retrieval-vn)
(MIT), itself a HuggingFace mirror of the
[Zalo AI Challenge 2021 Legal Text Retrieval](https://challenge.zalo.ai/)
public corpus (60,701 articles + 788 queries with qrels).

### Fixtures

| File | Articles | Questions |
|---|---|---|
| `fixtures/vn_legal_tiny.json` | 12 | 12 |
| `fixtures/vn_legal_zalo_2k.json` | ~1.5k | 50 |
| `fixtures/vn_legal_zalo_5k.json` | ~5k | 80 |
| `fixtures/vn_legal_zalo_full.json` | ~61k | 788 |

(The `_full` fixture is large; regenerate via `fixture_builder.py` if
the JSON isn't committed in your clone.)

### Reproducing the bench

```bash
git clone https://github.com/nrl-ai/nom-vn
cd nom-vn
pip install -e ".[chat,otel]" datasets

# Rebuild a fixture:
python benchmarks/rag/fixtures/_build_zalo_legal.py \\
    --n-questions 80 --n-distractors 5000 --seed 42 \\
    --out benchmarks/rag/fixtures/vn_legal_zalo_5k.json

# Real-models bench, GPU auto-pick:
python benchmarks/rag/bench_rag_vn.py \\
    --fixture benchmarks/rag/fixtures/vn_legal_zalo_5k.json \\
    --embedder vietnamese \\
    --reranker BAAI/bge-reranker-v2-m3 \\
    --retrievers bm25,dense,hybrid,hybrid+rerank \\
    --device auto \\
    --json benchmarks/rag/baselines/zalo_5k__dangvantuan__bge_v2_m3.json

# Whole grid:
bash benchmarks/rag/run_grid.sh
```

See per-baseline JSON for exact config + metrics.

---

## Component 2 — Vietnamese OCR

**Source dataset**: `vn_ocr_subset` — 478 image samples deterministically
drawn (seed=42) from
[`ducto489/ocr_datasets`](https://huggingface.co/datasets/ducto489/ocr_datasets)
shard 0 (Apache-2.0), filtered to rows containing Vietnamese diacritics
and at least 8 characters of ground-truth text.

The synthetic pencil-rendered fixture (`benchmarks/data/synthetic_ocr_vi/`,
20 + 20 images) stays in the main repo as a CI smoke test — Tesseract
gets ~100% on it which makes it useless for ranking engines.

### Reproducing the bench

```bash
# Rebuild the VN-only OCR subset (downloads one parquet shard ~150 MB):
python benchmarks/data/vn_ocr_subset/_build.py --n 500 --seed 42

# Run engines:
python benchmarks/accuracy/bench_ocr_real.py \\
    --corpus benchmarks/data/vn_ocr_subset \\
    --variant none \\
    --engines tesseract,easyocr \\
    --device cpu \\
    --json benchmarks/results/ocr_vn_subset__tesseract_easyocr.json
```

Engines benchmarked so far:

- **Tesseract 5** (`vie` traineddata, system-installed; Apache-2.0).
- **EasyOCR** 1.7+ (Apache-2.0; pip-installable).

Engines in the survey but not yet benched:

- VietOCR (Apache-2.0; install broken on Python 3.13 — pinned for
  follow-up).
- PaddleOCR PP-OCRv5 (Apache-2.0; lightweight detection + recognition).
- Qwen2-VL-2B (Apache-2.0; ~4 GB, GPU-recommended; deferred).
- Surya OCR — **GPL-3.0** code + open-RAIL-M models, license-incompatible
  with our Apache-2.0 default surface, can only bench for comparison.

---

## Licenses

This dataset repo: **MIT**.

Per-corpus licenses:
- `fixtures/vn_legal_tiny.json` — hand-curated, MIT.
- `fixtures/vn_legal_zalo_*.json` — derived from
  [GreenNode/zalo-ai-legal-text-retrieval-vn](https://huggingface.co/datasets/GreenNode/zalo-ai-legal-text-retrieval-vn)
  (MIT), itself the Zalo AI Challenge 2021 public corpus.
- `vn_ocr_subset/` (when added) — derived from
  [ducto489/ocr_datasets](https://huggingface.co/datasets/ducto489/ocr_datasets)
  (Apache-2.0).

Bench result JSONs reference embedder / reranker model IDs; consult
each upstream model card for license. We standardise on Apache-2.0
+ safetensors per
[`CLAUDE.md`](https://github.com/nrl-ai/nom-vn/blob/main/CLAUDE.md)
file-format trust ladder.
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-id", default=DEFAULT_REPO_ID)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    fixtures_dir = REPO / "benchmarks" / "rag" / "fixtures"
    baselines_dir = REPO / "benchmarks" / "rag" / "baselines"
    builder = fixtures_dir / "_build_zalo_legal.py"

    ocr_baselines_dir = REPO / "benchmarks" / "results"
    ocr_subset_dir = REPO / "benchmarks" / "data" / "vn_ocr_subset"
    ocr_builder = ocr_subset_dir / "_build.py"
    ocr_bench_script = REPO / "benchmarks" / "accuracy" / "bench_ocr_real.py"
    rag_bench_script = REPO / "benchmarks" / "rag" / "bench_rag_vn.py"
    rag_grid_script = REPO / "benchmarks" / "rag" / "run_grid.sh"

    fixtures = sorted(fixtures_dir.glob("*.json"))
    baselines = sorted(baselines_dir.glob("*.json"))
    ocr_baselines = (
        sorted(ocr_baselines_dir.glob("ocr_*.json")) if ocr_baselines_dir.is_dir() else []
    )
    ocr_gt = ocr_subset_dir / "ground_truth.jsonl" if ocr_subset_dir.is_dir() else None

    print(f"target repo: {args.repo_id}")
    print(f"fixtures   : {len(fixtures)} files, {sum(f.stat().st_size for f in fixtures):,} bytes")
    print(f"baselines  : {len(baselines)} files")
    print(f"ocr base   : {len(ocr_baselines)} files")
    print(f"ocr gt     : {'present' if ocr_gt and ocr_gt.is_file() else 'missing'}")
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

    # OCR — baselines, ground truth, builder, bench scripts
    for b in ocr_baselines:
        api.upload_file(
            path_or_fileobj=str(b),
            path_in_repo=f"baselines/ocr/{b.name}",
            repo_id=args.repo_id,
            repo_type="dataset",
            commit_message=f"ocr bench: baseline {b.name}",
        )
    if ocr_gt and ocr_gt.is_file():
        api.upload_file(
            path_or_fileobj=str(ocr_gt),
            path_in_repo="fixtures/vn_ocr_subset/ground_truth.jsonl",
            repo_id=args.repo_id,
            repo_type="dataset",
            commit_message="ocr fixture: vn_ocr_subset ground truth",
        )
    if ocr_builder.is_file():
        api.upload_file(
            path_or_fileobj=str(ocr_builder),
            path_in_repo="ocr_subset_builder.py",
            repo_id=args.repo_id,
            repo_type="dataset",
            commit_message="ocr fixture builder",
        )
    if ocr_bench_script.is_file():
        api.upload_file(
            path_or_fileobj=str(ocr_bench_script),
            path_in_repo="ocr_bench.py",
            repo_id=args.repo_id,
            repo_type="dataset",
            commit_message="ocr bench script",
        )
    if rag_bench_script.is_file():
        api.upload_file(
            path_or_fileobj=str(rag_bench_script),
            path_in_repo="rag_bench.py",
            repo_id=args.repo_id,
            repo_type="dataset",
            commit_message="rag bench script",
        )
    if rag_grid_script.is_file():
        api.upload_file(
            path_or_fileobj=str(rag_grid_script),
            path_in_repo="rag_run_grid.sh",
            repo_id=args.repo_id,
            repo_type="dataset",
            commit_message="rag grid runner",
        )

    print(f"\n→ pushed to https://huggingface.co/datasets/{args.repo_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
