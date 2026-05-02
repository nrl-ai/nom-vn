"""``Authenticator`` Protocol + OSS bearer-token default.

Production identity providers (OIDC, SAML, LDAP) live in
``nom-vn-enterprise`` and register via the
``nom.platform.authenticators`` entry-point group. The OSS default is
a constant-time bearer-token comparator equivalent to the existing
``NOM_AUTH_TOKEN`` middleware in ``nom.chat.server`` — but reachable
through the same Protocol the EE plugins implement.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from nom.platform.types import AuthDeniedError, Credentials, User

__all__ = ["Authenticator", "BearerTokenAuth"]


@runtime_checkable
class Authenticator(Protocol):
    """Identifies the user behind a request.

    Implementations are constructed with provider-specific config
    (issuer URL, client ID, signing keys for OIDC; bind DN for LDAP;
    a shared secret for the OSS bearer flow). The ``authenticate``
    call is the only thing the gateway invokes per request.
    """

    name: str

    def authenticate(self, *, credentials: Credentials) -> User:
        """Resolve credentials to a User.

        Raises:
            AuthDeniedError: credentials don't match any user.
            AuthExpiredError: credentials are expired.
            AuthError: any other auth failure.
        """
        ...


@dataclass
class BearerTokenAuth:
    """Compare ``Authorization: Bearer <token>`` against a fixed value.

    Used by single-tenant OSS deployments where the operator just
    wants to gate the API behind one shared secret. Equivalent in
    behaviour to the ``NOM_AUTH_TOKEN`` env-var path that already
    exists in ``nom.chat.server``, but reachable through the same
    Protocol that the EE OIDC plugin implements.

    The token comparison uses ``secrets.compare_digest`` so a
    timing-side-channel attacker can't binary-search the token.
    """

    token: str
    user_id: str = "anonymous"
    tenant_id: str = "default"
    name: str = "bearer"

    def authenticate(self, *, credentials: Credentials) -> User:
        if not credentials.bearer_token:
            raise AuthDeniedError("missing bearer token")
        # Encode to bytes so the comparison is byte-identical and
        # ``secrets.compare_digest`` can do its constant-time job
        # without UTF-8-encoding twice per call.
        if not secrets.compare_digest(
            credentials.bearer_token.encode("utf-8"),
            self.token.encode("utf-8"),
        ):
            raise AuthDeniedError("bearer token mismatch")
        return User(
            id=self.user_id,
            tenant_id=self.tenant_id,
            roles=("workspace.editor",),
        )
