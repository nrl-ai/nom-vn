"""Publish ``benchmarks/data/vn_documents_ocr/`` to Hugging Face as
``nrl-ai/vn-ocr-documents-eval`` — 12 realistic Vietnamese scanned
documents (contracts, receipts, government docs, forms) for measuring
PDF/image → DOCX conversion quality.

Layout pushed to HF (``imagefolder`` style so the dataset viewer
renders pages inline):

    contract/
        contract_lao_dong/p1.png
        contract_thue_nha/p1.png
        ...
        metadata.jsonl
    receipt/...
    government/...
    form/...
    docs/<doc_id>.pdf       — image-only PDF per doc
    metadata.jsonl          — flat per-doc record (full ground truth)
    README.md               — dataset card

Per the project's verify-after-publish rule, run::

    python scripts/publish_vn_documents_ocr.py --dry-run   # preview
    python scripts/publish_vn_documents_ocr.py             # push

Then open https://huggingface.co/datasets/nrl-ai/vn-ocr-documents-eval
and confirm:

- No yellow YAML metadata warning banner
- The configs (`contract` / `receipt` / `government` / `form`) parse
  via ``datasets.load_dataset(..., config_name="contract", split="test")``.
- The viewer renders the page PNGs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ID = "nrl-ai/vn-ocr-documents-eval"
LOCAL = Path(__file__).resolve().parents[1] / "benchmarks" / "data" / "vn_documents_ocr"

DATASET_README = """\
---
license: cc0-1.0
language:
- vi
task_categories:
- image-to-text
tags:
- ocr
- vietnamese
- documents
- contracts
- receipts
- forms
- government-documents
- scanned-pdf
size_categories:
- n<1K
pretty_name: Vietnamese scanned document evaluation set
configs:
- config_name: contract
  data_files:
  - split: test
    path: contract/**
- config_name: receipt
  data_files:
  - split: test
    path: receipt/**
- config_name: government
  data_files:
  - split: test
    path: government/**
- config_name: form
  data_files:
  - split: test
    path: form/**
---

# `vn-ocr-documents-eval`

12 realistic Vietnamese scanned documents — full A4-shaped pages with
multi-paragraph bodies, headers, signature blocks, and the layout
patterns common in Vietnamese business and government documents — for
evaluating Vietnamese OCR + PDF/image → DOCX flows on inputs that
match real user workloads (not line-level crops).

| Category | Count | Examples |
|---|---:|---|
| `contract` | 3 | hợp đồng lao động, hợp đồng kinh tế, hợp đồng thuê nhà |
| `receipt`  | 3 | biên lai thu tiền, hoá đơn giá trị gia tăng, phiếu chi |
| `government` | 3 | công văn, thông báo, quyết định |
| `form`     | 3 | đơn xin nghỉ việc, đơn xác nhận cư trú, đơn đăng ký nhập học |

All content is synthetic — names, addresses, IDs, amounts, phone
numbers are fictional. **No PII.**

## Why this set exists

Earlier line-level OCR corpora (e.g. `nrl-ai/vn-synthetic-ocr` with
1017x78 px crops) measure the recogniser on the easiest possible
input — single sentence, white background, no layout. Real users
scan whole-page contracts, receipts, government decrees, and forms.
This set mirrors that workload:

- A4-shaped pages (1700x2200 px @ ~200 dpi).
- Realistic paragraph lengths, multi-clause structure.
- Column-formatted signature blocks (the receipt block is the only
  category where the converter still loses a few diacritics).
- DejaVuSans rendering — captures the diacritic stack issues that
  Tesseract's `vie` pack actually hits in production.

## Files

```text
contract/<doc_id>/p<N>.png  — one PNG per page
contract/metadata.jsonl     — {file_name, doc_id, page_no, text, ...}
docs/<doc_id>.pdf           — image-only PDF (no text layer)
metadata.jsonl              — flat per-doc record
README.md                   — this file
```

## Usage

```python
from datasets import load_dataset

# Per-category (each row = one page)
ds = load_dataset("nrl-ai/vn-ocr-documents-eval", "contract", split="test")
sample = ds[0]
print(sample["text"])             # NFC ground truth
sample["image"].show()            # PIL.Image
```

For end-to-end PDF → DOCX evaluation, use the per-doc PDFs in
`docs/<doc_id>.pdf` plus the flat `metadata.jsonl` (`full_text` field).

## Reference baseline — `nom.convert.convert_to_docx`

Latest in-house bench
([source](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_convert_documents.json)),
Tesseract 5 (vie+eng pack) via the `pdf_to_docx` OCR-fallback path:

| Category | Mean CER (whitespace-normalized) | n |
|---|---:|---:|
| `contract` | 0.15 % | 3 |
| `form` | 0.10 % | 3 |
| `government` | 0.09 % | 3 |
| `receipt` | 0.84 % | 3 |
| **OVERALL** | **0.30 %** | 12 |

Throughput: 1.13 docs/sec on a single CPU.

CER is computed on whitespace-normalized strings (NFC, runs of
whitespace collapsed to single space). The receipt category includes
column-formatted signature blocks where Tesseract emits a single line
instead of two side-by-side; that's the dominant remaining error
mode.

Run yourself:

```bash
git clone https://github.com/nrl-ai/nom-vn
cd nom-vn
pip install -e ".[doc]"
python benchmarks/data/vn_documents_ocr/_generate.py     # rebuild the corpus
python benchmarks/accuracy/bench_convert_documents.py    # measure
```

## Honesty notes

- **n=12 is small.** Use for smoke-tests + regression checks. Headline
  numbers across many more documents need a larger set (extending this
  one with public-domain government docs from `vbpl.vn` is on the
  roadmap).
- **Synthetic content.** The templates are realistic but the values
  are made up. There's no slang, handwriting, or paper-scan noise.
  Real scans add 2-5 pp of CER from these factors.
- **Single-font rendering.** All pages use DejaVuSans. Real documents
  mix fonts (Times-style headers, sans-serif bodies, monospace
  numerics) - multi-font noise typically adds 0.5-1 pp of CER.
- **Vietnamese only.** No mixed VN ↔ EN documents. For multilingual
  scans, switch to Whisper-style cross-lingual OCR pipelines.

## Citation

```bibtex
@dataset{nguyen_vn_ocr_documents_eval_2026,
  author = {Nguyen, Viet-Anh and {Neural Research Lab}},
  title  = {{vn-ocr-documents-eval: Realistic Vietnamese scanned-document
             evaluation set}},
  year   = {2026},
  url    = {https://huggingface.co/datasets/nrl-ai/vn-ocr-documents-eval}
}
```

Released CC0 1.0 — public domain dedication.

Maintained as part of the [`nom-vn`](https://github.com/nrl-ai/nom-vn)
project by Viet-Anh Nguyen (`vietanh@nrl.ai`) and Neural Research Lab.
"""


def stage_files(out_dir: Path) -> list[tuple[Path, str]]:
    """Stage the upload bundle. Returns [(local_path, repo_path)]."""
    files: list[tuple[Path, str]] = []
    out_dir.mkdir(parents=True, exist_ok=True)

    meta_lines = (LOCAL / "metadata.jsonl").read_text(encoding="utf-8").splitlines()
    docs = [json.loads(line) for line in meta_lines if line.strip()]

    # Per-category imagefolder layout: <category>/<doc_id>_p<N>.png + metadata.jsonl
    by_cat: dict[str, list[dict]] = {}
    for d in docs:
        by_cat.setdefault(d["category"], []).append(d)

    for cat, cat_docs in by_cat.items():
        cat_dir = out_dir / cat
        cat_dir.mkdir(parents=True, exist_ok=True)
        meta_path = cat_dir / "metadata.jsonl"
        with meta_path.open("w", encoding="utf-8") as mf:
            for d in cat_docs:
                for page in d["pages"]:
                    src_png = LOCAL / page["image"]
                    dst_name = f"{d['doc_id']}_p{page['page_no']}.png"
                    dst_png = cat_dir / dst_name
                    dst_png.write_bytes(src_png.read_bytes())
                    mf.write(
                        json.dumps(
                            {
                                "file_name": dst_name,
                                "doc_id": d["doc_id"],
                                "page_no": page["page_no"],
                                "title": d["title"],
                                "n_pages": d["n_pages"],
                                "text": page["text"],
                            },
                            ensure_ascii=False,
                        )
                        + "\n"
                    )
                    files.append((dst_png, f"{cat}/{dst_name}"))
        files.append((meta_path, f"{cat}/metadata.jsonl"))

    # Image-only PDFs for the doc-level convert benchmark
    for d in docs:
        src_pdf = LOCAL / d["pdf"]
        dst_pdf_path = out_dir / "docs" / f"{d['doc_id']}.pdf"
        dst_pdf_path.parent.mkdir(parents=True, exist_ok=True)
        dst_pdf_path.write_bytes(src_pdf.read_bytes())
        files.append((dst_pdf_path, f"docs/{d['doc_id']}.pdf"))

    # Flat per-doc metadata at the root
    flat_meta = out_dir / "metadata.jsonl"
    flat_meta.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in docs) + "\n")
    files.append((flat_meta, "metadata.jsonl"))

    readme = out_dir / "README.md"
    readme.write_text(DATASET_README, encoding="utf-8")
    files.append((readme, "README.md"))

    return files


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--dry-run", action="store_true", help="Stage files but don't push.")
    parser.add_argument("--stage-dir", type=Path, default=Path("/tmp/vn_documents_ocr_publish"))
    args = parser.parse_args()

    files = stage_files(args.stage_dir)
    print(f"Staged {len(files)} files under {args.stage_dir}")
    for src, dst in files[:8]:
        print(f"  {dst}  ({src.stat().st_size} B)")
    if len(files) > 8:
        print(f"  ... ({len(files)} total)")

    if args.dry_run:
        print("\nDRY RUN — nothing pushed. Re-run without --dry-run to publish.")
        return 0

    from huggingface_hub import HfApi, create_repo

    api = HfApi()
    try:
        create_repo(REPO_ID, repo_type="dataset", exist_ok=True)
    except Exception as exc:
        print(f"create_repo: {exc} (continuing if exists)")

    api.upload_folder(
        folder_path=str(args.stage_dir),
        repo_id=REPO_ID,
        repo_type="dataset",
        commit_message="v0.1: 12 realistic VN scanned-document eval samples",
    )
    print(f"\nPushed to https://huggingface.co/datasets/{REPO_ID}")
    print("Verify:")
    print(f"  hf api datasets/{REPO_ID}")
    print(
        f"  python -c 'from datasets import load_dataset;"
        f' ds = load_dataset("{REPO_ID}", "contract", split="test");'
        f' print(ds[0]["text"][:80])\''
    )
    print("Open the HF page and confirm there's no yellow YAML warning banner.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
