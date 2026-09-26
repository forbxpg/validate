"""Startup of auth: what must fail at startup rather than on the first request."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

from auth_fakes import FakeHasher

from vld.auth.api._startup import startup
from vld.auth.application import EmailSender, PasswordHasher
from vld.auth.application.use_cases.session._dummy_hash import DummyHash

if TYPE_CHECKING:
    import pytest
    from dishka import AsyncContainer


@final
class _Container:
    def __init__(self) -> None:
        self.hasher = FakeHasher()
        self.requested: list[object] = []

    async def get(self, dependency: object) -> object:
        self.requested.append(dependency)
        known: dict[object, object] = {PasswordHasher: self.hasher}
        return known.get(dependency, object())


async def test_startup_resolves_the_sender_and_warms_the_hasher(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A broken sender fails the start, not the first letter."""
    monkeypatch.setattr(DummyHash, "_value", None)
    container = _Container()

    await startup(cast("AsyncContainer", cast("object", container)))

    assert EmailSender in container.requested
    assert container.hasher.hashed
