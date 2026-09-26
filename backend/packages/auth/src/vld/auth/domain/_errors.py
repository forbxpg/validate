"""Errors of the auth domain."""

from __future__ import annotations


class AuthDomainError(Exception):
    """Base error of the domain."""


class EmailAlreadyTakenError(AuthDomainError):
    """Another account already uses the address."""


class InvalidCredentialsError(AuthDomainError):
    """The email and password do not match an account that may log in."""


class AccountDeactivatedError(AuthDomainError):
    """An admin turned the account off."""


class AccountGoneError(AuthDomainError):
    """The account a token belongs to no longer exists."""


class EmailNotVerifiedError(AuthDomainError):
    """The password is right, but the address is not confirmed yet."""


class UserNotFoundError(AuthDomainError):
    """No account has the requested id."""


class EntityNotFoundError(AuthDomainError):
    """The entity being updated is not stored."""
