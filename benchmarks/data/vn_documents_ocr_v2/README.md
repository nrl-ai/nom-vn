# `vn_documents_ocr_v2` — Vietnamese scanned-document evaluation set v0.4

~155 single-page Vietnamese documents for evaluating PDF / image → DOCX
OCR pipelines. Eight configs covering the full register matrix
(formal / business / conversational / literary) plus real PD scans
and three categories of business documents (receipts / contracts /
forms) generated from parametrized fictional templates.

| Config | n | Source | License |
|---|---:|---|---|
| `real` | 9 | chinhphu.vn + hanoi.gov.vn signed scans | Public Domain (Luật SHTT VN, Điều 15) |
| `formal` | 24 | UDHR-vie articles (rendered + scan artifacts) | CC0 (rendered) — UDHR text is PD |
| `news_business` | 24 | wiki_vi article openings (rendered + scan artifacts) | CC-BY-SA 4.0 (Wikipedia VN) |
| `conversational` | 24 | tatoeba_vi sentence groups (rendered + scan artifacts) | CC-BY 2.0 FR (Tatoeba) |
| `literary` | 23 | wikisource_vi Truyện Kiều excerpts (rendered + scan artifacts) | Public Domain |
| `receipt` | 21 | 7 templates × 3 seeds + scan artifacts | CC0 1.0 |
| `contract` | 20 | 5 templates × 4 seeds + scan artifacts | CC0 1.0 |
| `form` | 20 | 5 templates × 4 seeds + scan artifacts | CC0 1.0 |

The 9 `real` documents are true production input — image-only PDFs
straight from chinhphu.vn / hanoi.gov.vn signed scans, ground-truthed
by visual reading. The 95 `synthetic_scan` documents (formal +
news_business + conversational + literary + receipt) render clean PD
text into a page, then layer a comprehensive scan-artifact pipeline:
skew, vignette, color cast, gaussian grain, periodic banding,
gaussian blur, edge bleed, JPEG round-trip. The original clean text
is the gold ground truth — no manual transcription needed.

## What's new vs v0.1

- v0.1 was 100 % PIL-rendered synthetic content. That made `convert_to_docx`
  look like a 0.30 % CER tool — accurate for the synthetic, misleading
  for real scans.
- v0.2 ships **9 real public-domain Vietnamese government scans** across
  central + provincial domains and 7 document types (Quyết định, Công văn,
  Nghị quyết, Thông tư, Thông báo, Kế hoạch + the synthetic receipts).
- The honest baseline number on real scans is **12.62 % whitespace-
  normalized CER** — 42x worse than the v0.1 synthetic baseline. That's
  the gap a "real document OCR" pipeline actually needs to close.

## Files

```text
docs/<id>.pdf               — image-only PDF (forces OCR fallback)
pages/<id>_p1.png           — page 1 at 200 dpi
sources/<id>_full.pdf       — original multi-page PDF (provenance)
metadata.jsonl              — per-doc record with source_url + license
LICENSE                     — CC0 / PD provenance per record
README.md                   — this file
_generate.py                — rebuilds the corpus deterministically
```

## `metadata.jsonl` fields

```jsonc
{
  "doc_id":      "real_qd_729_ttg",
  "config":      "real",                        // or "synthetic_scan"
  "category":    "government_real",             // 7 categories total
  "title":       "Quyết định 729/QĐ-TTg",
  "issuer":      "Thủ tướng Chính phủ",
  "source_url":  "https://datafiles.chinhphu.vn/.../729-ttg.signed.pdf",
  "license":     "Public Domain (Luật SHTT VN, Điều 15)",
  "gen_method":  "real_scan_chinhphu_vn",
  "n_pages":     1,
  "pdf":         "docs/real_qd_729_ttg.pdf",
  "image":       "pages/real_qd_729_ttg_p1.png",
  "text":        "...corrected ground truth..."
}
```

## Source diversity

