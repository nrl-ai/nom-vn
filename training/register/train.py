"""Fine-tune PhoBERT-base for VN 4-class register classification.

Architecture choice: ``vinai/phobert-base`` — 135 M params, MIT license,
.bin (VinAI is a recognised major lab so .bin is acceptable per the
project's file-format trust ladder). PhoBERT requires word-segmented
input — we run :func:`nom.text.word_tokenize` and join multi-syllable
words with underscores per the BKai gotcha (raw text drops ≥ 15 pp).

Corpus assembly (source-provenance labeling, no human annotation):

- **FORMAL**       — ``benchmarks/data/udhr_vi/udhr_vi.txt`` (UDHR, PD)
- **BUSINESS**     — ``benchmarks/data/wiki_vi/articles.jsonl`` (CC-BY-SA)
- **CONVERSATIONAL** — ``benchmarks/data/tatoeba_vi/vie_sentences_sample_3k.tsv`` (CC-BY 2.0 FR)
- **LITERARY**     — ``benchmarks/data/wikisource_vi/*.txt`` (PD)

This is a *bootstrapping* labelling — it gives ~2 000 sentences/class,
balanced, NFC-normalised. The survey flagged the absence of a public
multi-register VN dataset as a research gap; this assembly is the
project's first labelled set, and a CC0-publishable artifact in itself.

Eval: stratified 70/10/20 train/val/test split per corpus. Report
macro-F1 (the metric that survives class imbalance) plus per-class F1
to flag corpus-overfitting. Target macro-F1 ≥ 0.85 on test set per
``docs/sota_vn_2026q2_expansion.md`` Tier 1 #1.

Run on a GPU box::

    TRAIN_HOST="${TRAIN_HOST:-the-gpu-host}"  # set to your remote
    python training/register/train.py \\
        --output-dir checkpoints/register-phobert-base \\
        --epochs 4 \\
        --batch-size 32

Smoke test before committing to a full run::

    python training/register/train.py --epochs 1 --max-steps 50 \\
        --max-samples-per-class 200 --output-dir /tmp/register-smoke
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from collections.abc import Iterator
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

REGISTER_LABELS: tuple[str, ...] = ("formal", "business", "conversational", "literary")


def _load_lines(path: Path, *, comment_prefix: str = "#") -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith(comment_prefix)
    ]


def _split_into_sentences(text: str) -> Iterator[str]:
    """Cheap sentence split — VN-aware split on .!?… followed by whitespace.

    We don't need perfect segmentation for this task; PhoBERT classifier
    only sees up to ``max_length=256`` tokens regardless. Discard anything
    < 12 chars (too short to carry a register signal) or > 800 chars
    (likely an unsplit paragraph that'd just truncate).
    """
    import re

    parts = re.split(r"(?<=[.!?…])\s+", text.strip())
    for p in parts:
        s = p.strip()
        if 12 <= len(s) <= 800:
            yield s


def _conllu_sentences(path: Path) -> Iterator[str]:
    """Yield each ``# text = ...`` line from a CoNLL-U file."""
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# text"):
            _, _, val = line.partition("=")
            v = val.strip()
            if v:
                yield v


def load_register_corpus(repo: Path) -> dict[str, list[str]]:
    """Return ``{label: [sentence, ...]}`` for the four registers."""
    out: dict[str, list[str]] = {lbl: [] for lbl in REGISTER_LABELS}

    # FORMAL — UDHR full text + the curated 72-sentence diacritic eval slice
    # (same domain, just pre-segmented). Both are PD.
    udhr = repo / "benchmarks" / "data" / "udhr_vi" / "udhr_vi.txt"
    if udhr.exists():
        for para in _load_lines(udhr):
            out["formal"].extend(_split_into_sentences(para))
    udhr_eval = repo / "benchmarks" / "data" / "udhr_vi" / "diacritic_eval_udhr.txt"
    if udhr_eval.exists():
        out["formal"].extend(_load_lines(udhr_eval))

    # BUSINESS — wiki articles, take the `extract` field. Wikipedia is a
    # rough proxy for "modern factual prose" — not pure news, but the
    # closest permissive corpus we have. Tag is honest.
    wiki = repo / "benchmarks" / "data" / "wiki_vi" / "articles.jsonl"
    if wiki.exists():
        with wiki.open(encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                obj = json.loads(line)
                if obj.get("missing"):
                    continue
                extract = (obj.get("extract") or "").strip()
                if extract:
                    out["business"].extend(_split_into_sentences(extract))

    # CONVERSATIONAL — Tatoeba TSV (``id\tlang\tsentence``) + the 300-line
    # diacritic eval slice from the same source.
    tat = repo / "benchmarks" / "data" / "tatoeba_vi" / "vie_sentences_sample_3k.tsv"
    if tat.exists():
        for line in tat.read_text(encoding="utf-8").splitlines():
            parts = line.split("\t")
            if len(parts) >= 3:
                s = parts[2].strip()
                if 6 <= len(s) <= 800:
                    out["conversational"].append(s)
    tat_eval = repo / "benchmarks" / "data" / "tatoeba_vi" / "diacritic_eval_300.txt"
    if tat_eval.exists():
        out["conversational"].extend(_load_lines(tat_eval))

    # LITERARY — Wikisource classical prose AND UD-VTB (literary
    # treebank, ~3 300 sentences across train/dev/test). Without UD-VTB
    # the literary class is only ~90 sentences from Wikisource — way
    # too small for a balanced 4-class classifier.
    for txt in (repo / "benchmarks" / "data" / "wikisource_vi").glob("*.txt"):
        full = txt.read_text(encoding="utf-8")
        out["literary"].extend(_split_into_sentences(full))
    for split in ("train", "dev", "test"):
        conllu = repo / "benchmarks" / "data" / "ud_vi_vtb" / f"{split}.conllu"
        if conllu.exists():
            out["literary"].extend(_conllu_sentences(conllu))

    return out


def _word_segment(text: str) -> str:
    """PhoBERT-friendly form: NFC + word-segmented + underscore-joined.

    Falls back to whitespace-tokenised text if ``nom.text.word_tokenize``
    isn't available (the segmenter has heavy optional deps). The fallback
    costs ~ -10 to -15 pp accuracy per the BKai gotcha — but lets the
    smoke test run on a clean machine.
    """
    from nom.text import normalize

    clean = normalize(text)
    try:
        from nom.text import word_tokenize

        return " ".join(tok.replace(" ", "_") for tok in word_tokenize(clean))
    except Exception:
        return clean


def _stratified_split(
    samples: list[tuple[str, int]], *, val_frac: float, test_frac: float, seed: int
) -> tuple[list[tuple[str, int]], list[tuple[str, int]], list[tuple[str, int]]]:
    """Stratified train/val/test split keyed on the label."""
    by_label: dict[int, list[tuple[str, int]]] = {}
    for s, lbl in samples:
        by_label.setdefault(lbl, []).append((s, lbl))

    rng = random.Random(seed)
    train: list[tuple[str, int]] = []
    val: list[tuple[str, int]] = []
    test: list[tuple[str, int]] = []
    for lbl, group in by_label.items():
        rng.shuffle(group)
        n = len(group)
        n_test = round(n * test_frac)
        n_val = round(n * val_frac)
        test.extend(group[:n_test])
        val.extend(group[n_test : n_test + n_val])
        train.extend(group[n_test + n_val :])
        del lbl  # only used for grouping

    rng.shuffle(train)
    return train, val, test


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--model-id", default="vinai/phobert-base")
    parser.add_argument("--output-dir", required=True, help="Where to save the fine-tuned head")
    parser.add_argument("--epochs", type=int, default=4)
    parser.add_argument("--batch-size", type=int, default=32)
    parser.add_argument("--max-length", type=int, default=256)
    parser.add_argument("--learning-rate", type=float, default=3e-5)
    parser.add_argument("--max-samples-per-class", type=int, default=2000)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-steps", type=int, default=-1, help="Cap for smoke tests; -1 = full")
    parser.add_argument("--val-frac", type=float, default=0.10)
    parser.add_argument("--test-frac", type=float, default=0.20)
    args = parser.parse_args()

    print(f"Loading corpus from {REPO / 'benchmarks' / 'data'} ...", flush=True)
    raw = load_register_corpus(REPO)
    rng = random.Random(args.seed)

    samples: list[tuple[str, int]] = []
    cap = args.max_samples_per_class
    for idx, lbl in enumerate(REGISTER_LABELS):
        sents = raw[lbl]
        rng.shuffle(sents)
        sents = sents[:cap]
        samples.extend((s, idx) for s in sents)
        print(f"  {lbl:>15} → {len(sents):4d} sentences", flush=True)
    if not samples:
        raise SystemExit("No training samples found — check benchmarks/data/ presence.")

    train, val, test = _stratified_split(
        samples, val_frac=args.val_frac, test_frac=args.test_frac, seed=args.seed
    )
    print(f"Split: train={len(train)} val={len(val)} test={len(test)}", flush=True)

    # Lazy-import the heavy ML stack — keeps the script readable even
    # without GPU deps installed.
    try:
        import numpy as np
        from datasets import Dataset
        from sklearn.metrics import classification_report, f1_score
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            EarlyStoppingCallback,
            Trainer,
            TrainingArguments,
        )
    except ImportError as exc:
        raise SystemExit(
            f"Missing ML deps for training: {exc}. Install with: "
            "pip install 'transformers>=4.45' 'torch>=2.0' 'datasets>=2.20' "
            "'scikit-learn>=1.4' numpy"
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(args.model_id, use_fast=False)
    label2id = {lbl: i for i, lbl in enumerate(REGISTER_LABELS)}
    id2label = dict(enumerate(REGISTER_LABELS))

    def to_ds(rows: list[tuple[str, int]]) -> Dataset:
        texts = [_word_segment(t) for t, _ in rows]
        labels = [lbl for _, lbl in rows]
        ds = Dataset.from_dict({"text": texts, "label": labels})

        def tokenize(batch: dict[str, list[str]]) -> dict[str, list[int]]:
            return tokenizer(
                batch["text"],
                truncation=True,
                max_length=args.max_length,
                padding=False,
            )

        return ds.map(tokenize, batched=True, remove_columns=["text"])

    train_ds = to_ds(train)
    val_ds = to_ds(val)
    test_ds = to_ds(test)

    model = AutoModelForSequenceClassification.from_pretrained(
        args.model_id,
        num_labels=len(REGISTER_LABELS),
        id2label=id2label,
        label2id=label2id,
    )

    def compute_metrics(eval_pred: tuple[np.ndarray, np.ndarray]) -> dict[str, float]:
        logits, labels = eval_pred
        preds = logits.argmax(axis=-1)
        macro_f1 = f1_score(labels, preds, average="macro")
        # Per-class F1 — exposed as {f1_formal, f1_business, ...} in the
        # log so a regression on any single register is visible without
        # waiting for an offline analysis.
        per = f1_score(labels, preds, average=None, labels=list(range(len(REGISTER_LABELS))))
        out = {"macro_f1": float(macro_f1)}
        for i, lbl in enumerate(REGISTER_LABELS):
            out[f"f1_{lbl}"] = float(per[i])
        return out

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=args.epochs,
        per_device_train_batch_size=args.batch_size,
        per_device_eval_batch_size=args.batch_size * 2,
        learning_rate=args.learning_rate,
        weight_decay=0.01,
        warmup_ratio=0.1,
        eval_strategy="epoch",
        save_strategy="epoch",
        load_best_model_at_end=True,
        metric_for_best_model="macro_f1",
        greater_is_better=True,
        logging_steps=20,
        save_total_limit=2,
        max_steps=args.max_steps if args.max_steps > 0 else -1,
        seed=args.seed,
        report_to=[],
        # Avoid the SDPA gotcha on PhoBERT (position table = 256, not 514)
        # by capping max_length above; no extra arg needed here.
    )

    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        tokenizer=tokenizer,
        compute_metrics=compute_metrics,
        callbacks=[EarlyStoppingCallback(early_stopping_patience=2)],
    )

    t0 = time.time()
    trainer.train()
    train_seconds = time.time() - t0

    print("\n=== Test set evaluation ===", flush=True)
    test_metrics = trainer.evaluate(test_ds, metric_key_prefix="test")

    # Detailed classification report — for the README history table.
    preds_logits = trainer.predict(test_ds).predictions
    pred_labels = preds_logits.argmax(axis=-1)
    true_labels = np.array([row["label"] for row in test_ds])
    report = classification_report(
        true_labels,
        pred_labels,
        target_names=list(REGISTER_LABELS),
        digits=4,
        zero_division=0,
    )
    print(report, flush=True)

    # Save checkpoint, tokenizer, and result.json — same convention as
    # training/diacritic and training/spell_correction.
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    result = {
        "model_id": args.model_id,
        "trained_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "train_seconds": round(train_seconds, 1),
        "config": {
            "epochs": args.epochs,
            "batch_size": args.batch_size,
            "max_length": args.max_length,
            "learning_rate": args.learning_rate,
            "max_samples_per_class": args.max_samples_per_class,
            "seed": args.seed,
        },
        "split_sizes": {"train": len(train), "val": len(val), "test": len(test)},
        "test_metrics": {
            k: float(v) for k, v in test_metrics.items() if isinstance(v, (int, float))
        },
        "labels": list(REGISTER_LABELS),
    }
    (output_dir / "result.json").write_text(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"\nWrote checkpoint + result.json to {output_dir}", flush=True)


if __name__ == "__main__":
    main()
