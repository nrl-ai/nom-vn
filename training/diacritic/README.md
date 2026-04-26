# Training a Vietnamese diacritic-restoration model

## Why we're training

The 2026-04-26 audit measured `Toshiiiii1/Vietnamese_diacritics_restoration_5th`
(Apache 2.0, T5 200 M, ~1 GB safetensors) at:

| Eval corpus | Word acc |
|---|---:|
| `diacritic_eval_v0.txt` (55 sents, modern business) | **97.81 %** |
| `ud_vi_vtb/test.conllu` (800 sents, classical literary) | **89.40 %** |

Toshiiiii1 is the strongest off-the-shelf option but it's register-overfit
to modern/business Vietnamese — 8 pp drop on classical-literary register.
Training a register-balanced model on Wikipedia (which spans encyclopedic,
historical, and technical registers) is the natural next step.

## Architecture

`google/mt5-small` (Apache 2.0, safetensors, ~300 M params, ~1.2 GB on
disk). Smaller than Toshiiiii1's T5 base by total parameters but bigger
on disk because most of mT5-small's weight lives in the shared
multilingual embedding table. A future pruning pass (drop unused-language
embedding rows) could ship the active subset at ~500 MB; out of scope
for this experiment.

ByT5-small (300 M, char-level, robust to typos per
[arXiv:2201.13242](https://arxiv.org/abs/2201.13242)) is the canonical
SOTA for VN diacritic restoration in the literature. We picked mT5-small
instead for two reasons:

1. **Smaller fine-tuning footprint.** ByT5 needs ~4 × longer sequences
   (it's byte-level), so training cost is meaningfully higher.
2. **Closer architectural parallel to Toshiiiii1** — apples-to-apples
   register-spread comparison.

If mT5-small under-performs we'll follow up with ByT5-small as a
register-robustness experiment.

## Data

`benchmarks/data/diacritic_eval_v0.txt` and
`benchmarks/data/ud_vi_vtb/test.conllu` are **held out** — both are
public eval corpora and we MUST NOT include their sentences in
training. `prep_data.py` enforces this via a hash-set check.

Source: [`hirine/wikipedia-vietnamese-1M296K-dataset`](https://huggingface.co/datasets/hirine/wikipedia-vietnamese-1M296K-dataset)
(CC-BY-SA-4.0, ~1.3 M Wikipedia articles, light cleaning applied
upstream — wiki templates and `<ref>` tags removed).

Pipeline:

1. Stream the dataset (don't download all 1.5 GB).
2. Sentence-split each article (regex on terminator + capital VN letter).
3. Filter:
   - 30 ≤ len(sent) ≤ 300 chars (training-friendly length).
   - `has_diacritics(sent)` (no signal otherwise).
   - ASCII ratio ≤ 95 % (drop tables / URL blocks).
   - Not in eval-leak guard set.
   - Deduplicate against earlier emissions.
4. Stride-sample every 7th eligible sentence — diverse without RNG.
5. Generate `(stripped, target)` pairs.

Run::

    python training/diacritic/prep_data.py --max-pairs 200_000

For the v0.2.x training experiment we use **200 k pairs**. A v0.3 run
should use 1 M+ pairs.

## Training

`train.py` uses HF `Seq2SeqTrainer`. Defaults:

- `epochs=3`, `batch_size=32`, `lr=5e-4`, warmup 500 steps
- bf16 mixed precision (recommended on Ampere+ GPUs)
- `eval_steps=500`, `save_steps=500` (must be aligned for
  `load_best_model_at_end=True`)
- `metric_for_best_model="eval_loss"` for the inner loop
- After training, runs the multi-corpus eval and saves
  `training_summary.json`

Run on the GPU box (genpc2 in our setup)::

    ./training/diacritic/launch_genpc2.sh \
        --epochs 3 --batch-size 32 --bf16 \
        --output-dir training/diacritic/checkpoints/mt5-small-200k

The launcher rsyncs code+data to genpc2, kicks off `python train.py`
under `nohup`, and returns the PID. Monitoring::

    ssh genpc2 'tail -f ~/nom-vn-train/training/diacritic/run.log'
    ssh genpc2 'cat ~/nom-vn-train/training/diacritic/run.pid'

## Multi-corpus evaluation

Per CLAUDE.md autonomous-loop §5, single-corpus eval is not enough.
`train.py` generates predictions on **both** corpora at the end of
training and reports word-accuracy + sentence-exact for each:

```json
{
  "eval": {
    "business_55":  {"word_accuracy": 0.???, "sentence_exact": 0.???},
    "literary_udvtb": {"word_accuracy": 0.???, "sentence_exact": 0.???}
  }
}
```

## Adoption gate

We adopt the trained checkpoint **only if** both:

- `business_55.word_accuracy >= 0.96` (within 2 pp of Toshiiiii1's 97.81 %)
- `literary_udvtb.word_accuracy > 0.89` (improves on Toshiiiii1's 89.40 %)

That is: the model must be *at least* register-balanced, even if it
loses some absolute peak quality on business.

If the gate is met, publish to `nrl-ai/vn-diacritic-restoration`
on HF Hub via `huggingface-cli upload`.

If not met, archive the checkpoint, document why in
`docs/training_plan_2026q2.md`, and queue a follow-up: more data
(1 M+ pairs), bigger base (mT5-base 580 M), or character-level (ByT5).

## Reproducibility

```bash
python training/diacritic/prep_data.py --max-pairs 200_000 --seed 42
./training/diacritic/launch_genpc2.sh \
    --epochs 3 --batch-size 32 --bf16 \
    --output-dir training/diacritic/checkpoints/mt5-small-200k
```

Both scripts pin their data source (`hirine/wikipedia-vietnamese-1M296K-dataset`)
and stride/seed so a clean clone produces the same splits.
