"""Publish the hand-curated OOD spell-correction eval to HF Hub.

Pushes the 150-sentence eval set under
``benchmarks/data/spell_correction_eval_real/`` to
``nrl-ai/vn-spell-correction-eval-real`` as a dataset repo with one
config per slice (forum_25 / mobile_25 / telex_real_25 / ocr_25 /
legal_real_25 / news_real_25).

Requires: ``hf auth login`` (or ``HF_TOKEN`` env var) with write
access to ``nrl-ai``.

Run::

    python scripts/publish_ood_eval_to_hf.py
    python scripts/publish_ood_eval_to_hf.py --dry-run
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SOURCE_DIR = REPO / "benchmarks" / "data" / "spell_correction_eval_real"
DEFAULT_REPO_ID = "nrl-ai/vn-spell-correction-eval-real"

# YAML metadata header for HF dataset card.
README_TEMPLATE = """\
---
license: cc0-1.0
language:
  - vi
tags:
  - vietnamese
  - spell-correction
  - diacritic-restoration
  - out-of-distribution
  - benchmark
size_categories:
  - n<1K
configs:
  - config_name: forum_25
    data_files: forum_25.jsonl
  - config_name: mobile_25
    data_files: mobile_25.jsonl
  - config_name: telex_real_25
    data_files: telex_real_25.jsonl
  - config_name: ocr_25
    data_files: ocr_25.jsonl
  - config_name: legal_real_25
    data_files: legal_real_25.jsonl
  - config_name: news_real_25
    data_files: news_real_25.jsonl
---

# Vietnamese spell-correction OOD eval (150 sentences, 6 registers)

Hand-curated `(noisy, clean)` pairs whose noise patterns come from
**real Vietnamese error sources**, not from a synthetic noise
generator. Designed as the out-of-distribution complement to the
in-distribution synthetic eval at
[`nrl-ai/vn-spell-correction-eval`](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-eval)
— same input format, same metric, distinct noise distribution.

The synthetic eval measures how well a model inverts a specific noise
generator. This eval measures whether a model also handles errors
that no synthetic generator captures (or captures with different
statistics).

## Slices

| Config | Source of noise | Sentences | What it tests |
|---|---|---:|---|
| `forum_25` | Vietnamese forum / social-media posts | 25 | Teen-code abbreviations, missed accents, casual punctuation |
| `mobile_25` | Phone-typing autocorrect mishaps | 25 | Wrong-word substitutions, adjacent-key slips |
| `telex_real_25` | Real Telex/VNI keystroke artefacts | 25 | Stray `s`/`f`/`r`/`x`/`j`/`w` from missed escape |
| `ocr_25` | Tesseract / EasyOCR engine output on scanned VN | 25 | Engine-specific char confusions (`m`↔`rn`, `cl`↔`d`, `0`↔`o`) |
| `legal_real_25` | Stripped-diacritic VN legal documents | 25 | Formal-register vocab (căn cứ, điều, khoản), proper nouns |
| `news_real_25` | Stripped-diacritic VN news headlines/body | 25 | Modern formal Vietnamese, place names, current-affairs terms |

**Total: 150 sentences.** Six distinct registers covering the realistic
range of Vietnamese error sources a deployed model will encounter.

## Schema

Each line is `{"input": <noisy>, "target": <clean>}`. NFC-normalized
on both sides. Aligned at the sentence level — no token-level alignment
needed.

```python
from datasets import load_dataset

ds = load_dataset("nrl-ai/vn-spell-correction-eval-real", "forum_25", split="train")
for ex in ds.select(range(3)):
    print(ex["input"])
    print(ex["target"])
    print("---")
```

## Honest caveats

- **150 sentences is statistical noise territory.** Each 25-sentence
  slice has ±9 pp 95 % CI on word accuracy; aggregate ±5 pp. Treat
  this as a directional smell-test, not a leaderboard.
