# FLORES-200 vie_Latn — gated, not committed

[FLORES-200](https://huggingface.co/datasets/openlanguagedata/flores_plus) is
the gold-standard 200-language MT benchmark. The Vietnamese (vie_Latn) split
has 997 dev + 1012 devtest sentences, professionally translated, perfect for
sentence-level retrieval / embedding evaluation.

## Why no data here

The current canonical mirror — `openlanguagedata/flores_plus` — is **gated** on
Hugging Face. Programmatic download requires:

1. A Hugging Face account.
2. Accepting the dataset terms on the dataset page.
3. An access token with read scope.

We don't ship credentials, so this folder stays empty until a contributor with
access drops the files in.

## How to populate (manual)

```bash
huggingface-cli login   # enter your token
python - <<'PY'
from huggingface_hub import hf_hub_download
for split in ("dev", "devtest"):
    p = hf_hub_download(
        repo_id="openlanguagedata/flores_plus",
        filename=f"{split}/vie_Latn.jsonl",
        repo_type="dataset",
        local_dir="benchmarks/data/flores_vi",
    )
    print(p)
PY
```

## License (when populated)

**CC-BY-SA 4.0** — credit the FLORES+ project and the Open Language Data
Initiative. Link: https://huggingface.co/datasets/openlanguagedata/flores_plus
