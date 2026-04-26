"""Vietnamese OCR accuracy + latency benchmark — real engines.

Replaces the v0.0.1 ``bench_ocr.py`` scaffold. Compares OCR engines on a
held-out Vietnamese image corpus, reporting:

  - **CER** (character error rate) — Levenshtein / max(|gold|, |pred|)
  - **WER** (word error rate) — token-level mismatch
  - **Diacritic-CER** — CER computed on the *diacritic mask* only, so a
    correct base letter with a wrong tone mark costs the same as a
    missing letter. This is the metric Vietnamese readers actually feel.
  - **p50 / p95 per-image latency** — warmup + best-of-N protocol per
    parent CLAUDE.md principle 12.

Engines:

  - ``tesseract`` — Tesseract 5 with the ``vie`` traineddata. Always
    available (Apache 2.0, ships in apt / brew). Baseline.
  - ``vietocr`` — VN-specialised Transformer (Apache 2.0). Opt-in,
    lazy-loaded on first use. Install: ``pip install vietocr``.
  - ``easyocr`` — multilingual CNN+LSTM (Apache 2.0). Opt-in.

Corpus default: ``benchmarks/data/synthetic_ocr_vi/`` — 20 clean +
20 noisy synthetic VN sentences with ground truth (CC0). Tiny, but
deterministic and dependency-free; useful for harness validation
and CI smoke checks. Pass ``--corpus`` for a larger held-out set.

Run::

    python benchmarks/accuracy/bench_ocr_real.py
    python benchmarks/accuracy/bench_ocr_real.py --engines tesseract,vietocr
    python benchmarks/accuracy/bench_ocr_real.py --variant noisy \\
        --json benchmarks/results/ocr_synthetic_noisy.json
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import time
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
DEFAULT_CORPUS = REPO / "benchmarks" / "data" / "synthetic_ocr_vi"


# ---------------------------------------------------------------------------
# Engines
# ---------------------------------------------------------------------------


class TesseractOCR:
    """Tesseract 5 with vie traineddata (system-installed)."""

    name = "tesseract"

    def __init__(self, lang: str = "vie", config: str = "--psm 6") -> None:
        self.lang = lang
        self.config = config
        self._loaded = False

    def predict(self, image_path: Path) -> str:
        if not self._loaded:
            import pytesseract

            self._loaded = True
        import pytesseract
        from PIL import Image

        img = Image.open(image_path)
        return str(pytesseract.image_to_string(img, lang=self.lang, config=self.config)).strip()


class VietOCR:
    """VN-specialised Transformer OCR (pbcquoc/vietocr)."""

    name = "vietocr"

    def __init__(self, device: str = "cpu", weights: str = "vgg_transformer") -> None:
        self.device = device
        self.weights = weights
        self._predictor: Any | None = None

    def _ensure_loaded(self) -> None:
        if self._predictor is not None:
            return
        try:
            from vietocr.tool.config import Cfg
            from vietocr.tool.predictor import Predictor
        except ImportError as exc:
            raise ImportError("vietocr not installed. Install with: pip install vietocr") from exc

        cfg = Cfg.load_config_from_name(self.weights)
        cfg["device"] = self.device
        cfg["predictor"]["beamsearch"] = False
        self._predictor = Predictor(cfg)

    def predict(self, image_path: Path) -> str:
        self._ensure_loaded()
        from PIL import Image

        img = Image.open(image_path).convert("RGB")
        return str(self._predictor.predict(img)).strip()


class EasyOCR:
    """multilingual CNN+LSTM (JaidedAI/EasyOCR)."""

    name = "easyocr"

    def __init__(self, gpu: bool = False) -> None:
        self.gpu = gpu
        self._reader: Any | None = None

    def _ensure_loaded(self) -> None:
        if self._reader is not None:
            return
        try:
            import easyocr
        except ImportError as exc:
            raise ImportError("easyocr not installed. Install with: pip install easyocr") from exc

        self._reader = easyocr.Reader(["vi"], gpu=self.gpu, verbose=False)

    def predict(self, image_path: Path) -> str:
        self._ensure_loaded()
        results = self._reader.readtext(str(image_path), detail=0, paragraph=True)
        return " ".join(results).strip()


class OllamaVLM:
    """Vision-Language Model OCR via Ollama (e.g. qwen2.5vl, llava).

    Sends each image to Ollama's ``/api/generate`` with a tight VN-OCR
    prompt and returns the model's transcription. Quality and latency
    depend heavily on the model — qwen2.5vl:3b / 7b are the strong
    open-weight choices as of 2026-04-26.

    Set ``base_url`` for a remote Ollama (e.g. SSH-tunneled GPU box).
    """

    name = "ollama_vlm"

    def __init__(
        self,
        model: str = "qwen2.5vl:7b",
        base_url: str = "http://localhost:11434",
        prompt: str | None = None,
        timeout: float = 120.0,
        temperature: float = 0.0,
    ) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.temperature = temperature
        # Tight prompt — VLMs love to add chatter ("Here is the text:") or
        # explanations. We force a single line, no quoting, no labels.
        self.prompt = prompt or (
            "Trong ảnh có một đoạn văn bản tiếng Việt. "
            "Hãy gõ lại CHÍNH XÁC nội dung văn bản, giữ nguyên dấu, viết hoa, "
            "khoảng trắng. Chỉ trả về văn bản, không thêm tiêu đề, lời giải thích, "
            "hay dấu ngoặc kép."
        )
        self._httpx: Any = None

    def _ensure_loaded(self) -> None:
        if self._httpx is not None:
            return
        try:
            import httpx
        except ImportError as exc:
            raise ImportError("httpx not installed. Install with: pip install nom-vn[llm]") from exc
        self._httpx = httpx

    def predict(self, image_path: Path) -> str:
        self._ensure_loaded()
        import base64

        b64 = base64.b64encode(image_path.read_bytes()).decode()
        body = {
            "model": self.model,
            "prompt": self.prompt,
            "images": [b64],
            "stream": False,
            "think": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": 512,
            },
        }
        r = self._httpx.post(f"{self.base_url}/api/generate", json=body, timeout=self.timeout)
        r.raise_for_status()
        data = r.json()
        text = str(data.get("response", "")).strip()
        # Defensive trim — the same patterns as fix_diacritics: strip
        # ```code-fences```, drop a leading "Văn bản:" label echo, drop a
        # leading <think>...</think>.
        if "</think>" in text:
            text = text.split("</think>", 1)[1].lstrip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3].rstrip()
        if "\n" in text and text.split("\n", 1)[0].rstrip().endswith(":"):
            text = text.split("\n", 1)[1]
        return text.strip().strip('"')


ENGINES: dict[str, Any] = {
    "tesseract": TesseractOCR,
    "vietocr": VietOCR,
    "easyocr": EasyOCR,
    "ollama_vlm": OllamaVLM,
}


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------


def _levenshtein(a: str, b: str) -> int:
    """Iterative Levenshtein distance — standard DP, O(|a|·|b|) time / O(min) space."""
    if len(a) < len(b):
        a, b = b, a
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, start=1):
        cur = [i]
        for j, cb in enumerate(b, start=1):
            ins = cur[j - 1] + 1
            dele = prev[j] + 1
            sub = prev[j - 1] + (ca != cb)
            cur.append(min(ins, dele, sub))
        prev = cur
    return prev[-1]


def cer(pred: str, gold: str) -> float:
    if not gold and not pred:
        return 0.0
    return _levenshtein(pred, gold) / max(len(pred), len(gold), 1)


def wer(pred: str, gold: str) -> float:
    p = pred.split()
    g = gold.split()
    if not p and not g:
        return 0.0
    return _levenshtein(" ".join(p), " ".join(g)) / max(len(p), len(g), 1) * 1.0
    # Note: token-level Levenshtein over space-joined would double-count,
    # so we divide by max-word-len. Keep the formula explicit.


def _diacritic_mask(s: str) -> str:
    """Return only the diacritic codepoints from a NFD-decomposed string."""
    nfd = unicodedata.normalize("NFD", s)
    return "".join(c for c in nfd if unicodedata.combining(c))


def diacritic_cer(pred: str, gold: str) -> float:
    """CER computed on the diacritic mask of each string.

    Captures the failure mode VN readers care about most — a base letter
    correct but the tone mark wrong. Tesseract often hits this on noisy
    scans because the dots and acute marks are 1-3 pixels.
    """
    return cer(_diacritic_mask(pred), _diacritic_mask(gold))


# ---------------------------------------------------------------------------
# Corpus loading
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Sample:
    id: str
    image_path: Path
    text: str


def load_corpus(corpus_dir: Path, variant: str | None = None) -> list[Sample]:
    """Load an OCR fixture from ``ground_truth.jsonl``.

    Two layouts supported:
      A. **synthetic_ocr_vi** style — each row has ``id``, ``text``, plus
         ``clean`` and ``noisy`` keys pointing at image paths. Pass
         ``variant="clean"`` or ``"noisy"``.
      B. **vn_ocr_subset** style — each row has ``id``, ``text``,
         ``image`` (single path). Pass ``variant=None``.
    """
    gt_path = corpus_dir / "ground_truth.jsonl"
    if not gt_path.is_file():
        raise FileNotFoundError(f"ground truth not found at {gt_path}")
    samples: list[Sample] = []
    with gt_path.open(encoding="utf-8") as fp:
        for line in fp:
            r = json.loads(line)
            if variant is not None and variant in r:
                rel = r.get(variant)
            else:
                rel = r.get("image") or r.get("path") or r.get("file")
            if not rel:
                continue
            samples.append(
                Sample(
                    id=str(r["id"]),
                    image_path=corpus_dir / rel,
                    text=str(r["text"]),
                )
            )
    if not samples:
        raise ValueError(f"no samples for variant={variant!r} under {corpus_dir}")
    return samples


# Back-compat alias — older call sites may still reference the original name.
load_synthetic_corpus = load_corpus


# ---------------------------------------------------------------------------
# Run
# ---------------------------------------------------------------------------


def run_engine(
    engine: Any,
    samples: list[Sample],
    *,
    n_warmup: int,
    n_timed: int,
) -> dict[str, Any]:
    """Score + time one engine on the sample list. Returns metrics dict."""
    # Warmup — discard timings and outputs.
    for _ in range(n_warmup):
        for s in samples:
            engine.predict(s.image_path)

    pass_results: list[list[str]] = []
    pass_p50: list[float] = []
    pass_p95: list[float] = []

    for _ in range(n_timed):
        preds: list[str] = []
        per_q: list[float] = []
        for s in samples:
            t0 = time.perf_counter()
            p = engine.predict(s.image_path)
            per_q.append((time.perf_counter() - t0) * 1000.0)
            preds.append(p)
        pass_results.append(preds)
        per_q.sort()
        pass_p50.append(per_q[len(per_q) // 2])
        pass_p95.append(per_q[max(0, int(len(per_q) * 0.95) - 1)])

    # Use predictions from the last pass for quality metrics — they're
    # deterministic for Tesseract (greedy) but VietOCR/EasyOCR may vary
    # batch-to-batch; either way, all passes' quality should converge.
    final_preds = pass_results[-1]
    cers = [cer(p, s.text) for p, s in zip(final_preds, samples, strict=True)]
    wers = [wer(p, s.text) for p, s in zip(final_preds, samples, strict=True)]
    dcers = [diacritic_cer(p, s.text) for p, s in zip(final_preds, samples, strict=True)]
    exact = [
        1 if p.strip() == s.text.strip() else 0 for p, s in zip(final_preds, samples, strict=True)
    ]

    return {
        "n_samples": len(samples),
        "cer": round(statistics.mean(cers), 4),
        "wer": round(statistics.mean(wers), 4),
        "diacritic_cer": round(statistics.mean(dcers), 4),
        "exact_match": round(statistics.mean(exact), 4),
        "p50_ms": round(min(pass_p50), 2),
        "p95_ms": round(min(pass_p95), 2),
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------


def _git_sha() -> str | None:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--short=12", "HEAD"], cwd=REPO, stderr=subprocess.DEVNULL
        )
        return out.decode().strip()
    except Exception:
        return None


def _print_table(result: dict[str, Any]) -> None:
    cfg = result["config"]
    print(f"\nCorpus: {cfg['corpus']}  (variant={cfg['variant']}, n={cfg['n_samples']} samples)")
    cols = ["cer", "wer", "diacritic_cer", "exact_match", "p50_ms", "p95_ms"]
    name_w = max(8, max(len(r) for r in result["engines"]))
    header = "Engine".ljust(name_w) + "  " + "  ".join(c.rjust(13) for c in cols)
    print(header)
    print("-" * len(header))
    for name, m in result["engines"].items():
        cells = [
            f"{m['cer']:.4f}",
            f"{m['wer']:.4f}",
            f"{m['diacritic_cer']:.4f}",
            f"{m['exact_match']:.3f}",
            f"{m['p50_ms']:.1f}",
            f"{m['p95_ms']:.1f}",
        ]
        print(name.ljust(name_w) + "  " + "  ".join(c.rjust(13) for c in cells))
    print()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    p.add_argument(
        "--variant",
        default="clean",
        help="Image variant key in ground_truth.jsonl. Use 'none' for "
        "single-image corpora like vn_ocr_subset.",
    )
    p.add_argument("--engines", default="tesseract", help="Comma-separated engine names.")
    p.add_argument(
        "--device",
        default="auto",
        help="cpu | cuda | mps | auto (vietocr / easyocr only)",
    )
    p.add_argument("--n-warmup", type=int, default=1)
    p.add_argument("--n-timed", type=int, default=2)
    p.add_argument("--json", type=Path, default=None)
    p.add_argument(
        "--ollama-base-url",
        default="http://localhost:11434",
        help="Ollama server URL for ollama_vlm engine.",
    )
    p.add_argument(
        "--ollama-model",
        default="qwen2.5vl:7b",
        help="Ollama VLM model tag (qwen2.5vl:3b, qwen2.5vl:7b, llava, etc.)",
    )
    p.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Only run on the first N samples (useful for slow VLM benches).",
    )
    args = p.parse_args(argv)

    selected = [e.strip() for e in args.engines.split(",") if e.strip()]
    for e in selected:
        if e not in ENGINES:
            raise SystemExit(f"unknown engine: {e!r} (choices: {list(ENGINES)})")

    device = args.device
    if device == "auto":
        try:
            import torch

            if torch.cuda.is_available():
                device = "cuda"
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                device = "mps"
            else:
                device = "cpu"
        except ImportError:
            device = "cpu"

    print(f"device={device}")
    variant = None if args.variant == "none" else args.variant
    samples = load_corpus(args.corpus, variant=variant)
    if args.limit is not None and args.limit > 0:
        samples = samples[: args.limit]
    print(f"loaded {len(samples)} samples from {args.corpus} (variant={variant})")

    engines: dict[str, Any] = {}
    for name in selected:
        cls = ENGINES[name]
        if name == "vietocr":
            engines[name] = cls(device=device)
        elif name == "easyocr":
            engines[name] = cls(gpu=(device != "cpu"))
        elif name == "ollama_vlm":
            engines[name] = cls(model=args.ollama_model, base_url=args.ollama_base_url)
        else:
            engines[name] = cls()

    metrics: dict[str, dict[str, float]] = {}
    for name, eng in engines.items():
        print(f"  running {name}...")
        try:
            metrics[name] = run_engine(eng, samples, n_warmup=args.n_warmup, n_timed=args.n_timed)
        except ImportError as exc:
            print(f"    SKIP {name}: {exc}", file=sys.stderr)
            continue

    result: dict[str, Any] = {
        "config": {
            "corpus": str(args.corpus.relative_to(REPO))
            if args.corpus.is_relative_to(REPO)
            else str(args.corpus),
            "variant": args.variant,
            "n_samples": len(samples),
            "device": device,
        },
        "engines": metrics,
        "meta": {
            "ran_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "git_sha": _git_sha(),
            "n_warmup": args.n_warmup,
            "n_timed": args.n_timed,
            "python": sys.version.split()[0],
        },
    }

    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"→ wrote {args.json}")

    _print_table(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
