"""Bench a translation model on a parallel corpus (FLORES-style JSONL).

Computes chrF (primary), BLEU, diacritic recall, CJK-bleed count, and
latency. Supports two backend types:

  * ``--backend hf``     — HF seq2seq via ``transformers`` pipeline
                           (MADLAD-400-3B-mt, m2m100_418M).
  * ``--backend ollama`` — Any chat LLM via ``nom.llm.Ollama`` with a
                           structured-output JSON prompt.

Methodology follows our verified-benchmarks rule:

  - Warmup ``--warmup`` (default 3) calls before timed loop.
  - Best-of-N timing per sentence via ``--best-of`` (default 1; set 3
    for serious latency reporting). chrF / BLEU computed once per
    sentence on the first translation — re-translating the same input
    typically hits the model's cache and would understate variance.
  - Result JSON pins model id, transformers version, sacrebleu version,
    and run date.

Corpus format: one JSONL line per sentence, with at least a ``text``
field (FLORES-plus convention). The reference file uses the same line
ordering — line N of the reference is the gold translation of line N
of the corpus.

Usage::

    python benchmarks/translation/bench_translation_flores.py \\
        --backend hf --model google/madlad400-3b-mt \\
        --direction en2vi \\
        --corpus benchmarks/data/flores_vi/devtest/eng_Latn.jsonl \\
        --reference benchmarks/data/flores_vi/devtest/vie_Latn.jsonl \\
        --json benchmarks/results/baseline_translation_madlad3b_flores_en2vi.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
import unicodedata
from collections.abc import Callable
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))


def _load_jsonl_text(path: Path) -> list[str]:
    out: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            out.append(line)
            continue
        if isinstance(obj, dict):
            for key in ("text", "sentence", "src", "tgt"):
                if key in obj:
                    out.append(str(obj[key]))
                    break
            else:
                out.append(json.dumps(obj, ensure_ascii=False))
        else:
            out.append(str(obj))
    return out


_VN_DIACRITIC_CHARS = set("àáảãạăằắẳẵặâầấẩẫậèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵđ")
_VN_DIACRITIC_CHARS |= {c.upper() for c in _VN_DIACRITIC_CHARS}


def _diacritic_recall(hyp: str, ref: str) -> float:
    """% of VN diacritic-bearing chars in ref that also appear in hyp,
    counted via multiset intersection on NFC-normalized strings."""
    hyp_n = unicodedata.normalize("NFC", hyp)
    ref_n = unicodedata.normalize("NFC", ref)
    ref_chars = [c for c in ref_n if c in _VN_DIACRITIC_CHARS]
    if not ref_chars:
        return 1.0
    hyp_pool: dict[str, int] = {}
    for c in hyp_n:
        if c in _VN_DIACRITIC_CHARS:
            hyp_pool[c] = hyp_pool.get(c, 0) + 1
    matched = 0
    for c in ref_chars:
        if hyp_pool.get(c, 0) > 0:
            hyp_pool[c] -= 1
            matched += 1
    return matched / len(ref_chars)


def _count_cjk_bleed(text: str) -> int:
    """Count CJK Unified Ideographs leaked into output (should be ~0
    for a healthy EN→VN model)."""
    return sum(1 for ch in text if "一" <= ch <= "鿿" or "㐀" <= ch <= "䶿" or "豈" <= ch <= "﫿")


def _build_hf_translator(model_id: str, direction: str) -> Callable[[str], str]:
    """Return ``translate(text) -> str`` for a HF seq2seq model.

    Handles MADLAD's ``<2vi>`` / ``<2en>`` prefix and m2m100's
    ``forced_bos_token_id`` lang switch.
    """
    import torch
    from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

    tok = AutoTokenizer.from_pretrained(model_id)
    # Default load is on CPU — explicitly move to CUDA when available.
    # Without this, MADLAD-3B runs ~140x slower than necessary AND
    # produces "e e e e e ..." garbage on some configs (root cause
    # under investigation; see commit aae6a01).
    device = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.float16 if device == "cuda" else torch.float32
    model = AutoModelForSeq2SeqLM.from_pretrained(model_id, torch_dtype=dtype).to(device)
    print(f"  loaded {model_id} on {device} ({dtype})", flush=True)
    src, tgt = direction.split("2")  # "en2vi" -> ("en", "vi")

    is_madlad = "madlad" in model_id.lower()
    is_m2m100 = "m2m100" in model_id.lower()

    def translate(text: str) -> str:
        if is_madlad:
            prompt = f"<2{tgt}> {text}"
            inputs = tok(prompt, return_tensors="pt").to(device)
            out = model.generate(**inputs, max_new_tokens=512)
        elif is_m2m100:
            tok.src_lang = src
            inputs = tok(text, return_tensors="pt").to(device)
            out = model.generate(
                **inputs,
                forced_bos_token_id=tok.get_lang_id(tgt),
                max_new_tokens=512,
            )
        else:
            inputs = tok(text, return_tensors="pt").to(device)
            out = model.generate(**inputs, max_new_tokens=512)
        return tok.batch_decode(out, skip_special_tokens=True)[0].strip()

    return translate


def _build_ollama_translator(model: str, direction: str) -> Callable[[str], str]:
    """Return ``translate(text) -> str`` for an Ollama-served chat LLM,
    using JSON-structured output to suppress rambling."""
    from nom.llm import Ollama

    src, tgt = direction.split("2")
    src_name = {"en": "English", "vi": "Vietnamese"}[src]
    tgt_name = {"en": "English", "vi": "Vietnamese"}[tgt]
    llm = Ollama(model=model, think=False)
    schema = {
        "type": "object",
        "properties": {"translation": {"type": "string"}},
        "required": ["translation"],
    }

    def translate(text: str) -> str:
        prompt = (
            f"Translate the following {src_name} text into {tgt_name}. "
            f"Return only the translation as JSON.\n\n"
            f"Source ({src_name}): {text}"
        )
        raw = llm.complete(prompt, schema=schema, max_tokens=1024)
        try:
            return str(json.loads(raw).get("translation", "")).strip()
        except json.JSONDecodeError:
            return raw.strip()

    return translate


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--backend", choices=["hf", "ollama"], required=True)
    p.add_argument("--model", required=True)
    p.add_argument(
        "--direction",
        choices=["en2vi", "vi2en"],
        required=True,
        help="Source-to-target language pair.",
    )
    p.add_argument("--corpus", type=Path, required=True, help="JSONL of source sentences.")
    p.add_argument(
        "--reference",
        type=Path,
        required=True,
        help="JSONL of gold translations, same line order as --corpus.",
    )
    p.add_argument("--limit", type=int, default=0, help="Cap sentences (0 = full).")
    p.add_argument("--warmup", type=int, default=3)
    p.add_argument(
        "--best-of",
        type=int,
        default=1,
        help="Run each translation N times for latency stats (>1 may hit cache).",
    )
    p.add_argument("--precision", default="fp16", help="Recorded as metadata only.")
    p.add_argument("--json", type=Path, default=None)
    args = p.parse_args()

    if not args.corpus.exists():
        print(f"corpus not found: {args.corpus}", file=sys.stderr)
        print(
            "FLORES-200 is gated. See benchmarks/data/flores_vi/README.md "
            "for the manual fetch instructions.",
            file=sys.stderr,
        )
        return 2
    if not args.reference.exists():
        print(f"reference not found: {args.reference}", file=sys.stderr)
        return 2

    sources = _load_jsonl_text(args.corpus)
    references = _load_jsonl_text(args.reference)
    if len(sources) != len(references):
        print(
            f"corpus / reference length mismatch: {len(sources)} vs {len(references)}",
            file=sys.stderr,
        )
        return 2
    if args.limit:
        sources = sources[: args.limit]
        references = references[: args.limit]
    print(f"corpus: {len(sources)} sentences ({args.direction})")

    if args.backend == "hf":
        translate = _build_hf_translator(args.model, args.direction)
    else:
        translate = _build_ollama_translator(args.model, args.direction)

    print(f"warming up {args.warmup} call(s) ...")
    warmup_text = (
        "Hello, this is a warmup sentence."
        if args.direction == "en2vi"
        else "Đây là câu khởi động."
    )
    for _ in range(args.warmup):
        try:
            translate(warmup_text)
        except Exception as exc:
            print(f"warmup failed: {exc}", file=sys.stderr)
            return 3

    hyps: list[str] = []
    lats: list[float] = []
    diac_recalls: list[float] = []
    cjk_total = 0

    print(f"benching {len(sources)} sentences via {args.backend}:{args.model} ...")
    t_start = time.perf_counter()
    for i, (src_text, ref_text) in enumerate(zip(sources, references, strict=True)):
        per_sent_lats: list[float] = []
        hyp = ""
        for _ in range(max(1, args.best_of)):
            t0 = time.perf_counter()
            try:
                hyp = translate(src_text)
            except Exception:
                hyp = ""
            per_sent_lats.append(time.perf_counter() - t0)
        lats.append(statistics.median(per_sent_lats))
        hyps.append(hyp)
        if args.direction == "en2vi":
            diac_recalls.append(_diacritic_recall(hyp, ref_text))
            cjk_total += _count_cjk_bleed(hyp)
        if (i + 1) % 50 == 0:
            elapsed = time.perf_counter() - t_start
            eta = (len(sources) - i - 1) * elapsed / (i + 1)
            print(f"  {i + 1}/{len(sources)} ({elapsed:.0f}s elapsed, ETA {eta:.0f}s)")

    print("computing chrF / BLEU ...")
    import sacrebleu

    chrf = sacrebleu.corpus_chrf(hyps, [references]).score / 100.0
    bleu = sacrebleu.corpus_bleu(hyps, [references]).score

    p50 = statistics.median(lats) if lats else 0.0
    mean = statistics.mean(lats) if lats else 0.0
    diac = statistics.mean(diac_recalls) if diac_recalls else None

    print()
    print(f"=== {args.backend}:{args.model} on {len(sources)} sentences ({args.direction}) ===")
    print(f"  chrF:  {chrf * 100:.2f}")
    print(f"  BLEU:  {bleu:.2f}")
    if diac is not None:
        print(f"  diacritic recall (en2vi): {diac * 100:.2f}%")
        print(f"  CJK-bleed chars: {cjk_total}")
    print(f"  latency p50: {p50 * 1000:.0f} ms · mean: {mean * 1000:.0f} ms")

    if args.json:
        try:
            import transformers

            tx_ver = transformers.__version__
        except ImportError:
            tx_ver = None
        record: dict[str, object] = {
            "task": "translation",
            "direction": args.direction,
            "backend": args.backend,
            "model": args.model,
            "precision": args.precision,
            "corpus": str(args.corpus),
            "reference": str(args.reference),
            "n_sentences": len(sources),
            "warmup_calls": args.warmup,
            "best_of_n": args.best_of,
            "chrf": round(chrf, 4),
            "bleu": round(bleu, 2),
            "diacritic_recall": round(diac, 4) if diac is not None else None,
            "cjk_bleed_chars": cjk_total,
            "latency_ms_p50": round(p50 * 1000, 1),
            "latency_ms_mean": round(mean * 1000, 1),
            "transformers_version": tx_ver,
            "sacrebleu_version": sacrebleu.__version__,
            "run_date": date.today().isoformat(),
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n")
        print(f"\nResults: {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
