"""Publish a trained spell-correction checkpoint to Hugging Face Hub.

Same workflow as `training/diacritic/publish_hf.py` but with constants
adjusted for the 8-split spell-correction eval grid (4 registers x 2
noise levels) and a different "external SOTA" baseline
(`bmd1905/vietnamese-correction-v2` for spell correction; Toshiiiii1
is a diacritic-only model so isn't directly comparable).

Steps:

1. Read ``training_summary.json`` and verify the adoption gate.
2. Generate a model card (README.md) with license attribution, the
   measured 8-split eval table, training config, and a "How we
   compare" matrix vs other public spell-correction models.
3. Create the target repo on HF if it doesn't exist, then push the
   checkpoint folder + the generated README.

Usage::

    python training/spell_correction/publish_hf.py \\
        --checkpoint-dir training/spell_correction/checkpoints/vit5-base-500k/final \\
        --summary-json training/spell_correction/checkpoints/vit5-base-500k/training_summary.json \\
        --repo-id nrl-ai/vn-spell-correction-base \\
        --commit-message "v0.1: vit5-base 500K mixed noise"

Pre-flight: needs ``HUGGINGFACE_HUB_TOKEN`` (env) or ``hf auth login``
cached creds.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Adoption gate — looser than diacritic because spell correction is a
# strictly harder task. Both numbers must clear bar.
GATE_LIGHT_AVG_MIN = 0.92  # avg word_accuracy across the 4 light splits
GATE_HEAVY_AVG_MIN = 0.80  # avg across the 4 heavy splits

# 8-split eval registers — must match training/spell_correction/train.py
LIGHT_SPLITS = (
    "business_55_light",
    "formal_72_light",
    "conversational_300_light",
    "literary_800_light",
)
HEAVY_SPLITS = (
    "business_55_heavy",
    "formal_72_heavy",
    "conversational_300_heavy",
    "literary_800_heavy",
)
ALL_SPLITS = LIGHT_SPLITS + HEAVY_SPLITS

# Public landscape — every measured row has a JSON baseline.
COMPARISON_MATRIX: list[dict[str, Any]] = [
    {
        "repo_id": "bmd1905/vietnamese-correction-v2",
        "label": "bmd1905/vietnamese-correction-v2",
        "family": "public",
        "params": "400 M",
        "license": "Apache 2.0",
        "scores": {
            "business_55_light": 0.9118,
            "business_55_heavy": 0.7697,
            "formal_72_light": 0.8346,
            "formal_72_heavy": 0.7337,
            "conversational_300_light": 0.8472,
            "conversational_300_heavy": 0.7363,
            "literary_800_light": 0.8742,
            "literary_800_heavy": 0.6653,
        },
    },
    {
        "repo_id": "iAmHieu2012/vit5-vietnamese-spelling-correction",
        "label": "iAmHieu2012/vit5-vietnamese-spelling-correction",
        "family": "public",
        "params": "220 M",
        "license": "MIT",
        "scores": {
            "business_55_light": 0.9022,
            "business_55_heavy": 0.6898,
            "formal_72_light": 0.8538,
            "formal_72_heavy": 0.5133,
            "conversational_300_light": 0.8545,
            "conversational_300_heavy": 0.6377,
            "literary_800_light": 0.6181,
            "literary_800_heavy": 0.4211,
        },
    },
]


def check_gate(eval_data: dict[str, Any]) -> tuple[bool, str]:
    """Return (passed, reason)."""

    def _avg(splits: tuple[str, ...]) -> float | None:
        vals = [eval_data.get(s, {}).get("word_accuracy") for s in splits]
        present = [v for v in vals if v is not None]
        if not present:
            return None
        return sum(present) / len(present)

    light = _avg(LIGHT_SPLITS)
    heavy = _avg(HEAVY_SPLITS)
    if light is None or heavy is None:
        return False, f"missing eval data (light={light}, heavy={heavy})"
    if light < GATE_LIGHT_AVG_MIN:
        return False, (f"light avg word_accuracy {light:.4f} < gate {GATE_LIGHT_AVG_MIN:.4f}")
    if heavy < GATE_HEAVY_AVG_MIN:
        return False, (f"heavy avg word_accuracy {heavy:.4f} < gate {GATE_HEAVY_AVG_MIN:.4f}")
    return True, f"passed (light avg {light:.4f}, heavy avg {heavy:.4f})"


def _fmt_int(v: Any) -> str:
    if isinstance(v, int):
        return f"{v:,}"
    return "?"


def _render_comparison_section(
    publishing_repo_id: str,
    publishing_summary: dict[str, Any],
) -> str:
    eval_data = publishing_summary.get("eval", {})
    this_scores = {
        k: v.get("word_accuracy")
        for k, v in eval_data.items()
        if v.get("word_accuracy") is not None
    }

    rows: list[dict[str, Any]] = []
    matched = False
    for entry in COMPARISON_MATRIX:
        if entry["repo_id"] == publishing_repo_id:
            rows.append({**entry, "scores": this_scores or entry["scores"], "is_this": True})
            matched = True
        else:
            rows.append({**entry, "is_this": False})
    if not matched:
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

    # Compute light_avg + heavy_avg for each row.
    for r in rows:
        light_vals = [r["scores"].get(s) for s in LIGHT_SPLITS if r["scores"].get(s) is not None]
        heavy_vals = [r["scores"].get(s) for s in HEAVY_SPLITS if r["scores"].get(s) is not None]
        r["light_avg"] = sum(light_vals) / len(light_vals) if light_vals else None
        r["heavy_avg"] = sum(heavy_vals) / len(heavy_vals) if heavy_vals else None

    # Best in column for bolding.
    best_light = max((r["light_avg"] or 0.0 for r in rows), default=0.0)
    best_heavy = max((r["heavy_avg"] or 0.0 for r in rows), default=0.0)

    def _cell(v: float | None, best: float) -> str:
        if v is None:
            return "—"
        pct = f"{v * 100:.2f}"
        if abs(v - best) < 1e-6 and best > 0:
            return f"**{pct}**"
        return pct

    header = (
        "| Model | Family | Params | License | light avg | heavy avg |\n"
        "|---|---|---:|---|---:|---:|"
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
        cells = [
            label_md,
            r["family"],
            r["params"],
            r["license"],
            _cell(r["light_avg"], best_light),
            _cell(r["heavy_avg"], best_heavy),
        ]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def render_model_card(summary: dict[str, Any], repo_id: str, gate_status: str) -> str:
    base = summary["model_id"]
    eval_data = summary.get("eval", {})
    hp = summary.get("hyperparameters", {})

    base_lower = base.lower()
    if "vit5" in base_lower or "t5" in base_lower:
        arch_tag, arch_label = "t5", "ViT5"
    elif "bartpho" in base_lower:
        arch_tag, arch_label = "bartpho", "BARTpho-syllable"
    elif "mbart" in base_lower:
        arch_tag, arch_label = "mbart", "mBART"
    else:
        arch_tag, arch_label = "seq2seq", "seq2seq"

    rows: list[str] = []
    register_pretty = {
        "business_55_light": "Modern business / news (light)",
        "business_55_heavy": "Modern business / news (heavy / OCR)",
        "formal_72_light": "Formal / legal-prose (light)",
        "formal_72_heavy": "Formal / legal-prose (heavy / OCR)",
        "conversational_300_light": "Conversational (light)",
        "conversational_300_heavy": "Conversational (heavy / OCR)",
        "literary_800_light": "Classical literary (light)",
        "literary_800_heavy": "Classical literary (heavy / OCR)",
    }
    for key in ALL_SPLITS:
        m = eval_data.get(key)
        if not m:
            continue
        rows.append(
            f"| {register_pretty.get(key, key)} | {m['n_sentences']} | "
            f"{m['word_accuracy'] * 100:.2f} % | {m.get('sentence_exact', 0) * 100:.2f} % | "
            f"{m.get('mean_ms_per_sentence', 0):.0f} |"
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
  - spell-correction
  - seq2seq
  - {arch_tag}
pipeline_tag: text-generation
datasets:
  - nrl-ai/vn-spell-correction-train
metrics:
  - word_accuracy
  - sentence_exact
library_name: transformers
---

# {repo_id} — Vietnamese spell correction ({arch_label} fine-tune)

Fixes typos, missed accents, and OCR-style char errors in Vietnamese
text in one pass: `Toi yu Vit Nam` → `Tôi yêu Việt Nam`. Strictly more
than diacritic restoration — handles letter-level mistakes, missing /
extra characters, and OCR substitutions like `o`↔`0`, `l`↔`1`, `m`↔`rn`.

Fine-tuned from
[`{base}`](https://huggingface.co/{base}) on the
[`nrl-ai/vn-spell-correction-train`](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-train)
corpus (459K (noisy, clean) Vietnamese pairs synthesized from a
register-balanced Wiki+news mix via `nom.text.noise`).

**Adoption gate:** {gate_status}.

## Quick start

```python
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

tok = AutoTokenizer.from_pretrained("{repo_id}")
model = AutoModelForSeq2SeqLM.from_pretrained("{repo_id}").eval()

text = "Toi yu Vit Nam"
out = model.generate(**tok(text, return_tensors="pt"), max_length=256)
print(tok.decode(out[0], skip_special_tokens=True))
# Tôi yêu Việt Nam
```

For batched inference (recommended for high-throughput pipelines):

```python
from nom.text.diacritic_models import HFDiacriticModel
restorer = HFDiacriticModel(model_id="{repo_id}")
fixed = restorer.predict_batch(noisy_sentences, batch_size=16)
```

## Evaluation — 8-split spell-correction grid

Evaluation uses
[`nrl-ai/vn-spell-correction-eval`](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-eval)
(2,098 pairs across 4 registers x 2 noise levels). Word accuracy after
NFC + punctuation normalization on both sides.

| Register | Sents | Word acc | Sent exact | Mean ms/sent |
|---|---:|---:|---:|---:|
{eval_table}

Each split corresponds to a (register, noise level) combination:

- **light** noise — ~5 % char-level edit distance, models a person typing
  Vietnamese on a keyboard with a few accent slips and the occasional
  fat-finger.
- **heavy** noise — ~15-20 % edit distance, models OCR output of a
  mid-quality scan with diacritic drops + char confusions.

## How we compare

Where this model sits in the public Vietnamese spell-correction
landscape — same 8-split grid for every measured row.

{comparison_table}

The two averaged columns:

- **light avg** = mean word accuracy across the 4 light-noise splits.
- **heavy avg** = mean word accuracy across the 4 heavy-noise splits.

## Training

- **Base:** [`{base}`](https://huggingface.co/{base}) (MIT license)
- **Corpus:** {_fmt_int(summary.get("train_pairs"))} (noisy, clean) pairs from
  [`nrl-ai/vn-spell-correction-train`](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-train).
  Eval-leak guarded against [`nrl-ai/vn-spell-correction-eval`](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-eval)
  and [`nrl-ai/vn-diacritic-eval`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-eval).
- **Validation:** {_fmt_int(summary.get("val_pairs"))} held-out pairs.
- **Epochs:** {summary.get("epochs", "?")}
- **Effective batch size:** {hp.get("effective_batch_size", "?")} ({hp.get("batch_size", "?")} per device, grad-accum {hp.get("gradient_accumulation_steps", 1)})
- **Learning rate:** {hp.get("lr", "?")} with `{hp.get("lr_scheduler", "?")}` schedule, {hp.get("warmup_steps", "?")} warmup steps
- **Precision:** {"bf16" if hp.get("bf16") else "fp16" if hp.get("fp16") else "fp32"}
- **Sequence length:** input {hp.get("max_input_length", "?")}, target {hp.get("max_target_length", "?")}
- **Early stopping:** patience={hp.get("early_stopping_patience", "?")} on `eval_loss`
- **Training time:** {summary.get("training_minutes", "?")} min on a single NVIDIA RTX 3090 24 GB
- **Seed:** 42

## Intended use

- **Recommended:** cleaning up noisy Vietnamese text — OCR output,
  user-generated text from non-VN-IME keyboards, form data with typos,
  social-media short-form. Strictly harder than diacritic restoration
  but covers it as a subset.
- **Not recommended:** text generation, classification, sentiment, NER,
  or any task the input distribution doesn't match.

## Limitations

- **In-distribution metric, real-world is harder — measured.** Training
  and eval both use `nom.text.noise` with the same three presets —
  different seeds, but the same statistical noise distribution. The
  model has implicitly learned the inverse of *our* noise generator.
  We measured the OOD gap on a 100-sentence hand-curated real-world
  eval (forum slang / mobile autocorrect / real Telex / Tesseract+EasyOCR):

  | Slice | Word acc | Sent. exact |
  |---|---:|---:|
  | OCR engine output | 93.62 % | 60.0 % |
  | Mobile autocorrect | 95.01 % | 40.0 % |
  | Forum/social slang | 59.45 % | 0.0 % |
  | Real Telex keystrokes | 17.38 % | 0.0 % |
  | **Aggregate (n=100)** | **66.88 %** | 25.0 % |

  Synthetic light_avg is 98.58 %; real-world aggregate is 66.88 %. The
  32 pp gap is the cost of training only on `light/telex_typo/heavy`
  noise — those capture the *surface* of typos but not real Telex
  keystroke artefacts (`dduwojc` for `được`) or forum-style abbreviation
  syntax (`ko bt` for `không biết`). v0.2.29 retraining on the v2
  multi-source corpus + `comprehensive_noise()` (which adds
  `telex_grammar_noise()` and `mobile_noise()`) is queued and should
  close most of this gap.
- **Heavy-noise corner cases.** OCR outputs that drop entire words or
  add hallucinated text are out-of-scope; the noise generator we
  trained on caps edits per sentence (max 25 % edit ratio).
- **Long sequences truncate at {hp.get("max_target_length", "?")} sub-word tokens.**
  Split paragraphs at sentence boundaries before calling.
- **No grammar or stylistic correction.** This model fixes character /
  syllable / diacritic errors but doesn't rewrite phrasing.
- **Confidence intervals on small splits.** business_55 (44/55 sents)
  and formal_72 (65/72 sents) have ±3-4 pp 95 % CI; the larger
  literary_800 split has ±1 pp. Treat single-pp differences with care.

## License & attribution

Released under **Apache 2.0**. Cite both this model and the base:

```bibtex
@misc{{nom_vn_spell_correction_2026,
  title={{Vietnamese Spell Correction — register-balanced fine-tune}},
  author={{Nguyen, Viet-Anh and {{Neural Research Lab}}}},
  year={{2026}},
  howpublished={{\\url{{https://huggingface.co/{repo_id}}}}}
}}
```

Training data inherits CC-BY-SA-4.0 (Wikipedia portion) + CC-BY-4.0
(news portion). Output text is best treated as CC-BY-SA-4.0 if you
want to be safe.
"""


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--checkpoint-dir", type=Path, required=True)
    p.add_argument("--summary-json", type=Path, required=True)
    p.add_argument("--repo-id", required=True)
    p.add_argument("--commit-message", default="initial release")
    p.add_argument("--force", action="store_true")
    p.add_argument("--dry-run", action="store_true")
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
        gate_status = f"✅ passed — {reason}"
        print(f"Adoption gate: PASSED ({reason})")
    else:
        gate_status = f"⚠️  did not pass ({reason})"
        print(f"Adoption gate: FAILED — {reason}")
        if not args.force:
            print(
                "Refusing to publish a sub-gate model. Pass --force to override "
                "(the model card will note the gate-fail).",
                file=sys.stderr,
            )
            return 1

    readme_path = args.checkpoint_dir / "README.md"
    readme_text = render_model_card(summary, args.repo_id, gate_status)
    readme_path.write_text(readme_text, encoding="utf-8")
    print(f"Wrote model card: {readme_path}")

    if args.dry_run:
        print("\n--- DRY RUN — would upload ---")
        for f in sorted(args.checkpoint_dir.iterdir()):
            print(f"  {f.relative_to(args.checkpoint_dir)}  ({f.stat().st_size:,} bytes)")
        print(f"to https://huggingface.co/{args.repo_id}")
        return 0

    try:
        from huggingface_hub import HfApi, create_repo
    except ImportError as exc:
        print(f"ERROR: huggingface_hub not installed: {exc}", file=sys.stderr)
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
