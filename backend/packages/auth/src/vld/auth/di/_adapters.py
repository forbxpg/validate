"""Binding the ports of auth to their adapters."""

from __future__ import annotations

from dishka import Provider, Scope, provide
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from vld.auth.application import (
    AuthApi,
    Clock,
    EmailSender,
    Outbox,
    PasswordHasher,
    RateLimiter,
    RefreshedPairCache,
    RevocationStore,
    TokenIssuer,
    TokenRepository,
    UserRepository,
)
from vld.auth.config import EmailSettings, JwtSettings, VerificationSettings
from vld.auth.infrastructure import (
    AuthApiAdapter,
    AuthIdentityProvider,
    BcryptPasswordHasher,
    ConsoleEmailSender,
    JwtTokenIssuer,
    RedisRefreshedPairCache,
    RedisRevocationStore,
    SqlAlchemyOutbox,
    SqlAlchemyTokenRepository,
    SqlAlchemyUserRepository,
    SystemClock,
    build_smtp_sender,
)
from vld.core.config import AppSettings
from vld.core.ratelimit import RateLimiter as RedisRateLimiter
from vld.web.access import IdentityProvider


class AuthAdapterProvider(Provider):
    """Adapters of auth: PostgreSQL, Redis, bcrypt, JWT, SMTP."""

    @provide(scope=Scope.APP)
    def limiter(self, redis: Redis) -> RateLimiter:
        """Build the attempt limiter.

        Args:
            redis: Redis - Client from `CoreProvider`.

        Returns:
            RateLimiter - Fixed-window limiter on Redis.

        """
        return RedisRateLimiter(redis)

    @provide(scope=Scope.APP)
    def hasher(self) -> PasswordHasher:
        """Build the password hasher.

        Returns:
            PasswordHasher - bcrypt.

        """
        return BcryptPasswordHasher()

    @provide(scope=Scope.APP)
    def issuer(self, settings: JwtSettings) -> TokenIssuer:
        """Build the token issuer.

        Args:
            settings: JwtSettings - Signing key and lifetimes.

        Returns:
            TokenIssuer - HS256 over PyJWT.

        """
        return JwtTokenIssuer(settings)

    @provide(scope=Scope.APP)
    def clock(self) -> Clock:
        """Build the clock.

        Returns:
            Clock - System time in UTC.

        """
        return SystemClock()

    @provide(scope=Scope.APP)
    def email(self, settings: EmailSettings, app: AppSettings) -> EmailSender:
        """Build the sender: SMTP with a host set, the log otherwise.

        Args:
            settings: EmailSettings - SMTP settings.
            app: AppSettings - Environment; the log sender refuses production.

        Returns:
            EmailSender - The sender.

        """
        if not settings.is_configured:
            return ConsoleEmailSender(app)
        return build_smtp_sender(settings)

    @provide(scope=Scope.APP)
    def revocation(self, redis: Redis) -> RevocationStore:
        """Build the revocation list.

        Args:
            redis: Redis - Client from `CoreProvider`.

        Returns:
            RevocationStore - Revocation list in Redis.

        """
        return RedisRevocationStore(redis)

    @provide(scope=Scope.APP)
    def refreshed(self, redis: Redis) -> RefreshedPairCache:
        """Build the grace-window cache of refreshes.

        Args:
            redis: Redis - Client from `CoreProvider`.

        Returns:
            RefreshedPairCache - Cache in Redis.

        """
        return RedisRefreshedPairCache(redis)

    @provide(scope=Scope.REQUEST)
    def users(self, session: AsyncSession) -> UserRepository:
        """Build the account store.

        Args:
            session: AsyncSession - Request session.

        Returns:
            UserRepository - Store over SQLAlchemy.

        """
        return SqlAlchemyUserRepository(session)

    @provide(scope=Scope.REQUEST)
    def tokens(self, session: AsyncSession) -> TokenRepository:
        """Build the one-time token store.

        Args:
            session: AsyncSession - Request session.

        Returns:
            TokenRepository - Store over SQLAlchemy.

        """
        return SqlAlchemyTokenRepository(session)

    @provide(scope=Scope.REQUEST)
    def outbox(self, session: AsyncSession) -> Outbox:
        """Build the outbox writer.

        Args:
            session: AsyncSession - Request session.

        Returns:
            Outbox - Outbox over SQLAlchemy.

        """
        return SqlAlchemyOutbox(session)

    @provide(scope=Scope.REQUEST)
    def auth_api(self, users: UserRepository) -> AuthApi:
        """Build the contract for the other domains.

        Args:
            users: UserRepository - Account store.

        Returns:
            AuthApi - Answers about an account.

        """
        return AuthApiAdapter(users)

    @provide(scope=Scope.REQUEST)
    def identity(
        self,
        issuer: TokenIssuer,
        revocation: RevocationStore,
        users: UserRepository,
        verification: VerificationSettings,
    ) -> IdentityProvider:
        """Build the check of the access token of protected routes.

        Args:
            issuer: TokenIssuer - Token parser.
            revocation: RevocationStore - Revocation list.
            users: UserRepository - Account store.
            verification: VerificationSettings - Whether an unconfirmed address
                blocks the account.

        Returns:
            IdentityProvider - The check of auth.

        """
        return AuthIdentityProvider(issuer, revocation, users, verification)
