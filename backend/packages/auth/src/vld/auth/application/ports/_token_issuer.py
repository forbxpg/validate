"""Port of issuing and parsing session tokens."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

from vld.auth.domain import AuthDomainError

if TYPE_CHECKING:
    import uuid
    from datetime import datetime

    from ._access_claims import AccessClaims
    from ._device_claims import DeviceClaims
    from ._refresh_claims import RefreshClaims


class InvalidAccessTokenError(AuthDomainError, ValueError):
    """The access token is invalid, expired or of another type."""


class TokenIssuer(Protocol):
    """Issuing and parsing JWT."""

    def issue_pair(
        self,
        user_id: uuid.UUID,
        session_exp: datetime | None = None,
        *,
        not_before: datetime | None = None,
    ) -> tuple[str, str]:
        """Issue a pair of tokens.

        Args:
            user_id: uuid.UUID - Owner.
            session_exp: datetime | None - Ceiling of the session; None starts one.
            not_before: datetime | None - Earliest issue time: the invalidation mark
                of the account, so the pair is not void in the second it is issued.

        Returns:
            tuple[str, str] - Access and refresh tokens.

        """
        ...

    def parse_refresh(self, token: str) -> RefreshClaims:
        """Parse a refresh token.

        Args:
            token: str - The token.

        Returns:
            RefreshClaims - Owner, jti, moment of issue and session ceiling.

        Raises:
            ValueError: If the token is invalid, of another type or lacks the
                session ceiling.

        """
        ...

    def parse_access(self, token: str) -> AccessClaims:
        """Parse an access token.

        Args:
            token: str - The token.

        Returns:
            AccessClaims - Owner, jti and moment of issue.

        Raises:
            ValueError: If the token is invalid or of another type.

        """
        ...

    def remaining_ttl_seconds(self, token: str) -> int:
        """Tell how many seconds a token has left by its own `exp`.

        Args:
            token: str - The token.

        Returns:
            int - Remaining seconds.

        """
        ...

    def issue_device(self, user_id: uuid.UUID) -> str:
        """Issue a device marker for an account.

        Args:
            user_id: uuid.UUID - Account that logged in.

        Returns:
            str - The marker.

        """
        ...

    def parse_device(self, token: str) -> DeviceClaims:
        """Parse a device marker.

        Args:
            token: str - The marker.

        Returns:
            DeviceClaims - Account of the marker and moment of issue.

        Raises:
            ValueError: If the marker is invalid, expired or of another type.

        """
        ...
