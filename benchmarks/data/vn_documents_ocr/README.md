# `vn_documents_ocr` — Vietnamese scanned-document evaluation set

**License: CC0** (public domain). All content is synthetic.

A small evaluation set of 12 realistic Vietnamese scanned documents
covering the four document classes typical `nom-vn` users want to
extract from photos and PDFs:

| Category | Count | Examples |
|---|---:|---|
| Contracts (`contract`) | 3 | hợp đồng lao động, hợp đồng kinh tế, hợp đồng thuê nhà |
| Receipts (`receipt`) | 3 | biên lai thu tiền, hoá đơn giá trị gia tăng, phiếu chi |
| Government (`government`) | 3 | công văn, thông báo, quyết định |
| Forms (`form`) | 3 | đơn xin nghỉ việc, đơn xác nhận cư trú, đơn đăng ký nhập học |

## Why this set exists

Earlier OCR baselines used `synthetic_ocr_vi/` — line-level crops of
~1017×78 px. Real users scan whole pages, not lines. This corpus
mirrors the actual workload: full A4-shaped pages (1700×2200 px at
~200 dpi), realistic body lengths, headers / signatures / numbered
clauses, and the column-stacked signature blocks common in Vietnamese
business documents.

Numbers / IDs / amounts / names are all fictional. There is no PII.

## Layout

```text
vn_documents_ocr/
  pages/<doc_id>_p<N>.png   — one PNG per page (DejaVuSans, 200 dpi)
  docs/<doc_id>.pdf         — image-only PDF (no text layer)
  metadata.jsonl            — per-doc record with full ground truth
  README.md                 — this file
  _generate.py              — regenerates the corpus from templates
```

## `metadata.jsonl` fields

```jsonc
{
  "doc_id": "contract_lao_dong",
  "category": "contract",
  "title": "HỢP ĐỒNG LAO ĐỘNG",
  "n_pages": 1,
  "pdf": "docs/contract_lao_dong.pdf",
  "pages": [
    {"page_no": 1, "image": "pages/contract_lao_dong_p1.png", "text": "..."}
  ],
  "full_text": "..."
}
```

`full_text` is the canonical ground truth — concatenation of `pages[].text`
with `"\n\n"` between pages. Use this for whole-document CER.

## Why image-only PDFs

`pdf_to_docx` has two paths:

1. text-layer extraction via `pdfplumber` (fast, lossless).
2. OCR fallback via `pdfium2` rendering + Tesseract (the path tested
   here).

Building image-only PDFs forces the OCR fallback path so the bench
measures what real scans go through.

## Regenerating

```bash
python benchmarks/data/vn_documents_ocr/_generate.py
```

Requires `Pillow`, `reportlab`, and DejaVuSans (`apt install fonts-dejavu`).
The generator is deterministic — same templates → same bytes — so the
corpus is regeneratable from a clean clone.

## Bench

Numbers (whitespace-normalized CER, NFC) on this set:

| Category | Mean CER | n |
|---|---:|---:|
| contract | 0.15 % | 3 |
| form | 0.10 % | 3 |
| government | 0.09 % | 3 |
| receipt | 0.84 % | 3 |
| **OVERALL** | **0.30 %** | 12 |

Throughput: ~1.1 docs/sec on a single CPU.
Re-run: `python benchmarks/accuracy/bench_convert_documents.py`.

## License

CC0 1.0 Universal — no rights reserved. Redistribute, remix, build upon
without attribution. See `LICENSE` in this folder for the full text.