- **No PII in source.** Many entries are composites of patterns
  observed across multiple posts/scans. The structural noise patterns
  are faithful; surrounding sentence content was paraphrased from
  public Vietnamese text.
- **Forum slang ages quickly.** `vcl` today may be archaic tomorrow.
  Re-curate every 12-18 months.

## Reproduce a bench

```bash
pip install "nom-vn[diacritic-hf]"

# Sample bench script lives in the toolkit repo:
git clone https://github.com/nrl-ai/nom-vn.git
cd nom-vn
python benchmarks/accuracy/bench_spell_correction_real.py \\
    nrl-ai/vn-spell-correction-base \\
    --json benchmarks/results/baseline_real_spell_correction_base.json
```

The bench script reports word accuracy with bootstrap 95 % CI per
slice and a per-error-type breakdown
(missed_diacritic / wrong_tone / base_char / extra_word / missing_word).

## Citation

```bibtex
@misc{nom_vn_ood_eval_2026,
  title={Vietnamese Spell-Correction Out-of-Distribution Eval (n=150, 6 registers)},
  author={Nguyen, Viet-Anh and {Neural Research Lab}},
  year={2026},
  howpublished={\\url{https://huggingface.co/datasets/nrl-ai/vn-spell-correction-eval-real}}
}
```

Released under CC0 1.0 (public domain dedication). The toolkit code
that produces a measurement against this set is licensed Apache 2.0.

## See also

- The synthetic 8-split eval (in-distribution):
  [`nrl-ai/vn-spell-correction-eval`](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-eval)
- The shipped models that consume this eval:
  [`nrl-ai/vn-spell-correction-base`](https://huggingface.co/nrl-ai/vn-spell-correction-base) ·
  [`nrl-ai/vn-spell-correction-small`](https://huggingface.co/nrl-ai/vn-spell-correction-small)
- Toolkit repo: <https://github.com/nrl-ai/nom-vn>
"""


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--repo-id", default=DEFAULT_REPO_ID)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args(argv)

    if not SOURCE_DIR.exists():
        print(f"ERROR: {SOURCE_DIR} not found", file=sys.stderr)
        return 2

    jsonl_files = sorted(SOURCE_DIR.glob("*.jsonl"))
    if not jsonl_files:
        print(f"ERROR: no .jsonl files in {SOURCE_DIR}", file=sys.stderr)
        return 2

    print(f"Source: {SOURCE_DIR}")
    print(f"Repo:   {args.repo_id}")
    print()
    print("Files to upload:")
    for path in jsonl_files:
        print(f"  {path.name:<28} {path.stat().st_size:>6} bytes")
    print("  README.md (English card, generated, NOT the local VN one)")

    if args.dry_run:
        print()
        print("--- DRY RUN — would upload ---")
        return 0

    import tempfile

    from huggingface_hub import HfApi, create_repo

    create_repo(args.repo_id, exist_ok=True, repo_type="dataset")

    api = HfApi()

    # The local benchmarks/data/spell_correction_eval_real/README.md is
    # Vietnamese (matches the project's website / repo language rule).
    # Per the language-by-surface rule, HF dataset cards are English —
    # so we write the English card to a temp file and upload it
    # alongside the JSONLs. The local VN README stays untouched.
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_readme = Path(tmpdir) / "README.md"
        tmp_readme.write_text(README_TEMPLATE, encoding="utf-8")

        for jsonl in jsonl_files:
            api.upload_file(
                path_or_fileobj=str(jsonl),
                path_in_repo=jsonl.name,
                repo_id=args.repo_id,
                repo_type="dataset",
            )
        api.upload_file(
            path_or_fileobj=str(tmp_readme),
            path_in_repo="README.md",
            repo_id=args.repo_id,
            repo_type="dataset",
            commit_message="Publish OOD spell-correction eval (150 sentences, 6 registers)",
        )

    print()
    print(f"Published: https://huggingface.co/datasets/{args.repo_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
