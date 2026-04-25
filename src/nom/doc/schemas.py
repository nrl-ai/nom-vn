"""Vietnamese-aware shorthand types for ``nom.doc.extract`` schemas.

Users declare extraction schemas as plain dicts mapping field name → type.
The :class:`SchemaResolver` converts the dict into a runtime Pydantic model
that handles the messy formats LLMs produce on real Vietnamese documents:

- Dates in mixed formats: ``"14/3/2025"``, ``"14-3-2025"``,
  ``"ngày 14 tháng 3 năm 2025"``, ISO ``"2025-03-14"``.
- VND amounts with VN-style thousand separators: ``"1.500.000.000"`` →
  ``1500000000``. (Vietnamese conventionally uses ``.`` as thousands
  separator and ``,`` as decimal separator — opposite of English.)
- Parties (contract sides): a name plus optional ``tax_id`` / ``address`` /
  ``representative``.

We use Pydantic v2's ``Annotated`` + ``BeforeValidator`` pattern: the
coercion runs *before* type checking, so the LLM can return a string and
we hand the parsed Python object to the rest of the schema. Field
constraints stay in the fast Rust core (per Pydantic v2 best practices,
docs.pydantic.dev/latest/concepts/types).
"""

from __future__ import annotations

import re
from datetime import date
from typing import Annotated, Any

from pydantic import BaseModel, BeforeValidator, ConfigDict, create_model

__all__ = [
    "AmountVND",
    "Party",
    "SchemaResolver",
    "VNDate",
    "parse_amount_vnd",
    "parse_vn_date",
]


# ---------------------------------------------------------------------------
# VN date parsing
# ---------------------------------------------------------------------------

# Common patterns we see in VN contracts and OCR output.
_DATE_PATTERNS: list[tuple[re.Pattern[str], tuple[str, str, str]]] = [
    # ISO: 2025-03-14
    (re.compile(r"^(\d{4})-(\d{1,2})-(\d{1,2})$"), ("year", "month", "day")),
    # 14/3/2025 or 14/03/2025
    (re.compile(r"^(\d{1,2})/(\d{1,2})/(\d{4})$"), ("day", "month", "year")),
    # 14-3-2025 or 14-03-2025
    (re.compile(r"^(\d{1,2})-(\d{1,2})-(\d{4})$"), ("day", "month", "year")),
    # 14.3.2025 (period separator)
    (re.compile(r"^(\d{1,2})\.(\d{1,2})\.(\d{4})$"), ("day", "month", "year")),
    # ngày 14 tháng 3 năm 2025 (full Vietnamese form)
    (
        re.compile(
            r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})",
            re.IGNORECASE,
        ),
        ("day", "month", "year"),
    ),
    # 14 tháng 3 năm 2025 (ngày omitted)
    (
        re.compile(r"(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", re.IGNORECASE),
        ("day", "month", "year"),
    ),
]


def parse_vn_date(value: Any) -> date:
    """Coerce a VN-format string (or an existing ``date``) to ``datetime.date``.

    Args:
        value: a ``date``, an ISO string, or a Vietnamese-format string.

    Returns:
        ``datetime.date``.

    Raises:
        ValueError: if the value can't be parsed.

    Example:
        >>> parse_vn_date("14/3/2025")
        datetime.date(2025, 3, 14)
        >>> parse_vn_date("ngày 14 tháng 3 năm 2025")
        datetime.date(2025, 3, 14)
    """
    if isinstance(value, date):
        return value
    if not isinstance(value, str):
        raise ValueError(f"VNDate: expected str or date, got {type(value).__name__}")

    s = value.strip()
    for pattern, parts in _DATE_PATTERNS:
        m = pattern.search(s)
        if m:
            mapped = dict(zip(parts, m.groups(), strict=False))
            try:
                return date(
                    year=int(mapped["year"]),
                    month=int(mapped["month"]),
                    day=int(mapped["day"]),
                )
            except (KeyError, ValueError) as exc:
                raise ValueError(f"VNDate: invalid date components in {value!r}") from exc

    raise ValueError(f"VNDate: could not parse {value!r}")


VNDate = Annotated[date, BeforeValidator(parse_vn_date)]
"""A ``datetime.date`` with VN-format string coercion.

Use in schemas as ``"date"`` or directly as ``VNDate``.
"""


# ---------------------------------------------------------------------------
# VND amount parsing
# ---------------------------------------------------------------------------

# Match either:
#   - plain digit run: "1500000000"
#   - VN-format with period/space thousand separators: "1.500.000.000"
# Optionally followed by a comma decimal portion (VN uses comma for decimal).
# Negative amounts allowed via leading dash. We deliberately do NOT parse
# Vietnamese number words ("một tỷ năm trăm triệu") — belongs in v0.1.1+
# behind an explicit opt-in.
_AMOUNT_RE = re.compile(r"^-?(?:\d+|\d{1,3}(?:[.\s]\d{3})+)(?:,\d+)?$")


