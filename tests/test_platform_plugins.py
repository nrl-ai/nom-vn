"""Tests for ``nom.platform.plugins`` — entry-point discovery.

We can't easily install a real entry point inside a unit test, so we
monkeypatch ``importlib.metadata.entry_points`` to return synthetic
``EntryPoint`` objects. The end-to-end test in
``tests/test_platform_e2e.py`` (run only when ``nom-vn-enterprise`` is
installed alongside) exercises the real path.
"""

from __future__ import annotations

from importlib.metadata import EntryPoint
from typing import Any

import pytest

from nom.platform import plugins


class _FakeAuthenticator:
    """Loaded by the synthetic entry point below."""

    name = "fake"


def _ep(name: str, value: str, group: str) -> EntryPoint:
    return EntryPoint(name=name, value=value, group=group)


@pytest.fixture
def fake_entry_points(monkeypatch: pytest.MonkeyPatch) -> dict[str, list[EntryPoint]]:
    """Patch ``importlib.metadata.entry_points`` with a controlled registry."""
    registry: dict[str, list[EntryPoint]] = {
        "nom.platform.authenticators": [
            _ep(
                name="fake",
                value=f"{__name__}:_FakeAuthenticator",
                group="nom.platform.authenticators",
            ),
        ],
        "nom.platform.rbac": [],
    }

    def _entry_points(*, group: str) -> list[EntryPoint]:
        return registry.get(group, [])

    monkeypatch.setattr(plugins, "entry_points", _entry_points)
    return registry


def test_list_plugins_returns_registered(fake_entry_points: Any) -> None:
    eps = plugins.list_plugins("auth")
    assert [e.name for e in eps] == ["fake"]


def test_list_plugins_empty_for_unregistered_group(fake_entry_points: Any) -> None:
    assert plugins.list_plugins("rbac") == []


def test_load_plugin_by_name_returns_class(fake_entry_points: Any) -> None:
    cls = plugins.load_plugin("auth", "fake")
    assert cls is _FakeAuthenticator


def test_load_plugin_without_name_returns_first(fake_entry_points: Any) -> None:
    cls = plugins.load_plugin("auth")
    assert cls is _FakeAuthenticator


def test_load_plugin_unknown_name_raises(fake_entry_points: Any) -> None:
    with pytest.raises(plugins.PluginNotFoundError, match="ghost"):
        plugins.load_plugin("auth", "ghost")


def test_load_plugin_no_plugins_in_group_raises(fake_entry_points: Any) -> None:
    with pytest.raises(plugins.PluginNotFoundError, match="no plugins"):
        plugins.load_plugin("rbac")


def test_unknown_category_raises_value_error() -> None:
    with pytest.raises(ValueError, match="unknown plugin category"):
        plugins.load_plugin("not-a-real-category")  # type: ignore[arg-type]


def test_groups_table_has_expected_categories() -> None:
    assert set(plugins.ENTRY_POINT_GROUPS) == {"auth", "rbac", "pii", "redactor", "forwarder"}
    assert plugins.ENTRY_POINT_GROUPS["auth"] == "nom.platform.authenticators"
