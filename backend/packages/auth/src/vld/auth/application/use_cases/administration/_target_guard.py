"""Who an admin may act upon."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.auth.domain import AuthDomainError

if TYPE_CHECKING:
    import uuid

    from vld.auth.domain import User


class TargetForbiddenError(AuthDomainError):
    """The admin may not do this to this account."""


def guard_target(actor_id: uuid.UUID, target: User) -> None:
    """Refuse an action upon oneself or upon another admin.

    Admins are managed from the console only: one admin cannot lock another
    out through the site.

    Args:
        actor_id: uuid.UUID - The admin acting.
        target: User - The account acted upon.

    Raises:
        TargetForbiddenError: If the target is the actor or another admin.

    """
    if actor_id == target.id:
        msg = f"admin {actor_id} may not do this to their own account"
        raise TargetForbiddenError(msg)
    if target.is_admin:
        msg = f"admin {actor_id} may not do this to admin {target.id}"
        raise TargetForbiddenError(msg)
