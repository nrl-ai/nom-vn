# Trained models

All `nrl-ai/*` models are released under **Apache 2.0**, hosted on
Hugging Face Hub, in `safetensors` format. Principal author:
Viet-Anh Nguyen ([vietanh@nrl.ai](mailto:vietanh@nrl.ai)) — Neural
Research Lab.

## Diacritic restoration

| Model | Base | Params | Disk | Mean word acc |
|---|---|---:|---:|---:|
| [`nrl-ai/vn-diacritic-vit5-base`](https://huggingface.co/nrl-ai/vn-diacritic-vit5-base) | ViT5-base (MIT) | 220 M | 900 MB | **97.4 %** |
| [`nrl-ai/vn-diacritic-small`](https://huggingface.co/nrl-ai/vn-diacritic-small) | BARTpho-syllable (MIT) | 115 M | 530 MB | 93.6 % |

* `vn-diacritic-vit5-base` is the production default.
* `vn-diacritic-small` runs ~3× faster on the same hardware,
  trade-off ~3-4 pp word accuracy. Suited to mobile / browser
  inference once int8-quantized.

Full breakdown across the 4 registers: [Diacritic restoration](/tasks/diacritic-restoration).

## Spell correction

| Model | Base | Params | Disk | Light avg | Heavy avg |
|---|---|---:|---:|---:|---:|
| [`nrl-ai/vn-spell-correction-base`](https://huggingface.co/nrl-ai/vn-spell-correction-base) | ViT5-base (MIT) | 220 M | 900 MB | **98.58 %** | **97.35 %** |
| [`nrl-ai/vn-spell-correction-small`](https://huggingface.co/nrl-ai/vn-spell-correction-small) | BARTpho-syllable (MIT) | 115 M | 530 MB | 94.78 % | 92.69 % |

Spell correction is a strict superset of diacritic restoration —
same `HFDiacriticModel` interface, but also fixes character-level
typos, OCR substitutions, Telex/VNI keystrokes, and teen-code
abbreviations.

> **Honest caveat: numbers are in-distribution.** A 100-sentence
> hand-curated OOD bench shows a measurable gap on real Telex and
> forum slang. See the [task page](/tasks/spell-correction) for the
> full table. v0.2.29 is being trained on a v2 multi-source corpus
> to close most of this gap.

Full breakdown: [Spell correction](/tasks/spell-correction).

## Public datasets

| Dataset | Purpose | Records |
|---|---|---:|
| [`nrl-ai/vn-diacritic-train`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-train) | Train diacritic restoration (Wiki+news, NFC) | 500 K pairs |
| [`nrl-ai/vn-diacritic-eval`](https://huggingface.co/datasets/nrl-ai/vn-diacritic-eval) | 4-register eval | 1,227 sentences |
| [`nrl-ai/vn-spell-correction-train`](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-train) | Train spell correction (3-preset round-robin) | 459 K pairs |
| [`nrl-ai/vn-spell-correction-eval`](https://huggingface.co/datasets/nrl-ai/vn-spell-correction-eval) | 8-split eval (4 register × 2 noise level) | 2,098 pairs |

## Citation

```bibtex
@misc{nom_vn_2026,
  title={Nôm — Vietnamese AI toolkit (diacritic restoration + spell correction)},
  author={Nguyen, Viet-Anh and {Neural Research Lab}},
  year={2026},
  howpublished={\url{https://github.com/nrl-ai/nom-vn}}
}
```