| Issuer | Source domain | Doc types |
|---|---|---|
| Thủ tướng Chính phủ | chinhphu.vn | Quyết định × 2 |
| Văn phòng Chính phủ | chinhphu.vn | Công văn |
| Chính phủ | chinhphu.vn | Nghị quyết |
| Bộ Công Thương | chinhphu.vn | Thông tư |
| Bộ Công an | chinhphu.vn | Thông tư |
| UBND TP Hà Nội | hanoi.gov.vn | Quyết định, Thông báo, Kế hoạch |
| (synthetic) | — | Hoá đơn, Biên lai, Phiếu chi |

## Why image-only PDFs

`pdf_to_docx` has two paths:

1. text-layer extraction via `pdfplumber` (fast, lossless).
2. OCR fallback via `pdfium2` rendering + Tesseract (the path tested
   here).

The 6 chinhphu.vn PDFs are real signed scans (image-only by upstream).
The 3 hanoi.gov.vn PDFs are born-digital but rerendered to 200 dpi
image-only PDFs to force the OCR-fallback path. The 3 synthetic
receipts are generated then re-rendered with scan artifacts.

## Reference baseline — `nom.convert.convert_to_docx`

Latest in-house bench
([source](https://github.com/nrl-ai/nom-vn/blob/main/benchmarks/results/baseline_convert_documents_v2.json)),
Tesseract 5 (`vie+eng` pack) via the `pdf_to_docx` OCR-fallback path:

| Config | n | CER (whitespace-normalized) |
|---|---:|---:|
| `real` (chinhphu.vn + hanoi.gov.vn) | 9 | **12.62 %** |
| All synthetic_scan (95 docs) | 95 | ~10 % |
| `receipt` (synth + artifacts) | 3 | ~8 % |
| `formal`, `news_business`, `conversational`, `literary` | 95 | varies 4-15 % |
| **OVERALL** (107 docs) | 107 | **median 7.72 %, mean 10.51 %** |

Per-doc CER ranges 0-22 %. Real chinhphu.vn signed scans are the
hardest (skew + stamps + watermarks + admin abbreviations);
synthetic_scan literary/conversational pages with low information
density and clean fonts are the easiest.

Throughput: ~0.7 docs/sec on a single CPU.

CER computed on whitespace-normalized strings (NFC, runs of whitespace
collapsed to single space). The 12.62 % real-config CER reflects the
combined difficulty of: (a) skewed scans with stamps, (b) administrative
abbreviations Tesseract's vie pack doesn't handle gracefully (signature
blocks, "KT.", etc.), (c) low-contrast watermarks behind body text.

Per-doc CER ranges 4–22 % — `real_qd_707_ttg` is the cleanest scan (4 %),
`real_hanoi_tb_453_flag` is the worst (22 %, short bold title with
stamps).

## Honesty notes

- **n=12 is small.** Use for smoke + regression checks; for adoption
  claims expand to 50-100 docs covering more issuers and date ranges.
- **Ground truth is human-verified visual transcription.** Each text
  field was produced by directly reading the rendered page (not by
  trusting Tesseract output). Errors of judgment may remain in long
  numbered lists.
- **Page 1 only.** Some sources are multi-page; only page 1 is in the
  corpus. The `sources/<id>_full.pdf` files preserve the originals
  for future expansion.
- **No PII**. The chinhphu.vn / hanoi.gov.vn documents name public
  officials in their official capacity (PM, Ministers, Phó Chủ tịch
  UBND) — public record. Synthetic receipts contain only fictional
  names.

## License

- The 9 documents in `real/` config: **Public Domain** under Luật Sở
  hữu trí tuệ Việt Nam, Điều 15 (Vietnamese government works are
  not subject to copyright). Source URLs in metadata.
- The 3 documents in `synthetic_scan/` config: **CC0 1.0 Universal**
  (synthetic content, no rights reserved).
- This README + the `_generate.py` script: **CC0 1.0**.

The combined dataset is redistributable under either CC0 1.0 or as
public-domain content — choose whichever matches your downstream
license needs.

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
