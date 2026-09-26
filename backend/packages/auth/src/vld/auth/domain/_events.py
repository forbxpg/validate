"""Domain events that the worker turns into letters."""

from __future__ import annotations

from dataclasses import dataclass

USER_REGISTERED_EVENT = "auth.user_registered"
PASSWORD_RESET_REQUESTED_EVENT = "auth.password_reset_requested"  # ruff: ignore[hardcoded-password-string]


@dataclass(frozen=True, slots=True)
class DomainEvent:
    """A fact the domain records for the worker.

    Attributes:
        name: str - Event name, e.g. `auth.user_registered`.
        payload: dict[str, str] - Event data; never a secret, the outbox is plain.

    """

    name: str
    payload: dict[str, str]
