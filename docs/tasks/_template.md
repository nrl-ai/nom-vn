# {Task name}

> **Template** for `docs/tasks/<name>.md` pages. Each page consolidates
> everything a user needs to make a decision for one task: what's
> available publicly, what we built, what we measured, how to reproduce.
> Delete this blockquote when copying.

## TL;DR — our recommendation

One paragraph. What pip extra to install, what model to use, what license,
what the measured number is on what register.

## Public landscape

Per CLAUDE.md principles 11 + 12. Every row backed by a license + format
audit and a measured or cited number. **Numbers without a citation or a
runnable bench script are forbidden.**

| Model / Tool | License | Format | Reported quality | Verdict |
|---|---|---|---:|---|
| ... | Apache 2.0 | safetensors | XX.XX % on {corpus} | use / skip / TBD |

## Our pipeline

How `nom.{module}` solves this. Mention the Protocol seam, the default
backend, and the swap path for users who want a different model.

```python
# Typical 3-line use case
```

## Trained models — `nrl-ai/*`

Per CLAUDE.md principle 13 (Viet-Anh Nguyen on every artifact) +
principle 14 (verify HF page after publish).

| HF model | License | Tier | Δ vs SOTA | When to pick |
|---|---|---|---:|---|
| [`nrl-ai/vn-{task}-base`](https://huggingface.co/nrl-ai/vn-{task}-base) | Apache-2.0 | 220 M | TBD | default |
| [`nrl-ai/vn-{task}-small`](https://huggingface.co/nrl-ai/vn-{task}-small) | Apache-2.0 | 60 M | TBD | fast tier |

## Datasets — `nrl-ai/*`

| HF dataset | License | What it is | Splits |
|---|---|---|---|
| [`nrl-ai/vn-{task}-eval`](https://huggingface.co/datasets/nrl-ai/vn-{task}-eval) | mixed | held-out eval | per-register splits |
| [`nrl-ai/vn-{task}-train`](https://huggingface.co/datasets/nrl-ai/vn-{task}-train) | mixed | training pairs | per-source configs |

## Results — measured

The headline numbers, with a link to the JSON baseline + the bench script
that produced them. Per CLAUDE.md principle 12, every cell is reproducible
on a clean clone.

| Register | Sentences | Best model | Word acc | Latency |
|---|---:|---|---:|---:|
| ... | ... | ... | ... | ... |

JSON baselines:
- `benchmarks/results/baseline_<task>_<model>.json`

## Reproduce

```bash
# Build eval slices (deterministic, no network)
python benchmarks/data/<corpus>/build_eval.py

# Bench
python benchmarks/accuracy/bench_<task>.py \
    <model_id> --json benchmarks/results/baseline_<task>_<model>.json
```

## Training

If we trained models for this task, point at:

- `training/<task>/README.md` for the experiment history table.
- `training/<task>/train.py`, `prep_data.py`, `eval_checkpoint.py`,
  `publish_hf.py` for the full pipeline.

## References

- Paper / model card / project URL for every claim above.
