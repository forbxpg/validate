"""Use cases of a session: login, refresh, logout."""

from __future__ import annotations

from dishka import Provider, Scope, provide

from vld.auth.application import (
    Clock,
    InvalidateSessions,
    LoginWithPassword,
    Logout,
    PasswordHasher,
    RateLimiter,
    RefreshedPairCache,
    RefreshTokens,
    RevocationStore,
    TokenIssuer,
    UserRepository,
)
from vld.auth.config import VerificationSettings
from vld.core.audit import AuditLog
from vld.core.database import UnitOfWork


class AuthSessionUseCaseProvider(Provider):
    """Use cases of a session."""

    @provide(scope=Scope.REQUEST)
    def login(  # ruff: ignore[too-many-arguments] -- the use case needs all its ports
        self,
        *,
        users: UserRepository,
        hasher: PasswordHasher,
        issuer: TokenIssuer,
        limiter: RateLimiter,
        uow: UnitOfWork,
        audit: AuditLog,
        verification: VerificationSettings,
    ) -> LoginWithPassword:
        """Build the login.

        Args:
            users: UserRepository - Account store.
            hasher: PasswordHasher - Password hasher.
            issuer: TokenIssuer - Token issuer.
            limiter: RateLimiter - Attempt limiter.
            uow: UnitOfWork - Transaction boundary.
            audit: AuditLog - Audit log.
            verification: VerificationSettings - Whether confirmation is required.

        Returns:
            LoginWithPassword - The use case.

        """
        return LoginWithPassword(
            users=users,
            hasher=hasher,
            issuer=issuer,
            limiter=limiter,
            uow=uow,
            audit=audit,
            verification=verification,
        )

    @provide(scope=Scope.REQUEST)
    def refresh(  # ruff: ignore[too-many-arguments] -- the use case needs all its ports
        self,
        *,
        issuer: TokenIssuer,
        revocation: RevocationStore,
        refreshed: RefreshedPairCache,
        users: UserRepository,
        uow: UnitOfWork,
        verification: VerificationSettings,
    ) -> RefreshTokens:
        """Build the refresh.

        Args:
            issuer: TokenIssuer - Token issuer and parser.
            revocation: RevocationStore - Revocation list.
            refreshed: RefreshedPairCache - Grace-window cache.
            users: UserRepository - Account store.
            uow: UnitOfWork - Transaction boundary.
            verification: VerificationSettings - Whether confirmation is required.

        Returns:
            RefreshTokens - The use case.

        """
        return RefreshTokens(
            issuer=issuer,
            revocation=revocation,
            refreshed=refreshed,
            users=users,
            uow=uow,
            verification=verification,
        )

    @provide(scope=Scope.REQUEST)
    def logout(
        self,
        issuer: TokenIssuer,
        revocation: RevocationStore,
        uow: UnitOfWork,
        audit: AuditLog,
    ) -> Logout:
        """Build the logout.

        Args:
            issuer: TokenIssuer - Token parser.
            revocation: RevocationStore - Revocation list.
            uow: UnitOfWork - Transaction boundary.
            audit: AuditLog - Audit log.

        Returns:
            Logout - The use case.

        """
        return Logout(issuer, revocation, uow, audit)

    @provide(scope=Scope.REQUEST)
    def invalidate_sessions(
        self,
        users: UserRepository,
        clock: Clock,
        audit: AuditLog,
        uow: UnitOfWork,
    ) -> InvalidateSessions:
        """Build the logout everywhere.

        Args:
            users: UserRepository - Account store.
            clock: Clock - Clock.
            audit: AuditLog - Audit log.
            uow: UnitOfWork - Transaction boundary.

        Returns:
            InvalidateSessions - The use case.

        """
        return InvalidateSessions(users, clock, audit, uow)
