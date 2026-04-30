"""Build a Vietnamese spell-correction eval set from the diacritic eval slices.

Strategy: take the 4-register diacritic eval (`benchmarks/data/...`)
which is already curated, license-clean, and registers-balanced — and
apply realistic noise to each clean target to produce
`(noisy_input, clean_target)` pairs for spell-correction evaluation.

Two noise levels per source slice:

- **light** — ~5 % char-level edit distance, models a person typing
  Vietnamese on a keyboard with a few accent slips and the occasional
  fat-finger.
- **heavy** — ~15-20 % edit distance, models OCR output of a mid-quality
  scan with diacritic drops and char confusions (`o`↔`0`, `l`↔`1`, etc.).

The clean-target side is never modified (already NFC-normalized in the
upstream slices). The noise generator output is also NFC-normalized.

Output:
    benchmarks/data/spell_correction_eval/business_55_light.jsonl
    benchmarks/data/spell_correction_eval/business_55_heavy.jsonl
    ... x 4 registers x 2 noise levels  =  8 splits, 1227 x 2 = 2454 pairs

Determinism: same seed → same exact pairs. Run anytime to refresh.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "src"))
from nom.text.noise import NoiseGenerator, heavy_noise, light_noise  # noqa: E402

OUT_DIR = REPO / "benchmarks" / "data" / "spell_correction_eval"


def _load_txt_corpus(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    ]


def _load_conllu(path: Path) -> list[str]:
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("# text"):
            _, _, val = line.partition("=")
            v = val.strip()
            if v:
                out.append(v)
    return out


_PUNCT_LEAD = re.compile(r"\s+([,.;:!?\)\]\}\"\'»…])")
_PUNCT_TRAIL = re.compile(r"([\(\[\{\"\'«])\s+")


def _normalize_punct(text: str) -> str:
    """Same canonicalization the diacritic bench uses."""
    text = unicodedata.normalize("NFC", text)
    text = _PUNCT_LEAD.sub(r"\1", text)
    text = _PUNCT_TRAIL.sub(r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--seed-light", type=int, default=42)
    p.add_argument("--seed-heavy", type=int, default=43)
    args = p.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    sources = {
        "business_55": _load_txt_corpus(REPO / "benchmarks" / "data" / "diacritic_eval_v0.txt"),
        "formal_72": _load_txt_corpus(
            REPO / "benchmarks" / "data" / "udhr_vi" / "diacritic_eval_udhr.txt"
        ),
        "conversational_300": _load_txt_corpus(
            REPO / "benchmarks" / "data" / "tatoeba_vi" / "diacritic_eval_300.txt"
        ),
        "literary_800": _load_conllu(REPO / "benchmarks" / "data" / "ud_vi_vtb" / "test.conllu"),
    }

    # Two noise levels per register.
    levels = {
        "light": (light_noise(), args.seed_light),
        "heavy": (heavy_noise(), args.seed_heavy),
    }

    total = 0
    for reg, sentences in sources.items():
        for level_name, (cfg, seed) in levels.items():
            gen = NoiseGenerator(cfg, seed=seed)
            out_path = OUT_DIR / f"{reg}_{level_name}.jsonl"
            n_pairs = 0
            with out_path.open("w", encoding="utf-8") as f:
                for s in sentences:
                    target = _normalize_punct(s)
                    noisy = gen.noisify(target)
                    if noisy == target:
                        # No noise actually applied — drop; gives the eval
                        # a free 100% no-op which is uninformative.
                        continue
                    pair = {"input": noisy, "target": target}
                    f.write(json.dumps(pair, ensure_ascii=False) + "\n")
                    n_pairs += 1
            print(f"  {reg}_{level_name}: {n_pairs} pairs -> {out_path.name}")
            total += n_pairs

    print(f"\nTotal: {total} eval pairs across {len(sources)} registers x {len(levels)} levels")
    return 0


if __name__ == "__main__":
    sys.exit(main())
