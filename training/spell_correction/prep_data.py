"""Build a Vietnamese spell-correction training corpus from clean VN text.

Strategy: take the existing diacritic-restoration training corpus
(`training/diacritic/data/train_mixed_nfc.jsonl` — 500K NFC-normalized
Wikipedia + news pairs), KEEP its `target` (clean Vietnamese), DISCARD its
`input` (which was just `strip_diacritics(target)` — too narrow for
spell-correction), and generate a richer noisy `input` per clean target
using `nom.text.noise`.

The result is `(noisy, clean)` training pairs covering:

- Diacritic strip (full + partial)
- Tone-confusion substitution
- Char-level edit (swap / insert / delete)
- OCR-like char substitution

This is broader than diacritic-only restoration: a spell-correction model
trained on this can fix typos AND restore diacritics AND clean up OCR
errors in one pass.

Output:
    training/spell_correction/data/train.jsonl    (large)
    training/spell_correction/data/val.jsonl      (5 K held-out)
    training/spell_correction/data/stats.json     (corpus statistics)

Run:
    python training/spell_correction/prep_data.py
    python training/spell_correction/prep_data.py --max-pairs 500_000

Each clean target gets ONE noisy input by default. Bump `--noisy-per-clean`
to 2 or 3 for data augmentation (the seed-mixing keeps results
deterministic).

Eval-leak guards: clean side of the corpus is already eval-leak-guarded
by `prep_data.py` upstream — the underlying 500K mixed-NFC corpus filters
against `nrl-ai/vn-diacritic-eval`. Spell-correction eval reuses those
same clean sentences (with noise applied), so we add a stricter check
here: any clean sentence that appears verbatim in the spell-correction
eval set is dropped before noise generation.
"""

from __future__ import annotations

import argparse
import json
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))
from nom.text.noise import (  # noqa: E402
    NoiseConfig,
    NoiseGenerator,
    heavy_noise,
    light_noise,
    telex_typo_noise,
)

OUT_DIR = REPO / "training" / "spell_correction" / "data"


def _eval_leak_guards(repo: Path) -> set[str]:
    """Sentences in the spell-correction eval set we MUST NOT include."""
    blocked: set[str] = set()
    eval_dir = repo / "benchmarks" / "data" / "spell_correction_eval"
    if not eval_dir.exists():
        return blocked
    for jsonl in eval_dir.glob("*.jsonl"):
        for line in jsonl.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            tgt = rec.get("target")
            if tgt:
                blocked.add(unicodedata.normalize("NFC", tgt))
    # Also guard against diacritic eval (they're public clean VN sentences
    # we MUST NOT have memorized at training time).
    diac_dir = repo / "benchmarks" / "data"
    diac_files = [
        diac_dir / "diacritic_eval_v0.txt",
        diac_dir / "tatoeba_vi" / "diacritic_eval_300.txt",
        diac_dir / "udhr_vi" / "diacritic_eval_udhr.txt",
    ]
    for path in diac_files:
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                blocked.add(unicodedata.normalize("NFC", line))
    return blocked


def _pick_noise_config(idx: int) -> NoiseConfig:
    """Round-robin between three noise presets so the model sees a mix.

    Realistic typo distribution is bimodal: light typing (most users) +
    OCR-style (digitization pipelines). Telex covers the diacritic-leaning
    failures specifically. Mixing them gives the spell-corrector exposure
    to the full range of real-world noise.
    """
    cfgs = (light_noise(), telex_typo_noise(), heavy_noise())
    return cfgs[idx % len(cfgs)]


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--source",
        type=Path,
        default=REPO / "training" / "diacritic" / "data" / "train_mixed_nfc.jsonl",
        help="Source JSONL with clean targets (the diacritic-training mixed corpus).",
    )
    p.add_argument(
        "--max-pairs",
        type=int,
        default=500_000,
        help="Max (noisy, clean) pairs to keep.",
    )
    p.add_argument("--val-pairs", type=int, default=5_000)
    p.add_argument(
        "--noisy-per-clean",
        type=int,
        default=1,
        help="How many noisy variants to emit per clean target. >1 augments the corpus.",
    )
    p.add_argument("--seed", type=int, default=42)
    args = p.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    blocked = _eval_leak_guards(REPO)
    print(f"eval-leak guard: {len(blocked)} clean sentences excluded if seen")

    if not args.source.exists():
        print(f"ERROR: source corpus not found: {args.source}", file=sys.stderr)
        print("  Build it first via training/diacritic/prep_data.py.", file=sys.stderr)
        return 2

    print(f"reading clean targets from {args.source.name}...")

    train_path = OUT_DIR / "train.jsonl"
    val_path = OUT_DIR / "val.jsonl"
    stats_path = OUT_DIR / "stats.json"

    n_train = n_val = 0
    n_seen = 0
    n_skipped_blocked = 0
    n_skipped_dup = 0
    seen_targets: set[str] = set()

    with (
        args.source.open(encoding="utf-8") as src_f,
        train_path.open("w", encoding="utf-8") as f_train,
        val_path.open("w", encoding="utf-8") as f_val,
    ):
        for raw in src_f:
            n_seen += 1
            try:
                rec = json.loads(raw)
            except json.JSONDecodeError:
                continue
            target = rec.get("target")
            if not target:
                continue
            target = unicodedata.normalize("NFC", target)
            if target in blocked:
                n_skipped_blocked += 1
                continue
            if target in seen_targets:
                n_skipped_dup += 1
                continue
            seen_targets.add(target)

            for variant in range(args.noisy_per_clean):
                # Mix the global seed with the line index + variant id so each
                # noisy emission is deterministic but distinct.
                seed = args.seed * 31 + n_seen * 7 + variant
                gen = NoiseGenerator(_pick_noise_config(n_seen + variant), seed=seed)
                noisy = gen.noisify(target)
                if noisy == target:
                    # No noise actually applied — skip; gives us no training signal.
                    continue
                pair = {"input": noisy, "target": target}
                if n_val < args.val_pairs:
                    f_val.write(json.dumps(pair, ensure_ascii=False) + "\n")
                    n_val += 1
                else:
                    f_train.write(json.dumps(pair, ensure_ascii=False) + "\n")
                    n_train += 1
                    if n_train >= args.max_pairs:
                        break
            if n_train >= args.max_pairs:
                break

            if (n_train + n_val) % 10_000 == 0 and (n_train + n_val) > 0:
                print(f"  progress: train={n_train:,} val={n_val:,}")

    stats = {
        "source": str(args.source.relative_to(REPO)),
        "train_pairs": n_train,
        "val_pairs": n_val,
        "source_lines_seen": n_seen,
        "skipped_blocked_eval": n_skipped_blocked,
        "skipped_duplicate": n_skipped_dup,
        "noisy_per_clean": args.noisy_per_clean,
        "noise_presets_round_robin": ["light_noise", "telex_typo_noise", "heavy_noise"],
        "seed": args.seed,
    }
    stats_path.write_text(json.dumps(stats, indent=2, ensure_ascii=False) + "\n")
    print()
    print(f"wrote: {train_path} ({n_train:,} pairs)")
    print(f"wrote: {val_path}   ({n_val:,} pairs)")
    print(f"wrote: {stats_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
