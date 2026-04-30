# Quickstart

## Requirements

* Python ≥ 3.10
* Optional: CUDA-capable GPU. All models run on CPU; GPU only
  reduces latency from ~150 ms to ~30 ms per sentence.

## Install the core

```bash
pip install nom-vn
```

The core wheel ships Vietnamese normalization (`nom.text.normalize`,
`nom.text.strip_diacritics`), sentence splitting, and chunking — no
PyTorch dependency.

## Install the chat web app

```bash
pip install "nom-vn[chat]"
nom serve   # http://localhost:8080
```

## Diacritic restoration

```python
from nom.text import fix_diacritics
from nom.text.diacritic_models import HFDiacriticModel

restorer = HFDiacriticModel(model_id="nrl-ai/vn-diacritic-base")
print(fix_diacritics("Toi yu Vit Nam", model=restorer))
# 'Tôi yêu Việt Nam'
```

## Spell correction

```python
from nom.text.diacritic_models import HFDiacriticModel

speller = HFDiacriticModel(model_id="nrl-ai/vn-spell-correction-base")
print(speller("Hop dong nay duoc lap ngay 14/3/2025"))
# 'Hợp đồng này được lập ngày 14/3/2025'
```

## Local RAG — chat with documents

```bash
ollama pull qwen3:8b
nom serve
```

Drop PDF / DOCX into the UI; query in Vietnamese; answers cite
specific spans.

## Next

* [Trained models](/en/models)
* [Diacritic restoration task](/tasks/diacritic-restoration)
* [Spell correction task](/tasks/spell-correction)
* [Recipes](/recipes)
