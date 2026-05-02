"""HMAC-signed license tokens for EE plugins.

The EE distribution embeds a verification key. At plugin construction
time, the EE plugin calls :func:`verify_license` to confirm the
operator has a valid licence for the requested feature. The OSS code
here defines the format and verification primitive — the actual
signing key never appears in the OSS package.

License file format (JSON, single object)::

    {
      "customer": "Vietcombank JSC",
      "tenant_id": "vcb-prod",
      "tier": "enterprise",
      "issued_at": "2026-05-02",
      "expires_at": "2027-05-02",
      "features": ["oidc", "saml", "audit_shipper", "advanced_pii"],
      "_sig": "<hex hmac-sha256>"
    }

The signature is computed over a canonical-JSON encoding of every
field except ``_sig`` itself — same primitive ``nom.compliance.audit``
uses for the audit chain, so both verification surfaces share one
implementation and one test set.

Air-gapped deployments work: the licence file is delivered with the
EE wheel; verification is offline; expiry is checked against system
time.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

__all__ = [
    "License",
    "LicenseError",
    "LicenseExpiredError",
    "LicenseInvalidError",
    "LicenseMissingFeatureError",
    "canonical_license_payload",
    "sign_license",
    "verify_license",
]


class LicenseError(Exception):
    """Base for licence verification failures."""


class LicenseInvalidError(LicenseError):
    """Signature mismatch or malformed licence file."""


class LicenseExpiredError(LicenseError):
    """Licence is past its ``expires_at`` date."""


class LicenseMissingFeatureError(LicenseError):
    """Licence is valid but doesn't include a required feature."""


@dataclass(frozen=True, slots=True)
class License:
    """A verified, parsed licence token.

    Compare ``expires_at`` (ISO date) against ``datetime.utcnow().date()``
    via :meth:`is_expired`. Use :meth:`has_feature` to gate optional
    EE features (each feature flag toggles one plugin).
    """

    customer: str
    tenant_id: str
    tier: str
    issued_at: str
    expires_at: str
    features: tuple[str, ...]

    def has_feature(self, name: str) -> bool:
        return name in self.features

    def is_expired(self, *, now: datetime | None = None) -> bool:
        when = now if now is not None else datetime.now(tz=timezone.utc)
        try:
            expiry = datetime.fromisoformat(self.expires_at).replace(tzinfo=timezone.utc)
        except ValueError:
            return True
        return when > expiry


def canonical_license_payload(data: dict[str, Any]) -> bytes:
    """Encode the licence payload (without ``_sig``) for signing."""
    payload = {k: v for k, v in data.items() if k != "_sig"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def sign_license(data: dict[str, Any], *, key: bytes) -> str:
    """Compute the HMAC-SHA256 signature for a licence payload.

    Used by NRL's licence-issuing tool, not by EE plugins themselves.
    The output is hex-encoded so the licence file stays plain JSON.
    """
    if len(key) < 32:
        msg = "license signing key must be ≥32 bytes"
        raise ValueError(msg)
    return hmac.new(key, canonical_license_payload(data), hashlib.sha256).hexdigest()


def verify_license(
    *,
    key: bytes,
    license_path: Path | None = None,
    required_features: tuple[str, ...] = (),
) -> License:
    """Verify and parse the licence file.

    Args:
        key: the verification key. EE plugins pass a key embedded in
            their distribution; tests pass a key generated locally.
        license_path: explicit path; when ``None``, falls back to
            ``$NOM_EE_LICENSE_PATH`` then ``~/.nom/license.json``.
        required_features: each must be present in the licence.

    Raises:
        LicenseInvalidError: file missing, malformed, or signature
            doesn't match.
        LicenseExpiredError: expiry date in the past.
        LicenseMissingFeatureError: a required feature isn't in the
            licence's feature list.
    """
    if len(key) < 32:
        msg = "license verification key must be ≥32 bytes"
        raise ValueError(msg)

    path = _resolve_license_path(license_path)
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        msg = f"license file not found at {path}"
        raise LicenseInvalidError(msg) from exc

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        msg = f"license file at {path} is not valid JSON"
        raise LicenseInvalidError(msg) from exc

    if not isinstance(data, dict):
        msg = f"license file at {path} must be a JSON object"
        raise LicenseInvalidError(msg)

    sig = data.get("_sig")
    if not isinstance(sig, str):
        msg = "license missing _sig field"
        raise LicenseInvalidError(msg)

    expected = hmac.new(key, canonical_license_payload(data), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise LicenseInvalidError("license signature mismatch")

    try:
        features = tuple(data.get("features", ()))
        license_obj = License(
            customer=str(data["customer"]),
            tenant_id=str(data["tenant_id"]),
            tier=str(data["tier"]),
            issued_at=str(data["issued_at"]),
            expires_at=str(data["expires_at"]),
            features=features,
        )
    except KeyError as exc:
        msg = f"license missing required field: {exc.args[0]!r}"
        raise LicenseInvalidError(msg) from exc

    if license_obj.is_expired():
        msg = f"license expired on {license_obj.expires_at}"
        raise LicenseExpiredError(msg)

    missing = [f for f in required_features if not license_obj.has_feature(f)]
    if missing:
        msg = f"license missing required features: {missing}"
        raise LicenseMissingFeatureError(msg)

    return license_obj


def _resolve_license_path(explicit: Path | None) -> Path:
    if explicit is not None:
        return explicit
    env = os.environ.get("NOM_EE_LICENSE_PATH")
    if env:
        return Path(env)
    return Path.home() / ".nom" / "license.json"
