"""The map from outbox events to their handlers."""

from __future__ import annotations

from vld.auth.application import SendPasswordResetEmail, SendVerificationEmail
from vld.auth.domain import PASSWORD_RESET_REQUESTED_EVENT, USER_REGISTERED_EVENT
from vld.worker.tasks import handler_type


def test_each_event_maps_to_its_own_handler() -> None:
    """Each event resolves its own handler, not a neighbour's."""
    assert handler_type(USER_REGISTERED_EVENT) is SendVerificationEmail
    assert handler_type(PASSWORD_RESET_REQUESTED_EVENT) is SendPasswordResetEmail


def test_an_unknown_event_has_no_handler() -> None:
    """An unknown event is poison for the relay."""
    assert handler_type("auth.never_registered") is None
