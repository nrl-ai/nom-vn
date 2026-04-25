# Nôm

**Open-source Python toolkit for building Vietnamese AI applications.**

> Named after *chữ Nôm* — the script Vietnam wrote in for a millennium.

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Status](https://img.shields.io/badge/status-v0%20in%20development-orange)](https://nrl.ai/nom)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org)

Every team building Vietnamese AI re-implements OCR, text utilities, prompts. Nôm packages them as one library. One `pip install` — you focus on the product.

```bash
pip install nom-vn
```

> **Status: v0 in development.** `nom.text` ships in v0.0.1 (working). `nom.doc` and `nom.prompts` ship with v0.1. Star the repo to follow.

## Modules

| Module | What it does | Status |
|---|---|---|
| `nom.text` | Vietnamese text utilities — NFC, diacritic correction, code-switch detection | **v0.0.1** |
| `nom.doc` | Document extraction — PDF/scan → structured JSON via your LLM | v0.1 |
| `nom.prompts` | Battle-tested prompt library for contracts, official docs, business email | v0.2 |
| `nom.llm` | One-interface adapter for OpenAI, Anthropic, Ollama | v0.1 |

## Quick start

### Text normalization (works today)

```python
from nom.text import normalize, fix_diacritics

# NFC + tone-mark normalization
clean = normalize("Hợp đồng số 02/HĐ/2025")

# Restore diacritics on OCR output that lost them
fixed = fix_diacritics("Hop dong nay duoc lap ngay 14 thang 3")
# → "Hợp đồng này được lập ngày 14 tháng 3"
```

### Document extraction (planned for v0.1)

```python
from nom.doc import extract

result = extract("contract.pdf", schema={
    "contract_number": str,
    "signed_date": "date",
    "party_a": "party",
    "party_b": "party",
    "total_value_vnd": "amount_vnd",
})
```

### Bring your own LLM (planned for v0.1)

```python
from nom.doc import extract
from nom.llm import OpenAI, Anthropic, Ollama

# Any LLM, one interface
llm = Ollama(model="qwen3:8b")            # local, free
# llm = OpenAI(model="gpt-4o")            # cloud
# llm = Anthropic(model="claude-sonnet")  # cloud

result = extract("doc.pdf", schema={...}, llm=llm)
```

## Why Nôm?

Nôm is **infrastructure, not a model**. It doesn't ship LLM weights. It teaches whatever LLM you use to handle Vietnamese context properly:

- **Diacritic-aware tokenization** — most tokenizers split Vietnamese diacritics badly
- **OCR pipeline** — Tesseract + post-processing for Vietnamese tone marks
- **Prompts library** — system prompts tested against contracts, official docs, business email
- **Schema extraction** — structured output for VND amounts, contract numbers, official dates

Use any model — Qwen, Llama, GPT-4o, Claude. Nôm makes them better at Vietnamese.

## License

Apache 2.0. Fine-tune, redistribute, commercialize freely. Please keep attribution.

## Citation

```bibtex
@software{nom2026,
  title  = {Nôm: an open Python toolkit for Vietnamese AI applications},
  author = {Nguyen, Viet Anh and {Neural Research Lab}},
  year   = {2026},
  url    = {https://nrl.ai/nom},
  note   = {Apache 2.0}
}
```

## Built by

[Neural Research Lab](https://nrl.ai) — open-source AI tooling. Edge inference, private assistants, training, labeling.
