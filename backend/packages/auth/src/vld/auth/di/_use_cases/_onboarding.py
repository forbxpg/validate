"""Use cases of onboarding: registration, confirmation and their letters."""

from __future__ import annotations

from dishka import Provider, Scope, provide

from vld.auth.application import (
    Clock,
    EmailSender,
    Outbox,
    PasswordHasher,
    RateLimiter,
    RegisterUser,
    ResendVerification,
    SendPasswordResetEmail,
    SendVerificationEmail,
    TokenRepository,
    UserRepository,
    VerifyEmail,
)
from vld.auth.config import JwtSettings, PasswordSettings
from vld.core.database import UnitOfWork


class AuthOnboardingUseCaseProvider(Provider):
    """Use cases of onboarding."""

    @provide(scope=Scope.REQUEST)
    def register_user(
        self,
        users: UserRepository,
        hasher: PasswordHasher,
        outbox: Outbox,
        uow: UnitOfWork,
        settings: PasswordSettings,
    ) -> RegisterUser:
        """Build registration.

        Args:
            users: UserRepository - Account store.
            hasher: PasswordHasher - Password hasher.
            outbox: Outbox - Outbox writer.
            uow: UnitOfWork - Transaction boundary.
            settings: PasswordSettings - Password rules.

        Returns:
            RegisterUser - The use case.

        """
        return RegisterUser(users, hasher, outbox, uow, settings)

    @provide(scope=Scope.REQUEST)
    def verify_email(
        self,
        users: UserRepository,
        tokens: TokenRepository,
        clock: Clock,
        uow: UnitOfWork,
    ) -> VerifyEmail:
        """Build address confirmation.

        Args:
            users: UserRepository - Account store.
            tokens: TokenRepository - One-time token store.
            clock: Clock - Clock.
            uow: UnitOfWork - Transaction boundary.

        Returns:
            VerifyEmail - The use case.

        """
        return VerifyEmail(users, tokens, clock, uow)

    @provide(scope=Scope.REQUEST)
    def resend_verification(
        self,
        users: UserRepository,
        outbox: Outbox,
        limiter: RateLimiter,
        uow: UnitOfWork,
    ) -> ResendVerification:
        """Build another confirmation letter.

        Args:
            users: UserRepository - Account store.
            outbox: Outbox - Outbox writer.
            limiter: RateLimiter - Attempt limiter.
            uow: UnitOfWork - Transaction boundary.

        Returns:
            ResendVerification - The use case.

        """
        return ResendVerification(users, outbox, limiter, uow)

    @provide(scope=Scope.REQUEST)
    def send_verification_email(
        self,
        users: UserRepository,
        tokens: TokenRepository,
        email: EmailSender,
        clock: Clock,
        settings: JwtSettings,
    ) -> SendVerificationEmail:
        """Build the worker handler of `auth.user_registered`.

        Args:
            users: UserRepository - Account store.
            tokens: TokenRepository - One-time token store.
            email: EmailSender - Sender.
            clock: Clock - Clock.
            settings: JwtSettings - Key the link is derived from.

        Returns:
            SendVerificationEmail - The handler.

        """
        return SendVerificationEmail(users, tokens, email, clock, settings)

    @provide(scope=Scope.REQUEST)
    def send_password_reset_email(
        self,
        users: UserRepository,
        tokens: TokenRepository,
        email: EmailSender,
        clock: Clock,
        settings: JwtSettings,
    ) -> SendPasswordResetEmail:
        """Build the worker handler of `auth.password_reset_requested`.

        Args:
            users: UserRepository - Account store.
            tokens: TokenRepository - One-time token store.
            email: EmailSender - Sender.
            clock: Clock - Clock.
            settings: JwtSettings - Key the link is derived from.

        Returns:
            SendPasswordResetEmail - The handler.

        """
        return SendPasswordResetEmail(users, tokens, email, clock, settings)
