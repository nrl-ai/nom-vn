"""Tests for nom.doc.schemas — VN-aware Pydantic types + SchemaResolver."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from nom.doc.schemas import (
    Party,
    SchemaResolver,
    parse_amount_vnd,
    parse_vn_date,
)


class TestParseVNDate:
    def test_iso_format(self) -> None:
        assert parse_vn_date("2025-03-14") == date(2025, 3, 14)

    def test_slash_format(self) -> None:
        assert parse_vn_date("14/3/2025") == date(2025, 3, 14)
        assert parse_vn_date("14/03/2025") == date(2025, 3, 14)

    def test_dash_format(self) -> None:
        assert parse_vn_date("14-3-2025") == date(2025, 3, 14)

    def test_period_format(self) -> None:
        assert parse_vn_date("14.3.2025") == date(2025, 3, 14)

    def test_full_vietnamese(self) -> None:
        assert parse_vn_date("ngày 14 tháng 3 năm 2025") == date(2025, 3, 14)
        # Mixed casing
        assert parse_vn_date("Ngày 14 Tháng 3 Năm 2025") == date(2025, 3, 14)

    def test_partial_vietnamese(self) -> None:
        assert parse_vn_date("14 tháng 3 năm 2025") == date(2025, 3, 14)

    def test_passthrough_existing_date(self) -> None:
        d = date(2025, 3, 14)
        assert parse_vn_date(d) is d

    def test_invalid_string_raises(self) -> None:
        with pytest.raises(ValueError, match=r"could not parse"):
            parse_vn_date("not a date")

    def test_non_string_non_date_raises(self) -> None:
        with pytest.raises(ValueError, match=r"expected"):
            parse_vn_date(12345)

    def test_invalid_components_raise(self) -> None:
        with pytest.raises(ValueError, match=r"invalid date components"):
            parse_vn_date("32/13/2025")  # Feb 31st, etc.


class TestParseAmountVND:
    def test_plain_digits(self) -> None:
        assert parse_amount_vnd("1500000000") == 1_500_000_000

    def test_vn_thousand_separators(self) -> None:
        assert parse_amount_vnd("1.500.000.000") == 1_500_000_000
        assert parse_amount_vnd("100.000") == 100_000

    def test_int_passthrough(self) -> None:
        assert parse_amount_vnd(1_500_000_000) == 1_500_000_000

    def test_float_truncates(self) -> None:
        assert parse_amount_vnd(1_500_000_000.7) == 1_500_000_000

    def test_strips_vnd_suffix(self) -> None:
        assert parse_amount_vnd("1.500.000 đồng") == 1_500_000
        assert parse_amount_vnd("1.500.000 VND") == 1_500_000
        assert parse_amount_vnd("1.500.000 đ") == 1_500_000

    def test_drops_decimal(self) -> None:
        # VN uses comma for decimal; we drop it (VND has no subunit).
        assert parse_amount_vnd("1.500.000,50") == 1_500_000

    def test_negative(self) -> None:
        assert parse_amount_vnd("-1.500.000") == -1_500_000

    def test_invalid_string_raises(self) -> None:
        with pytest.raises(ValueError, match=r"could not parse"):
            parse_amount_vnd("một tỷ")  # number words not supported in v0

    def test_bool_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"bool"):
            parse_amount_vnd(True)


class TestParty:
    def test_minimal(self) -> None:
        p = Party(name="Cty ABC")
        assert p.name == "Cty ABC"
        assert p.tax_id is None

    def test_full(self) -> None:
        p = Party(
            name="Công ty Cổ phần Hồng Hà",
            tax_id="0123456789",
            address="Hà Nội",
            representative="Nguyễn Văn A",
            role="Bên A",
        )
        assert p.tax_id == "0123456789"
        assert p.role == "Bên A"

    def test_strips_whitespace(self) -> None:
        p = Party(name="  Cty ABC  ")
        assert p.name == "Cty ABC"

    def test_extra_fields_ignored(self) -> None:
        p = Party(name="X", bogus_field="y")  # type: ignore[call-arg]
        assert p.name == "X"


class TestSchemaResolver:
    def test_basic_string_field(self) -> None:
        r = SchemaResolver({"so": str})
        out = r.validate({"so": "HD-001"})
        assert out == {"so": "HD-001"}

    def test_date_shorthand(self) -> None:
        r = SchemaResolver({"ngay": "date"})
        out = r.validate({"ngay": "14/3/2025"})
        assert out == {"ngay": date(2025, 3, 14)}

    def test_amount_vnd_shorthand(self) -> None:
        r = SchemaResolver({"gia": "amount_vnd"})
        out = r.validate({"gia": "1.500.000.000"})
        assert out == {"gia": 1_500_000_000}

    def test_party_shorthand(self) -> None:
        r = SchemaResolver({"ben_a": "party"})
        out = r.validate({"ben_a": {"name": "Cty ABC", "tax_id": "012"}})
        assert out["ben_a"]["name"] == "Cty ABC"
        assert out["ben_a"]["tax_id"] == "012"

    def test_full_contract_schema(self) -> None:
        r = SchemaResolver(
            {
                "so_hop_dong": str,
                "ngay_ky": "date",
                "tong_gia_tri": "amount_vnd",
                "ben_a": "party",
                "ben_b": "party",
            }
        )
        out = r.validate(
            {
                "so_hop_dong": "HD-2025-002",
                "ngay_ky": "ngày 14 tháng 3 năm 2025",
                "tong_gia_tri": "1.500.000.000",
                "ben_a": {"name": "Hồng Hà", "tax_id": "0123456789"},
                "ben_b": {"name": "Bà Nguyễn"},
            }
        )
        assert out["so_hop_dong"] == "HD-2025-002"
        assert out["ngay_ky"] == date(2025, 3, 14)
        assert out["tong_gia_tri"] == 1_500_000_000
        assert out["ben_a"]["name"] == "Hồng Hà"
        assert out["ben_b"]["tax_id"] is None

    def test_unknown_shorthand_raises(self) -> None:
        with pytest.raises(ValueError, match=r"Unknown schema shorthand"):
            SchemaResolver({"x": "bogus_type"})

    def test_empty_schema_rejected(self) -> None:
        with pytest.raises(ValueError, match=r"empty"):
            SchemaResolver({})

    def test_invalid_data_raises_pydantic_error(self) -> None:
        r = SchemaResolver({"ngay": "date", "gia": "amount_vnd"})
        with pytest.raises(ValidationError):
            r.validate({"ngay": "not a date", "gia": "1.500.000"})

    def test_json_schema_for_prompting(self) -> None:
        r = SchemaResolver({"so": str, "ngay": "date"})
        js = r.json_schema()
        assert "properties" in js
        assert "so" in js["properties"]
        assert "ngay" in js["properties"]
