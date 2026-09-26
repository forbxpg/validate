"""Refreshing a session."""

from __future__ import annotations

from typing import TYPE_CHECKING

import anyio
import structlog

from vld.auth.application.use_cases.shared import TokenPair
from vld.auth.domain import AccountGoneError, AuthDomainError

if TYPE_CHECKING:
    from vld.auth.application.ports import (
        RefreshClaims,
        RefreshedPairCache,
        RevocationStore,
        TokenIssuer,
        UserRepository,
    )
    from vld.auth.config import VerificationSettings
    from vld.core.database import UnitOfWork

# Covers a double click, a client retry and tabs refreshing at once.
_GRACE_TTL_SECONDS = 30

# The loser of the race may arrive between the revocation and the cache write.
_GRACE_WRITE_WINDOW_SECONDS = 0.1

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


class TokenRevokedError(AuthDomainError):
    """The presented token is revoked."""


class InvalidRefreshTokenError(AuthDomainError, ValueError):
    """The refresh token is invalid, expired or of another type."""


class RefreshTokens:
    """Issue a new pair and revoke the presented refresh token."""

    def __init__(  # ruff: ignore[too-many-arguments]
        self,
        *,
        issuer: TokenIssuer,
        revocation: RevocationStore,
        refreshed: RefreshedPairCache,
        users: UserRepository,
        uow: UnitOfWork,
        verification: VerificationSettings,
    ) -> None:
        self._issuer: TokenIssuer = issuer
        self._revocation: RevocationStore = revocation
        self._refreshed: RefreshedPairCache = refreshed
        self._users: UserRepository = users
        self._uow: UnitOfWork = uow
        self._verification: VerificationSettings = verification

    async def __call__(self, refresh_token: str) -> TokenPair:
        """Refresh the session.

        Args:
            refresh_token: str - Presented refresh token.

        Returns:
            TokenPair - New pair.

        Raises:
            InvalidRefreshTokenError: If the token is invalid or not a refresh token.
            TokenRevokedError: If the token was revoked or issued before the
                account voided its tokens.
            AccountGoneError: If the account no longer exists.

        """
        try:
            claims = self._issuer.parse_refresh(refresh_token)
            ttl = self._issuer.remaining_ttl_seconds(refresh_token)
        except ValueError as exc:
            msg = "invalid token"
            raise InvalidRefreshTokenError(msg) from exc

        # Revoke atomically before the database: "check, then revoke" is a race.
        if not await self._revocation.revoke_if_new(claims.jti, ttl):
            return await self._replay(claims)

        async with self._uow:
            user = await self._users.get_by_id(claims.user_id)
        if user is None:
            msg = f"account {claims.user_id} no longer exists"
            raise AccountGoneError(msg)
        user.ensure_can_authenticate(
            require_verified_email=self._verification.require_email_verification,
        )
        invalidated_after = user.tokens_invalidated_after
        if invalidated_after is not None and claims.issued_at < invalidated_after:
            msg = "token issued before invalidation"
            raise TokenRevokedError(msg)

        # A refresh never extends the session ceiling.
        access, refresh = self._issuer.issue_pair(
            user.id,
            session_exp=claims.session_exp,
            not_before=invalidated_after,
        )
        # Grace pair first, rotation mark second: otherwise a retry looks like theft.
        if await self._refreshed.save(claims.jti, access, refresh, _GRACE_TTL_SECONDS):
            await self._revocation.mark_rotated(claims.jti)
        return TokenPair(access=access, refresh=refresh)

    async def _replay(self, claims: RefreshClaims) -> TokenPair:
        """Answer a jti that is already revoked.

        Args:
            claims: RefreshClaims - Claims of the presented token.

        Returns:
            TokenPair - The same new pair while the grace window is open.

        Raises:
            TokenRevokedError: If there is no window.

        """
        cached = await self._refreshed.load(claims.jti)
        if cached is None:
            await anyio.sleep(_GRACE_WRITE_WINDOW_SECONDS)
            cached = await self._refreshed.load(claims.jti)
        if cached is not None:
            access, refresh = cached
            return TokenPair(access=access, refresh=refresh)
        # Reuse is a jti used up by a rotation, not merely revoked. Only logged:
        # revoking the account on it waits until false positives are measured.
        if await self._revocation.was_rotated(claims.jti):
            _log.warning("refresh_token_reuse_detected", user_id=str(claims.user_id))
        msg = "token revoked"
        raise TokenRevokedError(msg)