def parse_amount_vnd(value: Any) -> int:
    """Coerce a VND-formatted string (or int/float) to integer VND.

    Vietnamese convention: ``.`` is the thousands separator, ``,`` is the
    decimal separator. Decimal portions are dropped (VND has no subunit).

    Args:
        value: int, float, or string in VN format.

    Returns:
        int (VND amount).

    Raises:
        ValueError: if not parseable.

    Example:
        >>> parse_amount_vnd("1.500.000.000")
        1500000000
        >>> parse_amount_vnd("1500000000")
        1500000000
        >>> parse_amount_vnd(1_500_000_000)
        1500000000
    """
    if isinstance(value, bool):
        # bool is a subclass of int — explicitly reject to avoid silent truth coercion.
        raise ValueError("AmountVND: expected number or string, got bool")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if not isinstance(value, str):
        raise ValueError(f"AmountVND: expected number or string, got {type(value).__name__}")

    s = value.strip()
    # Strip common VND suffixes / labels.
    for suffix in ("đ", "VND", "vnđ", "đồng"):
        if s.endswith(suffix):
            s = s[: -len(suffix)].strip()

    if not s:
        raise ValueError(f"AmountVND: empty after stripping suffixes: {value!r}")
    if not _AMOUNT_RE.match(s):
        raise ValueError(f"AmountVND: could not parse {value!r}")

    # Drop the decimal portion (VND has no subunit), then drop period/space
    # thousand separators.
    integer_part = s.split(",", 1)[0]
    digits_only = integer_part.replace(".", "").replace(" ", "")
    return int(digits_only)


AmountVND = Annotated[int, BeforeValidator(parse_amount_vnd)]
"""An integer VND amount with string coercion.

Use in schemas as ``"amount_vnd"`` or directly as ``AmountVND``.
"""


# ---------------------------------------------------------------------------
# Party (contract side, official-doc issuer, etc.)
# ---------------------------------------------------------------------------


class Party(BaseModel):
    """A party in a contract or official document.

    Fields are intentionally optional except ``name`` — LLMs frequently
    extract incomplete party information from short documents. Validation
    of completeness is the user's call.
    """

    model_config = ConfigDict(str_strip_whitespace=True, extra="ignore")

    name: str
    tax_id: str | None = None
    address: str | None = None
    representative: str | None = None
    role: str | None = None  # "Bên A", "Bên B", "Bên cho thuê", etc.


# ---------------------------------------------------------------------------
# Schema resolution: dict → Pydantic model
# ---------------------------------------------------------------------------

# Maps the user-facing shorthand strings to runtime types.
_SHORTHAND_TYPES: dict[str, type | Any] = {
    "date": VNDate,
    "amount_vnd": AmountVND,
    "party": Party,
    "str": str,
    "int": int,
    "float": float,
    "bool": bool,
}


class SchemaResolver:
    """Resolve a user-facing schema dict into a runtime Pydantic model.

    Users write::

        schema = {
            "so_hop_dong": str,
            "ngay_ky": "date",
            "ben_a": "party",
            "tong_gia_tri": "amount_vnd",
        }

    The resolver builds an anonymous Pydantic model with the right typed
    fields. The ``Extract`` stage uses the model's JSON schema to drive
    the LLM, and the ``Validate`` stage uses the model itself for parsing.
    """

    def __init__(self, schema: dict[str, Any]) -> None:
        if not schema:
            raise ValueError("Schema cannot be empty.")
        self.schema = schema
        self._model = self._build_model(schema)

    @property
    def model(self) -> type[BaseModel]:
        """The generated Pydantic model class."""
        return self._model

    def json_schema(self) -> dict[str, Any]:
        """Return the model's JSON schema (for prompting LLMs)."""
        return self._model.model_json_schema()

    def validate(self, raw: dict[str, Any]) -> dict[str, Any]:
        """Validate + coerce a raw dict against the schema.

        Returns the validated data as a plain dict (so downstream callers
        don't need to know about Pydantic).

        Raises:
            pydantic.ValidationError: on schema mismatch.
        """
        instance = self._model.model_validate(raw)
        return instance.model_dump()

    def _build_model(self, schema: dict[str, Any]) -> type[BaseModel]:
        # create_model's signature uses **kwargs so the dict-unpack here
        # confuses mypy's overload resolution. The runtime call is correct.
        fields: dict[str, Any] = {}
        for name, type_spec in schema.items():
            resolved = self._resolve_type(type_spec)
            fields[name] = (resolved, ...)
        return create_model("ExtractionSchema", **fields)

    @staticmethod
    def _resolve_type(spec: Any) -> type | Any:
        if isinstance(spec, str):
            if spec not in _SHORTHAND_TYPES:
                raise ValueError(
                    f"Unknown schema shorthand: {spec!r}. Known: {sorted(_SHORTHAND_TYPES)}"
                )
            return _SHORTHAND_TYPES[spec]
        # Allow direct type references (str, int, float, datetime.date,
        # custom Pydantic models, etc.).
        return spec
