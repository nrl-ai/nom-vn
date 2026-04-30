"""Publish a trained diacritic-restoration checkpoint to Hugging Face Hub.

Designed to run on the box that has the trained checkpoint locally. Steps:

1. Read ``training_summary.json`` and verify the adoption gate.
2. Generate a model card (README.md) with license attribution, the
   measured 4-register eval table, training config, and reproduction
   instructions.
3. Create the target repo on HF (via huggingface_hub) if it doesn't
   exist, then push the checkpoint folder + the generated README.

Usage::

    python training/diacritic/publish_hf.py \\
        --checkpoint-dir training/diacritic/checkpoints/vit5-base-500k-cosine/final \\
        --summary-json training/diacritic/checkpoints/vit5-base-500k-cosine/training_summary.json \\
        --repo-id nrl-ai/vn-diacritic-restoration \\
        --commit-message "v0.1: vit5-base 500k cosine"

Pre-flight: needs ``HUGGINGFACE_HUB_TOKEN`` (env) or ``huggingface-cli
login`` cached creds. Adoption gate is a hard gate — pass ``--force`` to
override (in which case the model card is honest about why we shipped a
sub-gate model anyway).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Adoption gate constants — kept here (not in summary) so they're explicit.
GATE_BUSINESS_MIN = 0.96  # word accuracy on 55-sent business corpus
GATE_LITERARY_MIN = 0.8940  # word accuracy on 800-sent UD-VTB literary
TOSHIIIII_BASELINE = {
    "formal_udhr": 0.9814,
    "business_55": 0.9781,
    "conversational_300": 0.9394,
    "literary_udvtb": 0.8940,
}

# Public landscape — every measured row has a JSON baseline in the repo.
# Used to render the "How we compare" section of every model card we publish.
# Adding a new candidate? Append a row; the table auto-renders.
COMPARISON_MATRIX: list[dict[str, Any]] = [
    {
        "repo_id": "Toshiiiii1/Vietnamese_diacritics_restoration_5th",
        "label": "Toshiiiii1/...5th",
        "family": "public",
        "params": "200 M",
        "license": "Apache 2.0",
        "scores": {
            "formal_udhr": 0.9814,
            "business_55": 0.9781,
            "conversational_300": 0.9394,
            "literary_udvtb": 0.8940,
        },
    },
    {
        "repo_id": "nrl-ai/vn-diacritic-vit5-base",
        "label": "nrl-ai/vn-diacritic-vit5-base",
        "family": "ours",
        "params": "220 M",
        "license": "Apache 2.0",
        "scores": {
            "formal_udhr": 0.9943,
            "business_55": 0.9498,
            "conversational_300": 0.9412,
            "literary_udvtb": 0.9024,
        },
    },
    {
        "repo_id": "nrl-ai/vn-diacritic-small",
        "label": "nrl-ai/vn-diacritic-small",
        "family": "ours",
        "params": "115 M",
        "license": "Apache 2.0",
        "scores": {
            "formal_udhr": 0.9151,
            "business_55": 0.9444,
            "conversational_300": 0.9068,
            "literary_udvtb": 0.8633,
        },
    },
    {
        "repo_id": "qthuan2604/ViT5_Restore_Diacritics_Vietnamese",
        "label": "qthuan2604/ViT5_Restore_Diacritics_Vietnamese",
        "family": "public",
        "params": "220 M",
        "license": "MIT",
        # Only business benched (90.59 was too far below SOTA to spend GPU
        # on the other 3 registers); other cells left blank intentionally.
        "scores": {"business_55": 0.9059},
    },
    {
        "repo_id": "qthuan2604/BARTPho_Syllable_Restore_Diacritics_Vietnamese",
        "label": "qthuan2604/BARTPho_Syllable_Restore_Diacritics_Vietnamese",
        "family": "public",
        "params": "115 M",
        "license": "MIT",
        "scores": {"business_55": 0.8392},
    },
    {
        "repo_id": None,  # cloud, no HF link
        "label": "OpenAI gpt-4o-mini (cloud)",
        "family": "external",
        "params": "proprietary",
        "license": "proprietary",
        "scores": {"business_55": 0.9537},
    },
    {
        "repo_id": None,
        "label": "rule-based (`nom.text.fix_diacritics`)",
        "family": "ours",
        "params": "0",
        "license": "Apache 2.0",
        "scores": {"business_55": 0.4106},
    },
]


def check_gate(eval_data: dict[str, Any]) -> tuple[bool, str]:
    """Return (passed, reason)."""
    biz = eval_data.get("business_55", {}).get("word_accuracy")
    lit = eval_data.get("literary_udvtb", {}).get("word_accuracy")
    if biz is None or lit is None:
        return False, f"missing eval data (business_55={biz}, literary_udvtb={lit})"
    if biz < GATE_BUSINESS_MIN:
        return False, f"business_55 word_accuracy {biz:.4f} < gate {GATE_BUSINESS_MIN:.4f}"
    if lit <= GATE_LITERARY_MIN:
        return False, (
            f"literary_udvtb word_accuracy {lit:.4f} not strictly > gate "
            f"{GATE_LITERARY_MIN:.4f} (Toshiiiii1 baseline)"
        )
    return True, "passed"


def _fmt_int(v: Any) -> str:
    """Format an int with thousands separators; ``"?"`` if missing."""
    if isinstance(v, int):
        return f"{v:,}"
    return "?"


def _render_comparison_section(
    publishing_repo_id: str,
    publishing_summary: dict[str, Any],
) -> str:
    """Render a comparison table putting the publishing model in context.

    Includes:
    - This model (highlighted)
    - Our other variants (`nrl-ai/*` siblings)
    - External public candidates we have measured
    - External cloud / rule baselines for context

    Bolds the top number per register so the reader can see who wins
    each one. Cells we haven't measured render as "—".
    """
    # Build a synthetic row for the publishing model from its training_summary,
    # in case it's not yet in COMPARISON_MATRIX (first publish of a new tier).
    eval_data = publishing_summary.get("eval", {})
    this_scores = {
        k: v.get("word_accuracy") for k, v in eval_data.items() if v.get("word_accuracy")
    }

    rows: list[dict[str, Any]] = []
    # Did we already include the publishing repo in the matrix?
    matched = False
    for entry in COMPARISON_MATRIX:
        if entry["repo_id"] == publishing_repo_id:
            # Override the matrix scores with this run's freshest numbers.
            row = {**entry, "scores": this_scores or entry["scores"], "is_this": True}
            rows.append(row)
            matched = True
        else:
            rows.append({**entry, "is_this": False})
    if not matched:
        # First publish of this repo — synthesize a row.
        rows.insert(
            0,
            {
                "repo_id": publishing_repo_id,
                "label": publishing_repo_id,
                "family": "ours",
                "params": "?",
                "license": "Apache 2.0",
                "scores": this_scores,
                "is_this": True,
            },
        )

    # Find the best score per register across all rows (for bolding).
    registers = ("formal_udhr", "business_55", "conversational_300", "literary_udvtb")
    best_per_reg = {
        reg: max((r["scores"].get(reg, 0.0) for r in rows), default=0.0) for reg in registers
    }

    def _cell(score: float | None, reg: str, is_this: bool) -> str:
        if score is None:
            return "—"
        pct = f"{score * 100:.2f}"
        # Bold the best in column.
        if abs(score - best_per_reg[reg]) < 1e-6 and best_per_reg[reg] > 0:
            return f"**{pct}**"
        return pct

    header = (
        "| Model | Family | Params | License "
        "| formal_72 | business_55 | conv_300 | literary_800 |\n"
        "|---|---|---:|---|---:|---:|---:|---:|"
    )
    lines = [header]
    for r in rows:
        label = r["label"]
        if r.get("repo_id"):
            label_md = f"[`{label}`](https://huggingface.co/{r['repo_id']})"
        else:
            label_md = label
        if r["is_this"]:
            label_md = f"**this** &rarr; {label_md}"
        scores = r["scores"]
        cells = [
            label_md,
            r["family"],
            r["params"],
            r["license"],
            _cell(scores.get("formal_udhr"), "formal_udhr", r["is_this"]),
            _cell(scores.get("business_55"), "business_55", r["is_this"]),
            _cell(scores.get("conversational_300"), "conversational_300", r["is_this"]),
            _cell(scores.get("literary_udvtb"), "literary_udvtb", r["is_this"]),
        ]
        lines.append("| " + " | ".join(cells) + " |")

    return "\n".join(lines)


def render_model_card(summary: dict[str, Any], repo_id: str, gate_status: str) -> str:
    """Generate the README.md model card from a training_summary.json."""
    base = summary["model_id"]
    eval_data = summary.get("eval", {})
    hp = summary.get("hyperparameters", {})

    # Arch family inferred from the base model id — drives the YAML tags
    # and the title prose so the card matches the actual architecture.
    base_lower = base.lower()
    if "vit5" in base_lower or "t5" in base_lower:
        arch_tag = "t5"
        arch_label = "ViT5"
    elif "bartpho" in base_lower:
        arch_tag = "bartpho"
        arch_label = "BARTpho-syllable"
    elif "mbart" in base_lower:
        arch_tag = "mbart"
        arch_label = "mBART"
    else:
        arch_tag = "seq2seq"
        arch_label = "seq2seq"

    # Training data heuristic: assume mixed Wiki+news if train_pairs > 200K
    # (the Wiki-only run was 200K). Avoids hard-coding the corpus name.
    pairs = summary.get("train_pairs", 0) or 0
    if pairs >= 400_000:
        train_corpus_blurb = (
            "a register-balanced mix of Vietnamese Wikipedia (CC-BY-SA-4.0) "
            "and Vietnamese news (`tmnam20/Vietnamese-News-dedup`, CC-BY-4.0, NFC-normalized)"
        )
        datasets_yaml = (
            "  - hirine/wikipedia-vietnamese-1M296K-dataset\n  - tmnam20/Vietnamese-News-dedup"
        )
    else:
        train_corpus_blurb = "Vietnamese Wikipedia (CC-BY-SA-4.0)"
        datasets_yaml = "  - hirine/wikipedia-vietnamese-1M296K-dataset"

    # Eval rows in monotonic register order, formal -> literary.
    register_order = [
        ("formal_udhr", "Formal / legal-prose (UDHR, public domain)"),
        ("business_55", "Modern business / contracts / news (CC0)"),
        ("conversational_300", "Conversational (Tatoeba, CC-BY 2.0 FR)"),
        ("literary_udvtb", "Classical literary (UD-VTB, CC-BY-SA-4.0)"),
    ]
    rows: list[str] = []
    for key, desc in register_order:
        m = eval_data.get(key)
        if not m:
            continue
        toshi = TOSHIIIII_BASELINE.get(key, 0.0)
        delta = (m["word_accuracy"] - toshi) * 100.0
        sign = "+" if delta >= 0 else ""
        rows.append(
            f"| {desc} | {m['n_sentences']} | {m['word_accuracy'] * 100:.2f} % "
            f"| {sign}{delta:.2f} pp | {m.get('mean_ms_per_sentence', 0):.0f} |"
        )
    eval_table = "\n".join(rows)
    comparison_table = _render_comparison_section(repo_id, summary)

    return f"""---
