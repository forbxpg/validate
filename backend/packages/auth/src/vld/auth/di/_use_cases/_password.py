"""Use cases of a password: reset through a letter and change."""

from __future__ import annotations

from dishka import Provider, Scope, provide

from vld.auth.application import (
    ChangePassword,
    Clock,
    Outbox,
    PasswordHasher,
    RateLimiter,
    RequestPasswordReset,
    ResetPassword,
    TokenIssuer,
    TokenRepository,
    UserRepository,
)
from vld.auth.config import PasswordSettings
from vld.core.audit import AuditLog
from vld.core.database import UnitOfWork


class AuthPasswordUseCaseProvider(Provider):
    """Use cases of a password."""

    @provide(scope=Scope.REQUEST)
    def request_password_reset(
        self,
        users: UserRepository,
        outbox: Outbox,
        limiter: RateLimiter,
        uow: UnitOfWork,
    ) -> RequestPasswordReset:
        """Build the request for a reset letter.

        Args:
            users: UserRepository - Account store.
            outbox: Outbox - Outbox writer.
            limiter: RateLimiter - Attempt limiter.
            uow: UnitOfWork - Transaction boundary.

        Returns:
            RequestPasswordReset - The use case.

        """
        return RequestPasswordReset(users, outbox, limiter, uow)

    @provide(scope=Scope.REQUEST)
    def reset_password(  # ruff: ignore[too-many-arguments] -- the use case needs all its ports
        self,
        *,
        users: UserRepository,
        tokens: TokenRepository,
        hasher: PasswordHasher,
        clock: Clock,
        uow: UnitOfWork,
        audit: AuditLog,
        settings: PasswordSettings,
    ) -> ResetPassword:
        """Build the reset through a letter.

        Args:
            users: UserRepository - Account store.
            tokens: TokenRepository - One-time token store.
            hasher: PasswordHasher - Password hasher.
            clock: Clock - Clock.
            uow: UnitOfWork - Transaction boundary.
            audit: AuditLog - Audit log.
            settings: PasswordSettings - Password rules.

        Returns:
            ResetPassword - The use case.

        """
        return ResetPassword(
            users=users,
            tokens=tokens,
            hasher=hasher,
            clock=clock,
            uow=uow,
            audit=audit,
            settings=settings,
        )

    @provide(scope=Scope.REQUEST)
    def change_password(  # ruff: ignore[too-many-arguments] -- the use case needs all its ports
        self,
        *,
        users: UserRepository,
        hasher: PasswordHasher,
        issuer: TokenIssuer,
        clock: Clock,
        uow: UnitOfWork,
        audit: AuditLog,
        settings: PasswordSettings,
    ) -> ChangePassword:
        """Build the change while logged in.

        Args:
            users: UserRepository - Account store.
            hasher: PasswordHasher - Password hasher.
            issuer: TokenIssuer - Token issuer.
            clock: Clock - Clock.
            uow: UnitOfWork - Transaction boundary.
            audit: AuditLog - Audit log.
            settings: PasswordSettings - Password rules.

        Returns:
            ChangePassword - The use case.

        """
        return ChangePassword(
            users=users,
            hasher=hasher,
            issuer=issuer,
            clock=clock,
            uow=uow,
            audit=audit,
            settings=settings,
        )
