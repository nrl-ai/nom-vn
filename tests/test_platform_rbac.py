"""Tests for ``nom.platform.rbac`` — defaults + role-set."""

from __future__ import annotations

from nom.platform import RBAC, AllowAllRBAC, Resource, RoleSetRBAC, User


def test_allow_all_satisfies_protocol() -> None:
    rbac = AllowAllRBAC()
    assert isinstance(rbac, RBAC)


def test_allow_all_returns_true_for_any_input() -> None:
    rbac = AllowAllRBAC()
    user = User(id="u", tenant_id="t")
    assert rbac.check(user=user, resource=Resource("workspace", "w"), action="any.action")


def _alice_admin() -> User:
    return User(id="alice", tenant_id="acme", roles=("workspace.admin",))


def _bob_viewer() -> User:
    return User(id="bob", tenant_id="acme", roles=("workspace.viewer",))


def _make_rbac() -> RoleSetRBAC:
    return RoleSetRBAC(
        role_actions={
            "workspace.admin": frozenset({"workspace"}),
            "workspace.editor": frozenset({"workspace.read", "workspace.write"}),
            "workspace.viewer": frozenset({"workspace.read"}),
        }
    )


def test_role_set_admin_grants_dotted_subactions() -> None:
    rbac = _make_rbac()
    res = Resource("workspace", "w1", tenant_id="acme")
    assert rbac.check(user=_alice_admin(), resource=res, action="workspace.read")
    assert rbac.check(user=_alice_admin(), resource=res, action="workspace.write")
    assert rbac.check(user=_alice_admin(), resource=res, action="workspace.delete")


def test_role_set_viewer_denied_write() -> None:
    rbac = _make_rbac()
    res = Resource("workspace", "w1", tenant_id="acme")
    assert rbac.check(user=_bob_viewer(), resource=res, action="workspace.read")
    assert not rbac.check(user=_bob_viewer(), resource=res, action="workspace.write")


def test_role_set_cross_tenant_blocked() -> None:
    rbac = _make_rbac()
    other_tenant = Resource("workspace", "w1", tenant_id="other")
    assert not rbac.check(user=_alice_admin(), resource=other_tenant, action="workspace.read")


def test_role_set_unknown_role_denies() -> None:
    rbac = _make_rbac()
    user = User(id="x", tenant_id="acme", roles=("unknown.role",))
    res = Resource("workspace", "w1", tenant_id="acme")
    assert not rbac.check(user=user, resource=res, action="workspace.read")


def test_role_set_no_tenant_scope_on_resource() -> None:
    rbac = _make_rbac()
    res = Resource("workspace", "w1")  # no tenant_id
    assert rbac.check(user=_alice_admin(), resource=res, action="workspace.read")
