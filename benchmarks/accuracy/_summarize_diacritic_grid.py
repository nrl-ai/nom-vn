"""Aggregate per-model diacritic bench JSONs into a comparison table.

Reads all ``diacritics_*.json`` files under
``benchmarks/results/local_diacritic_grid/`` (or a custom dir) and prints
a markdown-friendly table of accuracy and latency by model.

Run:
    python benchmarks/accuracy/_summarize_diacritic_grid.py
    python benchmarks/accuracy/_summarize_diacritic_grid.py --dir custom/path
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

DEFAULT_DIR = Path("benchmarks/results/local_diacritic_grid")

# Tag → approx Q4_K_M disk size (GB). Sourced from ollama.com/library/<model>/tags
# on 2026-04-26. Falls through to "?" when the model isn't in this map.
DISK_SIZES_GB: dict[str, str] = {
    "gemma4:e2b": "7.2",
    "gemma4:e4b": "9.6",
    "gemma4:26b": "18",
    "gemma4:31b": "20",
    "gemma3:4b": "3.3",
    "gemma3:1b": "0.8",
    "gemma3:12b": "8.1",
    "qwen3:1.7b": "1.4",
    "qwen3:4b": "2.5",
    "qwen3:8b": "5.2",
    "qwen3:14b": "9.0",
    "qwen3:30b-a3b": "18",
    "llama3.2:1b": "1.3",
    "llama3.2:3b": "2.0",
    "phi4-mini": "2.5",
    "phi4-mini:latest": "2.5",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--md", type=Path, default=None, help="Write markdown to this file.")
    args = parser.parse_args(argv)

    if not args.dir.is_dir():
        print(f"No grid dir at {args.dir}", file=sys.stderr)
        return 2

    rows: list[dict[str, str]] = []
    for fp in sorted(args.dir.glob("diacritics_*.json")):
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            print(f"skip {fp.name}: {e}", file=sys.stderr)
            continue
        s = data["summary"]
        # Reverse the safe filename "model__tag.json" -> "model:tag"
        stem = fp.stem.removeprefix("diacritics_")
        # Naive: replace last "__" with ":" but underscores are kept elsewhere
        if "__" in stem:
            head, sep, tail = stem.rpartition("__")
            tag = f"{head}:{tail}"
        else:
            tag = stem
        rows.append(
            {
                "model": tag,
                "size_gb": DISK_SIZES_GB.get(tag, "?"),
                "acc": f"{s['overall_word_accuracy'] * 100:.2f}%",
                "recall": f"{s['overall_diacritic_recall'] * 100:.2f}%",
                "p50": f"{s.get('latency_per_sentence_p50', 0):.2f}s",
                "p95": f"{s.get('latency_per_sentence_p95', 0):.2f}s",
                "mean": f"{s.get('latency_per_sentence_mean', 0):.2f}s",
                "warmup": str(s.get("warmup_calls", 0)),
                "elapsed": f"{s['elapsed_seconds']:.1f}s",
            }
        )

    if not rows:
        print("No results found.", file=sys.stderr)
        return 1

    # Sort by accuracy desc
    rows.sort(key=lambda r: float(r["acc"].rstrip("%")), reverse=True)

    cols = ["model", "size_gb", "acc", "recall", "mean", "p50", "p95", "elapsed", "warmup"]
    headers = {
        "model": "Model",
        "size_gb": "Q4 size GB",
        "acc": "Word acc",
        "recall": "Diacritic recall",
        "mean": "Mean s/sent",
        "p50": "p50 s/sent",
        "p95": "p95 s/sent",
        "elapsed": "Total",
        "warmup": "Warmup",
    }
    widths = {c: max(len(headers[c]), max(len(r[c]) for r in rows)) for c in cols}
    sep = "  "

    def fmt(row: dict[str, str]) -> str:
        return sep.join(row[c].ljust(widths[c]) for c in cols)

    header_line = sep.join(headers[c].ljust(widths[c]) for c in cols)
    divider = sep.join("-" * widths[c] for c in cols)
    print(header_line)
    print(divider)
    for r in rows:
        print(fmt(r))

    if args.md is not None:
        lines = [
            "| " + " | ".join(headers[c] for c in cols) + " |",
            "|" + "|".join(["---"] * len(cols)) + "|",
        ]
        for r in rows:
            lines.append("| " + " | ".join(r[c] for c in cols) + " |")
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\nMarkdown written to {args.md}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    sys.exit(main())
