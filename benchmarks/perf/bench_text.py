"""Performance benchmark for nom.text — measures throughput on a real-shape corpus.

Run:
    python scripts/bench_text.py
"""

from __future__ import annotations

import time
import unicodedata

from nom.text import (
    fix_diacritics,
    has_diacritics,
    is_vietnamese,
    normalize,
    strip_diacritics,
)

# Realistic corpus: contract-style Vietnamese (multiple registers).
_CORPUS = [
    "Hợp đồng số 02/HĐ/2025 được lập ngày 14 tháng 3 năm 2025 tại văn phòng công ty.",
    "Bên A: Công ty Cổ phần ProtonX, mã số thuế 0123456789, địa chỉ Hà Nội.",
    "Bên B: Bà Nguyễn Thị Hương, sinh năm 1990, CMND số 012345678901.",
    "Tổng giá trị hợp đồng: 1.500.000.000 đồng (một tỷ năm trăm triệu đồng chẵn).",
    "Điều 1. Đối tượng hợp đồng: triển khai hệ thống Chatbot tiếng Việt.",
    "Điều 2. Thời hạn thực hiện: 6 tháng kể từ ngày ký kết.",
    "Điều 3. Phương thức thanh toán: chuyển khoản, chia làm 3 đợt.",
    "Điều 4. Quyền và nghĩa vụ của các bên thực hiện theo quy định pháp luật hiện hành.",
    "Điều 5. Mọi tranh chấp được giải quyết thông qua thương lượng, hoà giải.",
    "Hai bên đã đọc, hiểu và đồng ý ký vào hợp đồng này.",
] * 100  # 1000 sentences total

# Diacritic-stripped variant for fix_diacritics benchmark.
_STRIPPED = [strip_diacritics(s) for s in _CORPUS]


def _bench(name: str, fn, inputs, runs: int = 3) -> tuple[float, float]:
    """Run a function on each input. Returns (best_total_seconds, ops_per_sec)."""
    best = float("inf")
    n = len(inputs)
    for _ in range(runs):
        start = time.perf_counter()
        for x in inputs:
            fn(x)
        elapsed = time.perf_counter() - start
        if elapsed < best:
            best = elapsed
    ops = n / best
    chars = sum(len(s) for s in inputs)
    char_rate = chars / best
    print(f"{name:>18}  {best * 1000:7.2f} ms  {ops:>10,.0f} ops/s  {char_rate:>12,.0f} chars/s")
    return best, ops


def main() -> None:
    print(f"Corpus: {len(_CORPUS)} sentences, {sum(len(s) for s in _CORPUS):,} chars total")
    print("Python: stdlib unicodedata only · pure-Python")
    print(f"{'function':>18}  {'time':>10}  {'throughput':>14}  {'char rate':>14}")
    print("-" * 70)

    _bench("normalize", normalize, _CORPUS)
    _bench("strip_diacritics", strip_diacritics, _CORPUS)
    _bench("has_diacritics", has_diacritics, _CORPUS)
    _bench("is_vietnamese", is_vietnamese, _CORPUS)
    _bench("fix_diacritics", fix_diacritics, _STRIPPED)

    # Reference: stdlib unicodedata.normalize directly.
    print()
    print("Reference comparisons (stdlib direct calls):")
    _bench("ud.normalize NFC", lambda s: unicodedata.normalize("NFC", s), _CORPUS)
    _bench("ud.normalize NFD", lambda s: unicodedata.normalize("NFD", s), _CORPUS)


if __name__ == "__main__":
    main()
