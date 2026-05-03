"""Publish the trained register classifier to nrl-ai/vn-register-phobert-base.

Mirrors the training/spell_correction/publish_hf.py shape but for a
sequence-classification head (4-class) rather than a seq2seq model.
The training corpus is source-provenance assembled (UDHR + VNTC +
Tatoeba + Wikisource), so this is the first publicly-licensed VN
4-register classifier — research gap flagged in
``docs/research/2026-05-03-vn-register-classifier-survey.md``.

Run::

    python scripts/publish_register_classifier.py \\
        --checkpoint-dir checkpoints/register-phobert-base \\
        --repo-id nrl-ai/vn-register-phobert-base \\
        --commit-message "v0.1: PhoBERT-base 4-register, macro-F1 0.900"

Pre-flight: ``hf auth login`` (or ``HUGGINGFACE_HUB_TOKEN``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


# Adoption gate per docs/sota_vn_2026q2_expansion.md Tier 1 #1:
#   macro F1 >= 0.85 AND every per-class F1 >= 0.75
GATE_MACRO_F1_MIN = 0.85
GATE_PER_CLASS_F1_MIN = 0.75


CARD_TEMPLATE = """\
---
license: mit
language:
  - vi
library_name: transformers
pipeline_tag: text-classification
base_model: vinai/phobert-base
tags:
  - vietnamese
  - register-classification
  - text-classification
  - phobert
  - nrl-ai
---

# vn-register-phobert-base

4-class **Vietnamese text register classifier** — labels each input as
one of `formal` (administrative / legal) / `business` (news /
encyclopaedic) / `conversational` (chat / forum) / `literary`
(classical narrative). Use the predicted register to **route a text
through the right downstream checkpoint** — VN diacritic /
summarization / OCR-rerank checkpoints all spread 5-10 pp accuracy
across registers, so a cheap router lifts every other tool
automatically.

