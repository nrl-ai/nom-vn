"""``RBAC`` Protocol + OSS allow-all default.

Multi-tenant RBAC with role hierarchies, workspace memberships, and
audit-officer read-only roles lives in ``nom-vn-enterprise``. The OSS
default is intentionally permissive — single-tenant deployments don't
need authorisation, only authentication.

Role naming convention (kept in sync between OSS and EE so plugins
and built-in code agree on what to check):

- ``tenant.admin`` — manage users, keys, audit
- ``compliance.officer`` — read-only audit + dossier export
- ``workspace.admin`` — manage workspace + materials
- ``workspace.editor`` — upload + ask
- ``workspace.viewer`` — ask only
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from nom.platform.types import Resource, User

__all__ = ["RBAC", "AllowAllRBAC", "RoleSetRBAC"]


@runtime_checkable
class RBAC(Protocol):
    """Decide whether a User may perform an action on a Resource.

    Implementations may consult an external store (database row in
    EE multi-tenant), a static map (OSS test fixture), or pure-policy
    rules (EE policy-as-code variant). Return value is binary: the
    gateway returns 403 on False, proceeds on True.
    """

    name: str

    def check(self, *, user: User, resource: Resource, action: str) -> bool:
        """Return True iff ``user`` may perform ``action`` on ``resource``."""
        ...


@dataclass
class AllowAllRBAC:
    """OSS default: any authenticated user may do anything.

    Single-tenant deployments don't need RBAC — the bearer-token gate
    is the entire access-control story. EE swaps this for a real
    multi-tenant impl via the ``nom.platform.rbac`` entry-point group.
    """

    name: str = "allow-all"

    def check(self, *, user: User, resource: Resource, action: str) -> bool:
        del user, resource, action
        return True


@dataclass
class RoleSetRBAC:
    """Static role → action map. Useful in tests and small deployments.

    Uses dotted action names: ``"workspace.read"``, ``"audit.read"``,
    ``"tenant.admin"``. A role grants every action whose prefix it
    matches — ``"workspace.admin"`` grants ``"workspace.read"`` and
    ``"workspace.write"`` automatically.

    Tenant scoping: when ``resource.tenant_id`` is set and differs
    from ``user.tenant_id``, the check fails regardless of role —
    cross-tenant access is never inferred from role names.
    """

    role_actions: dict[str, frozenset[str]]
    name: str = "role-set"

    def check(self, *, user: User, resource: Resource, action: str) -> bool:
        if resource.tenant_id is not None and resource.tenant_id != user.tenant_id:
            return False
        for role in user.roles:
            granted = self.role_actions.get(role, frozenset())
            for granted_action in granted:
                if action == granted_action or action.startswith(granted_action + "."):
                    return True
        return False