license: apache-2.0
base_model: {base}
language:
  - vi
tags:
  - vietnamese
  - diacritic-restoration
  - seq2seq
  - {arch_tag}
pipeline_tag: text-generation
datasets:
{datasets_yaml}
metrics:
  - word_accuracy
  - sentence_exact
library_name: transformers
---

# {repo_id} — Vietnamese diacritic restoration ({arch_label} fine-tune)

Restores diacritics on Vietnamese text written without them
(``Toi yeu Viet Nam`` → ``Tôi yêu Việt Nam``). Fine-tuned from
[`{base}`](https://huggingface.co/{base}) on {train_corpus_blurb}.

**Adoption gate:** {gate_status}.

## Quick start

```python
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

tok = AutoTokenizer.from_pretrained("{repo_id}")
model = AutoModelForSeq2SeqLM.from_pretrained("{repo_id}").eval()

text = "Toi yeu Viet Nam"
out = model.generate(**tok(text, return_tensors="pt"), max_length=256)
print(tok.decode(out[0], skip_special_tokens=True))
# Tôi yêu Việt Nam
```

For the full pipeline (with rule-based + LLM fallbacks), use the
[``nom-vn``](https://github.com/nrl-ai/nom-vn) Python package:

```python
from nom.text.diacritic_models import HFDiacriticModel
restorer = HFDiacriticModel(model_id="{repo_id}")
restorer("Toi yeu Viet Nam")  # 'Tôi yêu Việt Nam'
```

## Evaluation — 4-register matrix

Measured against [`Toshiiiii1/Vietnamese_diacritics_restoration_5th`][toshi]
(public SOTA at the time of training). Word accuracy after Unicode NFC
+ punctuation normalization on both sides.

| Register | Sents | Word acc | Δ vs Toshiiiii1 | Mean ms/sent |
|---|---:|---:|---:|---:|
{eval_table}

[toshi]: https://huggingface.co/Toshiiiii1/Vietnamese_diacritics_restoration_5th

Each eval corpus is open-license and reproducible from the
[`nom-vn`](https://github.com/nrl-ai/nom-vn) repo:

- **business_55** — `benchmarks/data/diacritic_eval_v0.txt` (CC0)
- **literary_udvtb** — `benchmarks/data/ud_vi_vtb/test.conllu` (CC-BY-SA-4.0)
- **conversational_300** — `benchmarks/data/tatoeba_vi/diacritic_eval_300.txt` (CC-BY 2.0 FR)
- **formal_udhr** — `benchmarks/data/udhr_vi/diacritic_eval_udhr.txt` (public domain)

## How we compare

Where this model sits in the public Vietnamese diacritic-restoration
landscape — same 4-register grid for every measured row. **Bold** = best
in column. Cells marked "—" weren't run on that register.

{comparison_table}

## Training

- **Base:** [`{base}`](https://huggingface.co/{base}) (MIT license)
- **Corpus:** {_fmt_int(summary.get("train_pairs"))} (input, target) pairs from {train_corpus_blurb}.
  Eval-leak guarded against the held-out `nrl-ai/vn-diacritic-eval` slices.
- **Validation:** {_fmt_int(summary.get("val_pairs"))} held-out pairs from the same training mix.
- **Epochs:** {summary.get("epochs", "?")}
- **Effective batch size:** {hp.get("effective_batch_size", "?")} ({hp.get("batch_size", "?")} per device, grad-accum {hp.get("gradient_accumulation_steps", 1)})
- **Learning rate:** {hp.get("lr", "?")} with `{hp.get("lr_scheduler", "?")}` schedule, {hp.get("warmup_steps", "?")} warmup steps
- **Precision:** {"bf16" if hp.get("bf16") else "fp16" if hp.get("fp16") else "fp32"}
- **Sequence length:** input {hp.get("max_input_length", "?")}, target {hp.get("max_target_length", "?")}
- **Early stopping:** patience={hp.get("early_stopping_patience", "?")} on `eval_loss`
- **Training time:** {summary.get("training_minutes", "?")} min on a single NVIDIA RTX 3090 24 GB
- **Seed:** 42

## Intended use

- **Recommended:** Restoring diacritics in modern Vietnamese text where the input is
  predominantly diacritic-stripped (e.g. user typed without IME, OCR with no
  diacritic-aware font, or imported foreign-keyboard data).
- **Not recommended:** Spelling correction (the model does not change letters,
  only adds tone/vowel marks), text generation, classification, or any task
  the input distribution doesn't match (heavy emoji / mixed-script text).

## Limitations

- **Register skew.** Encyclopedic Wikipedia training tilts the model toward
  formal/literary register. Conversational / dialect text may be slightly worse.
- **Proper noun ambiguity.** Multiple plausible diacritisations exist for the
  same ASCII form (``Hung`` → ``Hùng`` / ``Hưng`` / ``Hứng``). The model picks
  the most-likely-in-training, which may not match a specific person's name.
- **Long sentences truncate at {hp.get("max_target_length", "?")} sub-word tokens.**
  Split paragraphs at sentence boundaries before calling.

## License & attribution

This fine-tune is released under **Apache 2.0**.

Base model: [`{base}`](https://huggingface.co/{base}) by VietAI, MIT
license. Cite both this fine-tune and the base model:

```bibtex
@misc{{vit5_2022,
  title={{ViT5: Pretrained Text-to-Text Transformer for Vietnamese Language Generation}},
  author={{Long Phan and Hieu Tran and Hieu Nguyen and Trieu H. Trinh}},
  year={{2022}},
  note={{NAACL-SRW}}
}}

@misc{{nom_vn_diacritic_2026,
  title={{Vietnamese Diacritic Restoration — register-balanced ViT5 fine-tune}},
  author={{Nguyen, Viet-Anh and {{Neural Research Lab}}}},
  year={{2026}},
  howpublished={{\\url{{https://huggingface.co/{repo_id}}}}}
}}
```

Training corpus license: CC-BY-SA-4.0 (Wikipedia). Output text from this
model is therefore best treated as CC-BY-SA-4.0 if you want to be safe
about derivative-rights propagation, even though the model weights
themselves are Apache 2.0.
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--checkpoint-dir",
        type=Path,
        required=True,
        help="Directory with the trained model + tokenizer (typically "
        "<output-dir>/final from train.py).",
    )
    p.add_argument(
        "--summary-json",
        type=Path,
        required=True,
        help="Path to training_summary.json from the same training run.",
    )
    p.add_argument(
        "--repo-id",
        required=True,
        help="HF Hub target, e.g. nrl-ai/vn-diacritic-restoration",
    )
    p.add_argument("--commit-message", default="initial release")
    p.add_argument(
        "--force",
        action="store_true",
        help="Publish even if the adoption gate fails. Use sparingly — "
        "the model card will note the gate-fail honestly.",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate the README.md and print the upload plan, but don't push.",
    )
    args = p.parse_args()

    if not args.checkpoint_dir.exists():
        print(f"ERROR: checkpoint dir not found: {args.checkpoint_dir}", file=sys.stderr)
        return 2
    if not args.summary_json.exists():
        print(f"ERROR: summary json not found: {args.summary_json}", file=sys.stderr)
        return 2

    summary = json.loads(args.summary_json.read_text(encoding="utf-8"))
    eval_data = summary.get("eval", {})

    passed, reason = check_gate(eval_data)
    if passed:
        gate_status = "✅ passed"
        print(f"Adoption gate: PASSED ({reason})")
    else:
        gate_status = f"⚠️  did not pass ({reason})"
        print(f"Adoption gate: FAILED — {reason}")
        if not args.force:
            print(
                "Refusing to publish a sub-gate model. Pass --force to "
                "override (the model card will note the gate-fail).",
                file=sys.stderr,
            )
            return 1

    readme_path = args.checkpoint_dir / "README.md"
    readme_text = render_model_card(summary, args.repo_id, gate_status)
    readme_path.write_text(readme_text, encoding="utf-8")
    print(f"Wrote model card: {readme_path}")

    if args.dry_run:
        print()
        print("--- DRY RUN — would upload the following ---")
        for f in sorted(args.checkpoint_dir.iterdir()):
            print(f"  {f.relative_to(args.checkpoint_dir)}  ({f.stat().st_size:,} bytes)")
        print(f"to https://huggingface.co/{args.repo_id}")
        return 0

    try:
        from huggingface_hub import HfApi, create_repo
    except ImportError as exc:
        print(
            f"ERROR: huggingface_hub not installed: {exc}\n"
            "Install with: pip install huggingface_hub",
            file=sys.stderr,
        )
        return 2

    print(f"Creating repo (or no-op if exists): {args.repo_id}")
    create_repo(args.repo_id, exist_ok=True, repo_type="model")

    print(f"Uploading {args.checkpoint_dir} -> {args.repo_id}...")
    api = HfApi()
    api.upload_folder(
        folder_path=str(args.checkpoint_dir),
        repo_id=args.repo_id,
        commit_message=args.commit_message,
    )
    print(f"\n✅ Published: https://huggingface.co/{args.repo_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
