"""Export an HF seq2seq model to ONNX + dynamic int8 quantize.

Pipeline:
  1. Load source model (HF Hub repo id or local path).
  2. Use `optimum.exporters.onnx` to export the seq2seq → ONNX
     (encoder + decoder + decoder_with_past, three .onnx files).
  3. Apply dynamic int8 quantization on the encoder + decoder weights
     (stays fp32 on activations; matmul gets int8 weights at runtime).
  4. Save a self-contained ONNX directory ready to publish to HF.

Usage::

    python training/onnx_export/export_int8.py \\
        --source nrl-ai/vn-spell-correction-small \\
        --output training/onnx_export/vn-spell-correction-small-int8

The output directory holds:
  encoder_model.onnx              (fp32 → int8 quantized)
  decoder_model.onnx              (fp32 → int8 quantized)
  decoder_with_past_model.onnx    (fp32 → int8 quantized)
  config.json
  tokenizer files
  generation_config.json
"""

from __future__ import annotations

import argparse
import shutil
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--source",
        required=True,
        help="HF Hub repo id (e.g. nrl-ai/vn-spell-correction-small) or local path.",
    )
    p.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Local output directory for the ONNX artifacts.",
    )
    p.add_argument(
        "--task",
        default="text2text-generation",
        help="optimum task. Default text2text-generation (seq2seq encoder-decoder).",
    )
    args = p.parse_args(argv)

    args.output.mkdir(parents=True, exist_ok=True)

    print(f"==> [1/3] export {args.source} -> ONNX (fp32)")
    t0 = time.perf_counter()
    # We use ORTModelForSeq2SeqLM.from_pretrained(..., export=True) which
    # is the high-level path optimum recommends (calls
    # main_export under the hood, then re-loads the ORT models).
    from optimum.onnxruntime import ORTModelForSeq2SeqLM
    from transformers import AutoTokenizer

    fp32_dir = args.output.with_suffix(".fp32")
    fp32_dir.mkdir(parents=True, exist_ok=True)

    model = ORTModelForSeq2SeqLM.from_pretrained(args.source, export=True)
    model.save_pretrained(str(fp32_dir))
    tok = AutoTokenizer.from_pretrained(args.source)
    tok.save_pretrained(str(fp32_dir))
    fp32_size_mb = sum(p.stat().st_size for p in fp32_dir.glob("*.onnx")) / 1e6
    print(f"  fp32 ONNX size: {fp32_size_mb:.1f} MB ({time.perf_counter() - t0:.1f}s)")

    print()
    print(f"==> [2/3] dynamic int8 quantize -> {args.output}")
    t0 = time.perf_counter()
    from optimum.onnxruntime import ORTQuantizer
    from optimum.onnxruntime.configuration import AutoQuantizationConfig

    qconfig = AutoQuantizationConfig.avx2(is_static=False, per_channel=False)

    for component in ("encoder_model", "decoder_model", "decoder_with_past_model"):
        src = fp32_dir / f"{component}.onnx"
        if not src.exists():
            print(f"  skip {component}: not found in fp32 dir")
            continue
        quantizer = ORTQuantizer.from_pretrained(str(fp32_dir), file_name=src.name)
        quantizer.quantize(
            save_dir=str(args.output),
            quantization_config=qconfig,
            file_suffix="quantized",
        )
        print(f"  quantized {component}")

    # The optimum quantizer writes <name>_quantized.onnx; rename to the
    # canonical names so HF / loaders pick them up automatically.
    for component in ("encoder_model", "decoder_model", "decoder_with_past_model"):
        q = args.output / f"{component}_quantized.onnx"
        canonical = args.output / f"{component}.onnx"
        if q.exists():
            if canonical.exists():
                canonical.unlink()
            q.rename(canonical)

    # Copy tokenizer + config files into the int8 dir so the directory
    # is self-contained for HF publish.
    for src in fp32_dir.iterdir():
        if src.suffix in {".onnx", ".onnx_data"}:
            continue
        dst = args.output / src.name
        if not dst.exists():
            shutil.copy2(str(src), str(dst))

    int8_size_mb = sum(p.stat().st_size for p in args.output.glob("*.onnx")) / 1e6
    print(f"  int8 ONNX size: {int8_size_mb:.1f} MB ({time.perf_counter() - t0:.1f}s)")
    print(f"  reduction: {(1 - int8_size_mb / fp32_size_mb) * 100:.1f}%")

    print()
    print("==> [3/3] sanity test — load + generate one sample")
    t0 = time.perf_counter()
    int8_model = ORTModelForSeq2SeqLM.from_pretrained(str(args.output))
    int8_tok = AutoTokenizer.from_pretrained(str(args.output))
    inp = "Toi yeu Viet Nam, dat nuoc tuyet voi"
    encoded = int8_tok(inp, return_tensors="pt")
    out = int8_model.generate(**encoded, max_length=128, num_beams=1)
    decoded = int8_tok.decode(out[0], skip_special_tokens=True)
    print(f"  load + generate in {time.perf_counter() - t0:.1f}s")
    print(f"  IN : {inp}")
    print(f"  OUT: {decoded}")

    print()
    print(f"OK — int8 ONNX dir ready at {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
