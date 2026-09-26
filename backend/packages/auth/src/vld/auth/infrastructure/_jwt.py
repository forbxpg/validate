"""Issuing and parsing JWT."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast

import jwt

from vld.auth.application.ports import AccessClaims, DeviceClaims, RefreshClaims
from vld.auth.config import MIN_JWT_SECRET_BYTES

from ._clock import SystemClock

if TYPE_CHECKING:
    from collections.abc import Mapping

    from vld.auth.application import Clock
    from vld.auth.config import JwtSettings

_ACCESS = "access"
_REFRESH = "refresh"
_DEVICE = "device"

# A marker outlives rare logins, not a session.
_DEVICE_TTL = timedelta(days=365)

# Never take the algorithm from the token header: `alg: none` turns the signature off.
_ALGORITHM = "HS256"
_ALGORITHMS = [_ALGORITHM]

# PyJWT checks exp only when present: a token without exp would live forever.
_REQUIRED_CLAIMS = ["exp", "iat", "jti", "sub", "typ"]

# Only a refresh token carries the session ceiling.
_SESSION_EXP_CLAIM = "session_exp"
_REFRESH_REQUIRED_CLAIMS = [*_REQUIRED_CLAIMS, _SESSION_EXP_CLAIM]

# Allowance for clocks of processes that drift apart.
_LEEWAY = timedelta(seconds=30)

# Checked here too: settings built in code skip the environment validation.
_MIN_SECRET_BYTES = MIN_JWT_SECRET_BYTES


class JwtTokenIssuer:
    """HS256 signing of JWT.

    Raises:
        ValueError: On construction, if the secret is shorter than 32 bytes.

    """

    def __init__(self, settings: JwtSettings, clock: Clock | None = None) -> None:
        secret = settings.secret_key.get_secret_value()
        if len(secret.encode()) < _MIN_SECRET_BYTES:
            msg = "jwt secret must be at least 256 bits (RFC 7518, section 3.2)"
            raise ValueError(msg)
        self._secret: str = secret
        self._clock: Clock = clock or SystemClock()
        self._access_ttl: timedelta = settings.access_ttl
        self._refresh_ttl: timedelta = settings.refresh_ttl
        self._session_ttl: timedelta = settings.session_ttl

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
        now = self._clock.now()
        if not_before is not None:
            now = max(now, not_before)
        if session_exp is None:
            session_exp = now + self._session_ttl
        access = self._encode(user_id, _ACCESS, now, now + self._access_ttl)
        refresh = self._encode(
            user_id,
            _REFRESH,
            now,
            min(now + self._refresh_ttl, session_exp),
            extra={_SESSION_EXP_CLAIM: int(session_exp.timestamp())},
        )
        return access, refresh

    def parse_refresh(self, token: str) -> RefreshClaims:
        """Parse a refresh token.

        Args:
            token: str - The token.

        Returns:
            RefreshClaims - Owner, jti, moment of issue and session ceiling.

        """
        payload = self._payload(token, _REFRESH, _REFRESH_REQUIRED_CLAIMS)
        return RefreshClaims(
            user_id=uuid.UUID(str(payload["sub"])),
            jti=str(payload["jti"]),
            issued_at=datetime.fromtimestamp(cast("float", payload["iat"]), UTC),
            session_exp=datetime.fromtimestamp(
                cast("float", payload[_SESSION_EXP_CLAIM]),
                UTC,
            ),
        )

    def parse_access(self, token: str) -> AccessClaims:
        """Parse an access token.

        Args:
            token: str - The token.

        Returns:
            AccessClaims - Owner, jti and moment of issue.

        """
        payload = self._payload(token, _ACCESS, _REQUIRED_CLAIMS)
        return AccessClaims(
            user_id=uuid.UUID(str(payload["sub"])),
            jti=str(payload["jti"]),
            issued_at=datetime.fromtimestamp(cast("float", payload["iat"]), UTC),
        )

    def issue_device(self, user_id: uuid.UUID) -> str:
        """Issue a device marker: a JWT with `typ="device"` and `sub=user_id`.

        Args:
            user_id: uuid.UUID - Account that logged in.

        Returns:
            str - Marker valid for a year.

        """
        now = self._clock.now()
        return self._encode(user_id, _DEVICE, now, now + _DEVICE_TTL)

    def parse_device(self, token: str) -> DeviceClaims:
        """Parse a device marker, checking its type.

        Args:
            token: str - The marker.

        Returns:
            DeviceClaims - Account of the marker and moment of issue, by which a
                voiding of the account's tokens voids the marker too.

        """
        payload = self._payload(token, _DEVICE, _REQUIRED_CLAIMS)
        return DeviceClaims(
            user_id=uuid.UUID(str(payload["sub"])),
            issued_at=datetime.fromtimestamp(cast("float", payload["iat"]), UTC),
        )

    def _payload(
        self,
        token: str,
        expected_type: str,
        required: list[str],
    ) -> Mapping[str, object]:
        """Check the signature, the required claims and the token type.

        Args:
            token: str - The token.
            expected_type: str - Expected value of the `typ` claim.
            required: list[str] - Claims this type of token must carry.

        Returns:
            Mapping[str, object] - The payload.

        Raises:
            ValueError: If the token is of another type.

        """
        payload = self._decode(token, required)
        if payload.get("typ") != expected_type:
            msg = "unexpected token type"
            raise ValueError(msg)
        return payload

    def remaining_ttl_seconds(self, token: str) -> int:
        """Tell how many seconds a token has left by its own `exp`.

        Args:
            token: str - The token.

        Returns:
            int - Remaining seconds, at least one.

        """
        payload = self._decode(token, _REQUIRED_CLAIMS)
        expires_at = datetime.fromtimestamp(cast("float", payload["exp"]), UTC)
        return max(1, int((expires_at - self._clock.now()).total_seconds()))

    def _decode(self, token: str, required: list[str]) -> Mapping[str, object]:
        """Check the signature and the required claims.

        Args:
            token: str - The token.
            required: list[str] - Claims this type of token must carry.

        Returns:
            Mapping[str, object] - The payload.

        Raises:
            ValueError: If the token is invalid.

        """
        try:
            # Key types of PyJWT come from `cryptography`, which HS256 does not need.
            return cast(
                "Mapping[str, object]",
                jwt.decode(  # pyright: ignore[reportUnknownMemberType]
                    token,
                    self._secret,
                    algorithms=_ALGORITHMS,
                    leeway=_LEEWAY,
                    options={"require": required},
                ),
            )
        except jwt.InvalidTokenError as exc:
            msg = "invalid token"
            raise ValueError(msg) from exc

    def _encode(
        self,
        user_id: uuid.UUID,
        token_type: str,
        now: datetime,
        expires_at: datetime,
        extra: Mapping[str, object] | None = None,
    ) -> str:
        """Build and sign a token.

        Args:
            user_id: uuid.UUID - Owner.
            token_type: str - Token type.
            now: datetime - Moment of issue.
            expires_at: datetime - Moment of expiry.
            extra: Mapping[str, object] | None - Additional claims.

        Returns:
            str - Signed JWT.

        """
        return jwt.encode(  # pyright: ignore[reportUnknownMemberType] -- see _decode
            {
                "sub": str(user_id),
                "typ": token_type,
                "jti": uuid.uuid4().hex,
                "iat": now,
                "exp": expires_at,
                **(extra or {}),
            },
            self._secret,
            algorithm=_ALGORITHM,
        )
