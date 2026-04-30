"""Render a side-by-side comparison table from OOD bench JSONs.

Reads every ``benchmarks/results/baseline_real_*.json`` (or a custom
list passed on the command line) and prints a markdown comparison
table — slices on rows, models on columns, word accuracy in cells.

The bench harness in ``benchmarks/accuracy/bench_spell_correction_real.py``
writes one JSON per model run; this script aggregates them into the
table format used in ``docs/tasks/spell-correction.md`` and
``docs/tasks/diacritic-restoration.md``.

Usage::

    # All committed baselines.
    python scripts/summarize_ood_bench.py

    # A specific subset.
    python scripts/summarize_ood_bench.py \\
        benchmarks/results/baseline_real_spell_correction_base.json \\
        benchmarks/results/baseline_real_toshiiiii1.json

    # Markdown for a model card / docs page.
    python scripts/summarize_ood_bench.py --format markdown

    # Show 95 % CI brackets too.
    python scripts/summarize_ood_bench.py --ci
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEFAULT_DIR = REPO / "benchmarks" / "results"

SLICES = (
    "forum_25",
    "mobile_25",
    "telex_real_25",
    "ocr_25",
    "legal_real_25",
    "news_real_25",
    "__all_real__",
)


def _short_name(model_id: str) -> str:
    # nrl-ai/vn-spell-correction-base -> vn-spell-correction-base
    if "/" in model_id:
        return model_id.split("/", 1)[1]
    return model_id


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "json_files",
        nargs="*",
        type=Path,
        help="Specific JSON files to compare. Default: every "
        "benchmarks/results/baseline_real_*.json file.",
    )
    p.add_argument(
        "--format",
        choices=["text", "markdown"],
        default="text",
        help="text (default, fixed-width) or markdown (table).",
    )
    p.add_argument("--ci", action="store_true", help="Include 95 %% CI brackets.")
    args = p.parse_args()

    paths: list[Path]
    if args.json_files:
        paths = list(args.json_files)
    else:
        paths = sorted(DEFAULT_DIR.glob("baseline_real_*.json"))

    if not paths:
        print(f"no JSON files found under {DEFAULT_DIR}", file=sys.stderr)
        return 2

    rows: list[tuple[str, dict]] = []  # (label, eval_dict)
    for path in paths:
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            print(f"  skip {path.name}: bad JSON ({exc})", file=sys.stderr)
            continue
        label = _short_name(d.get("model_id") or path.stem)
        rows.append((label, d.get("eval", {})))

    if not rows:
        print("no valid JSON eval files", file=sys.stderr)
        return 2

    if args.format == "markdown":
        header = "| Slice | " + " | ".join(label for label, _ in rows) + " |"
        sep = "|---|" + "|".join("---:" for _ in rows) + "|"
        print(header)
        print(sep)
        for sl in SLICES:
            cells = [f"`{sl}`" if sl != "__all_real__" else "**Aggregate**"]
            for _, ev in rows:
                m = ev.get(sl, {})
                wa = m.get("word_accuracy")
                if wa is None:
                    cells.append("—")
                    continue
                cell = f"{wa * 100:.2f} %"
                if args.ci:
                    ci = m.get("word_accuracy_ci95")
                    if ci:
                        cell += f" [{ci[0] * 100:.1f}-{ci[1] * 100:.1f}]"
                cells.append(cell)
            print("| " + " | ".join(cells) + " |")
    else:
        col = max(len(label) for label, _ in rows) + 2
        col = max(col, 12)
        header = f"{'slice':<22s} " + " ".join(f"{label:>{col}s}" for label, _ in rows)
        print(header)
        print("-" * len(header))
        for sl in SLICES:
            row_cells = [f"{sl:<22s}"]
            for _, ev in rows:
                m = ev.get(sl, {})
                wa = m.get("word_accuracy")
                if wa is None:
                    row_cells.append(f"{'—':>{col}s}")
                    continue
                txt = f"{wa * 100:.2f}"
                if args.ci:
                    ci = m.get("word_accuracy_ci95")
                    if ci:
                        txt = f"{wa * 100:.2f} [{ci[0] * 100:.1f}-{ci[1] * 100:.1f}]"
                row_cells.append(f"{txt:>{col}s}")
            print(" ".join(row_cells))
    return 0


if __name__ == "__main__":
    sys.exit(main())
