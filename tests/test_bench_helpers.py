"""Tests for the shared bench helpers in bench_spell_correction_real.py.

These helpers are shared between bench_spell_correction_real.py and
bench_spell_correction_hf.py — single source of truth so synthetic
and OOD numbers stay methodologically comparable.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "benchmarks" / "accuracy"))

from bench_spell_correction_real import _bootstrap_ci_word_acc, _categorize_errors  # noqa: E402


class TestBootstrapCi:
    def test_perfect_predictions_have_tight_ci(self) -> None:
        # All-correct -> 100 % accuracy with no spread.
        preds = ["Tôi yêu Việt Nam"] * 30
        targets = ["Tôi yêu Việt Nam"] * 30
        lo, hi = _bootstrap_ci_word_acc(preds, targets)
        assert lo == 1.0
        assert hi == 1.0

    def test_empty_inputs_return_zero(self) -> None:
        lo, hi = _bootstrap_ci_word_acc([], [])
        assert lo == 0.0
        assert hi == 0.0

    def test_seed_reproducible(self) -> None:
        # Same inputs + same seed -> same CI bounds across calls.
        preds = ["Tôi yêu", "Việt Nam", "đất nước"]
        targets = ["Tôi yêu", "Việt Nam", "đất nước này"]
        a = _bootstrap_ci_word_acc(preds, targets, seed=42)
        b = _bootstrap_ci_word_acc(preds, targets, seed=42)
        assert a == b

    def test_lower_bound_at_or_below_upper_bound(self) -> None:
        preds = ["yêu Việt", "Tôi", "Hà Nội", "Đà Nẵng"]
        targets = ["yêu Việt", "Toi", "Hà Nội", "Da Nang"]
        lo, hi = _bootstrap_ci_word_acc(preds, targets)
        assert 0.0 <= lo <= hi <= 1.0


class TestCategorizeErrors:
    def test_perfect_match_only_counts_correct(self) -> None:
        preds = ["Tôi yêu Việt Nam"]
        targets = ["Tôi yêu Việt Nam"]
        c = _categorize_errors(preds, targets)
        assert c["correct"] == 4
        for key in ("missed_diacritic", "wrong_tone", "base_char", "extra_word", "missing_word"):
            assert c[key] == 0

    def test_missed_diacritic_classification(self) -> None:
        # 'không' -> 'khong' is a strict-strip case.
        preds = ["khong"]
        targets = ["không"]
        c = _categorize_errors(preds, targets)
        assert c["missed_diacritic"] == 1
        assert c["wrong_tone"] == 0
        assert c["base_char"] == 0

    def test_wrong_tone_classification(self) -> None:
        # 'không' -> 'khống' is same base letters, different tone.
        preds = ["khống"]
        targets = ["không"]
        c = _categorize_errors(preds, targets)
        assert c["wrong_tone"] == 1
        assert c["missed_diacritic"] == 0
        assert c["base_char"] == 0

    def test_base_char_classification(self) -> None:
        # 'không' -> 'khá' is a different word entirely.
        preds = ["khá"]
        targets = ["không"]
        c = _categorize_errors(preds, targets)
        assert c["base_char"] == 1
        assert c["missed_diacritic"] == 0
        assert c["wrong_tone"] == 0

    def test_extra_word_counted(self) -> None:
        preds = ["Tôi yêu Việt Nam quá"]
        targets = ["Tôi yêu Việt Nam"]
        c = _categorize_errors(preds, targets)
        assert c["extra_word"] == 1

    def test_missing_word_counted(self) -> None:
        preds = ["Tôi yêu"]
        targets = ["Tôi yêu Việt Nam"]
        c = _categorize_errors(preds, targets)
        assert c["missing_word"] == 2
