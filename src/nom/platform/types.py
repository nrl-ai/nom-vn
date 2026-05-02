"""Cross-module value types for ``nom.platform``.

Lives outside ``auth`` / ``rbac`` so each submodule can import it
without circular dependencies. New types belong here only when they're
referenced by ≥2 submodules.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "AuthDeniedError",
    "AuthError",
    "AuthExpiredError",
    "Credentials",
    "Resource",
    "User",
]


class AuthError(Exception):
    """Base class for authentication failures.

    The gateway converts these into 401 responses; concrete callers
    catch the base type and let subclasses surface specific reasons
    (expired token vs. denied vs. malformed).
    """


class AuthDeniedError(AuthError):
    """Credentials were syntactically valid but did not match any user."""


class AuthExpiredError(AuthError):
    """Credentials were valid once but have expired (refresh required)."""


@dataclass(frozen=True, slots=True)
class User:
    """An authenticated identity, normalized across providers.

    The ``id`` is whatever the upstream provider considers stable
    (OIDC ``sub``, LDAP DN, the bearer-token user_id). ``tenant_id``
    scopes every downstream resource lookup. ``roles`` is the merged
    role list for this user in this tenant — RBAC implementations
    consume it.

    ``claims`` carries the raw provider claims so advanced rules
    (group membership, custom attributes) can be implemented in EE
    without growing this dataclass.
    """

    id: str
    tenant_id: str
    email: str | None = None
    name: str | None = None
    roles: tuple[str, ...] = ()
    claims: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Credentials:
    """Inputs an Authenticator inspects.

    The gateway extracts these from the HTTP request before invoking
    the Authenticator — this keeps the Authenticator Protocol from
    knowing about FastAPI / Starlette / WSGI specifically.
    """

    bearer_token: str | None = None
    cookie_session: str | None = None
    api_key: str | None = None
    raw_headers: Mapping[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Resource:
    """A thing an action can be performed on.

    Generic on purpose — RBAC implementations interpret the ``type``
    string. Common types: ``"workspace"``, ``"material"``,
    ``"audit"``, ``"tenant"``, ``"agent_run"``.

    ``id`` may be ``"*"`` for "any resource of this type" checks
    (e.g., ``Resource("workspace", "*", tenant_id="vcb")`` —
    "may the user create workspaces in this tenant?").
    """

    type: str
    id: str
    tenant_id: str | None = None
