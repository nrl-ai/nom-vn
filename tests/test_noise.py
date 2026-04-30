"""Tests for nom.text.noise."""

from __future__ import annotations

import unicodedata

from nom.text.noise import (
    NoiseConfig,
    NoiseGenerator,
    heavy_noise,
    light_noise,
    telex_typo_noise,
)


class TestDeterminism:
    def test_same_seed_same_output(self) -> None:
        # Reproducibility is the load-bearing property — training corpora
        # depend on it.
        cfg = light_noise()
        a = NoiseGenerator(cfg, seed=42).noisify("Tôi yêu Việt Nam")
        b = NoiseGenerator(cfg, seed=42).noisify("Tôi yêu Việt Nam")
        assert a == b

    def test_different_seeds_different_output(self) -> None:
        cfg = heavy_noise()
        text = "Hợp đồng số 02/HĐ/2025 được lập ngày 14 tháng 3."
        outs = {NoiseGenerator(cfg, seed=s).noisify(text) for s in range(8)}
        # At least 4 distinct outputs across 8 seeds — heavy noise + non-trivial
        # input means seed should swing the result.
        assert len(outs) >= 4

    def test_zero_probabilities_passes_through(self) -> None:
        # All probabilities zero ≡ identity (modulo NFC normalization).
        cfg = NoiseConfig()
        text = "Tôi yêu Việt Nam"
        assert NoiseGenerator(cfg, seed=42).noisify(text) == text


class TestNFC:
    def test_output_is_nfc(self) -> None:
        # Even on heavy noise, the output round-trips through NFC.
        gen = NoiseGenerator(heavy_noise(), seed=7)
        for s in [
            "Tôi yêu Việt Nam",
            "Hợp đồng số 02/HĐ/2025",
            "Hà Nội — thủ đô Việt Nam",
            "Đại học Quốc gia",
        ]:
            out = gen.noisify(s)
            assert unicodedata.normalize("NFC", out) == out, f"non-NFC output: {out!r}"

    def test_handles_empty_input(self) -> None:
        gen = NoiseGenerator(heavy_noise(), seed=42)
        assert gen.noisify("") == ""
        assert gen.noisify("   ") == "   "


class TestEditBudget:
    def test_max_edit_ratio_capped(self) -> None:
        # With every probability at 100 % the budget should still cap edits.
        cfg = NoiseConfig(
            p_diacritic_strip=1.0,
            p_diacritic_strip_partial=1.0,
            p_confusion=1.0,
            p_char_swap=1.0,
            p_char_delete=1.0,
            p_char_insert=1.0,
            p_ocr=1.0,
            max_edit_ratio=0.10,
        )
        gen = NoiseGenerator(cfg, seed=42)
        clean = "Tôi yêu Việt Nam và đất nước này tuyệt vời."  # 43 chars
        noisy = gen.noisify(clean)
        # If the budget weren't capped, p=1 across all functions would
        # mangle the string beyond recognition. The 10 % cap means most
        # of the original chars are still present.
        # We assert the rough structural similarity: lengths within ±50 %.
        assert (
            0.5 * len(clean) <= len(noisy) <= 1.5 * len(clean)
        ), f"length blew up: clean={len(clean)}, noisy={len(noisy)}"


class TestSpecificNoises:
    def test_diacritic_strip_actually_strips(self) -> None:
        # p=1 for full diacritic strip → every accented char loses its mark.
        cfg = NoiseConfig(p_diacritic_strip=1.0, max_edit_ratio=1.0)
        gen = NoiseGenerator(cfg, seed=42)
        out = gen.noisify("Việt Nam")
        # No tone-marked vowel should survive — strip_diacritics also
        # converts đ → d.
        for ch in out:
            assert (
                ch.lower()
                not in "ăâđêôơưàáảãạằắẳẵặầấẩẫậèéẻẽẹềếểễệìíỉĩịòóỏõọồốổỗộờớởỡợùúủũụừứửữựỳýỷỹỵ"
            ), f"diacritic survived: {ch!r} in {out!r}"

    def test_confusion_substitutes_only_known_words(self) -> None:
        # p=1 for confusion → words in the table get substituted, others don't.
        cfg = NoiseConfig(p_confusion=1.0, max_edit_ratio=1.0)
        # 'thuê' is in the confusion group {thuê, thuế, thuệ}.
        seen = set()
        for s in range(20):
            out = NoiseGenerator(cfg, seed=s).noisify("thuê").strip()
            seen.add(out)
        # Across 20 seeds we should hit at least 2 different alternatives.
        assert len(seen) >= 2, f"no variety in confusion subs: {seen}"

    def test_unknown_word_passes_through_confusion(self) -> None:
        # Word NOT in the confusion table is unchanged when only p_confusion is on.
        cfg = NoiseConfig(p_confusion=1.0, max_edit_ratio=1.0)
        gen = NoiseGenerator(cfg, seed=42)
        out = gen.noisify("xyzunknownword")
        assert out == "xyzunknownword"


class TestPresets:
    def test_presets_are_well_formed(self) -> None:
        # Each preset must produce a NoiseConfig with sensible probabilities.
        for preset in (light_noise(), heavy_noise(), telex_typo_noise()):
            assert isinstance(preset, NoiseConfig)
            for p in (
                preset.p_diacritic_strip,
                preset.p_diacritic_strip_partial,
                preset.p_confusion,
                preset.p_char_swap,
                preset.p_char_delete,
                preset.p_char_insert,
                preset.p_ocr,
            ):
                assert 0.0 <= p <= 1.0

    def test_presets_actually_introduce_noise(self) -> None:
        # On a non-trivial sentence, each preset produces *some* deviation.
        clean = (
            "Hợp đồng số 02/HĐ/2025 được lập ngày 14 tháng 3 "
            "năm 2025 tại Hà Nội. Bên A: Công ty Cổ phần Hồng Hà."
        )
        for preset in (light_noise(), heavy_noise(), telex_typo_noise()):
            noisy = NoiseGenerator(preset, seed=11).noisify(clean)
            assert noisy != clean, f"{preset} produced no noise"