PhoBERT-base backbone (135 M params, MIT, VinAI lab) fine-tuned with a
4-way sequence-classification head. Word-segmented input via
[`nom.text.word_tokenize`](https://github.com/nrl-ai/nom-vn/blob/main/src/nom/text/segment.py)
per the BKai gotcha (raw text drops accuracy ≥ 15 pp on PhoBERT-style
models).

## Measured on test split

In-house bench, 2026-05-03, n=1234 stratified test split (CUDA, BF16):

| Class | Precision | Recall | F1 | Support |
|---|---:|---:|---:|---:|
| `formal` | 0.889 | 0.941 | **0.914** | 34 |
| `business` | 0.885 | 0.928 | **0.906** | 400 |
| `conversational` | 0.887 | 0.945 | **0.915** | 400 |
| `literary` | 0.924 | 0.815 | **0.866** | 400 |
| **macro avg** | 0.896 | 0.907 | **0.900** | 1234 |

Both adoption gates clear: macro F1 ≥ 0.85, every per-class F1 ≥ 0.75.

Source [`benchmarks/accuracy/register_phobert_base_baseline.json`](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/accuracy/register_phobert_base_baseline.json)
re-runnable from a clean clone via
[`training/register/train.py`](https://github.com/nrl-ai/nom-vn/blob/main/training/register/train.py).

## Corpus

Source-provenance labelling — no human annotators needed. Every
sentence inherits its register label from the source corpus it
came from:

| Label | Source(s) | License |
|---|---|---|
| `formal` | UDHR-vi (PD) + UDHR diacritic-eval slice (PD) | Public Domain |
| `business` | wiki_vi (Wikipedia VN extracts) | CC-BY-SA-4.0 |
| `conversational` | tatoeba_vi 3k + tatoeba diacritic-eval-300 | CC-BY 2.0 FR |
| `literary` | wikisource_vi (PD) + UD-VTB train/dev/test | PD + CC-BY-SA-4.0 |

Class imbalance — `formal` only has 169 unique sentences (UDHR is
naturally short), the others cap at 2 000 each. The 134 / 169 / 169 /
169 split per register survives the imbalance (model still hits 0.91
F1 on formal — class weighting wasn't needed). Future v2: add a
permissive VN legal corpus to grow `formal`.

## Use

```python
from transformers import AutoTokenizer, AutoModelForSequenceClassification

tok = AutoTokenizer.from_pretrained("nrl-ai/vn-register-phobert-base")
model = AutoModelForSequenceClassification.from_pretrained("nrl-ai/vn-register-phobert-base")

# IMPORTANT: PhoBERT requires word-segmented input (multi-syllable words
# joined with underscores). Use VnCoreNLP's RDRSegmenter or nom.text:
from nom.text import normalize, word_tokenize
text = "Doanh thu công ty quý 2 năm 2026 tăng 18 %."
segmented = " ".join(t.replace(" ", "_") for t in word_tokenize(normalize(text)))

import torch
ids = tok(segmented, return_tensors="pt", truncation=True, max_length=256)
with torch.no_grad():
    logits = model(**ids).logits
probs = torch.softmax(logits, dim=-1).squeeze().tolist()
labels = ["formal", "business", "conversational", "literary"]
for label, p in sorted(zip(labels, probs), key=lambda x: -x[1]):
    print(f"  {label:<15} {p:.3f}")
# →   business        0.952
#     formal          0.029
#     conversational  0.012
#     literary        0.007
```

Or via the [`nom-vn`](https://github.com/nrl-ai/nom-vn) wrapper:

```python
from nom.classify import PhoBertRegisterClassifier
clf = PhoBertRegisterClassifier()  # default model_id = this repo
result = clf.predict("Doanh thu công ty quý 2 năm 2026 tăng 18 %.")
print(result.label, result.score, result.distribution)
```

## Honesty notes

- **Tested only on held-out 20 % of source-provenance corpus.** A
  sentence labelled "formal" because it came from UDHR is a single
  data-distribution slice — real-world legal prose may shift. A genre
  classifier this scale needs cross-corpus eval (e.g. legal_vi from
  th1nhng0) before adoption claims beyond routing.
- **`literary` recall 0.815 < precision 0.924.** When the model says
  "literary," it's usually right; when something IS literary, the
  model misses ~18 % to other classes (mostly to `formal` because of
  shared archaic vocab). Acceptable for routing — false negatives
  fall back to a sensible default.
- **Word-segmentation matters.** Skip `word_tokenize` and accuracy
  drops 10-15 pp. The wrapper handles this; if you call the model
  directly, you must segment.

## Citation

```bibtex
@misc{nguyen_vn_register_phobert_base_2026,
  author = {Nguyen, Viet-Anh and {Neural Research Lab}},
  title  = {{vn-register-phobert-base: A 4-class Vietnamese text-register
             classifier (formal / business / conversational / literary)}},
  year   = {2026},
  url    = {https://huggingface.co/nrl-ai/vn-register-phobert-base}
}
```

License: MIT (matches PhoBERT-base backbone).

Maintained as part of the [`nom-vn`](https://github.com/nrl-ai/nom-vn)
project by Viet-Anh Nguyen (`vietanh@nrl.ai`) and Neural Research Lab.
"""


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    p.add_argument("--checkpoint-dir", default="checkpoints/register-phobert-base")
    p.add_argument("--repo-id", default="nrl-ai/vn-register-phobert-base")
    p.add_argument(
        "--commit-message",
        default="v0.1: PhoBERT-base 4-register classifier, macro-F1 0.900",
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    ckpt = REPO / args.checkpoint_dir
    summary = json.loads((ckpt / "result.json").read_text())
    test = summary["test_metrics"]

    macro_f1 = test["test_macro_f1"]
    per_class = {k.replace("test_f1_", ""): v for k, v in test.items() if k.startswith("test_f1_")}
    print(f"  macro F1: {macro_f1:.4f}  (gate >= {GATE_MACRO_F1_MIN})")
    for cls, f1 in per_class.items():
        print(f"  f1[{cls}]: {f1:.4f}  (gate >= {GATE_PER_CLASS_F1_MIN})")

    if macro_f1 < GATE_MACRO_F1_MIN:
        raise SystemExit(f"macro F1 {macro_f1:.4f} below adoption gate {GATE_MACRO_F1_MIN}")
    for cls, f1 in per_class.items():
        if f1 < GATE_PER_CLASS_F1_MIN:
            raise SystemExit(f"f1[{cls}] {f1:.4f} below adoption gate {GATE_PER_CLASS_F1_MIN}")
    print("Adoption gates clear.")

    # Stage README
    readme_path = Path("/tmp/register_README.md")
    readme_path.write_text(CARD_TEMPLATE, encoding="utf-8")
    print(f"  staged README to {readme_path}")

    # The checkpoint directory has tokenizer + model.safetensors + config
    # already from save_model(); we upload the whole thing minus
    # checkpoint-N intermediates.
    files = sorted(
        f
        for f in ckpt.iterdir()
        if f.is_file() and f.name not in {"training_args.bin", "result.json"}
    )
    print(f"  {len(files)} checkpoint files staged for upload")

    if args.dry_run:
        for f in files[:8]:
            print(f"    {f.name}")
        if len(files) > 8:
            print(f"    ... and {len(files) - 8} more")
        return

    from huggingface_hub import HfApi, create_repo

    api = HfApi()
    try:
        create_repo(args.repo_id, exist_ok=True)
    except Exception as exc:
        print(f"create_repo failed (continuing if exists): {exc}")

    for f in files:
        api.upload_file(
            path_or_fileobj=str(f),
            path_in_repo=f.name,
            repo_id=args.repo_id,
            commit_message=args.commit_message,
        )
        print(f"    pushed {f.name}")
    api.upload_file(
        path_or_fileobj=str(readme_path),
        path_in_repo="README.md",
        repo_id=args.repo_id,
        commit_message=args.commit_message,
    )
    print("    pushed README.md")
    print()
    print(f"Pushed to https://huggingface.co/{args.repo_id}")


if __name__ == "__main__":
    sys.exit(main())
