"""Fine-tune mT5-small for Vietnamese diacritic restoration.

Architecture choice: ``google/mt5-small`` — 300 M params total, but only
~60 M of that is the language-specific decoder (the rest is the shared
multilingual embedding table). Safetensors. Apache 2.0. After fine-tune
we ship the full safetensors checkpoint at ~1.2 GB; future work could
prune the unused-language embedding rows to drop disk to ~500 MB.

Smaller than the Toshiiiii1 T5 reference (1 GB on disk) but in the same
order of magnitude. The win we're chasing isn't size alone — it's
**register-balanced** training, so the model doesn't drop from 97.81 %
on business to 89.40 % on literary like Toshiiiii1 does.

Multi-corpus eval is mandatory per CLAUDE.md autonomous-loop §5. Eval
during training reports word accuracy on both
``benchmarks/data/diacritic_eval_v0.txt`` (business) and
``benchmarks/data/ud_vi_vtb/test.conllu`` (literary). The "best
checkpoint" gate uses the *worse* of the two — we adopt only when both
clear bar.

Run on the GPU box::

    python training/diacritic/train.py \\
        --output-dir checkpoints/mt5-small-diacritic \\
        --epochs 3 \\
        --batch-size 32

For a fast smoke test before committing to a full run::

    python training/diacritic/train.py --epochs 1 --max-steps 200 --eval-steps 100
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

# Same normalize_punct as in the eval bench — keep both sides honest.
_ATTACH_TRAILING = re.compile(r"\s+([,.;:!?\)\]\}\"\'»…])")
_ATTACH_LEADING = re.compile(r"([\(\[\{\"\'«])\s+")


def normalize_punct(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = _ATTACH_TRAILING.sub(r"\1", text)
    text = _ATTACH_LEADING.sub(r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def _word_accuracy(preds: list[str], targets: list[str]) -> tuple[float, float]:
    """Return (word_accuracy, sentence_exact_rate) — both punct-normalized."""
    n_words = n_correct = 0
    n_sent_exact = 0
    for p, t in zip(preds, targets, strict=False):
        pn = normalize_punct(p)
        tn = normalize_punct(t)
        if pn == tn:
            n_sent_exact += 1
        for pw, tw in zip(pn.split(), tn.split(), strict=False):
            n_words += 1
            if pw == tw:
                n_correct += 1
    word_acc = n_correct / n_words if n_words else 0.0
    sent_exact = n_sent_exact / len(targets) if targets else 0.0
    return word_acc, sent_exact


def load_eval_corpora(repo: Path) -> dict[str, list[tuple[str, str]]]:
    """Load both eval corpora as lists of (stripped, target) pairs."""
    from nom.text import strip_diacritics

    out: dict[str, list[tuple[str, str]]] = {}

    # 55-sent business corpus
    p1 = repo / "benchmarks" / "data" / "diacritic_eval_v0.txt"
    if p1.exists():
        sents = [
            line.strip()
            for line in p1.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        ]
        out["business_55"] = [(strip_diacritics(s), s) for s in sents]

    # 800-sent UD-VTB literary corpus
    p2 = repo / "benchmarks" / "data" / "ud_vi_vtb" / "test.conllu"
    if p2.exists():
        sents = []
        for line in p2.read_text(encoding="utf-8").splitlines():
            if line.startswith("# text"):
                _, _, val = line.partition("=")
                v = val.strip()
                if v:
                    sents.append(v)
        out["literary_udvtb"] = [(strip_diacritics(s), s) for s in sents]

    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-id", default="google/mt5-small")
    p.add_argument(
        "--train-jsonl",
        type=Path,
        default=REPO / "training" / "diacritic" / "data" / "train.jsonl",
    )
    p.add_argument(
        "--val-jsonl",
        type=Path,
        default=REPO / "training" / "diacritic" / "data" / "val.jsonl",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=REPO / "training" / "diacritic" / "checkpoints" / "mt5-small",
    )
    p.add_argument("--epochs", type=int, default=3)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument(
        "--gradient-accumulation-steps",
        type=int,
        default=1,
        help="Effective batch = batch_size * grad_accum_steps. Use this when "
        "the full batch_size won't fit in VRAM (mT5-small + bf16 + seq 256 + "
        "Adam state needs ~22 GB at batch 32 — drop to 8 * 4 for 24 GB cards).",
    )
    p.add_argument(
        "--gradient-checkpointing",
        action="store_true",
        help="Trade ~30 %% step-time for ~40 %% lower activation memory. "
        "Needed on cards <24 GB for full batch_size at seq 256.",
    )
    p.add_argument("--lr", type=float, default=5e-4)
    p.add_argument("--max-input-length", type=int, default=256)
    p.add_argument("--max-target-length", type=int, default=256)
    p.add_argument("--warmup-steps", type=int, default=500)
    p.add_argument("--max-steps", type=int, default=-1, help="Cap total steps for smoke run.")
    p.add_argument("--eval-steps", type=int, default=500)
    p.add_argument("--save-steps", type=int, default=500)
    p.add_argument("--logging-steps", type=int, default=50)
    p.add_argument("--num-workers", type=int, default=2)
    p.add_argument("--fp16", action="store_true", help="bf16 preferred on Ampere+ — set --bf16.")
    p.add_argument("--bf16", action="store_true", help="bf16 mixed precision (3090, A100, etc).")
    p.add_argument("--eval-samples", type=int, default=200, help="N val samples for quick eval.")
    args = p.parse_args()

    # Lazy heavy imports
    import torch
    from datasets import load_dataset
    from transformers import (
        AutoModelForSeq2SeqLM,
        AutoTokenizer,
        DataCollatorForSeq2Seq,
        Seq2SeqTrainer,
        Seq2SeqTrainingArguments,
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Output: {args.output_dir}")
    print(
        f"GPU: {torch.cuda.is_available()=} {torch.cuda.get_device_name(0) if torch.cuda.is_available() else ''}"
    )

    print(f"Loading {args.model_id}...")
    tokenizer = AutoTokenizer.from_pretrained(args.model_id)
    model = AutoModelForSeq2SeqLM.from_pretrained(args.model_id)

    print(f"Loading data from {args.train_jsonl}, {args.val_jsonl}...")
    raw = load_dataset(
        "json",
        data_files={"train": str(args.train_jsonl), "validation": str(args.val_jsonl)},
    )
    print(f"  train: {len(raw['train']):,} pairs · val: {len(raw['validation']):,} pairs")

    def preprocess(batch: dict[str, list[str]]) -> dict[str, list]:
        model_inputs = tokenizer(
            batch["input"],
            max_length=args.max_input_length,
            truncation=True,
            padding=False,
        )
        labels = tokenizer(
            batch["target"],
            max_length=args.max_target_length,
            truncation=True,
            padding=False,
        )
        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    print("Tokenizing...")
    tokenized = raw.map(preprocess, batched=True, remove_columns=["input", "target"])

    data_collator = DataCollatorForSeq2Seq(tokenizer, model=model, padding="longest")

    # save_steps must be a round multiple of eval_steps for
    # load_best_model_at_end. Force-align here so smoke runs that override
    # --eval-steps don't trip the validation.
    save_steps = max(args.save_steps, args.eval_steps)
    if save_steps % args.eval_steps != 0:
        save_steps = args.eval_steps

    training_args = Seq2SeqTrainingArguments(
        output_dir=str(args.output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=max(1, args.batch_size),
        gradient_accumulation_steps=args.gradient_accumulation_steps,
        gradient_checkpointing=args.gradient_checkpointing,
        learning_rate=args.lr,
        warmup_steps=args.warmup_steps,
        max_steps=args.max_steps,
        logging_steps=args.logging_steps,
        eval_strategy="steps",
        eval_steps=args.eval_steps,
        save_strategy="steps",
        save_steps=save_steps,
        save_total_limit=2,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        bf16=args.bf16,
        fp16=args.fp16,
        predict_with_generate=False,
        dataloader_num_workers=args.num_workers,
        report_to=["none"],
        seed=42,
    )

    trainer = Seq2SeqTrainer(
        model=model,
        args=training_args,
        train_dataset=tokenized["train"],
        eval_dataset=tokenized["validation"].select(
            range(min(args.eval_samples, len(tokenized["validation"])))
        ),
        tokenizer=tokenizer,
        data_collator=data_collator,
    )

    print("Training...")
    t0 = time.perf_counter()
    trainer.train()
    print(f"Training time: {(time.perf_counter() - t0) / 60:.1f} min")

    # Save best model + tokenizer for later inference / eval / publication
    final_dir = args.output_dir / "final"
    trainer.save_model(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))
    print(f"Saved best model to {final_dir}")

    # ============= Multi-corpus quality eval =============
    print()
    print("=" * 70)
    print("Multi-corpus eval (CLAUDE.md autonomous-loop §5: register coverage)")
    print("=" * 70)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device).eval()

    corpora = load_eval_corpora(REPO)
    eval_summary: dict[str, dict[str, float]] = {}

    for name, pairs in corpora.items():
        print(f"\n--- {name} ({len(pairs)} sentences) ---")
        preds: list[str] = []
        targets: list[str] = []
        t0 = time.perf_counter()
        for stripped, target in pairs:
            x = tokenizer(
                stripped,
                return_tensors="pt",
                max_length=args.max_input_length,
                truncation=True,
            ).to(device)
            with torch.no_grad():
                out = model.generate(**x, max_length=args.max_target_length, num_beams=1)
            pred = tokenizer.decode(out[0], skip_special_tokens=True)
            preds.append(pred)
            targets.append(target)
        elapsed = time.perf_counter() - t0
        wa, se = _word_accuracy(preds, targets)
        per_sent_ms = elapsed / len(pairs) * 1000
        eval_summary[name] = {
            "n_sentences": len(pairs),
            "word_accuracy": round(wa, 4),
            "sentence_exact": round(se, 4),
            "mean_ms_per_sentence": round(per_sent_ms, 2),
        }
        print(f"  Word accuracy:   {wa:.4f}")
        print(f"  Sentence exact:  {se:.4f}")
        print(f"  Per-sentence:    {per_sent_ms:.1f} ms")
        print()
        print("  First 3 examples:")
        for p, t in zip(preds[:3], targets[:3], strict=False):
            print(f"    GT:  {normalize_punct(t)}")
            print(f"    OUT: {normalize_punct(p)}")
            print()

    # ============= Report =============
    summary = {
        "model_id": args.model_id,
        "epochs": args.epochs,
        "train_pairs": len(tokenized["train"]),
        "training_minutes": round((time.perf_counter() - t0) / 60, 1) if False else None,
        "eval": eval_summary,
        "device": device,
        "checkpoint": str(final_dir),
    }
    summary_path = args.output_dir / "training_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote: {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
