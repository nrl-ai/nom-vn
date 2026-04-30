"""Fine-tune a seq2seq model for Vietnamese spell correction.

Same training pipeline as `training/diacritic/train.py` (same hyperparams,
same `Seq2SeqTrainer` setup, same NFC discipline) but evaluates on the
spell-correction eval set under `benchmarks/data/spell_correction_eval/`
instead of the diacritic-only one. The training data is
`(noisy, clean)` pairs from `training/spell_correction/data/`.

Use the same `--model-id` flag to swap arch tiers (e.g.
`VietAI/vit5-base` for the base tier, `vinai/bartpho-syllable-base`
for the small tier).

Run (base tier)::

    python training/spell_correction/train.py \\
        --model-id VietAI/vit5-base \\
        --train-jsonl training/spell_correction/data/train.jsonl \\
        --val-jsonl training/spell_correction/data/val.jsonl \\
        --epochs 5 --batch-size 32 --bf16 \\
        --lr 5e-4 --lr-scheduler cosine \\
        --early-stopping-patience 0 \\
        --eval-steps 2000 --save-steps 2000 --eval-samples 1000 \\
        --output-dir training/spell_correction/checkpoints/vit5-base-500k
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

# Reuse the metric definition and punct-normalization from the diacritic
# train script — keep behaviour aligned across tasks so a future tier
# bench is comparable.
sys.path.insert(0, str(REPO))
from training.diacritic.train import _word_accuracy, normalize_punct  # noqa: E402

# Spell-correction eval registers: 4 source registers x 2 noise levels.
EVAL_REGISTERS = (
    "business_55_light",
    "business_55_heavy",
    "formal_72_light",
    "formal_72_heavy",
    "conversational_300_light",
    "conversational_300_heavy",
    "literary_800_light",
    "literary_800_heavy",
)


def _load_eval_jsonl(path: Path) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw or raw.startswith("#"):
            continue
        rec = json.loads(raw)
        inp = unicodedata.normalize("NFC", rec["input"])
        tgt = unicodedata.normalize("NFC", rec["target"])
        pairs.append((inp, tgt))
    return pairs


def load_eval_corpora(repo: Path) -> dict[str, list[tuple[str, str]]]:
    """Load the spell-correction eval set (8 splits)."""
    out: dict[str, list[tuple[str, str]]] = {}
    eval_dir = repo / "benchmarks" / "data" / "spell_correction_eval"
    for name in EVAL_REGISTERS:
        path = eval_dir / f"{name}.jsonl"
        if path.exists():
            out[name] = _load_eval_jsonl(path)
    return out


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--model-id", default="VietAI/vit5-base")
    p.add_argument(
        "--train-jsonl",
        type=Path,
        default=REPO / "training" / "spell_correction" / "data" / "train.jsonl",
    )
    p.add_argument(
        "--val-jsonl",
        type=Path,
        default=REPO / "training" / "spell_correction" / "data" / "val.jsonl",
    )
    p.add_argument(
        "--output-dir",
        type=Path,
        default=REPO / "training" / "spell_correction" / "checkpoints" / "vit5-base",
    )
    p.add_argument("--epochs", type=int, default=5)
    p.add_argument("--batch-size", type=int, default=32)
    p.add_argument("--gradient-accumulation-steps", type=int, default=1)
    p.add_argument("--gradient-checkpointing", action="store_true")
    p.add_argument("--lr", type=float, default=5e-4)
    p.add_argument(
        "--lr-scheduler",
        choices=("linear", "cosine", "constant", "constant_with_warmup"),
        default="cosine",
    )
    p.add_argument("--max-input-length", type=int, default=256)
    p.add_argument("--max-target-length", type=int, default=256)
    p.add_argument("--warmup-steps", type=int, default=500)
    p.add_argument("--early-stopping-patience", type=int, default=0)
    p.add_argument("--max-steps", type=int, default=-1)
    p.add_argument("--eval-steps", type=int, default=2000)
    p.add_argument("--save-steps", type=int, default=2000)
    p.add_argument("--logging-steps", type=int, default=200)
    p.add_argument("--num-workers", type=int, default=2)
    p.add_argument("--fp16", action="store_true")
    p.add_argument("--bf16", action="store_true")
    p.add_argument("--eval-samples", type=int, default=1000)
    args = p.parse_args()

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
    print(f"GPU: {torch.cuda.is_available()=}")

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
        inputs = [unicodedata.normalize("NFC", s) for s in batch["input"]]
        targets = [unicodedata.normalize("NFC", s) for s in batch["target"]]
        model_inputs = tokenizer(
            inputs, max_length=args.max_input_length, truncation=True, padding=False
        )
        labels = tokenizer(
            targets, max_length=args.max_target_length, truncation=True, padding=False
        )
        model_inputs["labels"] = labels["input_ids"]
        return model_inputs

    print("Tokenizing...")
    tokenized = raw.map(preprocess, batched=True, remove_columns=["input", "target"])

    data_collator = DataCollatorForSeq2Seq(tokenizer, model=model, padding="longest")

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
        lr_scheduler_type=args.lr_scheduler,
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

    callbacks = []
    if args.early_stopping_patience > 0:
        from transformers import EarlyStoppingCallback

        callbacks.append(
            EarlyStoppingCallback(early_stopping_patience=args.early_stopping_patience)
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
        callbacks=callbacks,
    )

    print("Training...")
    t_train_start = time.perf_counter()
    trainer.train()
    training_minutes = round((time.perf_counter() - t_train_start) / 60, 1)
    print(f"Training time: {training_minutes:.1f} min")

    final_dir = args.output_dir / "final"
    trainer.save_model(str(final_dir))
    tokenizer.save_pretrained(str(final_dir))
    print(f"Saved best model to {final_dir}")

    # ============= 8-register spell-correction eval =============
    print()
    print("=" * 70)
    print("Multi-register spell-correction eval (4 registers x 2 noise levels)")
    print("=" * 70)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = model.to(device).eval()
    corpora = load_eval_corpora(REPO)
    eval_summary: dict[str, dict[str, float]] = {}
    for name, pairs in corpora.items():
        print(f"\n--- {name} ({len(pairs)} sentences) ---")
        preds: list[str] = []
        targets: list[str] = []
        t_eval = time.perf_counter()
        for noisy, target in pairs:
            x = tokenizer(
                noisy, return_tensors="pt", max_length=args.max_input_length, truncation=True
            ).to(device)
            with torch.no_grad():
                out = model.generate(**x, max_length=args.max_target_length, num_beams=1)
            pred = tokenizer.decode(out[0], skip_special_tokens=True)
            preds.append(pred)
            targets.append(target)
        elapsed = time.perf_counter() - t_eval
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
        for noisy, target in pairs[:2]:
            x = tokenizer(
                noisy, return_tensors="pt", max_length=args.max_input_length, truncation=True
            ).to(device)
            with torch.no_grad():
                out = model.generate(**x, max_length=args.max_target_length, num_beams=1)
            pred = tokenizer.decode(out[0], skip_special_tokens=True)
            print(f"    IN:  {noisy[:120]}")
            print(f"    GT:  {normalize_punct(target)[:120]}")
            print(f"    OUT: {normalize_punct(pred)[:120]}")
            print()

    summary = {
        "task": "spell-correction",
        "model_id": args.model_id,
        "epochs": args.epochs,
        "train_pairs": len(tokenized["train"]),
        "val_pairs": len(tokenized["validation"]),
        "training_minutes": training_minutes,
        "hyperparameters": {
            "batch_size": args.batch_size,
            "gradient_accumulation_steps": args.gradient_accumulation_steps,
            "effective_batch_size": args.batch_size * args.gradient_accumulation_steps,
            "lr": args.lr,
            "lr_scheduler": args.lr_scheduler,
            "warmup_steps": args.warmup_steps,
            "max_input_length": args.max_input_length,
            "max_target_length": args.max_target_length,
            "early_stopping_patience": args.early_stopping_patience,
            "bf16": args.bf16,
            "fp16": args.fp16,
            "gradient_checkpointing": args.gradient_checkpointing,
        },
        "eval": eval_summary,
        "device": device,
        "checkpoint": str(final_dir),
    }
    summary_path = args.output_dir / "training_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    print(f"Wrote: {summary_path}")
    return 0


# Make `re` import explicit (used by normalize_punct via training.diacritic.train)
_ = re

if __name__ == "__main__":
    sys.exit(main())
