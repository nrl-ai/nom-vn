"""Sample the Zalo Legal QA HF mirror down to a benchmark-ready fixture.

The full ZacLegalTextRetrieval corpus is 60k articles + 788 queries with
qrels. That's slow to index every iteration. This script samples a
deterministic subset:

  - All relevant articles for the chosen queries (so recall is achievable).
  - K random distractors (so the corpus has realistic noise).
  - N queries from the test split.

Output JSON matches the schema ``benchmarks/rag/bench_rag_vn.py`` reads:

  {
    "name": "vn_legal_zalo_2k",
    "corpus":    [{"id": "...", "text": "..."}, ...],
    "questions": [{"q": "...", "gold_ids": ["...", ...]}, ...]
  }

Source: https://huggingface.co/datasets/GreenNode/zalo-ai-legal-text-retrieval-vn
License (per HF dataset card, accessed 2026-04-25): MIT.

Run::

    python benchmarks/rag/fixtures/_build_zalo_legal.py
    python benchmarks/rag/fixtures/_build_zalo_legal.py --n-questions 100 --n-distractors 4000
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

OUT = Path(__file__).resolve().parent / "vn_legal_zalo_2k.json"


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--n-questions", type=int, default=50)
    p.add_argument("--n-distractors", type=int, default=2000)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--out", type=Path, default=OUT)
    args = p.parse_args(argv)

    try:
        from datasets import load_dataset
    except ImportError:
        print(
            "datasets package missing. Install with: pip install datasets",
            file=sys.stderr,
        )
        return 2

    print(f"loading GreenNode/zalo-ai-legal-text-retrieval-vn (seed={args.seed})...")
    queries = load_dataset(
        "GreenNode/zalo-ai-legal-text-retrieval-vn",
        "queries",
        split="test",
    )
    qrels = load_dataset(
        "GreenNode/zalo-ai-legal-text-retrieval-vn",
        "qrels",
        split="test",
    )
    corpus = load_dataset(
        "GreenNode/zalo-ai-legal-text-retrieval-vn",
        "corpus",
        split="test",
    )

    # Build (query_id -> text) and (query_id -> gold doc ids)
    q_text: dict[str, str] = {}
    for row in queries:
        qid = str(row["_id"]) if "_id" in row else str(row.get("id", row.get("query_id")))
        text = row.get("text") or row.get("query") or ""
        if text:
            q_text[qid] = text

    qid_to_gold: dict[str, list[str]] = {}
    for row in qrels:
        qid = str(row.get("query-id", row.get("query_id", row.get("qid"))))
        did = str(row.get("corpus-id", row.get("doc_id", row.get("did"))))
        score = row.get("score", 1)
        if int(score) > 0:
            qid_to_gold.setdefault(qid, []).append(did)

    # Sample N queries that have at least one gold answer.
    rng = random.Random(args.seed)
    answerable_qids = [qid for qid, gold in qid_to_gold.items() if gold and qid in q_text]
    rng.shuffle(answerable_qids)
    chosen_qids = answerable_qids[: args.n_questions]
    print(f"  picked {len(chosen_qids)}/{len(answerable_qids)} answerable queries")

    # All gold doc ids must end up in the fixture corpus.
    gold_ids: set[str] = set()
    for qid in chosen_qids:
        gold_ids.update(qid_to_gold[qid])

    # Pull docs by id — iterate corpus once to find them, then sample distractors.
    chosen_docs: dict[str, str] = {}
    distractor_pool: list[tuple[str, str]] = []
    for row in corpus:
        did = str(row.get("_id", row.get("id", row.get("doc_id"))))
        text = row.get("text", row.get("contents", ""))
        if not text:
            continue
        if did in gold_ids:
            chosen_docs[did] = text
        else:
            distractor_pool.append((did, text))

    rng.shuffle(distractor_pool)
    for did, text in distractor_pool[: args.n_distractors]:
        chosen_docs[did] = text

    # Drop questions whose gold docs aren't in the corpus (shouldn't happen,
    # but defensive against missing rows).
    fixture_questions: list[dict[str, Any]] = []
    for qid in chosen_qids:
        gold_in_corpus = [d for d in qid_to_gold[qid] if d in chosen_docs]
        if not gold_in_corpus:
            continue
        fixture_questions.append(
            {
                "q": q_text[qid],
                "gold_ids": gold_in_corpus,
            }
        )

    fixture: dict[str, Any] = {
        "name": f"vn_legal_zalo_{len(chosen_docs) // 1000}k",
        "source": "GreenNode/zalo-ai-legal-text-retrieval-vn (MIT, accessed 2026-04-25)",
        "seed": args.seed,
        "corpus": [{"id": did, "text": text} for did, text in chosen_docs.items()],
        "questions": fixture_questions,
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(fixture, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"→ wrote {args.out}\n"
        f"  corpus: {len(fixture['corpus'])} articles\n"
        f"  questions: {len(fixture['questions'])} (each with >=1 gold doc)\n"
        f"  total bytes: {sum(len(d['text']) for d in fixture['corpus']):,}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
