"""Publish ``benchmarks/data/vn_documents_ocr_v2/`` to Hugging Face as
``nrl-ai/vn-ocr-documents-eval`` v0.2 — 9 real PD scans (chinhphu.vn,
hanoi.gov.vn) + 3 synthetic-scan receipts.

Layout pushed (HF imagefolder style; the dataset viewer renders
pages inline; configs split into separate folders):

    real/
        real_qd_729_ttg_p1.png
        real_cv_3722_metro_p1.png
        ...
        metadata.jsonl
    synthetic_scan/
        synth_scan_receipt_hoa_don_p1.png
        ...
        metadata.jsonl
    docs/<doc_id>.pdf       — image-only PDF per doc
    sources/<doc_id>_full.pdf — original multi-page PDF (provenance)
    metadata.jsonl          — flat per-doc record (for whole-doc bench)
    README.md               — dataset card

Run::

    python scripts/publish_vn_documents_ocr_v2.py --dry-run    # preview
    python scripts/publish_vn_documents_ocr_v2.py              # push

Verify (per the project's verify-after-publish rule):

    hf api datasets/nrl-ai/vn-ocr-documents-eval
    python -c 'from datasets import load_dataset;
        ds = load_dataset("nrl-ai/vn-ocr-documents-eval", "real", split="test");
        print(ds[0]["text"][:80])'

Open the HF page and confirm there's no yellow YAML metadata
warning banner.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

REPO_ID = "nrl-ai/vn-ocr-documents-eval"
LOCAL = Path(__file__).resolve().parents[1] / "benchmarks" / "data" / "vn_documents_ocr_v2"


def stage_files(out_dir: Path) -> list[tuple[Path, str]]:
    """Stage the v0.2 upload bundle. Returns [(local_path, repo_path)]."""
    files: list[tuple[Path, str]] = []
    out_dir.mkdir(parents=True, exist_ok=True)

    meta_lines = (LOCAL / "metadata.jsonl").read_text(encoding="utf-8").splitlines()
    docs = [json.loads(line) for line in meta_lines if line.strip()]

    # v0.3: split by category, not just config — gives users 6 configs
    # (real / literary / formal / news_business / conversational / receipt)
    # rather than the v0.2 two-config split that lumped 80+ synth docs
    # together.
    cat_to_cfg = {
        "government_real": "real",
        "literary": "literary",
        "formal": "formal",
        "news_business": "news_business",
        "conversational": "conversational",
        "receipt_synthetic_scan": "receipt",
    }
    by_cfg: dict[str, list[dict]] = {}
    for d in docs:
        cfg = cat_to_cfg.get(d["category"], d["config"])
        by_cfg.setdefault(cfg, []).append(d)

    for cfg, cfg_docs in by_cfg.items():
        cfg_dir = out_dir / cfg
        cfg_dir.mkdir(parents=True, exist_ok=True)
        meta_path = cfg_dir / "metadata.jsonl"
        with meta_path.open("w", encoding="utf-8") as mf:
            for d in cfg_docs:
                src_png = LOCAL / d["image"]
                dst_name = f"{d['doc_id']}_p1.png"
                dst_png = cfg_dir / dst_name
                dst_png.write_bytes(src_png.read_bytes())
                mf.write(
                    json.dumps(
                        {
                            "file_name": dst_name,
                            "doc_id": d["doc_id"],
                            "category": d["category"],
                            "title": d["title"],
                            "issuer": d["issuer"],
                            "source_url": d["source_url"],
                            "license": d["license"],
                            "gen_method": d["gen_method"],
                            "text": d["text"],
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
                files.append((dst_png, f"{cfg}/{dst_name}"))
        files.append((meta_path, f"{cfg}/metadata.jsonl"))

    # Image-only PDFs for whole-doc bench (loose under docs/)
    for d in docs:
        src_pdf = LOCAL / d["pdf"]
        dst_pdf = out_dir / "docs" / f"{d['doc_id']}.pdf"
        dst_pdf.parent.mkdir(parents=True, exist_ok=True)
        dst_pdf.write_bytes(src_pdf.read_bytes())
        files.append((dst_pdf, f"docs/{d['doc_id']}.pdf"))

    # Original multi-page PDFs (provenance)
    sources_in = LOCAL / "sources"
    if sources_in.is_dir():
        sources_out = out_dir / "sources"
        sources_out.mkdir(parents=True, exist_ok=True)
        for src in sources_in.iterdir():
            if src.is_file():
                dst = sources_out / src.name
                dst.write_bytes(src.read_bytes())
                files.append((dst, f"sources/{src.name}"))

    flat_meta = out_dir / "metadata.jsonl"
    flat_meta.write_text("\n".join(json.dumps(d, ensure_ascii=False) for d in docs) + "\n")
    files.append((flat_meta, "metadata.jsonl"))

    readme = out_dir / "README.md"
    readme.write_text(_README_TEMPLATE, encoding="utf-8")
    files.append((readme, "README.md"))

    license_dst = out_dir / "LICENSE"
    license_src = LOCAL / "LICENSE"
    if license_src.exists():
        license_dst.write_text(license_src.read_text(encoding="utf-8"), encoding="utf-8")
        files.append((license_dst, "LICENSE"))

    return files


_README_TEMPLATE = """\
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
- public-domain
- government-documents
- scanned-pdf
- contracts
- receipts
size_categories:
- n<1K
pretty_name: Vietnamese scanned document evaluation set (real PD + synthetic_scan)
configs:
- config_name: real
  data_files:
  - split: test
    path: real/**
- config_name: synthetic_scan
  data_files:
  - split: test
    path: synthetic_scan/**
---

# `vn-ocr-documents-eval` v0.2

12 single-page Vietnamese documents for evaluating PDF / image → DOCX
OCR pipelines. Two configs covering 7+ document types from 3 source
domains.

| Config | n | Source | License |
|---|---:|---|---|
| `real` | 9 | chinhphu.vn (6) + hanoi.gov.vn (3) | Public Domain (Luật SHTT VN, Điều 15) |
| `synthetic_scan` | 3 | synthetic templates + scan artifacts | CC0 1.0 |

## What's new vs v0.1

- v0.1 was 100 % PIL-rendered synthetic content. That made
  `convert_to_docx` look like a 0.30 % CER tool — accurate for the
  synthetic, misleading for real scans.
- v0.2 ships **9 real public-domain Vietnamese government scans**
  across central + provincial domains and 7 document types
  (Quyết định, Công văn, Nghị quyết, Thông tư, Thông báo, Kế hoạch +
  the synthetic receipts).
- The honest baseline number on real scans is **12.62 %
  whitespace-normalized CER** — 42x worse than the v0.1 synthetic
  baseline. That's the gap a "real document OCR" pipeline actually
  needs to close.

## Source diversity

| Issuer | Source domain | Doc types |
|---|---|---|
| Thủ tướng Chính phủ | chinhphu.vn | Quyết định x 2 |
| Văn phòng Chính phủ | chinhphu.vn | Công văn |
| Chính phủ | chinhphu.vn | Nghị quyết |
| Bộ Công Thương | chinhphu.vn | Thông tư |
| Bộ Công an | chinhphu.vn | Thông tư |
| UBND TP Hà Nội | hanoi.gov.vn | Quyết định, Thông báo, Kế hoạch |
| (synthetic) | — | Hoá đơn, Biên lai, Phiếu chi |

## Usage

```python
from datasets import load_dataset

# Real PD scans (each row = one page + ground-truth text)
real = load_dataset("nrl-ai/vn-ocr-documents-eval", "real", split="test")
print(real[0]["text"][:120])
real[0]["image"].show()

# Synthetic receipts with scan artifacts
synth = load_dataset("nrl-ai/vn-ocr-documents-eval", "synthetic_scan", split="test")
```

For end-to-end PDF → DOCX evaluation, use the per-doc PDFs in
`docs/<doc_id>.pdf` plus the flat `metadata.jsonl` (`text` field) which
covers both configs.

## Reference baseline — `nom.convert.convert_to_docx`

Latest in-house bench
([source](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_convert_documents_v2.json)),
Tesseract 5 (`vie+eng` pack) via the `pdf_to_docx` OCR-fallback path:

| Config | CER (whitespace-normalized) | n |
|---|---:|---:|
| `real` | **12.62 %** | 9 |
| `synthetic_scan` | 0.43 % | 3 |
| **OVERALL** | **9.57 %** | 12 |

Throughput: ~0.7 docs/sec on a single CPU.

CER computed on whitespace-normalized strings (NFC, runs of whitespace
collapsed to single space). The 12.62 % real-config CER reflects the
combined difficulty of: (a) skewed scans with stamps, (b) admin
abbreviations Tesseract's vie pack doesn't handle gracefully
(signature blocks, "KT.", etc.), (c) low-contrast watermarks behind
body text.

Per-doc CER ranges 4-22 % — `real_qd_707_ttg` is the cleanest scan
(4 %), `real_hanoi_tb_453_flag` is the worst (22 %, short bold title
with stamps).

Run yourself:

```bash
git clone https://github.com/nrl-ai/nom-vn
cd nom-vn
pip install -e ".[doc]"
python benchmarks/data/vn_documents_ocr_v2/_generate.py
python benchmarks/accuracy/bench_convert_documents_v2.py
```

## Honesty notes

- **n=12 is small.** Use for smoke + regression checks; for adoption
  claims expand to 50-100 docs covering more issuers and date ranges.
- **Ground truth is human-verified visual transcription** — each
  `text` field was produced by directly reading the rendered page
  (not by trusting Tesseract output). Errors of judgment may remain
  in long numbered lists.
- **Page 1 only.** Some sources are multi-page; only page 1 is in
  the corpus. The `sources/<id>_full.pdf` files preserve the
  originals for future expansion.
- **No PII**. The chinhphu.vn / hanoi.gov.vn documents name public
  officials in their official capacity (PM, Ministers, Phó Chủ tịch
  UBND) — public record. Synthetic receipts contain only fictional
  names.

## License

- The 9 documents in `real` config: **Public Domain** under Luật Sở
  hữu trí tuệ Việt Nam, Điều 15 (Vietnamese government works are
  not subject to copyright). Source URLs in metadata.
- The 3 documents in `synthetic_scan` config: **CC0 1.0 Universal**
  (synthetic content, no rights reserved).
- This README + the `_generate.py` script: **CC0 1.0**.

## Citation

```bibtex
@dataset{nguyen_vn_ocr_documents_eval_v2_2026,
  author = {Nguyen, Viet-Anh and {Neural Research Lab}},
  title  = {{vn-ocr-documents-eval v0.2: Realistic Vietnamese
             scanned-document evaluation set with central + provincial
             government documents}},
  year   = {2026},
  url    = {https://huggingface.co/datasets/nrl-ai/vn-ocr-documents-eval}
}
```

Maintained as part of the [`nom-vn`](https://github.com/nrl-ai/nom-vn)
project by Viet-Anh Nguyen (`vietanh@nrl.ai`) and Neural Research Lab.
"""


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--dry-run", action="store_true", help="Stage files but don't push.")
    parser.add_argument("--stage-dir", type=Path, default=Path("/tmp/vn_documents_ocr_v2_publish"))
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
        commit_message="v0.2: 9 real PD scans (chinhphu.vn + hanoi.gov.vn) + 3 synthetic_scan receipts",
        delete_patterns=["contract/**", "form/**", "government/**", "receipt/**"],
    )
    print(f"\nPushed to https://huggingface.co/datasets/{REPO_ID}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
