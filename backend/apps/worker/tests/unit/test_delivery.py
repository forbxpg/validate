"""Sending one letter: the transaction before the letter, the sorting of failures."""

from __future__ import annotations

from typing import TYPE_CHECKING, cast, final

import pytest
from auth_fakes import FakeUnitOfWork
from dishka import Provider, Scope, make_async_container, provide
from prometheus_client import REGISTRY

from vld.auth.application import (
    EmailPermanentlyUndeliverableError,
    SendVerificationEmail,
)
from vld.auth.domain import USER_REGISTERED_EVENT
from vld.core.database import UnitOfWork
from vld.worker._delivery import send_email

if TYPE_CHECKING:
    from vld.auth.domain import DomainEvent


@final
class _Handler:
    def __init__(self, uow: FakeUnitOfWork, failure: Exception | None) -> None:
        self.uow = uow
        self.failure = failure
        self.committed_before_delivery: bool | None = None

    async def prepare(self, event: DomainEvent, delivery_id: int) -> tuple[str, str]:
        """Record the call and name the recipient."""
        del event, delivery_id
        return "u@b.co", "token"

    async def deliver(self, recipient: str, content: str) -> None:
        """Note whether the preparation was committed, then fail if asked."""
        del recipient, content
        self.committed_before_delivery = self.uow.committed
        if self.failure is not None:
            raise self.failure


@final
class _Fakes(Provider):
    def __init__(self, handler: _Handler) -> None:
        super().__init__()
        self.handler = handler

    @provide(scope=Scope.REQUEST)
    def verification(self) -> SendVerificationEmail:
        """Give the fake in place of the handler."""
        return cast("SendVerificationEmail", cast("object", self.handler))

    @provide(scope=Scope.REQUEST)
    def uow(self) -> UnitOfWork:
        """Give the boundary the handler reports on."""
        return self.handler.uow


async def _send(failure: Exception | None) -> _Handler:
    handler = _Handler(FakeUnitOfWork(), failure)
    container = make_async_container(_Fakes(handler))
    try:
        await send_email(container, USER_REGISTERED_EVENT, 1, {"user_id": "x"})
    finally:
        await container.close()
    return handler


async def test_the_token_is_committed_before_the_letter_leaves() -> None:
    """A letter never carries a token the database does not hold."""
    handler = await _send(None)

    assert handler.committed_before_delivery is True


async def test_a_permanent_failure_is_dropped() -> None:
    """A hard bounce is not retried by the broker."""
    _ = await _send(EmailPermanentlyUndeliverableError("550"))


async def test_a_transient_failure_is_raised_for_a_retry() -> None:
    """Anything else goes back to the broker for a retry."""
    with pytest.raises(OSError, match="timeout"):
        _ = await _send(OSError("timeout"))


def _letters(outcome: str) -> float:
    labels = {"event": USER_REGISTERED_EVENT, "outcome": outcome}
    return REGISTRY.get_sample_value("vld_worker_letters_total", labels) or 0.0


def _timed() -> float:
    labels = {"event": USER_REGISTERED_EVENT}
    return REGISTRY.get_sample_value("vld_worker_letter_seconds_count", labels) or 0.0


async def test_a_sent_letter_is_counted_and_timed() -> None:
    """One letter, one count, one observation of its time."""
    sent, timed = _letters("sent"), _timed()

    _ = await _send(None)

    assert (_letters("sent") - sent, _timed() - timed) == (1, 1)


async def test_a_dropped_and_a_failed_letter_are_told_apart() -> None:
    """A hard bounce is dropped; anything else is a failure the broker retries."""
    sent, dropped, failed = _letters("sent"), _letters("dropped"), _letters("failed")

    _ = await _send(EmailPermanentlyUndeliverableError("550"))
    with pytest.raises(OSError, match="timeout"):
        _ = await _send(OSError("timeout"))

    assert _letters("dropped") - dropped == 1
    assert _letters("failed") - failed == 1
    assert _letters("sent") == sent
