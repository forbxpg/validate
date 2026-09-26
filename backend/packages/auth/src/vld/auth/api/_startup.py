"""Startup of auth: what must fail at startup rather than on the first request."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.auth.application import EmailSender, PasswordHasher, warm_password_verification

if TYPE_CHECKING:
    from dishka import AsyncContainer


async def startup(container: AsyncContainer) -> None:
    """Resolve the letter sender and warm up password hashing.

    A missing Redis is left to readiness: the process starts and waits for it.

    Args:
        container: AsyncContainer - Container of the application.

    """
    _ = await container.get(EmailSender)
    await warm_password_verification(await container.get(PasswordHasher))
