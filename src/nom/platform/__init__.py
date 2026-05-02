"""``nom.platform`` — extensibility seams for enterprise deployments.

The OSS package ships small Protocol surfaces for the four cross-cutting
concerns that change between a solo install and a regulated multi-tenant
deployment: identity (``Authenticator``), authorisation (``RBAC``),
privacy (``PIIDetector`` + ``Redactor``), and external audit shipping
(``AuditForwarder``).

Each Protocol has a working OSS default impl (bearer token, allow-all
RBAC, regex-based VN PII, no-op forwarder). Production implementations
(OIDC/SAML/LDAP, multi-tenant RBAC, ML-based PII, Splunk/ELK shippers)
live in the ``nom-vn-enterprise`` package and register themselves via
``importlib.metadata`` entry points — installing them turns the seam on
without any change to OSS code.

Why this layer exists outside ``nom.compliance``: the compliance module
records *what happened*; the platform layer decides *who is allowed to
do it*. A solo developer running ``nom serve`` doesn't need either of
these — but every deployment of size does, and they're the seams an
audit team will inspect first.
"""

from __future__ import annotations

from nom.platform.audit_forward import AuditForwarder, NoOpAuditForwarder
from nom.platform.auth import Authenticator, BearerTokenAuth
from nom.platform.context import current_user, set_current_user
from nom.platform.license import (
    License,
    LicenseError,
    LicenseExpiredError,
    LicenseInvalidError,
    LicenseMissingFeatureError,
    sign_license,
    verify_license,
)
from nom.platform.plugins import (
    ENTRY_POINT_GROUPS,
    PluginNotFoundError,
    list_plugins,
    load_plugin,
)
from nom.platform.privacy import (
    MaskRedactor,
    PIIDetector,
    PIISpan,
    Redactor,
    RegexPIIDetector,
)
from nom.platform.rbac import RBAC, AllowAllRBAC, RoleSetRBAC
from nom.platform.types import (
    AuthDeniedError,
    AuthError,
    AuthExpiredError,
    Credentials,
    Resource,
    User,
)

__all__ = [
    "ENTRY_POINT_GROUPS",
    "RBAC",
    "AllowAllRBAC",
    "AuditForwarder",
    "AuthDeniedError",
    "AuthError",
    "AuthExpiredError",
    "Authenticator",
    "BearerTokenAuth",
    "Credentials",
    "License",
    "LicenseError",
    "LicenseExpiredError",
    "LicenseInvalidError",
    "LicenseMissingFeatureError",
    "MaskRedactor",
    "NoOpAuditForwarder",
    "PIIDetector",
    "PIISpan",
    "PluginNotFoundError",
    "Redactor",
    "RegexPIIDetector",
    "Resource",
    "RoleSetRBAC",
    "User",
    "current_user",
    "list_plugins",
    "load_plugin",
    "set_current_user",
    "sign_license",
    "verify_license",
]
