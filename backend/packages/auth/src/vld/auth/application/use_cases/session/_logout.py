"""Ending a session."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.auth.domain import AuthAuditAction
from vld.core.audit import AuditEntry

if TYPE_CHECKING:
    import uuid

    from vld.auth.application.ports import RevocationStore, TokenIssuer
    from vld.core.audit import AuditLog
    from vld.core.database import UnitOfWork


class Logout:
    """Revoke the presented tokens."""

    def __init__(
        self,
        issuer: TokenIssuer,
        revocation: RevocationStore,
        uow: UnitOfWork,
        audit: AuditLog,
    ) -> None:
        self._issuer: TokenIssuer = issuer
        self._revocation: RevocationStore = revocation
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit

    async def __call__(self, refresh_token: str, access_token: str | None) -> None:
        """End the session.

        Args:
            refresh_token: str - Refresh token.
            access_token: str | None - Access token, if presented.

        """
        actor = self._actor(refresh_token)
        if actor is not None:
            await self._record(actor)
        await self._revoke(refresh_token, refresh=True)
        if access_token is not None:
            await self._revoke(access_token, refresh=False)

    async def _record(self, actor: uuid.UUID) -> None:
        """Record the logout in the audit log.

        Args:
            actor: uuid.UUID - Owner of the refresh token.

        """
        async with self._uow:
            await self._audit.record(
                AuditEntry(action=AuthAuditAction.LOGGED_OUT, actor_id=actor),
            )
            await self._uow.commit()

    def _actor(self, refresh_token: str) -> uuid.UUID | None:
        """Tell the owner of a refresh token, if it parses at all.

        Args:
            refresh_token: str - Refresh token.

        Returns:
            uuid.UUID | None - The owner, or None.

        """
        try:
            return self._issuer.parse_refresh(refresh_token).user_id
        except ValueError:
            return None

    async def _revoke(self, token: str, *, refresh: bool) -> None:
        """Revoke one token, skipping one that does not parse.

        Args:
            token: str - The token.
            refresh: bool - True for a refresh token, False for an access token.

        """
        try:
            if refresh:
                jti = self._issuer.parse_refresh(token).jti
            else:
                jti = self._issuer.parse_access(token).jti
            ttl = self._issuer.remaining_ttl_seconds(token)
        except ValueError:
            # Broken, expired or of another type: nothing to revoke.
            return
        if ttl <= 0:
            # It expires on its own this very second; a zero TTL is refused by Redis.
            return
        await self._revocation.revoke(jti, ttl)
