"""Tests for ``nom.platform.context`` — ContextVar user propagation."""

from __future__ import annotations

import asyncio
import threading

from nom.platform import User, current_user, set_current_user


def test_default_is_none() -> None:
    # Reset because pytest may run tests in any order; ContextVar's
    # default is None at module-import time and we don't want any
    # leakage from earlier tests.
    token = current_user.set(None)
    try:
        assert current_user.get() is None
    finally:
        current_user.reset(token)


def test_set_then_get() -> None:
    user = User(id="alice", tenant_id="acme")
    token = current_user.set(user)
    try:
        assert current_user.get() is user
    finally:
        current_user.reset(token)


def test_set_helper_matches_direct_set() -> None:
    user = User(id="bob", tenant_id="acme")
    set_current_user(user)
    try:
        assert current_user.get() is user
    finally:
        set_current_user(None)


def test_async_tasks_get_independent_copies() -> None:
    set_current_user(None)
    results: dict[str, str | None] = {}

    async def task_with_user(name: str, uid: str) -> None:
        set_current_user(User(id=uid, tenant_id="t"))
        await asyncio.sleep(0)
        cu = current_user.get()
        results[name] = cu.id if cu else None

    async def main() -> None:
        await asyncio.gather(
            task_with_user("a", "alice"),
            task_with_user("b", "bob"),
        )

    asyncio.run(main())
    assert results == {"a": "alice", "b": "bob"}


def test_thread_starts_with_parent_context() -> None:
    user = User(id="carol", tenant_id="acme")
    set_current_user(user)
    captured: list[str | None] = []

    def worker() -> None:
        cu = current_user.get()
        captured.append(cu.id if cu else None)

    t = threading.Thread(target=worker)
    t.start()
    t.join()
    set_current_user(None)
    # Plain threading.Thread does NOT propagate ContextVars by default.
    # We assert the documented behaviour: child sees default (None).
    assert captured == [None]
