"""Tests for ``nom.platform.license`` — HMAC sign / verify roundtrip."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from nom.platform.license import (
    LicenseExpiredError,
    LicenseInvalidError,
    LicenseMissingFeatureError,
    sign_license,
    verify_license,
)


def _make_payload(
    *,
    expires_at: str | None = None,
    features: tuple[str, ...] = ("oidc", "saml"),
) -> dict[str, object]:
    return {
        "customer": "Vietcombank JSC",
        "tenant_id": "vcb-prod",
        "tier": "enterprise",
        "issued_at": "2026-05-02",
        "expires_at": expires_at or "2099-01-01",
        "features": list(features),
    }


def _write_signed(tmp_path: Path, key: bytes, payload: dict[str, object]) -> Path:
    payload = dict(payload)
    payload["_sig"] = sign_license(payload, key=key)
    p = tmp_path / "license.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def test_sign_then_verify_roundtrip(tmp_path: Path) -> None:
    key = secrets.token_bytes(32)
    path = _write_signed(tmp_path, key, _make_payload())
    lic = verify_license(key=key, license_path=path)
    assert lic.customer == "Vietcombank JSC"
    assert lic.has_feature("oidc")
    assert not lic.has_feature("saml-extended")


def test_verify_fails_on_signature_tamper(tmp_path: Path) -> None:
    key = secrets.token_bytes(32)
    path = _write_signed(tmp_path, key, _make_payload())
    data = json.loads(path.read_text())
    data["customer"] = "Tampered"
    path.write_text(json.dumps(data))
    with pytest.raises(LicenseInvalidError, match="signature"):
        verify_license(key=key, license_path=path)


def test_verify_fails_on_wrong_key(tmp_path: Path) -> None:
    issuing_key = secrets.token_bytes(32)
    other_key = secrets.token_bytes(32)
    path = _write_signed(tmp_path, issuing_key, _make_payload())
    with pytest.raises(LicenseInvalidError):
        verify_license(key=other_key, license_path=path)


def test_verify_fails_on_expired(tmp_path: Path) -> None:
    key = secrets.token_bytes(32)
    yesterday = (datetime.now(tz=timezone.utc) - timedelta(days=1)).date().isoformat()
    path = _write_signed(tmp_path, key, _make_payload(expires_at=yesterday))
    with pytest.raises(LicenseExpiredError):
        verify_license(key=key, license_path=path)


def test_verify_fails_on_missing_feature(tmp_path: Path) -> None:
    key = secrets.token_bytes(32)
    path = _write_signed(tmp_path, key, _make_payload(features=("oidc",)))
    with pytest.raises(LicenseMissingFeatureError):
        verify_license(key=key, license_path=path, required_features=("audit_shipper",))


def test_verify_passes_when_features_present(tmp_path: Path) -> None:
    key = secrets.token_bytes(32)
    path = _write_signed(tmp_path, key, _make_payload(features=("oidc", "saml")))
    lic = verify_license(key=key, license_path=path, required_features=("oidc",))
    assert lic.tenant_id == "vcb-prod"


def test_short_keys_rejected_for_signing() -> None:
    with pytest.raises(ValueError, match="≥32 bytes"):
        sign_license(_make_payload(), key=b"short")


def test_short_keys_rejected_for_verification(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="≥32 bytes"):
        verify_license(key=b"short", license_path=tmp_path / "x.json")


def test_missing_file_raises_invalid(tmp_path: Path) -> None:
    key = secrets.token_bytes(32)
    with pytest.raises(LicenseInvalidError, match="not found"):
        verify_license(key=key, license_path=tmp_path / "nope.json")


def test_malformed_json_raises_invalid(tmp_path: Path) -> None:
    key = secrets.token_bytes(32)
    path = tmp_path / "bad.json"
    path.write_text("not json")
    with pytest.raises(LicenseInvalidError, match="not valid JSON"):
        verify_license(key=key, license_path=path)


def test_env_var_path_resolution(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key = secrets.token_bytes(32)
    path = _write_signed(tmp_path, key, _make_payload())
    monkeypatch.setenv("NOM_EE_LICENSE_PATH", str(path))
    lic = verify_license(key=key)  # no explicit path
    assert lic.customer == "Vietcombank JSC"
