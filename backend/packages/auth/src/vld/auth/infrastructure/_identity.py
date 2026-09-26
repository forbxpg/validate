"""Identifying the owner of an access token."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vld.auth.application import (
    InvalidAccessTokenError,
    TokenRevokedError,
)
from vld.auth.domain import AccountGoneError
from vld.web.access import Identity

if TYPE_CHECKING:
    from vld.auth.application import RevocationStore, TokenIssuer, UserRepository
    from vld.auth.config import VerificationSettings


class AuthIdentityProvider:
    """Checks the access token of every protected request."""

    def __init__(
        self,
        issuer: TokenIssuer,
        revocation: RevocationStore,
        users: UserRepository,
        verification: VerificationSettings,
    ) -> None:
        self._issuer: TokenIssuer = issuer
        self._revocation: RevocationStore = revocation
        self._users: UserRepository = users
        self._verification: VerificationSettings = verification

    async def identify(self, token: str) -> Identity:
        """Check a token and tell whom it belongs to.

        The role and the admin flag come from the database, not from the token:
        a changed role or a turned-off account takes effect on the next request.

        Args:
            token: str - Presented access token.

        Returns:
            Identity - Owner, role and admin flag.

        Raises:
            InvalidAccessTokenError: If the token is invalid, expired or of
                another type.
            TokenRevokedError: If the token was revoked or issued before the
                account voided its tokens.
            AccountGoneError: If the account no longer exists.

        """
        try:
            claims = self._issuer.parse_access(token)
        except ValueError as exc:
            msg = "invalid access token"
            raise InvalidAccessTokenError(msg) from exc

        if await self._revocation.is_revoked(claims.jti):
            msg = "access token revoked"
            raise TokenRevokedError(msg)

        user = await self._users.get_by_id(claims.user_id)
        if user is None:
            msg = f"account {claims.user_id} no longer exists"
            raise AccountGoneError(msg)
        user.ensure_can_authenticate(
            require_verified_email=self._verification.require_email_verification,
        )
        invalidated_after = user.tokens_invalidated_after
        if invalidated_after is not None and claims.issued_at < invalidated_after:
            msg = "access token issued before invalidation"
            raise TokenRevokedError(msg)
        return Identity(user_id=user.id, role=str(user.role), is_admin=user.is_admin)
