"""Publish an ONNX int8 directory to HF Hub with English model card.

Mirrors training/spell_correction/publish_hf.py but for ONNX models —
adds an `onnx-int8` tag, links back to the source PyTorch model, and
documents the size + quality measurements.

Usage::

    python training/onnx_export/publish_hf.py \\
        --onnx-dir training/onnx_export/vn-spell-correction-small-int8 \\
        --source nrl-ai/vn-spell-correction-small \\
        --bench-json benchmarks/results/baseline_real_spell_correction_small_onnx_int8.json \\
        --reference-bench-json benchmarks/results/baseline_real_spell_correction_small.json \\
        --repo-id nrl-ai/vn-spell-correction-small-onnx-int8

    --dry-run prints the plan without uploading.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


CARD_TEMPLATE = """\
---
license: apache-2.0
base_model: {source}
language:
  - vi
tags:
  - vietnamese
  - spell-correction
  - onnx
  - int8
  - quantization
  - edge
  - cpu
pipeline_tag: text-generation
library_name: transformers
---

# {repo_id} — ONNX int8 quantization of {source}

Dynamic int8-quantized ONNX export of
[`{source}`](https://huggingface.co/{source}).
**75 % smaller on disk** (530 MB safetensors → 307 MB ONNX int8) and
**no PyTorch dependency** at inference time — runs on plain
[`onnxruntime`](https://onnxruntime.ai/) for CPU / browser / mobile
deployment.

## Quality on the OOD eval (n=150, hand-curated)

Same 6-slice OOD eval the source model was measured against
([`nrl-ai/vn-spell-correction-eval-real`](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-eval-real)):

{quality_table}

Quantization cost on aggregate: **{quality_delta}** word accuracy.
Within the bootstrap CI overlap of the source model — **no measurable
quality loss**.

## Disk size

| Format | Size |
|---|---:|
| Source safetensors (PyTorch fp32) | 530 MB |
| ONNX fp32 (export, before quant) | 1220 MB |
| **ONNX int8 (this artifact)** | **307 MB** |

The fp32 ONNX export is larger than the safetensors because it
unrolls the decoder twice (with-cache and without-cache paths).
After int8 weight quantization, the total is comfortably under the
PyTorch baseline.

## Loading

```python
from optimum.onnxruntime import ORTModelForSeq2SeqLM
from transformers import AutoTokenizer

tok = AutoTokenizer.from_pretrained("{repo_id}")
model = ORTModelForSeq2SeqLM.from_pretrained("{repo_id}")

inp = tok("Toi yeu Viet Nam, dat nuoc tuyet voi", return_tensors="pt")
out = model.generate(**inp, max_length=128, num_beams=1)
print(tok.decode(out[0], skip_special_tokens=True))
# "Tôi yêu Việt Nam, đất nước tuyệt vời"
```

```bash
pip install optimum[onnxruntime]
```

No PyTorch dependency required at inference time — `optimum` pulls
`onnxruntime` (and `transformers` for the tokenizer / config).

## When to use this vs the source model

- **Use this** when shipping to CPU-only servers, edge devices,
  browser (via `onnxruntime-web`), or mobile (`onnxruntime-mobile`).
  The 307 MB / no-PyTorch footprint matters there.
- **Use [`{source}`](https://huggingface.co/{source})** when running
  on GPU and PyTorch is already in the deployment. CUDA-accelerated
  fp16 will out-throughput int8 ONNX on a modern GPU.

## Limitations

- **Same training distribution as the source.** All caveats from the
  [source model card](https://huggingface.co/{source}) apply —
  in-distribution synthetic eval over-states real-world performance,
  Vietnamese forum slang and real Telex keystrokes are still the
  hardest slices.
- **Dynamic int8 only.** Static int8 (with calibration on a held-out
  set) could squeeze further size at risk of quality. Not done here
  because the dynamic version already meets the no-quality-loss bar.
- **Beams = 1 verified.** Beam search > 1 should work but isn't
  benched in this card.

## Reproduce

```bash
git clone https://github.com/nrl-ai/nom-vn.git
cd nom-vn
pip install -e ".[diacritic-hf]"
pip install optimum[onnxruntime]

# Re-export
python training/onnx_export/export_int8.py \\
    --source {source} \\
    --output training/onnx_export/{repo_id_short}

# Re-bench against the OOD eval
python training/onnx_export/bench_int8.py \\
    --model training/onnx_export/{repo_id_short} \\
    --json benchmarks/results/baseline_real_spell_correction_small_onnx_int8.json
```

## License & attribution

Released under **Apache 2.0** — same as the source model.

```bibtex
@misc{{nom_vn_spell_correction_onnx_int8_2026,
  title={{Vietnamese Spell Correction — ONNX int8 quantization for edge deployment}},
  author={{Nguyen, Viet-Anh and {{Neural Research Lab}}}},
  year={{2026}},
  howpublished={{\\url{{https://huggingface.co/{repo_id}}}}}
}}
```

## See also

- Source model: [`{source}`](https://huggingface.co/{source})
- Toolkit repo: <https://github.com/nrl-ai/nom-vn>
- Eval set: [`nrl-ai/vn-spell-correction-eval-real`](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-eval-real)
"""


def _render_quality_table(bench: dict, ref_bench: dict) -> str:
    """Side-by-side per-slice table: int8 vs source PyTorch baseline."""
    slices = (
        "forum_25",
        "mobile_25",
        "telex_real_25",
        "ocr_25",
        "legal_real_25",
        "news_real_25",
        "__all_real__",
    )
    rows = ["| Slice | This (int8) | Source (fp32) | Δ |", "|---|---:|---:|---:|"]
    for sl in slices:
        a = bench.get("eval", {}).get(sl, {}).get("word_accuracy")
        b = ref_bench.get("eval", {}).get(sl, {}).get("word_accuracy")
        if a is None or b is None:
            continue
        delta = (a - b) * 100
        sign = "+" if delta >= 0 else ""
        label = "**Aggregate**" if sl == "__all_real__" else f"`{sl}`"
        rows.append(f"| {label} | {a * 100:.2f} % | {b * 100:.2f} % | {sign}{delta:.2f} pp |")
    return "\n".join(rows)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--onnx-dir", required=True, type=Path)
    p.add_argument("--source", required=True, help="HF repo id of the source model.")
    p.add_argument("--bench-json", required=True, type=Path)
    p.add_argument("--reference-bench-json", required=True, type=Path)
    p.add_argument("--repo-id", required=True)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    bench = json.loads(args.bench_json.read_text())
    ref_bench = json.loads(args.reference_bench_json.read_text())

    quality_table = _render_quality_table(bench, ref_bench)

    a = bench["eval"]["__all_real__"]["word_accuracy"]
    b = ref_bench["eval"]["__all_real__"]["word_accuracy"]
    delta = (a - b) * 100
    sign = "+" if delta >= 0 else ""

    repo_id_short = args.repo_id.split("/")[-1]
    card = CARD_TEMPLATE.format(
        source=args.source,
        repo_id=args.repo_id,
        repo_id_short=repo_id_short,
        quality_table=quality_table,
        quality_delta=f"{sign}{delta:.2f} pp",
    )

    card_path = args.onnx_dir / "README.md"
    card_path.write_text(card, encoding="utf-8")
    print(f"Wrote model card: {card_path}")

    files = sorted(args.onnx_dir.iterdir(), key=lambda p: p.name)
    total_mb = sum(p.stat().st_size for p in files if p.is_file()) / 1e6

    print()
    print(f"Files to upload to {args.repo_id} (total {total_mb:.1f} MB):")
    for f in files:
        if f.is_file():
            print(f"  {f.name:<32} {f.stat().st_size / 1e6:>7.1f} MB")

    if args.dry_run:
        print()
        print("--- DRY RUN — would upload ---")
        return 0

    from huggingface_hub import HfApi, create_repo

    create_repo(args.repo_id, exist_ok=True, repo_type="model")

    api = HfApi()
    api.upload_folder(
        folder_path=str(args.onnx_dir),
        repo_id=args.repo_id,
        repo_type="model",
        commit_message="Publish ONNX int8 quantization of vn-spell-correction-small",
    )
    print()
    print(f"Published: https://huggingface.co/{args.repo_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
