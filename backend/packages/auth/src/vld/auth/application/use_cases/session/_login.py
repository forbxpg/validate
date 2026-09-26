"""Logging in with a password."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

import structlog

from vld.auth.application.use_cases.shared import (
    LoginResult,
    TokenPair,
    email_bucket_key,
    email_sha256,
)
from vld.auth.domain import (
    AuthAuditAction,
    AuthDomainError,
    InvalidCredentialsError,
    normalize_email,
)
from vld.core.audit import AuditEntry

from ._dummy_hash import DummyHash

if TYPE_CHECKING:
    from vld.auth.application.ports import (
        DeviceClaims,
        PasswordHasher,
        RateLimiter,
        TokenIssuer,
        UserRepository,
    )
    from vld.auth.config import VerificationSettings
    from vld.auth.domain import User
    from vld.core.audit import AuditLog
    from vld.core.database import UnitOfWork

# By address, not by client IP: credential stuffing comes from a botnet.
_EMAIL_LIMIT = 5
_EMAIL_WINDOW_MS = 15 * 60_000

_log: structlog.stdlib.BoundLogger = structlog.stdlib.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class LoginCommand:
    """A login request.

    Attributes:
        email: str - Address.
        password: str - Plain password.
        device_token: str | None - Device marker from the cookie.

    """

    email: str
    password: str
    device_token: str | None = None


def _device_bypasses(claims: DeviceClaims, user: User | None) -> bool:
    """Say whether a device marker lets the login skip the address bucket.

    A known device keeps its owner able to log in while someone else burns the
    bucket of the address with wrong passwords.

    Args:
        claims: DeviceClaims - Parsed marker.
        user: User | None - Account found by the address of the request.

    Returns:
        bool - True if the marker belongs to this account and is not voided.

    """
    if user is None or user.id != claims.user_id:
        return False
    mark = user.tokens_invalidated_after
    return mark is None or claims.issued_at >= mark


class LoginWithPassword:
    """Check an address and a password and issue tokens."""

    def __init__(  # ruff: ignore[too-many-arguments]
        self,
        *,
        users: UserRepository,
        hasher: PasswordHasher,
        issuer: TokenIssuer,
        limiter: RateLimiter,
        uow: UnitOfWork,
        audit: AuditLog,
        verification: VerificationSettings,
    ) -> None:
        self._users: UserRepository = users
        self._hasher: PasswordHasher = hasher
        self._issuer: TokenIssuer = issuer
        self._limiter: RateLimiter = limiter
        self._uow: UnitOfWork = uow
        self._audit: AuditLog = audit
        self._verification: VerificationSettings = verification

    async def __call__(self, command: LoginCommand) -> LoginResult:
        """Log in.

        Args:
            command: LoginCommand - Login data.

        Returns:
            LoginResult - Tokens and a fresh device marker.

        Raises:
            InvalidCredentialsError: If the address is unknown or the password
                does not match.
            AuthDomainError: If the account may not log in now.

        """
        normalized = normalize_email(command.email)
        limit_key = email_bucket_key("login", normalized)

        # The marker is checked before the bucket, or the bypass could not work.
        device = self._device_claims(command.device_token)
        if device is None:
            # The bucket does not depend on the account existing.
            await self._limiter.hit(limit_key, _EMAIL_LIMIT, _EMAIL_WINDOW_MS)
            async with self._uow:
                user = await self._users.get_by_email(normalized)
        else:
            async with self._uow:
                user = await self._users.get_by_email(normalized)
            if not _device_bypasses(device, user):
                await self._limiter.hit(limit_key, _EMAIL_LIMIT, _EMAIL_WINDOW_MS)

        # An unknown address checks a dummy hash, so the timing reveals nothing.
        stored_hash = (
            user.password_hash
            if user is not None
            else await DummyHash.get(self._hasher)
        )
        matched = await self._hasher.verify(command.password, stored_hash)
        if user is None or not matched:
            await self._record_failure(normalized, user)
            msg = "invalid email or password"
            raise InvalidCredentialsError(msg)

        try:
            user.ensure_can_authenticate(
                require_verified_email=self._verification.require_email_verification,
            )
        except AuthDomainError:
            await self._record_failure(normalized, user)
            raise

        # Audit before the tokens: a failed write leaves the login undone.
        async with self._uow:
            await self._audit.record(
                AuditEntry(action=AuthAuditAction.LOGIN_SUCCEEDED, actor_id=user.id),
            )
            await self._uow.commit()

        access, refresh = self._issuer.issue_pair(
            user.id,
            not_before=user.tokens_invalidated_after,
        )
        marker = self._issuer.issue_device(user.id)
        # A successful login clears the bucket, or typos would eat the limit.
        await self._limiter.reset(limit_key)
        await self._rehash_if_needed(user, command.password, stored_hash)
        return LoginResult(
            user_id=user.id,
            pair=TokenPair(access=access, refresh=refresh),
            device=marker,
        )

    async def _record_failure(self, email: str, user: User | None) -> None:
        """Record a refused login in the audit log.

        The log is append-only, so it keeps a hash of the address instead of the
        address: attempts on one address still line up, and nothing personal
        stays after the account is deleted.

        Args:
            email: str - Normalized address of the attempt.
            user: User | None - The account, if the address is known.

        """
        async with self._uow:
            await self._audit.record(
                AuditEntry(
                    action=AuthAuditAction.LOGIN_FAILED,
                    actor_id=None if user is None else user.id,
                    payload={"email_sha256": email_sha256(email)},
                ),
            )
            await self._uow.commit()

    def _device_claims(self, token: str | None) -> DeviceClaims | None:
        """Parse the device marker if it is presented and valid.

        Args:
            token: str | None - Marker from the cookie.

        Returns:
            DeviceClaims | None - Parsed claims, or None.

        """
        if token is None:
            return None
        try:
            return self._issuer.parse_device(token)
        except ValueError:
            return None

    async def _rehash_if_needed(
        self,
        user: User,
        password: str,
        stored_hash: str,
    ) -> None:
        """Hash the password again if the stored hash used outdated parameters.

        Args:
            user: User - Account whose password matched.
            password: str - Plain password.
            stored_hash: str - Hash the password matched.

        """
        if not self._hasher.needs_rehash(stored_hash):
            return
        try:
            new_hash = await self._hasher.hash(password)
            async with self._uow:
                updated = await self._users.update_password_hash(
                    user.id,
                    stored_hash,
                    new_hash,
                )
                await self._uow.commit()
        except Exception:  # ruff: ignore[blind-except] -- the login happened; a failed rehash does not undo it
            _log.exception("password_rehash_failed", user_id=str(user.id))
            return
        if not updated:
            # The password changed between the check and the write.
            _log.info("password_rehash_skipped_stale", user_id=str(user.id))
