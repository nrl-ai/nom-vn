"""Performance benchmark for ``nom.doc.schemas`` parsers.

Measures throughput of the VN-aware Pydantic coercions:
- ``parse_vn_date`` across the supported date formats.
- ``parse_amount_vnd`` across digit / period-thousands / suffix variants.
- Full ``SchemaResolver`` roundtrip on a contract-shaped dict.

Methodology (per CLAUDE.md principle 12):
- Warmup: 3 calls per function over the corpus.
- Best-of-5 over the corpus.
- Reports ops/sec for each parser + roundtrip latency.

Run::

    python benchmarks/perf/bench_schemas.py
    python benchmarks/perf/bench_schemas.py --json results/schemas.json
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from nom.doc.schemas import SchemaResolver, parse_amount_vnd, parse_vn_date

# Realistic mixture — same shape an LLM emits.
_DATES = [
    "2025-03-14",
    "14/3/2025",
    "14/03/2025",
    "14-3-2025",
    "14.3.2025",
    "ngày 14 tháng 3 năm 2025",
    "14 tháng 3 năm 2025",
    "Ngày 14 Tháng 3 Năm 2025",
    "ngày 30 tháng 12 năm 2024",
    "1/1/2025",
] * 100  # 1,000 dates

_AMOUNTS = [
    "1500000000",
    "1.500.000.000",
    "1.500.000.000 đồng",
    "1.500.000.000 VND",
    "1.500.000.000 đ",
    "100.000",
    "10.500.000",
    "-1.500.000",
    "1.500.000,50",
    "1500000",
] * 100  # 1,000 amounts

_CONTRACT_RECORD = {
    "so_hop_dong": "HD-2025-002",
    "ngay_ky": "ngày 14 tháng 3 năm 2025",
    "tong_gia_tri": "1.500.000.000",
    "ben_a": {"name": "Công ty Cổ phần Hồng Hà", "tax_id": "0123456789"},
    "ben_b": {"name": "Bà Nguyễn Thị Hương"},
}
_CONTRACT_SCHEMA = {
    "so_hop_dong": str,
    "ngay_ky": "date",
    "tong_gia_tri": "amount_vnd",
    "ben_a": "party",
    "ben_b": "party",
}


@dataclass
class BenchResult:
    parse_vn_date_per_sec: float
    parse_amount_vnd_per_sec: float
    schema_validate_per_sec: float
    n_dates: int
    n_amounts: int


def _bench(label: str, fn, items: list, *, warmup: int = 3, runs: int = 5) -> float:
    for _ in range(warmup):
        for x in items[:50]:
            fn(x)
    best = float("inf")
    for _ in range(runs):
        start = time.perf_counter()
        for x in items:
            fn(x)
        elapsed = time.perf_counter() - start
        if elapsed < best:
            best = elapsed
    return len(items) / best


def run() -> BenchResult:
    # Sanity: assert correctness once before timing
    assert parse_vn_date("14/3/2025") == date(2025, 3, 14)
    assert parse_amount_vnd("1.500.000.000") == 1_500_000_000

    date_per_sec = _bench("parse_vn_date", parse_vn_date, _DATES)
    amount_per_sec = _bench("parse_amount_vnd", parse_amount_vnd, _AMOUNTS)

    # Full validate roundtrip on contract-shaped data
    resolver = SchemaResolver(_CONTRACT_SCHEMA)

    def _validate(_unused: object) -> dict:
        return resolver.validate(_CONTRACT_RECORD)

    validate_per_sec = _bench("schema_validate", _validate, list(range(1000)))

    return BenchResult(
        parse_vn_date_per_sec=round(date_per_sec, 0),
        parse_amount_vnd_per_sec=round(amount_per_sec, 0),
        schema_validate_per_sec=round(validate_per_sec, 0),
        n_dates=len(_DATES),
        n_amounts=len(_AMOUNTS),
    )


def _print_human(r: BenchResult) -> None:
    print(f"Corpus: {r.n_dates} dates, {r.n_amounts} amounts, 1000 contract dicts")
    print("Methodology: warmup x 3, best-of-5.")
    print()
    print(f"{'function':>26}  {'ops/sec':>14}")
    print("-" * 44)
    print(f"{'parse_vn_date':>26}  {r.parse_vn_date_per_sec:>14,.0f}")
    print(f"{'parse_amount_vnd':>26}  {r.parse_amount_vnd_per_sec:>14,.0f}")
    print(f"{'SchemaResolver.validate':>26}  {r.schema_validate_per_sec:>14,.0f}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", type=Path, default=None)
    args = parser.parse_args(argv)

    result = run()
    _print_human(result)

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with args.json.open("w", encoding="utf-8") as f:
            json.dump(asdict(result), f, indent=2)
        print(f"\nResults written to {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
