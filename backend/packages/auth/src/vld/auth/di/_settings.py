"""Settings of auth, read once per process."""

from __future__ import annotations

from dishka import Provider, Scope, provide

from vld.auth.config import (
    EmailSettings,
    JwtSettings,
    PasswordSettings,
    VerificationSettings,
)


class AuthSettingsProvider(Provider):
    """Settings of the domain."""

    @provide(scope=Scope.APP)
    def jwt(self) -> JwtSettings:
        """Read `JWT_*`.

        Returns:
            JwtSettings - Signing key and lifetimes.

        """
        # `JWT_SECRET_KEY` is required and read from the environment.
        return JwtSettings()  # pyright: ignore[reportCallIssue]

    @provide(scope=Scope.APP)
    def password(self) -> PasswordSettings:
        """Read `PASSWORD_*`.

        Returns:
            PasswordSettings - Password rules.

        """
        return PasswordSettings()

    @provide(scope=Scope.APP)
    def verification(self) -> VerificationSettings:
        """Read `AUTH_*`.

        Returns:
            VerificationSettings - Whether a login waits for the confirmation.

        """
        return VerificationSettings()

    @provide(scope=Scope.APP)
    def email(self) -> EmailSettings:
        """Read `EMAIL_*`.

        Returns:
            EmailSettings - SMTP of the letters.

        """
        return EmailSettings()
